"""
backend/api/views.py

文件用途
-------
后端 HTTP API 的主入口（Django REST Framework Views / ViewSets）。

该文件承担“面向前端的业务 API 编排”，特点是：
1) CRUD 类 API：大量 ModelViewSet（项目/环境/接口/用例/计划/任务/场景/UI 自动化等）
2) 组合类 API：看板统计、计划范围预览、任务结果/事件聚合等
3) 异步任务入口：
   - /api/test-tasks/：仅创建 TestTask 并异步投递 Celery（enqueue_test_task_async）
   - /api/ui-tasks/：创建 UiTask 并异步投递 Celery（enqueue_ui_task_async）
   说明：真正的执行逻辑在 backend/api/services/db_runner.py 与 ui_runner.py
4) 导入入口：
   - ExcelImportView：上传 Excel -> ExcelImportService().import_file()
   - CurlImportView：粘贴 cURL -> CurlImportService
5) 定时任务入口：
   - ScheduleViewSet：维护 Schedule（简单周期/Cron），并计算 next_run_at
   - run-now：从 Schedule 立即生成 TestTask（create_task_from_schedule）并投递执行

面试讲解建议
-----------
- 这是“接口层/控制器层”：它不关心如何跑用例，只负责权限、参数校验、数据查询与触发执行
- 通过 enqueue_*_async 把“创建任务”与“执行任务”解耦（Web 快速响应，执行可水平扩展）
- TaskEvent/结果查询 API 是可观测性关键：让前端能实时展示进度、时间线和失败原因
"""

from django.contrib.auth import login, logout
from django.conf import settings
from django.db.models import Avg, Case, Count, IntegerField, Max, Q, When
from django.utils import timezone
from datetime import timedelta
from rest_framework import mixins, status, viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from threading import Thread
import json
import time
import requests
from rest_framework.decorators import action
from rest_framework.response import Response
from .services.db_runner import DbVariablePool

from .models import (
    ApiCase,
    ApiDefinition,
    Environment,
    Module,
    Project,
    TestPlan,
    TestResult,
    TestTask,
    TaskEvent,
    UiArtifact,
    UiDataset,
    UiDatasetRow,
    UiElement,
    UiMethodStep,
    UiPage,
    UiPageMethod,
    UiScenario,
    UiScenarioStep,
    UiStep,
    UiStepResult,
    UiPlan,
    UiExecTask,
    UiTask,
    UiTaskEvent,
    UiRun,
)
from .models import EnvironmentCookie, EnvironmentVariable, ProjectVariable, ScenarioCase, ScenarioStep, ScenarioStepResult, Schedule
from .serializers import (
    ApiCaseSerializer,
    ApiDefinitionSerializer,
    CreateTestTaskSerializer,
    EnvironmentVariableSerializer,
    EnvironmentSerializer,
    EnvironmentCookieSerializer,
    LoginSerializer,
    ModuleSerializer,
    ProjectVariableSerializer,
    ProjectSerializer,
    ScenarioCaseSerializer,
    ScenarioStepResultSerializer,
    ScenarioStepSerializer,
    ScheduleSerializer,
    TaskEventSerializer,
    UiArtifactSerializer,
    UiDatasetRowSerializer,
    UiDatasetSerializer,
    UiElementSerializer,
    UiMethodStepSerializer,
    UiPageMethodSerializer,
    UiPageSerializer,
    UiScenarioSerializer,
    UiScenarioStepSerializer,
    UiStepResultSerializer,
    UiStepSerializer,
    UiPlanSerializer,
    CreateUiPlanSerializer,
    UiExecTaskSerializer,
    CreateUiExecTaskSerializer,
    UiTaskEventSerializer,
    UiTaskSerializer,
    CreateUiTaskSerializer,
    CreateUiRunSerializer,
    UiRunSerializer,
    TestPlanSerializer,
    TestResultSerializer,
    TestTaskSerializer,
    resolve_plan_cases,
    resolve_plan_scenarios,
)
from .services.importer import ExcelImportService
from .services.curl_importer import CurlImportError, CurlImportService
from .services.scheduler import compute_next_run, create_task_from_schedule
from .tasks import run_test_task, run_ui_task


def preview_plan_scope(data):
    project_id = data.get("project")
    cases = ApiCase.objects.none()
    scenarios = ScenarioCase.objects.none()
    if not project_id:
        return [], []

    case_ids = data.get("case_ids") or []
    api_definition_ids = data.get("api_definition_ids") or []
    module_ids = data.get("module_ids") or []
    scenario_ids = data.get("scenario_ids") or []
    if scenario_ids and (case_ids or api_definition_ids or module_ids):
        raise ValueError("场景用例不能和模块、接口、用例范围同时选择")

    case_queryset = ApiCase.objects.none()
    if not scenario_ids:
        case_queryset = ApiCase.objects.filter(api__module__project_id=project_id, enabled=True, is_setup=False)

        if case_ids:
            case_queryset = case_queryset.filter(id__in=case_ids)
        elif api_definition_ids:
            case_queryset = case_queryset.filter(api_id__in=api_definition_ids)
        elif module_ids:
            case_queryset = case_queryset.filter(api__module_id__in=module_ids)

    levels = data.get("levels") or []
    if levels:
        case_queryset = case_queryset.filter(level__in=levels)

    for tag in data.get("tags") or []:
        if tag:
            case_queryset = case_queryset.filter(tags__icontains=tag)

    suites = data.get("suites") or []
    if suites:
        case_queryset = case_queryset.filter(suite__in=suites)

    if scenario_ids:
        scenario_queryset = ScenarioCase.objects.filter(project_id=project_id, enabled=True, id__in=scenario_ids)
        if levels:
            scenario_queryset = scenario_queryset.filter(level__in=levels)
    elif module_ids:
        scenario_queryset = ScenarioCase.objects.filter(project_id=project_id, enabled=True, module_id__in=module_ids)
        if levels:
            scenario_queryset = scenario_queryset.filter(level__in=levels)
    else:
        scenario_queryset = ScenarioCase.objects.none()

    cases = list(case_queryset.select_related("api", "api__module").order_by("sort_order", "id"))
    scenarios = list(scenario_queryset.prefetch_related("steps").order_by("sort_order", "id"))
    return cases, scenarios


