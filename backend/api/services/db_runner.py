import json
import time
from datetime import datetime, timezone as datetime_timezone
from http.cookies import SimpleCookie
from html import escape
from pathlib import Path

import requests
from requests.cookies import create_cookie
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from jsonpath import jsonpath
from pactverify.matchers import PactJsonVerify

from api.models import ApiCase, EnvironmentCookie, ScenarioCase, ScenarioStepResult, TestResult, TestTask
from api.serializers import resolve_plan_scenarios


class DbVariablePool:
    def __init__(self):
        self.pool = {}

    def save(self, case_code, response_data):
        if case_code and isinstance(response_data, (dict, list)):
            self.pool[case_code] = response_data

    def save_value(self, name, value):
        if name:
            self.pool[name] = value

    def replace(self, content):
        if not isinstance(content, str) or "${" not in content:
            return content
        result = content
        for token in set(part.split("}", 1)[0] for part in result.split("${")[1:]):
            if token in self.pool:
                result = result.replace(f"${{{token}}}", str(self.pool[token]))
                continue
            if "." in token:
                case_code, path = token.split(".", 1)
                values = jsonpath(self.pool.get(case_code, {}), f"$.{path}")
                if values:
                    result = result.replace(f"${{{token}}}", str(values[0]))
        return result

    def load_mapping(self, values):
        for key, value in values.items():
            self.save_value(key, value)


