"""
backend/api/services/db_runner.py

文件用途
-------
这是 OmniQA 接口/场景执行引擎的“核心运行时”实现（DB Runner）。

平台在 Web 层创建 TestTask 后，会由 Celery 异步 Worker 调用这里的逻辑完成真正的用例执行。
它的职责不是“组织数据”（那是 views/serializers 的事），而是“按计划把用例跑起来、产出结果与报告”：

1) 选择待执行对象：
   - 接口用例（ApiCase）：来自测试计划 TestPlan 的筛选范围
   - 场景用例（ScenarioCase）：由多个步骤（ScenarioStep）组成
2) 解决依赖与顺序：
   - ApiCase.dependencies / ScenarioStep.dependencies 拓扑排序
   - 依赖失败时自动 SKIPPED，并记录失败链路
3) 变量体系（DbVariablePool）：
   - 三层变量注入：项目变量(ProjectVariable) / 环境变量(EnvironmentVariable) / 运行期提取变量(extractors)
   - 支持在字符串中用 ${var} 或 ${case_code.jsonpath} 引用历史响应数据
4) 请求执行与断言：
   - 基于 requests.Session 复用连接与 Cookie
   - expect 支持“简单结构匹配”与“可视化断言 __assertions”（状态码、字段存在/比较/正则等）
   - 结构匹配通过 PactJsonVerify（宽松模式）实现
5) 结果与可观测性：
   - TestResult / ScenarioStepResult：保存每个用例/步骤的请求、响应、耗时、失败分类
   - TaskEvent：结构化事件流（用于任务详情页时间线、看板统计）
6) 报告：
   - write_html_report() 生成轻量 HTML 报告到 settings.OMNIQA_REPORT_ROOT 对应目录

面试讲解抓手
-----------
- “执行引擎”与“Web API”分层：API 只建任务，Runner 才是真正执行者（异步解耦、可扩展）
- 依赖拓扑排序 + 自动跳过：保证链路稳定，失败能定位，且不会一错全错阻塞后续
- 变量池与 Cookie 持久化：让接口用例具备“状态流转”能力，贴近真实链路
"""

import json
import time
from http.cookies import SimpleCookie
from html import escape
from pathlib import Path

import requests
from django.conf import settings
from django.utils import timezone
from jsonpath import jsonpath
from pactverify.matchers import PactJsonVerify