def enqueue_test_task_async(task_id):
    def publish():
        try:
            async_result = run_test_task.apply_async(args=[task_id], retry=False)
            TestTask.objects.filter(id=task_id, status=TestTask.Status.PENDING).update(
                log=f"Celery task id: {async_result.id}",
                updated_at=timezone.now(),
            )
        except Exception as exc:
            TestTask.objects.filter(id=task_id, status=TestTask.Status.PENDING).update(
                status=TestTask.Status.FAILED,
                log=f"Celery 投递失败: {exc}",
                failure_reason=str(exc),
                finished_at=timezone.now(),
                updated_at=timezone.now(),
            )

    Thread(target=publish, daemon=True).start()


def enqueue_ui_task_async(task_id):
    def publish():
        try:
            async_result = run_ui_task.apply_async(args=[task_id], retry=False)
            UiTask.objects.filter(id=task_id, status=UiTask.Status.PENDING).update(
                updated_at=timezone.now(),
                celery_task_id=str(async_result.id),
            )
        except Exception as exc:
            UiTask.objects.filter(id=task_id, status=UiTask.Status.PENDING).update(
                status=UiTask.Status.FAILED,
                failure_reason=f"Celery 投递失败: {exc}",
                finished_at=timezone.now(),
                updated_at=timezone.now(),
            )

    Thread(target=publish, daemon=True).start()


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        login(request, user)
        return Response({"id": user.id, "username": user.username})


class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response({"ok": True})


class MeView(APIView):
    def get(self, request):
        return Response({"id": request.user.id, "username": request.user.username})


class DashboardQualityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())
        trend_start = today_start - timedelta(days=6)
        stats_start = today_start - timedelta(days=6)

        def task_pass_rate(queryset):
            total = queryset.count()
            passed = queryset.filter(status=TestTask.Status.PASSED).count()
            return round(passed / total * 100, 1) if total else 0

        today_tasks = TestTask.objects.filter(created_at__gte=today_start)
        week_tasks = TestTask.objects.filter(created_at__gte=week_start)
        failed_statuses = [TestResult.Status.FAILED, TestResult.Status.ERROR]

        trend = []
        for offset in range(7):
            day = trend_start + timedelta(days=offset)
            next_day = day + timedelta(days=1)
            qs = TestTask.objects.filter(created_at__gte=day, created_at__lt=next_day)
            trend.append(
                {
                    "date": day.date().isoformat(),
                    "total": qs.count(),
                    "passed": qs.filter(status=TestTask.Status.PASSED).count(),
                    "failed": qs.filter(status=TestTask.Status.FAILED).count(),
                    "pass_rate": task_pass_rate(qs),
                }
            )

        failed_modules = list(
            TestResult.objects.filter(status__in=failed_statuses, case__isnull=False)
            .values("case__api__module__name")
            .annotate(failed_count=Count("id"))
            .order_by("-failed_count")[:5]
        )
        failed_interfaces = list(
            TestResult.objects.filter(status__in=failed_statuses, case__isnull=False)
            .values("case__api__method", "case__api__path", "case__api__name")
            .annotate(failed_count=Count("id"), avg_duration_ms=Avg("duration_ms"))
            .order_by("-failed_count")[:5]
        )

        # 近 7 天失败原因分布（接口用例 + 场景步骤）
        failure_categories = list(
            TestResult.objects.filter(created_at__gte=stats_start, status__in=failed_statuses)
            .values("failure_category")
            .annotate(count=Count("id"))
        )
        step_failure_categories = list(
            ScenarioStepResult.objects.filter(created_at__gte=stats_start, status__in=failed_statuses)
            .values("failure_category")
            .annotate(count=Count("id"))
        )
        category_map = {}
        for item in [*failure_categories, *step_failure_categories]:
            key = item.get("failure_category") or "-"
            category_map[key] = category_map.get(key, 0) + int(item.get("count") or 0)
        failure_categories = [
            {"failure_category": key, "count": value}
            for key, value in sorted(category_map.items(), key=lambda kv: kv[1], reverse=True)
        ][:10]

        # 近 7 天最慢接口 Top（仅统计接口用例；场景步骤会在任务详情页单独分析）
        slow_interfaces = list(
            TestResult.objects.filter(created_at__gte=stats_start, case__isnull=False)
            .values("case__api__method", "case__api__path", "case__api__name")
            .annotate(avg_duration_ms=Avg("duration_ms"), max_duration_ms=Max("duration_ms"), total=Count("id"))
            .order_by("-avg_duration_ms")[:5]
        )
        flaky_cases = list(
            TestResult.objects.filter(created_at__gte=now - timedelta(days=30), case__isnull=False)
            .values("case_code", "title")
            .annotate(
                total_count=Count("id"),
                failed_count=Count("id", filter=Q(status__in=failed_statuses)),
            )
            .filter(total_count__gte=2, failed_count__gt=0)
            .order_by("-failed_count", "-total_count")[:5]
        )
        for item in flaky_cases:
            item["failure_rate"] = round(item["failed_count"] / item["total_count"] * 100, 1)

        coverage = []
        for module in Module.objects.all().order_by("project_id", "sort_order", "id")[:20]:
            api_count = module.apis.count()
            covered_api_count = module.apis.filter(cases__isnull=False).distinct().count()
            coverage.append(
                {
                    "project": module.project.name,
                    "module": module.name,
                    "api_count": api_count,
                    "covered_api_count": covered_api_count,
                    "coverage_rate": round(covered_api_count / api_count * 100, 1) if api_count else 0,
                }
            )

        enabled_schedules = Schedule.objects.filter(enabled=True)
        environments = Environment.objects.all()
        no_assertion_cases = ApiCase.objects.filter(expect={}).count() + ScenarioStep.objects.filter(expect={}).count()
        duplicate_interfaces = (
            ApiDefinition.objects.values("module__project_id", "path", "method")
            .annotate(total=Count("id"))
            .filter(total__gt=1)
            .count()
        )
        unexecuted_cases = ApiCase.objects.filter(testresult__isnull=True).count()
        long_failed_cases = (
            TestResult.objects.filter(status__in=failed_statuses, created_at__gte=now - timedelta(days=14))
            .values("case_id")
            .annotate(failed_count=Count("id"))
            .filter(failed_count__gte=3)
            .count()
        )

        return Response(
            {
                "metrics": {
                    "projects": Project.objects.count(),
                    "apis": ApiDefinition.objects.count(),
                    "cases": ApiCase.objects.count(),
                    "scenarios": ScenarioCase.objects.count(),
                    "plans": TestPlan.objects.count(),
                    "tasks": TestTask.objects.count(),
                    "today_pass_rate": task_pass_rate(today_tasks),
                    "week_pass_rate": task_pass_rate(week_tasks),
                    "today_tasks": today_tasks.count(),
                    "week_tasks": week_tasks.count(),
                    "failed_tasks_week": week_tasks.filter(status=TestTask.Status.FAILED).count(),
                },
                "trend": trend,
                "failed_modules": failed_modules,
                "failed_interfaces": failed_interfaces,
                "failure_categories": failure_categories,
                "slow_interfaces": slow_interfaces,
                "flaky_cases": flaky_cases,
                "schedule_health": {
                    "enabled": enabled_schedules.count(),
                    "overdue": enabled_schedules.filter(next_run_at__lt=now).count(),
                    "disabled": Schedule.objects.filter(enabled=False).count(),
                },
                "environment_health": {
                    "total": environments.count(),
                    "configured": environments.exclude(base_url="").count(),
                    "missing_base_url": environments.filter(base_url="").count(),
                },
                "governance": {
                    "no_assertion_cases": no_assertion_cases,
                    "unexecuted_cases": unexecuted_cases,
                    "long_failed_cases": long_failed_cases,
                    "duplicate_interfaces": duplicate_interfaces,
                    "no_module_scenarios": ScenarioCase.objects.filter(module__isnull=True).count(),
                },
                "coverage": coverage,
            }
        )


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all().order_by("-id")
    serializer_class = ProjectSerializer