class DbTaskRunner:
    def __init__(self, task):
        self.task = task
        self.plan = task.plan
        self.env = self.plan.environment
        self.session = requests.Session()
        self.variables = DbVariablePool()
        self.variables.load_mapping(
            {
                item.key: item.value
                for item in self.plan.project.variables.filter(enabled=True)
            }
        )
        self.variables.load_mapping(
            {
                item.key: item.value
                for item in self.env.variables.filter(enabled=True)
            }
        )
        self.load_environment_cookies()

    def selected_cases(self):
        if self.plan.scenarios.exists():
            return []
        queryset = ApiCase.objects.filter(api__module__project=self.plan.project, enabled=True)
        selected = self.plan.cases.all()
        if selected.exists():
            queryset = queryset.filter(id__in=selected.values("id"))
        elif self.plan.api_definitions.exists():
            queryset = queryset.filter(api__in=self.plan.api_definitions.all())
        elif self.plan.modules.exists():
            queryset = queryset.filter(api__module__in=self.plan.modules.all())
        if self.plan.levels:
            queryset = queryset.filter(level__in=self.plan.levels)
        for tag in self.plan.tags or []:
            if tag:
                queryset = queryset.filter(tags__icontains=tag)
        if self.plan.suites:
            queryset = queryset.filter(suite__in=self.plan.suites)
        setup_cases = ApiCase.objects.filter(
            api__module__project=self.plan.project, is_setup=True, enabled=True
        )
        business_cases = queryset.filter(is_setup=False)
        setup = list(setup_cases.order_by("sort_order", "id"))
        business = list(business_cases.prefetch_related("dependencies").order_by("sort_order", "id"))
        return setup + self.order_by_dependencies(business)

    def selected_scenarios(self):
        return list(resolve_plan_scenarios(self.plan))

    def order_by_dependencies(self, cases):
        case_map = {case.id: case for case in cases}
        ordered = []
        visited = set()
        visiting = set()

        def visit(case):
            if case.id in visiting:
                raise ValueError(f"接口用例存在循环依赖: {case.case_code}")
            if case.id in visited:
                return
            visiting.add(case.id)
            visited.add(case.id)
            for dependency in case.dependencies.all():
                if dependency.id in case_map:
                    visit(case_map[dependency.id])
            visiting.remove(case.id)
            ordered.append(case)

        for case in cases:
            visit(case)
        return ordered

    def run(self):
        self.task.results.all().delete()
        self.task.step_results.all().delete()
        cases = self.selected_cases()
        scenarios = self.selected_scenarios()
        failed_case_ids = set()
        skipped_case_ids = set()
        scenario_steps_count = sum(scenario.steps.filter(enabled=True).count() for scenario in scenarios)
        self.task.total_count = len([case for case in cases if not case.is_setup]) + scenario_steps_count
        self.task.passed_count = 0
        self.task.failed_count = 0
        self.task.skipped_count = 0
        self.task.progress = 0
        self.task.save(
            update_fields=[
                "total_count",
                "passed_count",
                "failed_count",
                "skipped_count",
                "progress",
                "updated_at",
            ]
        )
        for case in cases:
            if TestTask.objects.filter(id=self.task.id, status=TestTask.Status.CANCELED).exists():
                return
            blocked_by = self.blocked_dependencies(case, failed_case_ids | skipped_case_ids)
            if blocked_by:
                self.skip_case(case, blocked_by)
                skipped_case_ids.add(case.id)
                continue
            result = self.run_case(case)
            if result.status in [TestResult.Status.FAILED, TestResult.Status.ERROR]:
                failed_case_ids.add(case.id)
        for scenario in scenarios:
            self.run_scenario(scenario)
        business_results = self.task.results.filter(case__is_setup=False)
        step_results = self.task.step_results.all()
        failed = business_results.filter(status__in=[TestResult.Status.FAILED, TestResult.Status.ERROR]).count()
        failed += step_results.filter(status__in=[TestResult.Status.FAILED, TestResult.Status.ERROR]).count()
        passed = business_results.filter(status=TestResult.Status.PASSED).count()
        passed += step_results.filter(status=TestResult.Status.PASSED).count()
        skipped = business_results.filter(status=TestResult.Status.SKIPPED).count()
        skipped += step_results.filter(status=TestResult.Status.SKIPPED).count()
        self.task.failed_count = failed
        self.task.passed_count = passed
        self.task.skipped_count = skipped
        self.task.progress = 100
        self.task.status = TestTask.Status.FAILED if failed else TestTask.Status.PASSED
        self.task.current_case = None
        self.task.current_case_code = ""
        self.task.current_case_title = ""
        self.task.current_step_message = "执行完成"
        self.task.finished_at = timezone.now()
        self.task.save()
        try:
            self.write_html_report()
        except Exception as exc:
            self.task.log = f"{self.task.log}\nHTML 报告生成失败: {exc}".strip()
            self.task.save(update_fields=["log", "updated_at"])

    def run_scenario(self, scenario):
        self.task.current_object_type = "SCENARIO"
        self.task.current_case_code = f"SCN-{scenario.id}"
        self.task.current_case_title = scenario.name
        self.task.current_step_message = "开始执行场景"
        self.task.save(
            update_fields=[
                "current_object_type",
                "current_case_code",
                "current_case_title",
                "current_step_message",
                "updated_at",
            ]
        )
        steps = self.order_by_step_dependencies(
            list(scenario.steps.filter(enabled=True).select_related("api").prefetch_related("dependencies"))
        )
        blocked = set()
        for step in steps:
            blocked_by = [item.name for item in step.dependencies.all() if item.id in blocked]
            if blocked_by:
                self.skip_step(scenario, step, blocked_by)
                blocked.add(step.id)
                continue
            result = self.run_step(scenario, step)
            if result.status in [TestResult.Status.FAILED, TestResult.Status.ERROR]:
                blocked.add(step.id)

    def order_by_step_dependencies(self, steps):
        step_map = {step.id: step for step in steps}
        ordered = []
        visited = set()
        visiting = set()

        def visit(step):
            if step.id in visiting:
                raise ValueError(f"场景步骤存在循环依赖: {step.name}")
            if step.id in visited:
                return
            visiting.add(step.id)
            for dependency in step.dependencies.all():
                if dependency.id in step_map:
                    visit(step_map[dependency.id])
            visiting.remove(step.id)
            visited.add(step.id)
            ordered.append(step)

        for step in steps:
            visit(step)
        return ordered

    def skip_step(self, scenario, step, blocked_by):
        message = f"依赖失败，跳过步骤: {', '.join(blocked_by)}"
        result = ScenarioStepResult.objects.create(
            task=self.task,
            scenario=scenario,
            step=step,
            scenario_name=scenario.name,
            step_name=step.name,
            status=TestResult.Status.SKIPPED,
            failure_category="DEPENDENCY_FAILED",
            assertion_error=message,
        )
        self.update_progress(message)
        return result

    def run_step(self, scenario, step):
        self.task.current_object_type = "SCENARIO_STEP"
        self.task.current_case_code = f"SCN-{scenario.id}"
        self.task.current_case_title = scenario.name
        self.task.current_step_name = step.name
        self.task.current_step_message = "正在执行场景步骤"
        self.task.save(
            update_fields=[
                "current_object_type",
                "current_case_code",
                "current_case_title",
                "current_step_name",
                "current_step_message",
                "updated_at",
            ]
        )
        start = time.monotonic()
        status = TestResult.Status.PASSED
        failure_category = ""
        assertion_error = ""
        response_status = None
        response_body = ""
        request_data = {}
        try:
            method = step.api.method.upper()
            url = self.build_url(step.api.path)
            headers = self.prepare_headers({**(self.env.headers or {}), **(step.api.default_headers or {}), **(step.header or {})})
            payload = self.replace_json(step.payload)
            request_data = {"method": method, "url": url, "headers": headers, "payload": payload}
            response = self.session.request(
                method,
                url,
                json=payload if isinstance(payload, (dict, list)) else None,
                data=payload if not isinstance(payload, (dict, list)) else None,
                headers=headers,
                verify=self.env.verify_ssl,
                timeout=self.env.timeout_seconds or settings.NEXUS_REQUEST_TIMEOUT,
            )
            request_data["headers"] = dict(response.request.headers)
            response_status = response.status_code
            response_body = response.text
            actual = response.json() if response.text else {}
            self.save_session_cookies(response)
            self.variables.save(f"step_{step.id}", actual)
            self.apply_extractors(step, actual)
            expect = self.replace_json(step.expect) if step.expect else {}
            expected_status = self.expected_status_code(expect)
            if response.status_code != expected_status:
                status = TestResult.Status.FAILED
                failure_category = "ENVIRONMENT_ERROR" if response.status_code >= 500 else "REQUEST_ERROR"
                assertion_error = f"HTTP 状态码不匹配: 期望 {expected_status}, 实际 {response.status_code}"
            elif expect:
                self.assert_expect(actual, expect, response.status_code)
        except AssertionError as exc:
            status = TestResult.Status.FAILED
            failure_category = "ASSERTION_FAILED"
            assertion_error = str(exc)
        except Exception as exc:
            status = TestResult.Status.ERROR
            failure_category = "SCRIPT_ERROR"
            assertion_error = str(exc)
        duration_ms = int((time.monotonic() - start) * 1000)
        result = ScenarioStepResult.objects.create(
            task=self.task,
            scenario=scenario,
            step=step,
            scenario_name=scenario.name,
            step_name=step.name,
            status=status,
            duration_ms=duration_ms,
            request_data=request_data,
            response_status=response_status,
            response_body=response_body,
            failure_category=failure_category,
            assertion_error=assertion_error,
        )
        self.update_progress("执行中")
        return result

    def blocked_dependencies(self, case, blocked_ids):
        return [
            dependency.case_code
            for dependency in case.dependencies.all()
            if dependency.id in blocked_ids
        ]

    def skip_case(self, case, blocked_by):
        message = f"依赖失败，跳过执行: {', '.join(blocked_by)}"
        result = TestResult.objects.create(
            task=self.task,
            case=case,
            case_code=case.case_code,
            title=case.subtitle or case.title,
            status=TestResult.Status.SKIPPED,
            failure_category="DEPENDENCY_FAILED",
            assertion_error=message,
        )
        if not case.is_setup:
            self.update_progress(message)
        return result

    def run_case(self, case):
        self.task.current_object_type = "API_CASE"
        self.task.current_case = case
        self.task.current_case_code = case.case_code
        self.task.current_case_title = case.subtitle or case.title
        self.task.current_step_message = "正在执行请求"
        self.task.save(
            update_fields=[
                "current_case",
                "current_object_type",
                "current_case_code",
                "current_case_title",
                "current_step_message",
                "updated_at",
            ]
        )
        start = time.monotonic()
        status = TestResult.Status.PASSED
        failure_category = ""
        assertion_error = ""
        response_status = None
        response_body = ""
        request_data = {}
        result = None
        try:
            method = case.api.method.upper()
            url = self.build_url(case.api.path)
            headers = self.prepare_headers({**(self.env.headers or {}), **(case.header or {})})
            payload = self.replace_json(case.payload)
            request_data = {"method": method, "url": url, "headers": headers, "payload": payload}
            response = self.session.request(
                method,
                url,
                json=payload if isinstance(payload, (dict, list)) else None,
                data=payload if not isinstance(payload, (dict, list)) else None,
                headers=headers,
                verify=self.env.verify_ssl,
                timeout=self.env.timeout_seconds or settings.NEXUS_REQUEST_TIMEOUT,
            )
            request_data["headers"] = dict(response.request.headers)
            response_status = response.status_code
            response_body = response.text
            actual = response.json() if response.text else {}
            self.save_session_cookies(response)
            self.variables.save(case.case_code, actual)
            self.apply_extractors(case, actual)
            expect = self.replace_json(case.expect) if case.expect else {}
            expected_status = self.expected_status_code(expect)
            if response.status_code != expected_status:
                status = TestResult.Status.FAILED
                failure_category = "ENVIRONMENT_ERROR" if response.status_code >= 500 else "REQUEST_ERROR"
                assertion_error = f"HTTP 状态码不匹配: 期望 {expected_status}, 实际 {response.status_code}"
            elif expect:
                self.assert_expect(actual, expect, response.status_code)
        except AssertionError as exc:
            status = TestResult.Status.FAILED
            failure_category = "ASSERTION_FAILED"
            assertion_error = str(exc)
        except Exception as exc:
            status = TestResult.Status.ERROR
            failure_category = "SCRIPT_ERROR"
            assertion_error = str(exc)
        finally:
            duration_ms = int((time.monotonic() - start) * 1000)
            result = TestResult.objects.create(
                task=self.task,
                case=case,
                case_code=case.case_code,
                title=case.subtitle or case.title,
                status=status,
                duration_ms=duration_ms,
                request_data=request_data,
                response_status=response_status,
                response_body=response_body,
                failure_category=failure_category,
                assertion_error=assertion_error,
            )
            if not case.is_setup:
                self.update_progress("执行中")
        return result

    def apply_extractors(self, case, actual):
        for extractor in case.extractors or []:
            name = extractor.get("name")
            path = extractor.get("path")
            if not name or not path:
                continue
            values = jsonpath(actual, self.normalize_json_path(path))
            if values:
                self.variables.save_value(name, values[0])
            elif extractor.get("required"):
                raise AssertionError(f"变量提取失败: {name} <- {path}")

    def save_session_cookies(self, response=None):
        cookie_parts = [
            f"{cookie.name}={cookie.value}"
            for cookie in self.session.cookies
        ]
        set_cookie = response.headers.get("Set-Cookie", "") if response is not None else ""
        if set_cookie:
            parsed = SimpleCookie()
            try:
                parsed.load(set_cookie)
                cookie_parts.extend(f"{key}={morsel.value}" for key, morsel in parsed.items())
            except Exception:
                self.variables.save_value("set_cookie", set_cookie)
        cookie_header = "; ".join(dict.fromkeys(cookie_parts))
        if cookie_header:
            self.variables.save_value("cookie", cookie_header)
            self.variables.save_value("cookies", cookie_header)
            self.variables.save_value("cookie_header", cookie_header)
        self.persist_environment_cookies()

    def prepare_headers(self, headers):
        prepared = self.replace_json(headers or {})
        return {
            key: value
            for key, value in prepared.items()
            if value not in ("", None) and key.lower() not in {"host", "cookie"}
        }

    def load_environment_cookies(self):
        now = timezone.now()
        cookies = self.env.cookies.filter(enabled=True).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        for item in cookies:
            cookie = create_cookie(
                name=item.name,
                value=item.value,
                domain=item.domain,
                path=item.path or "/",
                secure=item.secure,
                expires=int(item.expires_at.timestamp()) if item.expires_at else None,
                rest={"HttpOnly": item.http_only},
            )
            self.session.cookies.set_cookie(cookie)

    def persist_environment_cookies(self):
        for cookie in self.session.cookies:
            expires_at = None
            if cookie.expires:
                expires_at = datetime.fromtimestamp(cookie.expires, tz=datetime_timezone.utc)
            rest = getattr(cookie, "_rest", {}) or {}
            EnvironmentCookie.objects.update_or_create(
                environment=self.env,
                domain=cookie.domain or "",
                path=cookie.path or "/",
                name=cookie.name,
                defaults={
                    "value": cookie.value or "",
                    "expires_at": expires_at,
                    "secure": bool(cookie.secure),
                    "http_only": "HttpOnly" in rest,
                    "enabled": True,
                },
            )

    def update_progress(self, message):
        done = self.task.results.filter(case__is_setup=False).count() + self.task.step_results.count()
        total = self.task.total_count or 1
        self.task.progress = min(99, int(done / total * 100))
        self.task.passed_count = self.task.results.filter(
            case__is_setup=False, status=TestResult.Status.PASSED
        ).count() + self.task.step_results.filter(status=TestResult.Status.PASSED).count()
        self.task.failed_count = self.task.results.filter(
            case__is_setup=False, status__in=[TestResult.Status.FAILED, TestResult.Status.ERROR]
        ).count() + self.task.step_results.filter(status__in=[TestResult.Status.FAILED, TestResult.Status.ERROR]).count()
        self.task.skipped_count = self.task.results.filter(
            case__is_setup=False, status=TestResult.Status.SKIPPED
        ).count() + self.task.step_results.filter(status=TestResult.Status.SKIPPED).count()
        self.task.current_step_message = message
        self.task.save(
            update_fields=[
                "progress",
                "passed_count",
                "failed_count",
                "skipped_count",
                "current_step_message",
                "updated_at",
            ]
        )

    def build_url(self, path):
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return f"{self.env.base_url.rstrip('/')}/{path.lstrip('/')}"

    def replace_json(self, value):
        raw = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
        replaced = self.variables.replace(raw)
        try:
            return json.loads(replaced)
        except json.JSONDecodeError:
            return replaced

    def expected_status_code(self, expect):
        if isinstance(expect, dict):
            if "status_code" in expect:
                return int(expect.get("status_code") or 200)
            for rule in expect.get("__assertions", []):
                if rule.get("type") == "status_code":
                    return int(rule.get("value") or 200)
        return 200

    def assert_expect(self, actual, expect, response_status=None):
        expect = self.evaluate_visual_assertions(actual, expect, response_status)
        if not expect:
            return
        expected = self.wrap_expect(expect)
        if isinstance(actual, list):
            actual = {"_root_": actual}
            expected = {"$Like": {"_root_": expected}}
        verifier = PactJsonVerify(expected, hard_mode=False)
        verifier.verify(actual)
        assert verifier.verify_result, verifier.value_not_match_error

    def evaluate_visual_assertions(self, actual, expect, response_status):
        if not isinstance(expect, dict) or "__assertions" not in expect:
            return expect
        for rule in expect.get("__assertions", []):
            rule_type = rule.get("type")
            operator = rule.get("operator") or "equals"
            expected = rule.get("value")
            if rule_type == "status_code":
                assert int(response_status or 0) == int(expected or 200), (
                    f"状态码断言失败: 期望 {expected}, 实际 {response_status}"
                )
                continue
            path = self.normalize_json_path(rule.get("path") or "$")
            values = jsonpath(actual, path)
            exists = values is not False and len(values) > 0
            if operator == "exists":
                assert exists, f"字段不存在: {path}"
                continue
            assert exists, f"字段不存在，无法断言: {path}"
            actual_value = values[0]
            if operator == "not_empty":
                assert self.is_not_empty(actual_value), f"字段为空: {path}"
                continue
            if operator == "contains":
                assert str(expected) in str(actual_value), (
                    f"字段包含断言失败: {path}, 期望包含 {expected}, 实际 {actual_value}"
                )
            else:
                assert actual_value == expected, (
                    f"字段等于断言失败: {path}, 期望 {expected}, 实际 {actual_value}"
                )
        return {key: value for key, value in expect.items() if key != "__assertions"}

    def normalize_json_path(self, path):
        path = str(path or "$").strip()
        if path == "$" or path.startswith("$"):
            return path
        if path.startswith("["):
            return f"${path}"
        return f"$.{path}"

    def is_not_empty(self, value):
        if value is None:
            return False
        if isinstance(value, (str, list, dict, tuple, set)):
            return len(value) > 0
        return True

    def wrap_expect(self, expect):
        def expand(source):
            if not isinstance(source, dict):
                return source
            target = {}
            for key, value in source.items():
                if "." in str(key):
                    cursor = target
                    parts = str(key).split(".")
                    for part in parts[:-1]:
                        cursor = cursor.setdefault(part, {})
                    cursor[parts[-1]] = expand(value)
                else:
                    target[key] = expand(value)
            return target

        def wrap(node):
            if not isinstance(node, dict):
                return {"$Matcher": node}
            if any(str(key).startswith("$") for key in node):
                return node
            if node and all(str(key).isdigit() for key in node):
                size = max(int(key) for key in node) + 1
                result = [None] * size
                for key, value in node.items():
                    result[int(key)] = wrap(value)
                return result
            return {"$Like": {key: wrap(value) for key, value in node.items()}}

        return wrap(expand(expect))

    def write_html_report(self):
        if not self.task.report_html_path:
            return
        report_dir = Path(self.task.report_html_path)
        report_dir.mkdir(parents=True, exist_ok=True)

        def status_badge(status):
            return f"<span class=\"status {escape((status or '').lower())}\">{escape(status or '-')}</span>"

        def category_label(category):
            labels = {
                "ASSERTION_FAILED": "断言失败",
                "REQUEST_ERROR": "请求异常",
                "DEPENDENCY_FAILED": "依赖失败",
                "ENVIRONMENT_ERROR": "环境异常",
                "SCRIPT_ERROR": "脚本异常",
            }
            return labels.get(category, category or "-")

        def short_text(value, limit=900):
            if value is None:
                return ""
            if not isinstance(value, str):
                value = json.dumps(value, ensure_ascii=False, indent=2)
            return value if len(value) <= limit else f"{value[:limit]}..."

        api_results = []
        if not self.plan.scenarios.exists():
            api_results = list(self.task.results.select_related("case", "case__api").order_by("id"))
        step_results = list(self.task.step_results.select_related("scenario", "step", "step__api").order_by("id"))
        all_results = [*api_results, *step_results]
        durations = [item.duration_ms or 0 for item in all_results]
        total_duration = sum(durations)
        avg_duration = round(total_duration / len(durations)) if durations else 0
        max_duration = max(durations) if durations else 0
        total_count = len(all_results) if self.plan.scenarios.exists() else self.task.total_count
        passed_count = len([item for item in all_results if item.status == TestResult.Status.PASSED])
        failed_count = len([item for item in all_results if item.status in [TestResult.Status.FAILED, TestResult.Status.ERROR]])
        skipped_count = len([item for item in all_results if item.status == TestResult.Status.SKIPPED])
        report_status = TestTask.Status.FAILED if failed_count else self.task.status
        if total_count and passed_count + failed_count + skipped_count >= total_count and not failed_count:
            report_status = TestTask.Status.PASSED
        pass_rate = round((passed_count / total_count) * 100, 1) if total_count else 0
        failed_items = [
            item for item in all_results
            if item.status in [TestResult.Status.FAILED, TestResult.Status.ERROR, TestResult.Status.SKIPPED]
        ]
        category_counts = {}
        for item in failed_items:
            key = category_label(item.failure_category)
            category_counts[key] = category_counts.get(key, 0) + 1

        api_rows = []
        for result in api_results:
            api_rows.append(
                "<tr>"
                f"<td>{escape(result.case_code)}</td>"
                f"<td>{escape(result.title)}</td>"
                f"<td>{status_badge(result.status)}</td>"
                f"<td>{result.duration_ms}</td>"
                f"<td>{result.response_status or ''}</td>"
                f"<td>{escape(category_label(result.failure_category))}</td>"
                f"<td>{escape(result.assertion_error or '')}</td>"
                "</tr>"
            )

        step_rows = []
        for result in step_results:
            step_rows.append(
                "<tr>"
                f"<td>{escape(result.scenario_name or getattr(result.scenario, 'name', '') or '')}</td>"
                f"<td>{escape(result.step_name)}</td>"
                f"<td>{status_badge(result.status)}</td>"
                f"<td>{result.duration_ms}</td>"
                f"<td>{result.response_status or ''}</td>"
                f"<td>{escape(category_label(result.failure_category))}</td>"
                f"<td>{escape(result.assertion_error or '')}</td>"
                "</tr>"
            )

        failure_cards = []
        for item in failed_items:
            title = getattr(item, "case_code", "") or getattr(item, "step_name", "")
            subtitle = getattr(item, "title", "") or getattr(item, "scenario_name", "") or getattr(getattr(item, "scenario", None), "name", "")
            request_data = short_text(getattr(item, "request_data", {}), 700)
            response_body = short_text(getattr(item, "response_body", ""), 700)
            failure_cards.append(
                "<details class=\"failure\" open>"
                f"<summary>{status_badge(item.status)} <b>{escape(title)}</b> {escape(subtitle or '')}"
                f"<span>{escape(category_label(item.failure_category))}</span></summary>"
                f"<p class=\"error-text\">{escape(item.assertion_error or '无错误信息')}</p>"
                "<div class=\"detail-grid\">"
                f"<div><h4>请求</h4><pre>{escape(request_data)}</pre></div>"
                f"<div><h4>响应</h4><pre>{escape(response_body)}</pre></div>"
                "</div>"
                "</details>"
            )

        category_items = "".join(
            f"<span class=\"chip\">{escape(name)} <b>{count}</b></span>"
            for name, count in category_counts.items()
        ) or "<span class=\"muted\">无失败分类</span>"

        html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>测试报告 #{self.task.id}</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #1f2937; background: #f3f4f6; }}
    main {{ max-width: 1280px; margin: 0 auto; padding: 32px; }}
    header {{ display: flex; justify-content: space-between; gap: 24px; align-items: flex-start; margin-bottom: 20px; }}
    h1 {{ margin: 0 0 8px; font-size: 30px; }}
    h2 {{ margin: 28px 0 12px; font-size: 18px; }}
    h4 {{ margin: 0 0 8px; color: #374151; }}
    .meta {{ color: #6b7280; line-height: 1.8; }}
    .panel {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 18px; margin-bottom: 18px; }}
    .summary {{ display: grid; grid-template-columns: repeat(6, minmax(120px, 1fr)); gap: 12px; }}
    .summary div {{ border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px 14px; background: #fff; }}
    .summary span {{ display: block; color: #6b7280; font-size: 13px; margin-bottom: 6px; }}
    .summary strong {{ font-size: 24px; }}
    .chips {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .chip {{ border: 1px solid #d1d5db; border-radius: 999px; padding: 5px 10px; background: #f9fafb; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border-bottom: 1px solid #e5e7eb; padding: 10px 12px; text-align: left; vertical-align: top; }}
    th {{ background: #f9fafb; color: #6b7280; }}
    .status {{ border-radius: 999px; padding: 2px 10px; font-weight: 600; }}
    .passed {{ color: #047857; background: #d1fae5; }}
    .failed, .error {{ color: #b91c1c; background: #fee2e2; }}
    .skipped {{ color: #92400e; background: #fef3c7; }}
    .failure {{ border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; margin-bottom: 10px; background: #fff; }}
    .failure summary {{ cursor: pointer; display: flex; align-items: center; gap: 10px; }}
    .failure summary span:last-child {{ margin-left: auto; color: #6b7280; }}
    .error-text {{ color: #b91c1c; background: #fef2f2; border-radius: 6px; padding: 10px; }}
    .detail-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
    pre {{ margin: 0; max-height: 260px; overflow: auto; white-space: pre-wrap; background: #111827; color: #f9fafb; border-radius: 6px; padding: 12px; }}
    .muted {{ color: #6b7280; }}
    @media (max-width: 900px) {{ .summary, .detail-grid {{ grid-template-columns: 1fr; }} header {{ display: block; }} main {{ padding: 18px; }} }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>测试报告 #{self.task.id}</h1>
        <div class="meta">
          计划：{escape(self.plan.name)}<br>
          项目：{escape(self.plan.project.name)} / 环境：{escape(self.env.name)}
        </div>
      </div>
      <div class="meta">
        开始：{escape(str(self.task.started_at or '-'))}<br>
        结束：{escape(str(self.task.finished_at or '-'))}
      </div>
    </header>

    <section class="summary">
      <div><span>状态</span><strong>{escape(report_status)}</strong></div>
      <div><span>总数</span><strong>{total_count}</strong></div>
      <div><span>通过</span><strong>{passed_count}</strong></div>
      <div><span>失败</span><strong>{failed_count}</strong></div>
      <div><span>跳过</span><strong>{skipped_count}</strong></div>
      <div><span>通过率</span><strong>{pass_rate}%</strong></div>
    </section>

    <section class="panel">
      <h2>耗时与失败分类</h2>
      <div class="summary">
        <div><span>总耗时</span><strong>{total_duration} ms</strong></div>
        <div><span>平均耗时</span><strong>{avg_duration} ms</strong></div>
        <div><span>最慢耗时</span><strong>{max_duration} ms</strong></div>
      </div>
      <div class="chips" style="margin-top: 14px;">{category_items}</div>
    </section>

    <section>
      <h2>失败与跳过详情</h2>
      {''.join(failure_cards) or '<div class="panel muted">暂无失败、错误或跳过项</div>'}
    </section>

    <section class="panel">
      <h2>接口用例结果</h2>
      <table>
        <thead>
          <tr><th>用例ID</th><th>标题</th><th>状态</th><th>耗时(ms)</th><th>HTTP</th><th>分类</th><th>错误</th></tr>
        </thead>
        <tbody>{''.join(api_rows) or '<tr><td colspan="7" class="muted">暂无接口用例结果</td></tr>'}</tbody>
      </table>
    </section>

    <section class="panel">
      <h2>场景步骤结果</h2>
      <table>
        <thead>
          <tr><th>场景</th><th>步骤</th><th>状态</th><th>耗时(ms)</th><th>HTTP</th><th>分类</th><th>错误</th></tr>
        </thead>
        <tbody>{''.join(step_rows) or '<tr><td colspan="7" class="muted">暂无场景步骤结果</td></tr>'}</tbody>
      </table>
    </section>
  </main>
</body>
</html>
"""
        (report_dir / "index.html").write_text(html, encoding="utf-8")
