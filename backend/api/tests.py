"""
backend/api/tests.py

文件用途
-------
后端自动化测试（pytest 风格写在 Django TestCase 中）。

覆盖重点：
- 测试计划 TestPlan：创建校验、范围冲突（场景 vs 接口范围）、预览逻辑
- 执行任务 TestTask：创建后应立即返回（异步投递不阻塞）、投递失败记录、删除限制
- 场景执行：只统计/返回场景步骤结果（避免混入历史接口结果）
- cURL 导入：解析能力、限制项（文件上传/非法命令）、落库结果，以及跨域 base_url 执行验证

说明
----
这份测试对面试讲解很加分：它体现了你对业务规则的“可验证性”与对异步边界的理解。
"""

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from time import perf_counter, sleep
from unittest.mock import patch
from rest_framework.test import APIClient

from .models import (
    ApiCase,
    ApiDefinition,
    Environment,
    Module,
    Project,
    ScenarioCase,
    ScenarioStep,
    ScenarioStepResult,
    TestPlan,
    TestResult,
    TestTask,
)
from .services.db_runner import DbTaskRunner
from .services.curl_importer import CurlImportError, CurlImportService
from .serializers import resolve_plan_cases


class TestPlanApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user("tester", password="pass123")
        self.client.force_authenticate(self.user)
        self.project = Project.objects.create(name="项目A")
        self.environment = Environment.objects.create(
            project=self.project, name="测试环境", base_url="https://example.com"
        )
        self.module = Module.objects.create(project=self.project, name="模块A")
        self.api = ApiDefinition.objects.create(
            module=self.module, name="接口A", path="/api/demo", method="GET"
        )
        self.case = ApiCase.objects.create(api=self.api, case_code="CASE-001", title="用例A")

    def test_create_test_plan(self):
        response = self.client.post(
            "/api/test-plans/",
            {
                "name": "回归计划",
                "project": self.project.id,
                "environment": self.environment.id,
                "levels": [1, 2],
                "module_ids": [self.module.id],
                "case_ids": [self.case.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        plan = TestPlan.objects.get(id=response.data["id"])
        self.assertEqual(plan.created_by, self.user)
        self.assertEqual(list(plan.modules.values_list("id", flat=True)), [self.module.id])
        self.assertEqual(list(plan.cases.values_list("id", flat=True)), [self.case.id])

    def test_create_test_plan_rejects_environment_from_other_project(self):
        other_project = Project.objects.create(name="项目B")
        other_environment = Environment.objects.create(project=other_project, name="测试环境")

        response = self.client.post(
            "/api/test-plans/",
            {
                "name": "错误计划",
                "project": self.project.id,
                "environment": other_environment.id,
                "levels": [],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["environment"][0], "环境不属于所选项目")

    def test_create_test_plan_requires_project_and_environment(self):
        response = self.client.post(
            "/api/test-plans/",
            {"name": "缺少项目环境", "project": None, "environment": None, "levels": []},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["project"][0], "请选择项目")
        self.assertEqual(response.data["environment"][0], "请选择环境")

    def test_create_test_plan_rejects_scenario_with_api_scope(self):
        scenario = ScenarioCase.objects.create(project=self.project, module=self.module, name="完整场景")

        response = self.client.post(
            "/api/test-plans/",
            {
                "name": "冲突计划",
                "project": self.project.id,
                "environment": self.environment.id,
                "api_definition_ids": [self.api.id],
                "scenario_ids": [scenario.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["scenario_ids"][0], "场景用例不能和模块、接口、用例范围同时选择")

    def test_preview_scenario_plan_does_not_include_project_api_cases(self):
        scenario = ScenarioCase.objects.create(project=self.project, module=self.module, name="完整场景")
        ScenarioStep.objects.create(scenario=scenario, api=self.api, name="登录")

        response = self.client.post(
            "/api/test-plans/preview/",
            {
                "name": "场景计划",
                "project": self.project.id,
                "environment": self.environment.id,
                "scenario_ids": [scenario.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["cases_count"], 0)
        self.assertEqual(response.data["scenarios_count"], 1)

    def test_resolve_plan_cases_returns_none_for_scenario_plan(self):
        scenario = ScenarioCase.objects.create(project=self.project, module=self.module, name="完整场景")
        plan = TestPlan.objects.create(name="场景计划", project=self.project, environment=self.environment)
        plan.scenarios.set([scenario])

        self.assertEqual(resolve_plan_cases(plan).count(), 0)


class TestTaskApiTests(TransactionTestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user("tester", password="pass123")
        self.client.force_authenticate(self.user)
        self.project = Project.objects.create(name="项目A")
        self.environment = Environment.objects.create(project=self.project, name="测试环境")
        self.plan = TestPlan.objects.create(
            name="回归计划",
            project=self.project,
            environment=self.environment,
            created_by=self.user,
        )

    def wait_for_task(self, task_id, condition, timeout=1):
        deadline = perf_counter() + timeout
        while perf_counter() < deadline:
            task = TestTask.objects.get(id=task_id)
            if condition(task):
                return task
            sleep(0.01)
        return TestTask.objects.get(id=task_id)

    @patch("api.views.run_test_task.apply_async")
    def test_create_test_task_returns_pending_without_waiting_for_enqueue(self, mock_apply_async):
        mock_apply_async.return_value.id = "celery-task-id"

        response = self.client.post("/api/test-tasks/", {"plan": self.plan.id}, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], TestTask.Status.PENDING)
        self.assertEqual(response.data["log"], "任务已创建，等待异步投递")
        mock_apply_async.assert_called_once_with(args=[response.data["id"]], retry=False)
        task = self.wait_for_task(response.data["id"], lambda item: item.log == "Celery task id: celery-task-id")
        self.assertEqual(task.log, "Celery task id: celery-task-id")

    @patch("api.views.run_test_task.apply_async", side_effect=ConnectionError("broker unavailable"))
    def test_create_test_task_records_enqueue_failure_asynchronously(self, mock_apply_async):
        response = self.client.post("/api/test-tasks/", {"plan": self.plan.id}, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], TestTask.Status.PENDING)
        mock_apply_async.assert_called_once_with(args=[response.data["id"]], retry=False)
        task = self.wait_for_task(response.data["id"], lambda item: item.status == TestTask.Status.FAILED)
        self.assertIn("Celery 投递失败", task.log)
        self.assertEqual(task.failure_reason, "broker unavailable")
        self.assertIsNotNone(task.finished_at)

    @patch("api.views.run_test_task.apply_async", side_effect=lambda *args, **kwargs: sleep(0.1))
    def test_create_test_task_returns_immediately_when_enqueue_hangs(self, mock_apply_async):
        started_at = perf_counter()

        response = self.client.post("/api/test-tasks/", {"plan": self.plan.id}, format="json")
        elapsed = perf_counter() - started_at

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], TestTask.Status.PENDING)
        self.assertLess(elapsed, 0.05)
        deadline = perf_counter() + 1
        while perf_counter() < deadline and not mock_apply_async.called:
            sleep(0.01)
        mock_apply_async.assert_called_once_with(args=[response.data["id"]], retry=False)

    def test_allure_returns_report_url(self):
        task = TestTask.objects.create(
            plan=self.plan,
            report_xml_path="/tmp/nexus/reports/tasks/1/xml",
            report_html_path="/tmp/nexus/reports/tasks/1/html",
        )

        response = self.client.get(f"/api/test-tasks/{task.id}/allure/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["task"], task.id)
        self.assertEqual(response.data["url"], f"/reports/tasks/{task.id}/html/index.html")

    def test_list_test_tasks_filters_by_status(self):
        TestTask.objects.create(plan=self.plan, status=TestTask.Status.PASSED)
        TestTask.objects.create(plan=self.plan, status=TestTask.Status.FAILED)

        response = self.client.get("/api/test-tasks/", {"status": TestTask.Status.FAILED})

        self.assertEqual(response.status_code, 200)
        rows = response.data.get("results", response.data)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], TestTask.Status.FAILED)

    def test_delete_completed_test_task(self):
        task = TestTask.objects.create(plan=self.plan, status=TestTask.Status.FAILED)

        response = self.client.delete(f"/api/test-tasks/{task.id}/")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(TestTask.objects.filter(id=task.id).exists())

    def test_delete_running_test_task_is_rejected(self):
        task = TestTask.objects.create(plan=self.plan, status=TestTask.Status.RUNNING)

        response = self.client.delete(f"/api/test-tasks/{task.id}/")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "执行中任务不能删除")

    def test_scenario_only_plan_executes_only_scenario_steps(self):
        module = Module.objects.create(project=self.project, name="模块A")
        api = ApiDefinition.objects.create(module=module, name="接口A", path="/api/demo", method="GET")
        ApiCase.objects.create(api=api, case_code="CASE-001", title="不应执行的接口用例")
        scenario = ScenarioCase.objects.create(project=self.project, module=module, name="完整场景")
        ScenarioStep.objects.create(scenario=scenario, api=api, name="步骤1")
        ScenarioStep.objects.create(scenario=scenario, api=api, name="步骤2")
        self.plan.scenarios.set([scenario])
        task = TestTask.objects.create(plan=self.plan)

        with patch("api.services.db_runner.requests.Session.request") as mock_request:
            mock_response = mock_request.return_value
            mock_response.status_code = 200
            mock_response.text = "{}"
            mock_response.json.return_value = {}
            mock_response.request.headers = {}
            DbTaskRunner(task).run()

        task.refresh_from_db()
        self.assertEqual(task.total_count, 2)
        self.assertEqual(task.results.count(), 0)
        self.assertEqual(task.step_results.count(), 2)
        self.assertEqual(task.status, TestTask.Status.PASSED)

    def test_scenario_task_detail_ignores_stale_api_case_results(self):
        module = Module.objects.create(project=self.project, name="模块A")
        api = ApiDefinition.objects.create(module=module, name="接口A", path="/api/demo", method="GET")
        case = ApiCase.objects.create(api=api, case_code="CASE-001", title="旧接口结果")
        scenario = ScenarioCase.objects.create(project=self.project, module=module, name="完整场景")
        step = ScenarioStep.objects.create(scenario=scenario, api=api, name="步骤1")
        self.plan.scenarios.set([scenario])
        task = TestTask.objects.create(
            plan=self.plan,
            status=TestTask.Status.FAILED,
            total_count=2,
            passed_count=2,
            failed_count=0,
            progress=50,
        )
        TestResult.objects.create(task=task, case=case, case_code=case.case_code, title=case.title, status=TestResult.Status.PASSED)
        ScenarioStepResult.objects.create(
            task=task,
            scenario=scenario,
            scenario_name=scenario.name,
            step=step,
            step_name=step.name,
            status=TestResult.Status.PASSED,
        )

        detail_response = self.client.get(f"/api/test-tasks/{task.id}/")
        results_response = self.client.get(f"/api/test-tasks/{task.id}/results/")

        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.data["total_count"], 1)
        self.assertEqual(detail_response.data["passed_count"], 1)
        self.assertEqual(detail_response.data["failed_count"], 0)
        self.assertEqual(detail_response.data["progress"], 100)
        self.assertEqual(detail_response.data["status"], TestTask.Status.PASSED)
        rows = results_response.data.get("results", results_response.data)
        self.assertEqual(rows, [])

    def test_step_results_return_execution_scenario_snapshot(self):
        module = Module.objects.create(project=self.project, name="模块A")
        api = ApiDefinition.objects.create(module=module, name="接口A", path="/api/demo", method="GET")
        scenario = ScenarioCase.objects.create(project=self.project, module=module, name="执行时场景")
        step = ScenarioStep.objects.create(scenario=scenario, api=api, name="登录")
        task = TestTask.objects.create(plan=self.plan)
        ScenarioStepResult.objects.create(
            task=task,
            scenario=scenario,
            scenario_name=scenario.name,
            step=step,
            step_name=step.name,
            status=TestResult.Status.PASSED,
        )
        scenario.name = "后来改名的场景"
        scenario.save(update_fields=["name"])

        response = self.client.get(f"/api/test-tasks/{task.id}/step-results/")

        self.assertEqual(response.status_code, 200)
        rows = response.data.get("results", response.data)
        self.assertEqual(rows[0]["scenario_name"], "执行时场景")


class CurlImportServiceTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="项目A")
        self.module = Module.objects.create(project=self.project, name="模块A")
        self.service = CurlImportService()

    def test_parse_json_curl_and_create_api_case(self):
        result = self.service.import_curl(
            module_id=self.module.id,
            curl_text=(
                "curl 'https://example.com/api/login?tenant=oms' "
                "-H 'Content-Type: application/json' "
                "-H 'Authorization: Bearer token' "
                "--data-raw '{\"username\":\"ron\",\"password\":\"123456\"}'"
            ),
            name="登录接口",
            case_title="登录默认用例",
        )

        self.assertEqual(result["parsed"]["method"], "POST")
        self.assertEqual(result["parsed"]["base_url"], "https://example.com")
        self.assertEqual(result["parsed"]["path"], "/api/login")
        self.assertEqual(result["parsed"]["query"], {"tenant": "oms"})
        self.assertEqual(result["parsed"]["payload"], {"username": "ron", "password": "123456"})
        api = ApiDefinition.objects.get(id=result["api_definition"]["id"])
        case = ApiCase.objects.get(id=result["api_case"]["id"])
        self.assertEqual(api.name, "登录接口")
        self.assertEqual(api.default_headers["Authorization"], "Bearer token")
        self.assertEqual(
            case.payload,
            {
                "__base_url": "https://example.com",
                "__query": {"tenant": "oms"},
                "__body": {"username": "ron", "password": "123456"},
            },
        )
        self.assertEqual(case.title, "登录默认用例")
        self.assertEqual(case.subtitle, "cURL 导入默认用例")

    def test_parse_form_curl_payload_as_object(self):
        result = self.service.import_curl(
            module_id=self.module.id,
            curl_text=(
                "curl --request POST 'https://example.com/api/form' "
                "--header 'Content-Type: application/x-www-form-urlencoded' "
                "--data-raw 'code=1001&name=ron'"
            ),
        )

        self.assertEqual(result["parsed"]["payload"], {"code": "1001", "name": "ron"})
        case = ApiCase.objects.get(id=result["api_case"]["id"])
        self.assertEqual(
            case.payload,
            {"__base_url": "https://example.com", "__body": {"code": "1001", "name": "ron"}},
        )

    def test_reuse_existing_api_and_fill_missing_headers(self):
        api = ApiDefinition.objects.create(
            module=self.module,
            name="已维护接口",
            path="/api/login",
            method="POST",
            default_headers={"X-Trace-Id": "keep-me"},
        )
        existing_case = ApiCase.objects.create(
            api=api,
            case_code=f"CURL_AUTO_{api.id}",
            title="旧默认用例",
            subtitle="cURL 导入默认用例",
        )

        result = self.service.import_curl(
            module_id=self.module.id,
            curl_text=(
                "curl 'https://example.com/api/login' "
                "-H 'Content-Type: application/json' "
                "--data-raw '{\"hello\":\"world\"}'"
            ),
        )

        api.refresh_from_db()
        existing_case.refresh_from_db()
        self.assertEqual(result["action"]["api_definition"], "updated")
        self.assertEqual(result["action"]["api_case"], "updated")
        self.assertEqual(api.name, "已维护接口")
        self.assertEqual(api.default_headers["X-Trace-Id"], "keep-me")
        self.assertEqual(api.default_headers["Content-Type"], "application/json")
        self.assertEqual(existing_case.payload, {"__base_url": "https://example.com", "__body": {"hello": "world"}})

    def test_parse_rejects_invalid_curl(self):
        with self.assertRaises(CurlImportError):
            self.service.import_curl(module_id=self.module.id, curl_text="not-a-curl")

    def test_parse_get_query_into_special_payload(self):
        result = self.service.import_curl(
            module_id=self.module.id,
            curl_text="curl 'https://example.com/api/users?page=1&size=20' --compressed",
        )

        self.assertEqual(result["parsed"]["query"], {"page": "1", "size": "20"})
        case = ApiCase.objects.get(id=result["api_case"]["id"])
        self.assertEqual(case.payload, {"__base_url": "https://example.com", "__query": {"page": "1", "size": "20"}})

    def test_parse_rejects_file_upload(self):
        with self.assertRaises(CurlImportError) as context:
            self.service.import_curl(
                module_id=self.module.id,
                curl_text="curl 'https://example.com/upload' -F 'file=@/tmp/demo.txt'",
            )

        self.assertIn("文件上传", str(context.exception))


class CurlImportApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user("tester", password="pass123")
        self.client.force_authenticate(self.user)
        self.project = Project.objects.create(name="项目A")
        self.module = Module.objects.create(project=self.project, name="模块A")

    def test_import_curl_api_success(self):
        response = self.client.post(
            "/api/imports/curl/",
            {
                "module": self.module.id,
                "name": "用户详情",
                "curl_text": "curl 'https://example.com/api/user/detail?id=1' -H 'Accept: application/json'",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["api_definition"]["name"], "用户详情")
        self.assertEqual(response.data["parsed"]["path"], "/api/user/detail")
        self.assertTrue(ApiDefinition.objects.filter(path="/api/user/detail", method="GET").exists())

    def test_import_curl_api_requires_fields(self):
        response = self.client.post("/api/imports/curl/", {"module": "", "curl_text": ""}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "请选择目标模块")

    def test_import_curl_api_reuses_existing_api(self):
        api = ApiDefinition.objects.create(
            module=self.module,
            name="接口A",
            path="/api/demo",
            method="GET",
        )
        ApiCase.objects.create(
            api=api,
            case_code=f"CURL_AUTO_{api.id}",
            title="接口A",
            subtitle="cURL 导入默认用例",
        )

        response = self.client.post(
            "/api/imports/curl/",
            {
                "module": self.module.id,
                "curl_text": "curl 'https://example.com/api/demo' -H 'Accept: application/json'",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["action"]["api_definition"], "updated")
        self.assertEqual(ApiDefinition.objects.filter(module=self.module, path="/api/demo", method="GET").count(), 1)

    def test_import_curl_api_supports_preview(self):
        response = self.client.post(
            "/api/imports/curl/",
            {
                "module": self.module.id,
                "curl_text": "curl 'https://example.com/api/demo?id=1'",
                "dry_run": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["action"]["api_definition"], "created")
        self.assertFalse(ApiDefinition.objects.exists())


class CurlImportedCaseExecutionTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="项目A")
        self.environment = Environment.objects.create(
            project=self.project,
            name="测试环境",
            base_url="https://b.geekbang.org",
        )
        self.module = Module.objects.create(project=self.project, name="模块A")
        self.api = ApiDefinition.objects.create(
            module=self.module,
            name="课程列表",
            path="/serv/v1/column/newAll",
            method="GET",
        )
        self.case = ApiCase.objects.create(
            api=self.api,
            case_code="CURL_AUTO_1",
            title="课程列表",
            payload={"__base_url": "https://time.geekbang.org", "__query": {"page": "1"}},
        )
        self.plan = TestPlan.objects.create(name="计划A", project=self.project, environment=self.environment)
        self.plan.cases.set([self.case])
        self.task = TestTask.objects.create(plan=self.plan)

    @patch("api.services.db_runner.requests.Session.request")
    def test_imported_case_uses_curl_base_url_instead_of_environment_base_url(self, mock_request):
        mock_response = mock_request.return_value
        mock_response.status_code = 200
        mock_response.text = "{}"
        mock_response.json.return_value = {}
        mock_response.request.headers = {}

        DbTaskRunner(self.task).run()

        mock_request.assert_called_once()
        args, kwargs = mock_request.call_args
        self.assertEqual(args[1], "https://time.geekbang.org/serv/v1/column/newAll")
        self.assertEqual(kwargs["params"], {"page": "1"})