class EnvironmentViewSet(viewsets.ModelViewSet):
    queryset = Environment.objects.select_related("project").all().order_by("-id")
    serializer_class = EnvironmentSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        project = self.request.query_params.get("project")
        return qs.filter(project_id=project) if project else qs


class ProjectVariableViewSet(viewsets.ModelViewSet):
    queryset = ProjectVariable.objects.select_related("project").all()
    serializer_class = ProjectVariableSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        project = self.request.query_params.get("project")
        return qs.filter(project_id=project) if project else qs


class EnvironmentVariableViewSet(viewsets.ModelViewSet):
    queryset = EnvironmentVariable.objects.select_related("environment", "environment__project").all()
    serializer_class = EnvironmentVariableSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        environment = self.request.query_params.get("environment")
        project = self.request.query_params.get("project")
        if environment:
            qs = qs.filter(environment_id=environment)
        if project:
            qs = qs.filter(environment__project_id=project)
        return qs


class EnvironmentCookieViewSet(viewsets.ModelViewSet):
    queryset = EnvironmentCookie.objects.select_related("environment", "environment__project").all()
    serializer_class = EnvironmentCookieSerializer

    def _deprecated(self):
        return Response(
            {
                "detail": "环境级 Cookie 持久化能力已弃用：当前版本 Cookie 仅在单次任务内存中维护（多账号会话隔离）。"
            },
            status=status.HTTP_410_GONE,
        )

    def list(self, request, *args, **kwargs):
        return self._deprecated()

    def retrieve(self, request, *args, **kwargs):
        return self._deprecated()

    def create(self, request, *args, **kwargs):
        return self._deprecated()

    def update(self, request, *args, **kwargs):
        return self._deprecated()

    def partial_update(self, request, *args, **kwargs):
        return self._deprecated()

    def destroy(self, request, *args, **kwargs):
        return self._deprecated()

    def get_queryset(self):
        qs = super().get_queryset()
        environment = self.request.query_params.get("environment")
        project = self.request.query_params.get("project")
        domain = self.request.query_params.get("domain")
        if environment:
            qs = qs.filter(environment_id=environment)
        if project:
            qs = qs.filter(environment__project_id=project)
        if domain:
            qs = qs.filter(domain__icontains=domain)
        return qs

    @action(detail=False, methods=["post"])
    def clear(self, request):
        return self._deprecated()


class ModuleViewSet(viewsets.ModelViewSet):
    queryset = Module.objects.select_related("project").all()
    serializer_class = ModuleSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        project = self.request.query_params.get("project")
        return qs.filter(project_id=project) if project else qs