from api.models import ApiCase, ScenarioCase, ScenarioStepResult, TaskEvent, TestResult, TestTask
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

        # 多账号/多角色隔离：每个 session_key 一套 requests.Session + 变量池
        self.sessions = {}
        self.variable_pools = {}

        # 基础变量（公共配置）：项目变量 + 环境变量。每个会话变量池都会拷贝一份。
        self.base_variable_mapping = {
            item.key: item.value for item in self.plan.project.variables.filter(enabled=True)
        }
        self.base_variable_mapping.update(
            {item.key: item.value for item in self.env.variables.filter(enabled=True)}
        )

        # 默认会话
        self.session = None
        self.variables = None
        self.activate_session("default")

    def activate_session(self, session_key: str):
        """
        切换到指定会话上下文（Cookie + 运行时变量）。

        - 同一 session_key：共享 Cookie 与运行时变量（extractors、历史响应快照等）
        - 不同 session_key：相互隔离
        """
        key = (session_key or "default").strip() or "default"
        if key not in self.sessions:
            self.sessions[key] = requests.Session()
            pool = DbVariablePool()
            pool.load_mapping(self.base_variable_mapping)
            self.variable_pools[key] = pool
        self.session = self.sessions[key]
        self.variables = self.variable_pools[key]

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
        TaskEvent.objects.create(
            task=self.task,
            level=TaskEvent.Level.INFO,
            category=TaskEvent.Category.TASK,
            object_type="TASK",
            message="任务开始执行",
            data={"plan": self.plan.id, "plan_name": self.plan.name, "environment": self.env.id},
        )
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
                TaskEvent.objects.create(
                    task=self.task,
                    level=TaskEvent.Level.WARN,
                    category=TaskEvent.Category.TASK,
                    object_type="TASK",
                    message="任务已取消，提前结束",
                )
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
            TaskEvent.objects.create(
                task=self.task,
                level=TaskEvent.Level.INFO,
                category=TaskEvent.Category.REPORT,
                object_type="TASK",
                message="HTML 报告已生成",
                data={"report_html_path": self.task.report_html_path},
            )
        except Exception as exc:
            self.task.log = f"{self.task.log}\nHTML 报告生成失败: {exc}".strip()
            self.task.save(update_fields=["log", "updated_at"])
            TaskEvent.objects.create(
                task=self.task,
                level=TaskEvent.Level.ERROR,
                category=TaskEvent.Category.REPORT,
                object_type="TASK",
                message="HTML 报告生成失败",
                data={"error": str(exc)},
            )

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
        TaskEvent.objects.create(
            task=self.task,
            level=TaskEvent.Level.WARN,
            category=TaskEvent.Category.DEPENDENCY,
            object_type="SCENARIO_STEP",
            case_code=f"SCN-{scenario.id}",
            step_name=step.name,
            message=message,
            data={"blocked_by": blocked_by},
        )
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
        TaskEvent.objects.create(
            task=self.task,
            level=TaskEvent.Level.INFO,
            category=TaskEvent.Category.REQUEST,
            object_type="SCENARIO_STEP",
            case_code=f"SCN-{scenario.id}",
            step_name=step.name,
            message="开始执行场景步骤",
            data={"api": {"method": step.api.method, "path": step.api.path, "id": step.api.id}},
        )
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
            # 多会话隔离：每个步骤绑定到各自 session_key 的 Cookie/变量上下文
            current_session_key = getattr(step, "session_key", None) or "default"
            self.activate_session(current_session_key)
            mismatched = [
                dep.name
                for dep in step.dependencies.all()
                if (getattr(dep, "session_key", None) or "default") != current_session_key
            ]
            if mismatched:
                TaskEvent.objects.create(
                    task=self.task,
                    level=TaskEvent.Level.WARN,
                    category=TaskEvent.Category.DEPENDENCY,
                    object_type="SCENARIO_STEP",
                    case_code=f"SCN-{scenario.id}",
                    step_name=step.name,
                    message=f"步骤依赖跨会话，可能无法继承登录态/变量：{', '.join(mismatched)}",
                    data={"session_key": current_session_key, "mismatched_dependencies": mismatched},
                )
            method = step.api.method.upper()

            # 步骤可选择“引用用例（ApiCase）”，继承用例配置并允许步骤覆盖。
            base_case = getattr(step, "case", None)
            base_header = base_case.header if base_case else {}
            merged_header = {**(self.env.headers or {}), **(step.api.default_headers or {}), **(base_header or {}), **(step.header or {})}
            headers = self.prepare_headers(merged_header)

            merged_payload = self.merge_json_config(base_case.payload if base_case else None, step.payload)
            params, payload, payload_base_url = self.split_request_payload(method, merged_payload)
            url = self.build_url(step.api.path, payload_base_url)
            request_data = {"method": method, "url": url, "headers": headers, "payload": payload}
            if params is not None:
                request_data["query"] = params
            response = self.session.request(
                method,
                url,
                json=payload if isinstance(payload, (dict, list)) else None,
                data=payload if not isinstance(payload, (dict, list)) else None,
                params=params,
                headers=headers,
                verify=self.env.verify_ssl,
                timeout=self.env.timeout_seconds or getattr(settings, "OMNIQA_REQUEST_TIMEOUT", 10),
            )
            request_data["headers"] = dict(response.request.headers)
            response_status = response.status_code
            response_body = response.text
            try:
                actual = response.json() if response.text else {}
            except Exception:
                actual = {}
                status = TestResult.Status.ERROR
                failure_category = "RESPONSE_PARSE_ERROR"
                assertion_error = "响应 JSON 解析失败"
                raise
            self.save_session_cookies(response)
            if base_case and getattr(base_case, "case_code", None):
                self.variables.save(base_case.case_code, actual)
            self.variables.save(f"step_{step.id}", actual)
            if base_case:
                self.apply_extractors(base_case, actual)
            self.apply_extractors(step, actual)

            merged_expect = self.merge_json_config(base_case.expect if base_case else None, step.expect)
            expect = self.replace_json(merged_expect) if merged_expect else {}
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
        except requests.exceptions.Timeout as exc:
            status = TestResult.Status.ERROR
            failure_category = "TIMEOUT"
            assertion_error = str(exc)
        except requests.exceptions.RequestException as exc:
            status = TestResult.Status.ERROR
            failure_category = "NETWORK_ERROR"
            assertion_error = str(exc)
        except Exception as exc:
            status = TestResult.Status.ERROR
            failure_category = failure_category or "SCRIPT_ERROR"
            assertion_error = assertion_error or str(exc)
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
        if result.status in [TestResult.Status.FAILED, TestResult.Status.ERROR, TestResult.Status.SKIPPED]:
            TaskEvent.objects.create(
                task=self.task,
                level=TaskEvent.Level.ERROR if result.status != TestResult.Status.SKIPPED else TaskEvent.Level.WARN,
                category=TaskEvent.Category.ASSERTION if failure_category == "ASSERTION_FAILED" else TaskEvent.Category.REQUEST,
                object_type="SCENARIO_STEP",
                case_code=f"SCN-{scenario.id}",
                step_name=step.name,
                message=f"场景步骤结束: {result.status}",
                data={
                    "status": result.status,
                    "failure_category": failure_category,
                    "assertion_error": assertion_error,
                    "response_status": response_status,
                },
            )
        return result

    def blocked_dependencies(self, case, blocked_ids):
        return [
            dependency.case_code
            for dependency in case.dependencies.all()
            if dependency.id in blocked_ids
        ]

    def skip_case(self, case, blocked_by):
        message = f"依赖失败，跳过执行: {', '.join(blocked_by)}"
        TaskEvent.objects.create(
            task=self.task,
            level=TaskEvent.Level.WARN,
            category=TaskEvent.Category.DEPENDENCY,
            object_type="API_CASE",
            case_code=case.case_code,
            message=message,
            data={"blocked_by": blocked_by},
        )
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
        TaskEvent.objects.create(
            task=self.task,
            level=TaskEvent.Level.INFO,
            category=TaskEvent.Category.REQUEST,
            object_type="API_CASE",
            case_code=case.case_code,
            message="开始执行用例",
            data={"api": {"method": case.api.method, "path": case.api.path, "id": case.api.id}},
        )
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
            # 多会话隔离：每个用例绑定到各自 session_key 的 Cookie/变量上下文
            current_session_key = getattr(case, "session_key", None) or "default"
            self.activate_session(current_session_key)
            mismatched = [
                dep.case_code
                for dep in case.dependencies.all()
                if (getattr(dep, "session_key", None) or "default") != current_session_key
            ]
            if mismatched:
                TaskEvent.objects.create(
                    task=self.task,
                    level=TaskEvent.Level.WARN,
                    category=TaskEvent.Category.DEPENDENCY,
                    object_type="API_CASE",
                    case_code=case.case_code,
                    message=f"用例依赖跨会话，可能无法继承登录态/变量：{', '.join(mismatched)}",
                    data={"session_key": current_session_key, "mismatched_dependencies": mismatched},
                )
            method = case.api.method.upper()
            headers = self.prepare_headers({**(self.env.headers or {}), **(case.header or {})})
            params, payload, payload_base_url = self.split_request_payload(method, case.payload)
            url = self.build_url(case.api.path, payload_base_url)
            request_data = {"method": method, "url": url, "headers": headers, "payload": payload}
            if params is not None:
                request_data["query"] = params
            response = self.session.request(
                method,
                url,
                json=payload if isinstance(payload, (dict, list)) else None,
                data=payload if not isinstance(payload, (dict, list)) else None,
                params=params,
                headers=headers,
                verify=self.env.verify_ssl,
                timeout=self.env.timeout_seconds or getattr(settings, "OMNIQA_REQUEST_TIMEOUT", 10),
            )
            request_data["headers"] = dict(response.request.headers)
            response_status = response.status_code
            response_body = response.text
            try:
                actual = response.json() if response.text else {}
            except Exception:
                actual = {}
                status = TestResult.Status.ERROR
                failure_category = "RESPONSE_PARSE_ERROR"
                assertion_error = "响应 JSON 解析失败"
                raise
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
        except requests.exceptions.Timeout as exc:
            status = TestResult.Status.ERROR
            failure_category = "TIMEOUT"
            assertion_error = str(exc)
        except requests.exceptions.RequestException as exc:
            status = TestResult.Status.ERROR
            failure_category = "NETWORK_ERROR"
            assertion_error = str(exc)
        except Exception as exc:
            status = TestResult.Status.ERROR
            failure_category = failure_category or "SCRIPT_ERROR"
            assertion_error = assertion_error or str(exc)
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
        if result.status in [TestResult.Status.FAILED, TestResult.Status.ERROR, TestResult.Status.SKIPPED]:
            TaskEvent.objects.create(
                task=self.task,
                level=TaskEvent.Level.ERROR if result.status != TestResult.Status.SKIPPED else TaskEvent.Level.WARN,
                category=TaskEvent.Category.ASSERTION if failure_category == "ASSERTION_FAILED" else TaskEvent.Category.REQUEST,
                object_type="API_CASE",
                case_code=case.case_code,
                message=f"用例结束: {result.status}",
                data={
                    "status": result.status,
                    "failure_category": failure_category,
                    "assertion_error": assertion_error,
                    "response_status": response_status,
                },
            )
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
        # Cookie 仅任务内存：不再写入 EnvironmentCookie（环境级持久化）

    def prepare_headers(self, headers):
        prepared = self.replace_json(headers or {})
        return {
            key: value
            for key, value in prepared.items()
            if value not in ("", None) and key.lower() not in {"host", "cookie"}
        }

    def split_request_payload(self, method, payload):
        normalized = self.replace_json(payload)
        params = None
        body = normalized
        base_url = None
        if isinstance(normalized, dict) and ("__query" in normalized or "__body" in normalized):
            params = normalized.get("__query") or None
            body = normalized.get("__body")
            base_url = normalized.get("__base_url") or None
        elif isinstance(normalized, dict) and "__base_url" in normalized and len(normalized) == 1:
            base_url = normalized.get("__base_url") or None
            body = None
        elif method.upper() == "GET" and isinstance(normalized, dict):
            params = normalized or None
            body = None
        if body in ({}, "", None):
            body = None
        return params, body, base_url

    def merge_json_config(self, base, override):
        """
        用于用例继承 + 步骤覆盖的浅合并：
        - override 为空（None/''/{}）：返回 base
        - base 为空：返回 override
        - dict + dict：浅合并（override 覆盖同名 key）
        - 其他类型：以 override 为准
        """
        if override in (None, "", {}):
            return base
        if base in (None, "", {}):
            return override
        if isinstance(base, dict) and isinstance(override, dict):
            return {**base, **override}
        return override

    def update_progress(self, message):
        done = self.task.results.filter(case__is_setup=False).count() + self.task.step_results.count()
        total = self.task.total_count or 1
        self.task.progress = min(99, int(done / total * 100))
        self.task.passed_count = self.task.results.filter(
            case__is_setup=False, status=TestResult.Status.PASSED
        ).count() + self.task.step_results.filter(status=TestResult.Status.PASSED).count()
        self.task.failed_count = self.task.results.filter(
            case__is_setup=False, status__in=[TestResult.Status.FAILED, TestResult.Status.ERROR]
        ).count() + self.task.step_results.filter(
            status__in=[TestResult.Status.FAILED, TestResult.Status.ERROR]).count()
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

    # 🚀 这里是你需要但是遗漏的跨域 URL 修复逻辑
    def build_url(self, path, base_url=None):
        # 1. 优先对 path 进行变量解析（支持 ${domain}/api/v1 这种动态赋值形式）
        replaced_path = self.variables.replace(str(path or "")).strip()

        # 2. 判断解析后是否已经是绝对路径，如果是，直接返回（彻底忽略环境 base_url，完美支持跨域）
        if replaced_path.startswith("http://") or replaced_path.startswith("https://"):
            return replaced_path

        # 3. 对 base_url 也进行变量解析，支持动态环境前缀
        raw_base_url = base_url if base_url is not None else getattr(self.env, "base_url", "")
        effective_base_url = self.variables.replace(str(raw_base_url or "")).strip()

        if not effective_base_url:
            return replaced_path

        return f"{effective_base_url.rstrip('/')}/{replaced_path.lstrip('/')}"

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
            elif operator == "not_equals":
                assert actual_value != expected, (
                    f"字段不等于断言失败: {path}, 期望不等于 {expected}, 实际 {actual_value}"
                )
            elif operator in {"gt", "gte", "lt", "lte"}:
                try:
                    left = float(actual_value)
                    right = float(expected)
                except Exception:
                    raise AssertionError(f"字段比较断言要求数字: {path}, 实际 {actual_value}, 期望 {expected}")
                if operator == "gt":
                    assert left > right, f"字段大于断言失败: {path}, 期望 > {right}, 实际 {left}"
                elif operator == "gte":
                    assert left >= right, f"字段大于等于断言失败: {path}, 期望 >= {right}, 实际 {left}"
                elif operator == "lt":
                    assert left < right, f"字段小于断言失败: {path}, 期望 < {right}, 实际 {left}"
                else:
                    assert left <= right, f"字段小于等于断言失败: {path}, 期望 <= {right}, 实际 {left}"
            elif operator == "regex":
                import re
                assert re.search(str(expected), str(actual_value) or ""), (
                    f"正则断言失败: {path}, 期望匹配 {expected}, 实际 {actual_value}"
                )
            elif operator == "in":
                assert actual_value in (expected or []), (
                    f"包含于断言失败: {path}, 期望在 {expected}, 实际 {actual_value}"
                )
            elif operator == "not_in":
                assert actual_value not in (expected or []), (
                    f"不包含于断言失败: {path}, 期望不在 {expected}, 实际 {actual_value}"
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
        failed_count = len(
            [item for item in all_results if item.status in [TestResult.Status.FAILED, TestResult.Status.ERROR]])
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
            subtitle = getattr(item, "title", "") or getattr(item, "scenario_name", "") or getattr(
                getattr(item, "scenario", None), "name", "")
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
