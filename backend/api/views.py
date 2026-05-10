from django.contrib.auth import login, logout
from django.conf import settings
from django.db.models import Avg, Case, Count, IntegerField, Q, When
from django.utils import timezone
from datetime import timedelta
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from threading import Thread

from .models import ApiCase, ApiDefinition, Environment, Module, Project, TestPlan, TestResult, TestTask
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
    TestPlanSerializer,
    TestResultSerializer,
    TestTaskSerializer,
    resolve_plan_cases,
    resolve_plan_scenarios,
)
from .services.importer import ExcelImportService
from .services.scheduler import compute_next_run, create_task_from_schedule
from .tasks import run_test_task


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
        environment = request.data.get("environment")
        domain = request.data.get("domain")
        qs = self.get_queryset()
        if environment:
            qs = qs.filter(environment_id=environment)
        if domain:
            qs = qs.filter(domain=domain)
        deleted, _ = qs.delete()
        return Response({"deleted": deleted})


class ModuleViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
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
        if task.status in [TestTask.Status.PENDING, TestTask.Status.RUNNING]:
            return Response({"detail": "执行中任务不能删除"}, status=status.HTTP_400_BAD_REQUEST)
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
        return Response(
            {
                "task": task.id,
                "xml_path": task.report_xml_path,
                "html_path": task.report_html_path,
                "url": f"{settings.NEXUS_REPORT_URL}tasks/{task.id}/html/index.html" if task.report_html_path else "",
            }
        )


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