class ApiDefinitionViewSet(viewsets.ModelViewSet):
    queryset = ApiDefinition.objects.select_related("module", "module__project").all()
    serializer_class = ApiDefinitionSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        project = self.request.query_params.get("project")
        module = self.request.query_params.get("module")
        keyword = self.request.query_params.get("keyword")
        if project:
            qs = qs.filter(module__project_id=project)
        if module:
            qs = qs.filter(module_id=module)
        if keyword:
            qs = qs.filter(Q(name__icontains=keyword) | Q(path__icontains=keyword))
        return qs

    @action(detail=False, methods=["post"])
    def debug(self, request):
        data = request.data
        method = data.get("method", "GET").upper()
        path = data.get("path", "")
        headers = data.get("headers", {})
        payload = data.get("payload", None)
        env_id = data.get("environment_id")

        # -----------------------------
        # 变量解析（支持 ${变量}）
        #
        # 背景：
        # - 平台的接口/用例/场景执行支持在 URL、Header、Payload 中使用 ${变量} 引用
        # - 变量来源：项目变量(ProjectVariable) + 环境变量(EnvironmentVariable)
        # - 调试接口（debug）也应与执行引擎保持一致，否则会出现：
        #   `https://b.geekbang.org/${account}/...` 这种“未展开变量”的错误 URL
        # -----------------------------
        pool = DbVariablePool()
        env = None
        if env_id:
            try:
                env = Environment.objects.select_related("project").get(id=env_id)
            except Environment.DoesNotExist:
                env = None
        if env:
            pool.load_mapping({item.key: item.value for item in env.project.variables.filter(enabled=True)})
            pool.load_mapping({item.key: item.value for item in env.variables.filter(enabled=True)})

        def replace_json(value):
            if value is None:
                return None
            if isinstance(value, (dict, list)):
                raw = json.dumps(value, ensure_ascii=False)
                replaced = pool.replace(raw)
                try:
                    return json.loads(replaced)
                except Exception:
                    return replaced
            if isinstance(value, str):
                return pool.replace(value)
            return value

        # -----------------------------
        # 兼容“用例格式”的调试参数（与 db_runner.py 的 split_request_payload 语义对齐）
        #
        # 目的：
        # - 支持 cURL 导入后携带 __base_url/__query/__body 的调试
        # - 支持 GET 请求使用 query params（否则很多接口看起来“调试不通”）
        # -----------------------------
        resolved_payload = None
        if payload:
            if isinstance(payload, str):
                try:
                    resolved_payload = json.loads(payload)
                except json.JSONDecodeError:
                    resolved_payload = payload
            else:
                resolved_payload = payload

        # 对 payload 做变量替换（支持 query/body 中出现 ${var}）
        resolved_payload = replace_json(resolved_payload)

        query_params = None
        body = resolved_payload
        base_url_override = None
        if isinstance(resolved_payload, dict) and (
            "__query" in resolved_payload or "__body" in resolved_payload or "__base_url" in resolved_payload
        ):
            query_params = resolved_payload.get("__query") or None
            body = resolved_payload.get("__body")
            base_url_override = resolved_payload.get("__base_url") or None
        elif method == "GET" and isinstance(resolved_payload, dict):
            # GET 请求的 payload 若是 dict，默认当作 query params 使用（更符合调试直觉）
            query_params = resolved_payload or None
            body = None

        # path 也支持变量替换（例如 ${host_account}/api/login）
        url = str(replace_json(path) or "").strip()
        if not url.startswith("http://") and not url.startswith("https://"):
            base_url = ""
            # 1) 优先使用 payload 内置 __base_url（通常来自 cURL 导入/跨域调试）
            if base_url_override:
                base_url = str(replace_json(base_url_override) or "").strip()
            # 2) 若未提供 __base_url，则回退使用所选环境的 base_url（同样支持 ${var}）
            if env and not base_url:
                base_url = str(replace_json(env.base_url) or "").strip()
            if base_url:
                url = f"{base_url.rstrip('/')}/{url.lstrip('/')}"

        # headers 支持变量替换（例如 Authorization: Bearer ${token}）
        resolved_headers = {}
        for k, v in (replace_json(headers) or {}).items():
            if v not in ("", None):
                resolved_headers[k] = str(v)

        try:
            start = time.monotonic()
            res = requests.request(
                method,
                url,
                params=replace_json(query_params) if isinstance(query_params, (dict, list)) else query_params,
                json=replace_json(body) if isinstance(body, (dict, list)) else None,
                data=replace_json(body) if not isinstance(body, (dict, list)) else None,
                headers=resolved_headers,
                timeout=10,
                verify=False
            )
            duration = int((time.monotonic() - start) * 1000)
            return Response({
                "status": res.status_code,
                "body": res.text,
                "url": url,
                "query": query_params or {},
                "duration_ms": duration
            })
        except Exception as e:
            return Response({"error": str(e), "url": url}, status=400)

class ApiCaseViewSet(viewsets.ModelViewSet):
    queryset = ApiCase.objects.select_related("api", "api__module", "api__module__project").all()
    serializer_class = ApiCaseSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if params.get("project"):
            qs = qs.filter(api__module__project_id=params["project"])
        if params.get("module"):
            qs = qs.filter(api__module_id=params["module"])
        if params.get("level"):
            qs = qs.filter(level=params["level"])
        if params.get("suite"):
            qs = qs.filter(suite=params["suite"])
        if params.get("tag"):
            qs = qs.filter(tags__icontains=params["tag"])
        if params.get("keyword"):
            keyword = params["keyword"]
            qs = qs.filter(
                Q(case_code__icontains=keyword)
                | Q(title__icontains=keyword)
                | Q(subtitle__icontains=keyword)
                | Q(api__path__icontains=keyword)
            )
        if params.get("is_setup") in ("true", "false"):
            qs = qs.filter(is_setup=params["is_setup"] == "true")
        return qs


class ScenarioCaseViewSet(viewsets.ModelViewSet):
    queryset = ScenarioCase.objects.select_related("project", "module").prefetch_related("steps").all()
    serializer_class = ScenarioCaseSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        project = self.request.query_params.get("project")
        module = self.request.query_params.get("module")
        keyword = self.request.query_params.get("keyword")
        if project:
            qs = qs.filter(project_id=project)
        if module:
            qs = qs.filter(module_id=module)
        if keyword:
            qs = qs.filter(Q(name__icontains=keyword) | Q(description__icontains=keyword))
        return qs


class ScenarioStepViewSet(viewsets.ModelViewSet):
    queryset = ScenarioStep.objects.select_related("scenario", "api").prefetch_related("dependencies").all()
    serializer_class = ScenarioStepSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        scenario = self.request.query_params.get("scenario")
        project = self.request.query_params.get("project")
        if scenario:
            qs = qs.filter(scenario_id=scenario)
        if project:
            qs = qs.filter(scenario__project_id=project)
        return qs


class ExcelImportView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        upload = request.FILES.get("file")
        if not upload:
            return Response({"detail": "请上传 file"}, status=status.HTTP_400_BAD_REQUEST)
        project_name = request.data.get("project_name") or upload.name.rsplit(".", 1)[0]
        module_name = request.data.get("module_name") or project_name
        environment_name = request.data.get("environment_name") or "测试环境(dev)"
        base_url = request.data.get("base_url") or ""
        result = ExcelImportService().import_file(
            file_obj=upload,
            project_name=project_name,
            module_name=module_name,
            environment_name=environment_name,
            base_url=base_url,
        )
        return Response(result)


class CurlImportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        module_id = request.data.get("module")
        curl_text = request.data.get("curl_text")
        name = request.data.get("name") or ""
        case_title = request.data.get("case_title") or ""
        case_code = request.data.get("case_code") or ""
        dry_run = str(request.data.get("dry_run", "")).lower() in {"1", "true", "yes"}
        if not module_id:
            return Response({"detail": "请选择目标模块"}, status=status.HTTP_400_BAD_REQUEST)
        if not curl_text:
            return Response({"detail": "请粘贴 cURL 内容"}, status=status.HTTP_400_BAD_REQUEST)
        service = CurlImportService()
        try:
            result = (
                service.preview(
                    module_id=module_id,
                    curl_text=curl_text,
                    name=name,
                    case_title=case_title,
                    case_code=case_code,
                )
                if dry_run
                else service.import_curl(
                    module_id=module_id,
                    curl_text=curl_text,
                    name=name,
                    case_title=case_title,
                    case_code=case_code,
                )
            )
        except CurlImportError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)


class TestPlanViewSet(viewsets.ModelViewSet):
    queryset = TestPlan.objects.select_related("project", "environment", "created_by").prefetch_related(
        "modules", "api_definitions", "cases", "scenarios"
    )
    serializer_class = TestPlanSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("project"):
            qs = qs.filter(project_id=self.request.query_params["project"])
        if self.request.query_params.get("keyword"):
            qs = qs.filter(name__icontains=self.request.query_params["keyword"])
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        """
        删除测试计划：
        - 若存在执行中的任务（RUNNING/PENDING），禁止删除，避免执行引擎/异步任务引用已删除 plan。
        - 允许删除已结束计划；其关联的 tasks/results/events/schedules 将按模型级联删除（on_delete=CASCADE）。
        """
        plan = self.get_object()
        running = plan.tasks.filter(status__in=[TestTask.Status.PENDING, TestTask.Status.RUNNING]).exists()
        if running:
            return Response({"detail": "计划存在执行中的任务，请先取消任务后再删除"}, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["get"])
    def cases(self, request, pk=None):
        plan = self.get_object()
        return Response(
            {
                "cases": ApiCaseSerializer(resolve_plan_cases(plan), many=True).data,
                "scenarios": ScenarioCaseSerializer(resolve_plan_scenarios(plan), many=True).data,
            }
        )

    @action(detail=False, methods=["post"])
    def preview(self, request):
        try:
            cases, scenarios = preview_plan_scope(request.data)
        except ValueError as exc:
            return Response({"scenario_ids": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        estimated_duration_ms = sum(case.estimated_duration_ms or 1000 for case in cases)
        estimated_duration_ms += sum(scenario.steps.filter(enabled=True).count() * 1000 for scenario in scenarios)
        return Response(
            {
                "cases_count": len(cases),
                "scenarios_count": len(scenarios),
                "estimated_duration_ms": estimated_duration_ms,
                "cases": ApiCaseSerializer(cases[:100], many=True).data,
                "scenarios": ScenarioCaseSerializer(scenarios[:100], many=True).data,
            }
        )


class TestTaskViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = TestTask.objects.select_related("plan", "plan__project", "plan__environment").all()

    def get_serializer_class(self):
        return CreateTestTaskSerializer if self.action == "create" else TestTaskSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("status"):
            qs = qs.filter(status=self.request.query_params["status"])
        if self.request.query_params.get("project"):
            qs = qs.filter(plan__project_id=self.request.query_params["project"])
        if self.request.query_params.get("plan"):
            qs = qs.filter(plan_id=self.request.query_params["plan"])
        if self.request.query_params.get("keyword"):
            qs = qs.filter(plan__name__icontains=self.request.query_params["keyword"])
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = TestTask.objects.create(
            plan=serializer.validated_data["plan"],
            log="任务已创建，等待异步投递",
        )
        enqueue_test_task_async(task.id)
        return Response(TestTaskSerializer(task).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        task = self.get_object()
        # 允许删除 PENDING：Celery 尚未抢占执行时，删除可直接阻止任务开始（run_test_task 会 updated=0 后退出）
        # 禁止删除 RUNNING：避免执行过程中写库/写报告时引用已删除 task 导致异常
        if task.status == TestTask.Status.RUNNING:
            return Response({"detail": "执行中任务不能删除，请先取消"}, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        task = self.get_object()
        if task.status in [TestTask.Status.PENDING, TestTask.Status.RUNNING]:
            task.status = TestTask.Status.CANCELED
            task.save(update_fields=["status", "updated_at"])
        return Response(TestTaskSerializer(task).data)

    @action(detail=True, methods=["get"])
    def results(self, request, pk=None):
        task = self.get_object()
        if task.plan.scenarios.exists():
            results = TestResult.objects.none()
        else:
            results = TestResult.objects.filter(task=task).select_related("case", "case__api", "case__api__module")
        if request.query_params.get("status"):
            results = results.filter(status=request.query_params["status"])
        if request.query_params.get("failure_category"):
            results = results.filter(failure_category=request.query_params["failure_category"])
        results = results.annotate(
            status_order=Case(
                When(status__in=[TestResult.Status.FAILED, TestResult.Status.ERROR], then=0),
                When(status=TestResult.Status.SKIPPED, then=1),
                default=2,
                output_field=IntegerField(),
            )
        ).order_by("status_order", "id")
        page = self.paginate_queryset(results)
        serializer = TestResultSerializer(page or results, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="step-results")
    def step_results(self, request, pk=None):
        results = ScenarioStepResult.objects.filter(task_id=pk).select_related("scenario", "step", "step__api")
        if request.query_params.get("status"):
            results = results.filter(status=request.query_params["status"])
        if request.query_params.get("failure_category"):
            results = results.filter(failure_category=request.query_params["failure_category"])
        results = results.annotate(
            status_order=Case(
                When(status__in=[TestResult.Status.FAILED, TestResult.Status.ERROR], then=0),
                When(status=TestResult.Status.SKIPPED, then=1),
                default=2,
                output_field=IntegerField(),
            )
        ).order_by("status_order", "id")
        page = self.paginate_queryset(results)
        serializer = ScenarioStepResultSerializer(page or results, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def allure(self, request, pk=None):
        task = self.get_object()
        report_url = getattr(settings, "OMNIQA_REPORT_URL", "/reports/")
        return Response(
            {
                "task": task.id,
                "xml_path": task.report_xml_path,
                "html_path": task.report_html_path,
                "url": f"{report_url}tasks/{task.id}/html/index.html" if task.report_html_path else "",
            }
        )

    @action(detail=True, methods=["get"])
    def events(self, request, pk=None):
        """
        返回任务结构化日志（按时间顺序）
        支持过滤：level/category/object_type
        """
        qs = TaskEvent.objects.filter(task_id=pk)
        if request.query_params.get("level"):
            qs = qs.filter(level=request.query_params["level"])
        if request.query_params.get("category"):
            qs = qs.filter(category=request.query_params["category"])
        if request.query_params.get("object_type"):
            qs = qs.filter(object_type=request.query_params["object_type"])
        page = self.paginate_queryset(qs.order_by("id"))
        serializer = TaskEventSerializer(page or qs, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


class UiPageViewSet(viewsets.ModelViewSet):
    queryset = UiPage.objects.select_related("project", "module").all()
    serializer_class = UiPageSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("project"):
            qs = qs.filter(project_id=self.request.query_params["project"])
        if self.request.query_params.get("module"):
            qs = qs.filter(module_id=self.request.query_params["module"])
        if self.request.query_params.get("keyword"):
            qs = qs.filter(name__icontains=self.request.query_params["keyword"])
        return qs


class UiElementViewSet(viewsets.ModelViewSet):
    queryset = UiElement.objects.select_related("page", "page__project").all()
    serializer_class = UiElementSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        # 注意：DRF 分页默认使用 query param "page"，不能拿来做过滤参数，否则会被分页器消费并报“无效页面”。
        # 这里统一用 page_id 作为过滤参数。
        if self.request.query_params.get("page_id"):
            qs = qs.filter(page_id=self.request.query_params["page_id"])
        return qs


class UiPageMethodViewSet(viewsets.ModelViewSet):
    queryset = UiPageMethod.objects.select_related("page", "page__project").all()
    serializer_class = UiPageMethodSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        # 同上：用 page_id 过滤，避免与分页参数 page 冲突
        if self.request.query_params.get("page_id"):
            qs = qs.filter(page_id=self.request.query_params["page_id"])
        return qs


class UiMethodStepViewSet(viewsets.ModelViewSet):
    queryset = UiMethodStep.objects.select_related("method", "method__page", "element").all()
    serializer_class = UiMethodStepSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("method"):
            qs = qs.filter(method_id=self.request.query_params["method"])
        return qs


class UiDatasetViewSet(viewsets.ModelViewSet):
    queryset = UiDataset.objects.select_related("project").all()
    serializer_class = UiDatasetSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("project"):
            qs = qs.filter(project_id=self.request.query_params["project"])
        if self.request.query_params.get("keyword"):
            qs = qs.filter(name__icontains=self.request.query_params["keyword"])
        return qs


class UiDatasetRowViewSet(viewsets.ModelViewSet):
    queryset = UiDatasetRow.objects.select_related("dataset", "dataset__project").all()
    serializer_class = UiDatasetRowSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("dataset"):
            qs = qs.filter(dataset_id=self.request.query_params["dataset"])
        return qs


class UiScenarioStepViewSet(viewsets.ModelViewSet):
    queryset = UiScenarioStep.objects.select_related("scenario", "method", "method__page").all()
    serializer_class = UiScenarioStepSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("scenario"):
            qs = qs.filter(scenario_id=self.request.query_params["scenario"])
        return qs


class UiRunViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = UiRun.objects.select_related("scenario", "scenario__project", "dataset").all()

    def get_serializer_class(self):
        return CreateUiRunSerializer if self.action == "create" else UiRunSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("project"):
            qs = qs.filter(scenario__project_id=self.request.query_params["project"])
        if self.request.query_params.get("scenario"):
            qs = qs.filter(scenario_id=self.request.query_params["scenario"])
        if self.request.query_params.get("dataset"):
            qs = qs.filter(dataset_id=self.request.query_params["dataset"])
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        scenario = serializer.validated_data["scenario"]
        dataset = serializer.validated_data["dataset"]
        mode = serializer.validated_data.get("mode") or UiTask.Mode.HEADLESS

        run = UiRun.objects.create(
            scenario=scenario,
            dataset=dataset,
            mode=mode,
            created_by=request.user if request.user.is_authenticated else None,
        )
        rows = list(dataset.rows.filter(enabled=True).order_by("id"))
        tasks = []
        for row in rows:
            task = UiTask.objects.create(
                scenario=scenario,
                run=run,
                dataset_row=row,
                mode=mode,
                status=UiTask.Status.PENDING,
            )
            enqueue_ui_task_async(task.id)
            tasks.append(task)
        run.total = len(tasks)
        run.save(update_fields=["total", "updated_at"])
        return Response(UiRunSerializer(run).data, status=status.HTTP_201_CREATED)


class ScheduleViewSet(viewsets.ModelViewSet):
    queryset = Schedule.objects.select_related("plan", "plan__project").all()
    serializer_class = ScheduleSerializer

    def perform_create(self, serializer):
        schedule = serializer.save(created_by=self.request.user)
        schedule.next_run_at = compute_next_run(schedule) if schedule.enabled else None
        schedule.save(update_fields=["next_run_at", "updated_at"])

    def perform_update(self, serializer):
        schedule = serializer.save()
        schedule.next_run_at = compute_next_run(schedule) if schedule.enabled else None
        schedule.save(update_fields=["next_run_at", "updated_at"])

    @action(detail=True, methods=["post"])
    def enable(self, request, pk=None):
        schedule = self.get_object()
        schedule.enabled = True
        schedule.next_run_at = compute_next_run(schedule)
        schedule.save(update_fields=["enabled", "next_run_at", "updated_at"])
        return Response(ScheduleSerializer(schedule).data)

    @action(detail=True, methods=["post"])
    def disable(self, request, pk=None):
        schedule = self.get_object()
        schedule.enabled = False
        schedule.next_run_at = None
        schedule.save(update_fields=["enabled", "next_run_at", "updated_at"])
        return Response(ScheduleSerializer(schedule).data)

    @action(detail=True, methods=["post"], url_path="run-now")
    def run_now(self, request, pk=None):
        schedule = self.get_object()
        task = create_task_from_schedule(schedule)
        enqueue_test_task_async(task.id)
        return Response(TestTaskSerializer(task).data, status=status.HTTP_201_CREATED)


class FrontendCatchAllView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        """
        SPA 入口兜底：
        - 让 Django 在刷新任意前端路由（/api-definitions 等）时返回 dist/index.html
        - 静态资源（/assets/*）应由 urls.py 单独路由到 dist/assets，避免被此处错误返回 index 导致白页
        """
        from django.http import FileResponse, HttpResponse
        from pathlib import Path

        # 防止静态资源请求被兜底为 index.html（会导致浏览器把 HTML 当 JS/CSS 解析，从而白页）
        if request.path.startswith("/assets/"):
            return HttpResponse(status=404)

        frontend_index = Path(getattr(settings, "REPO_ROOT", Path(__file__).resolve().parents[2])) / "frontend" / "dist" / "index.html"

        if frontend_index.exists():
            return FileResponse(open(frontend_index, "rb"), content_type="text/html")
        
        if settings.DEBUG:
            try:
                import requests
                frontend_url = "http://127.0.0.1:5173/index.html"
                response = requests.get(frontend_url)
                return HttpResponse(response.content, content_type=response.headers.get('Content-Type', 'text/html'))
            except Exception:
                pass
        
        return HttpResponse('Frontend not built', status=503)


# -----------------------------
# UI 自动化 API
# -----------------------------


class UiScenarioViewSet(viewsets.ModelViewSet):
    queryset = UiScenario.objects.select_related("project", "module").all()
    serializer_class = UiScenarioSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("project"):
            qs = qs.filter(project_id=self.request.query_params["project"])
        if self.request.query_params.get("module"):
            qs = qs.filter(module_id=self.request.query_params["module"])
        if self.request.query_params.get("keyword"):
            qs = qs.filter(name__icontains=self.request.query_params["keyword"])
        return qs


class UiStepViewSet(viewsets.ModelViewSet):
    queryset = UiStep.objects.select_related("scenario", "scenario__project").all()
    serializer_class = UiStepSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("scenario"):
            qs = qs.filter(scenario_id=self.request.query_params["scenario"])
        return qs


class UiTaskViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = UiTask.objects.select_related("scenario", "scenario__project").all()

    def get_serializer_class(self):
        return CreateUiTaskSerializer if self.action == "create" else UiTaskSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("status"):
            qs = qs.filter(status=self.request.query_params["status"])
        if self.request.query_params.get("project"):
            qs = qs.filter(scenario__project_id=self.request.query_params["project"])
        if self.request.query_params.get("scenario"):
            qs = qs.filter(scenario_id=self.request.query_params["scenario"])
        if self.request.query_params.get("exec_task"):
            qs = qs.filter(exec_task_id=self.request.query_params["exec_task"])
        if self.request.query_params.get("run"):
            qs = qs.filter(run_id=self.request.query_params["run"])
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        scenario = serializer.validated_data["scenario"]
        dataset = serializer.validated_data.get("dataset")
        mode = serializer.validated_data.get("mode") or UiTask.Mode.HEADLESS
        task = UiTask.objects.create(
            scenario=scenario,
            dataset=dataset,
            mode=mode,
            status=UiTask.Status.PENDING,
        )
        enqueue_ui_task_async(task.id)
        return Response(UiTaskSerializer(task).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        task = self.get_object()
        if task.status in [UiTask.Status.PENDING, UiTask.Status.RUNNING]:
            return Response({"detail": "执行中任务不能删除"}, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        task = self.get_object()
        if task.status in [UiTask.Status.PENDING, UiTask.Status.RUNNING]:
            task.status = UiTask.Status.CANCELED
            task.save(update_fields=["status", "updated_at"])
        return Response(UiTaskSerializer(task).data)

    @action(detail=True, methods=["get"])
    def report(self, request, pk=None):
        """
        UI 任务报告（MVP）：返回 trace.zip 的 URL（若存在）。
        """
        trace = UiArtifact.objects.filter(task_id=pk, type=UiArtifact.Type.TRACE).order_by("-id").first()
        return Response(
            {
                "task": int(pk),
                "url": trace.url if trace and trace.url else "",
                "path": trace.path if trace else "",
            }
        )

    @action(detail=True, methods=["get"])
    def results(self, request, pk=None):
        qs = UiStepResult.objects.filter(task_id=pk).order_by("id")
        if request.query_params.get("status"):
            qs = qs.filter(status=request.query_params["status"])
        if request.query_params.get("failure_category"):
            qs = qs.filter(failure_category=request.query_params["failure_category"])
        page = self.paginate_queryset(qs)
        serializer = UiStepResultSerializer(page or qs, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def artifacts(self, request, pk=None):
        qs = UiArtifact.objects.filter(task_id=pk).order_by("id")
        page = self.paginate_queryset(qs)
        serializer = UiArtifactSerializer(page or qs, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def events(self, request, pk=None):
        qs = UiTaskEvent.objects.filter(task_id=pk).order_by("id")
        if request.query_params.get("level"):
            qs = qs.filter(level=request.query_params["level"])
        if request.query_params.get("category"):
            qs = qs.filter(category=request.query_params["category"])
        page = self.paginate_queryset(qs)
        serializer = UiTaskEventSerializer(page or qs, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


class UiPlanViewSet(viewsets.ModelViewSet):
    queryset = UiPlan.objects.select_related("project", "default_dataset").prefetch_related("scenarios").all()

    def get_serializer_class(self):
        return CreateUiPlanSerializer if self.action in {"create", "update", "partial_update"} else UiPlanSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("project"):
            qs = qs.filter(project_id=self.request.query_params["project"])
        if self.request.query_params.get("keyword"):
            qs = qs.filter(name__icontains=self.request.query_params["keyword"])
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user if self.request.user.is_authenticated else None)

    @action(detail=True, methods=["post"], url_path="run")
    def run_plan(self, request, pk=None):
        """
        执行 UI 计划：创建一次 UiExecTask，并按计划中关联的场景生成 UiTask（每场景一个）。
        运行时必须选择 dataset + mode（由前端传入）。
        """
        plan = self.get_object()
        serializer = CreateUiExecTaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dataset = serializer.validated_data["dataset"]
        mode = serializer.validated_data["mode"]

        scenarios = list(plan.scenarios.filter(enabled=True).order_by("id"))
        exec_task = UiExecTask.objects.create(
            plan=plan,
            dataset=dataset,
            mode=mode,
            status=UiExecTask.Status.RUNNING,
            total=len(scenarios),
            started_at=timezone.now(),
            created_by=request.user if request.user.is_authenticated else None,
        )

        for sc in scenarios:
            t = UiTask.objects.create(
                scenario=sc,
                exec_task=exec_task,
                dataset=dataset,
                mode=mode,
                status=UiTask.Status.PENDING,
            )
            enqueue_ui_task_async(t.id)

        return Response(UiExecTaskSerializer(exec_task).data, status=status.HTTP_201_CREATED)


class UiExecTaskViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = UiExecTask.objects.select_related("plan", "plan__project", "dataset").all()
    serializer_class = UiExecTaskSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("status"):
            qs = qs.filter(status=self.request.query_params["status"])
        if self.request.query_params.get("project"):
            qs = qs.filter(plan__project_id=self.request.query_params["project"])
        if self.request.query_params.get("plan"):
            qs = qs.filter(plan_id=self.request.query_params["plan"])
        return qs

    def destroy(self, request, *args, **kwargs):
        exec_task = self.get_object()
        if exec_task.status in [UiExecTask.Status.PENDING, UiExecTask.Status.RUNNING]:
            return Response({"detail": "执行中记录不能删除，请先取消"}, status=status.HTTP_400_BAD_REQUEST)
        # UiTask.exec_task 是 SET_NULL；为了“删除执行记录=清理整条执行链路”，这里主动删除关联 UiTask。
        UiTask.objects.filter(exec_task_id=exec_task.id).delete()
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        exec_task = self.get_object()
        if exec_task.status not in [UiExecTask.Status.PENDING, UiExecTask.Status.RUNNING]:
            return Response(UiExecTaskSerializer(exec_task).data)

        now = timezone.now()
        # 取消尚未结束的子任务
        UiTask.objects.filter(exec_task_id=exec_task.id, status__in=[UiTask.Status.PENDING, UiTask.Status.RUNNING]).update(
            status=UiTask.Status.CANCELED,
            finished_at=now,
            updated_at=now,
        )
        # 聚合回写（尽量保持统计字段可读）
        qs = UiTask.objects.filter(exec_task_id=exec_task.id)
        total = exec_task.total or qs.count()
        passed = qs.filter(status=UiTask.Status.PASSED).count()
        failed = qs.filter(status=UiTask.Status.FAILED).count()
        canceled = qs.filter(status=UiTask.Status.CANCELED).count()
        finished = passed + failed + canceled
        progress = int(finished / total * 100) if total else 100

        exec_task.status = UiExecTask.Status.CANCELED
        exec_task.passed = passed
        exec_task.failed = failed
        exec_task.canceled = canceled
        exec_task.progress = progress
        exec_task.finished_at = now
        exec_task.failure_reason = ""
        exec_task.save(
            update_fields=[
                "status",
                "passed",
                "failed",
                "canceled",
                "progress",
                "finished_at",
                "failure_reason",
                "updated_at",
            ]
        )
        return Response(UiExecTaskSerializer(exec_task).data)
