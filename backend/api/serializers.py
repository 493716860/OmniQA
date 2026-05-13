"""
backend/api/serializers.py

文件用途
-------
REST API 的序列化层（DRF Serializers）。

它的核心职责是把 models.py 的领域对象转换成前端可直接使用的 JSON，并在写入时完成：
- 参数校验（例如：环境必须属于项目、场景范围不能与接口/用例范围混用）
- 多对多关系的读写封装（modules/api_definitions/cases/scenarios/dependencies 等）
- “组合视图字段”补充（module_name、api_path、dependency_codes、steps_count 等）

其中 resolve_plan_cases/resolve_plan_scenarios 非常关键：
- 它们定义了“测试计划的选取规则”，并在多个地方复用：
  - views.py 的计划预览/任务执行
  - db_runner.py 的 selected_cases()/selected_scenarios()

面试讲解抓手
-----------
- 清晰的三层结构：models（数据）→ serializers（规则/格式）→ views（入口/编排）
- serializer.validate(...) 是业务约束的最佳落点：比散落在 views 更可复用、更可测试
"""

import re

from django.contrib.auth import authenticate
from rest_framework import serializers

from .models import (
    ApiCase,
    ApiDefinition,
    EnvironmentCookie,
    EnvironmentVariable,
    Environment,
    Module,
    Project,
    ProjectVariable,
    ScenarioCase,
    ScenarioStep,
    ScenarioStepResult,
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
    Schedule,
    TestPlan,
    TestResult,
    TestTask,
)


_SESSION_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _normalize_session_key(value):
    """
    允许前端传空字符串；统一归一化为 default。
    """
    if value is None:
        return None
    key = str(value).strip()
    return key or "default"


def _validate_session_key(value):
    key = _normalize_session_key(value)
    if key is None:
        return None
    if not _SESSION_KEY_RE.fullmatch(key):
        raise serializers.ValidationError("session_key 仅允许字母/数字/下划线/短横线，长度 1~64")
    return key


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(username=attrs["username"], password=attrs["password"])
        if not user:
            raise serializers.ValidationError("用户名或密码错误")
        attrs["user"] = user
        return attrs


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = "__all__"


class EnvironmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Environment
        fields = "__all__"


class ProjectVariableSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectVariable
        fields = "__all__"


class EnvironmentVariableSerializer(serializers.ModelSerializer):
    project = serializers.IntegerField(source="environment.project_id", read_only=True)

    class Meta:
        model = EnvironmentVariable
        fields = "__all__"


class EnvironmentCookieSerializer(serializers.ModelSerializer):
    project = serializers.IntegerField(source="environment.project_id", read_only=True)
    environment_name = serializers.CharField(source="environment.name", read_only=True)

    class Meta:
        model = EnvironmentCookie
        fields = "__all__"


class ModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = "__all__"


class ApiDefinitionSerializer(serializers.ModelSerializer):
    module_name = serializers.CharField(source="module.name", read_only=True)

    class Meta:
        model = ApiDefinition
        fields = "__all__"


class ApiCaseSerializer(serializers.ModelSerializer):
    api_path = serializers.CharField(source="api.path", read_only=True)
    api_method = serializers.CharField(source="api.method", read_only=True)
    module = serializers.IntegerField(source="api.module_id", read_only=True)
    module_name = serializers.CharField(source="api.module.name", read_only=True)
    dependency_codes = serializers.SerializerMethodField()
    dependency_ids = serializers.PrimaryKeyRelatedField(
        source="dependencies", queryset=ApiCase.objects.all(), many=True, required=False
    )

    class Meta:
        model = ApiCase
        fields = "__all__"

    def get_dependency_codes(self, obj):
        return list(obj.dependencies.values_list("case_code", flat=True))

    def validate(self, attrs):
        # session_key 合法性与归一化（允许空字符串 -> default）
        if "session_key" in attrs:
            attrs["session_key"] = _validate_session_key(attrs.get("session_key"))
        return attrs

    def create(self, validated_data):
        dependencies = validated_data.pop("dependencies", [])
        case = ApiCase.objects.create(**validated_data)
        case.dependencies.set(dependencies)
        return case

    def update(self, instance, validated_data):
        dependencies = validated_data.pop("dependencies", None)
        case = super().update(instance, validated_data)
        if dependencies is not None:
            case.dependencies.set(dependencies)
        return case


class ScenarioStepSerializer(serializers.ModelSerializer):
    api_path = serializers.CharField(source="api.path", read_only=True)
    api_method = serializers.CharField(source="api.method", read_only=True)
    case_id = serializers.PrimaryKeyRelatedField(
        source="case", queryset=ApiCase.objects.all(), required=False, allow_null=True
    )
    case_code = serializers.CharField(source="case.case_code", read_only=True)
    case_title = serializers.CharField(source="case.subtitle", read_only=True)
    dependency_ids = serializers.PrimaryKeyRelatedField(
        source="dependencies", queryset=ScenarioStep.objects.all(), many=True, required=False
    )
    dependency_names = serializers.SerializerMethodField()

    class Meta:
        model = ScenarioStep
        fields = "__all__"

    def get_dependency_names(self, obj):
        return list(obj.dependencies.values_list("name", flat=True))

    def validate(self, attrs):
        if "session_key" in attrs:
            attrs["session_key"] = _validate_session_key(attrs.get("session_key"))

        scenario = attrs.get("scenario") or getattr(self.instance, "scenario", None)
        dependencies = attrs.get("dependencies", [])
        invalid = [step.id for step in dependencies if step.scenario_id != scenario.id]
        if invalid:
            raise serializers.ValidationError({"dependency_ids": f"依赖步骤不属于当前场景: {invalid}"})

        # 引用用例：自动对齐 api，并校验项目归属一致
        case = attrs.get("case", None)
        if case is not None:
            # scenario.project 与 case.api.module.project 必须一致
            if getattr(case.api.module, "project_id", None) != getattr(scenario, "project_id", None):
                raise serializers.ValidationError({"case_id": "引用的用例不属于当前场景所在项目"})
            attrs["api"] = case.api

        return attrs

    def create(self, validated_data):
        dependencies = validated_data.pop("dependencies", [])
        step = ScenarioStep.objects.create(**validated_data)
        step.dependencies.set(dependencies)
        return step

    def update(self, instance, validated_data):
        dependencies = validated_data.pop("dependencies", None)
        step = super().update(instance, validated_data)
        if dependencies is not None:
            step.dependencies.set(dependencies)
        return step


class ScenarioCaseSerializer(serializers.ModelSerializer):
    module_name = serializers.CharField(source="module.name", read_only=True)
    steps = ScenarioStepSerializer(many=True, read_only=True)
    steps_count = serializers.IntegerField(source="steps.count", read_only=True)

    class Meta:
        model = ScenarioCase
        fields = "__all__"


class TestPlanSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(),
        error_messages={"required": "请选择项目", "null": "请选择项目", "does_not_exist": "项目不存在"},
    )
    environment = serializers.PrimaryKeyRelatedField(
        queryset=Environment.objects.all(),
        error_messages={"required": "请选择环境", "null": "请选择环境", "does_not_exist": "环境不存在"},
    )
    module_ids = serializers.PrimaryKeyRelatedField(
        source="modules", queryset=Module.objects.all(), many=True, required=False
    )
    case_ids = serializers.PrimaryKeyRelatedField(
        source="cases", queryset=ApiCase.objects.all(), many=True, required=False
    )
    api_definition_ids = serializers.PrimaryKeyRelatedField(
        source="api_definitions", queryset=ApiDefinition.objects.all(), many=True, required=False
    )
    scenario_ids = serializers.PrimaryKeyRelatedField(
        source="scenarios", queryset=ScenarioCase.objects.all(), many=True, required=False
    )
    project_name = serializers.CharField(source="project.name", read_only=True)
    environment_name = serializers.CharField(source="environment.name", read_only=True)
    modules_count = serializers.IntegerField(source="modules.count", read_only=True)
    cases_count = serializers.SerializerMethodField()
    scenarios_count = serializers.IntegerField(source="scenarios.count", read_only=True)

    class Meta:
        model = TestPlan
        fields = [
            "id",
            "name",
            "project",
            "project_name",
            "environment",
            "environment_name",
            "levels",
            "module_ids",
            "api_definition_ids",
            "case_ids",
            "scenario_ids",
            "tags",
            "suites",
            "modules_count",
            "cases_count",
            "scenarios_count",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_by", "created_at", "updated_at"]

    def validate_levels(self, value):
        if value in (None, ""):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("等级必须是数组")
        invalid_levels = [item for item in value if not isinstance(item, int)]
        if invalid_levels:
            raise serializers.ValidationError("等级必须全部是数字")
        return value

    def get_cases_count(self, obj):
        return resolve_plan_cases(obj).count()

    def validate(self, attrs):
        project = attrs.get("project") or getattr(self.instance, "project", None)
        environment = attrs.get("environment") or getattr(self.instance, "environment", None)

        def relation_values(name):
            if name in attrs:
                return attrs[name]
            if self.instance:
                return list(getattr(self.instance, name).all())
            return []

        modules = relation_values("modules")
        api_definitions = relation_values("api_definitions")
        cases = relation_values("cases")
        scenarios = relation_values("scenarios")

        if project and environment and environment.project_id != project.id:
            raise serializers.ValidationError({"environment": "环境不属于所选项目"})

        if scenarios and (modules or api_definitions or cases):
            raise serializers.ValidationError(
                {"scenario_ids": "场景用例不能和模块、接口、用例范围同时选择"}
            )

        invalid_modules = [module.id for module in modules if module.project_id != project.id]
        if invalid_modules:
            raise serializers.ValidationError({"module_ids": f"模块不属于所选项目: {invalid_modules}"})

        invalid_apis = [api.id for api in api_definitions if api.module.project_id != project.id]
        if invalid_apis:
            raise serializers.ValidationError({"api_definition_ids": f"接口不属于所选项目: {invalid_apis}"})

        invalid_cases = [
            case.id for case in cases if case.api and case.api.module.project_id != project.id
        ]
        if invalid_cases:
            raise serializers.ValidationError({"case_ids": f"用例不属于所选项目: {invalid_cases}"})

        invalid_scenarios = [scenario.id for scenario in scenarios if scenario.project_id != project.id]
        if invalid_scenarios:
            raise serializers.ValidationError({"scenario_ids": f"场景不属于所选项目: {invalid_scenarios}"})

        return attrs

    def create(self, validated_data):
        modules = validated_data.pop("modules", [])
        api_definitions = validated_data.pop("api_definitions", [])
        cases = validated_data.pop("cases", [])
        scenarios = validated_data.pop("scenarios", [])
        plan = TestPlan.objects.create(**validated_data)
        plan.modules.set(modules)
        plan.api_definitions.set(api_definitions)
        plan.cases.set(cases)
        plan.scenarios.set(scenarios)
        return plan

    def update(self, instance, validated_data):
        modules = validated_data.pop("modules", None)
        api_definitions = validated_data.pop("api_definitions", None)
        cases = validated_data.pop("cases", None)
        scenarios = validated_data.pop("scenarios", None)
        plan = super().update(instance, validated_data)
        if modules is not None:
            plan.modules.set(modules)
        if api_definitions is not None:
            plan.api_definitions.set(api_definitions)
        if cases is not None:
            plan.cases.set(cases)
        if scenarios is not None:
            plan.scenarios.set(scenarios)
        return plan


class TestTaskSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    project_name = serializers.CharField(source="plan.project.name", read_only=True)
    environment_name = serializers.CharField(source="plan.environment.name", read_only=True)
    status = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()
    total_count = serializers.SerializerMethodField()
    passed_count = serializers.SerializerMethodField()
    failed_count = serializers.SerializerMethodField()
    skipped_count = serializers.SerializerMethodField()

    class Meta:
        model = TestTask
        fields = "__all__"

    def is_scenario_plan(self, obj):
        return obj.plan.scenarios.exists()

    def scenario_total_count(self, obj):
        return sum(
            scenario.steps.filter(enabled=True).count()
            for scenario in resolve_plan_scenarios(obj.plan)
        )

    def scenario_counts(self, obj):
        results = obj.step_results.all()
        failed = results.filter(status__in=[TestResult.Status.FAILED, TestResult.Status.ERROR]).count()
        passed = results.filter(status=TestResult.Status.PASSED).count()
        skipped = results.filter(status=TestResult.Status.SKIPPED).count()
        return passed, failed, skipped

    def get_total_count(self, obj):
        return self.scenario_total_count(obj) if self.is_scenario_plan(obj) else obj.total_count

    def get_passed_count(self, obj):
        return self.scenario_counts(obj)[0] if self.is_scenario_plan(obj) else obj.passed_count

    def get_failed_count(self, obj):
        return self.scenario_counts(obj)[1] if self.is_scenario_plan(obj) else obj.failed_count

    def get_skipped_count(self, obj):
        return self.scenario_counts(obj)[2] if self.is_scenario_plan(obj) else obj.skipped_count

    def get_progress(self, obj):
        if not self.is_scenario_plan(obj):
            return obj.progress
        total = self.scenario_total_count(obj)
        if not total:
            return obj.progress
        done = sum(self.scenario_counts(obj))
        if obj.status in [TestTask.Status.PASSED, TestTask.Status.FAILED, TestTask.Status.CANCELED] and done >= total:
            return 100
        return min(100, int(done / total * 100))

    def get_status(self, obj):
        if (
            not self.is_scenario_plan(obj)
            or obj.status in [TestTask.Status.PENDING, TestTask.Status.RUNNING, TestTask.Status.CANCELED]
        ):
            return obj.status
        total = self.scenario_total_count(obj)
        passed, failed, skipped = self.scenario_counts(obj)
        if total and passed + failed + skipped >= total:
            return TestTask.Status.FAILED if failed else TestTask.Status.PASSED
        return obj.status


class TaskEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskEvent
        fields = "__all__"


class UiScenarioSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    module_name = serializers.CharField(source="module.name", read_only=True)
    steps_count = serializers.IntegerField(source="steps.count", read_only=True)

    class Meta:
        model = UiScenario
        fields = "__all__"


class UiPageSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    module_name = serializers.CharField(source="module.name", read_only=True)
    elements_count = serializers.IntegerField(source="elements.count", read_only=True)
    methods_count = serializers.IntegerField(source="methods.count", read_only=True)

    class Meta:
        model = UiPage
        fields = "__all__"


class UiElementSerializer(serializers.ModelSerializer):
    page_name = serializers.CharField(source="page.name", read_only=True)

    class Meta:
        model = UiElement
        fields = "__all__"


class UiPageMethodSerializer(serializers.ModelSerializer):
    page_name = serializers.CharField(source="page.name", read_only=True)
    steps_count = serializers.IntegerField(source="steps.count", read_only=True)

    class Meta:
        model = UiPageMethod
        fields = "__all__"


class UiMethodStepSerializer(serializers.ModelSerializer):
    element_name = serializers.CharField(source="element.name", read_only=True)

    class Meta:
        model = UiMethodStep
        fields = "__all__"


class UiDatasetSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    rows_count = serializers.IntegerField(source="rows.count", read_only=True)

    class Meta:
        model = UiDataset
        fields = "__all__"


class UiDatasetRowSerializer(serializers.ModelSerializer):
    dataset_name = serializers.CharField(source="dataset.name", read_only=True)

    class Meta:
        model = UiDatasetRow
        fields = "__all__"


class UiScenarioStepSerializer(serializers.ModelSerializer):
    method_name = serializers.CharField(source="method.name", read_only=True)
    page_name = serializers.CharField(source="method.page.name", read_only=True)

    class Meta:
        model = UiScenarioStep
        fields = "__all__"


class UiRunSerializer(serializers.ModelSerializer):
    scenario_name = serializers.CharField(source="scenario.name", read_only=True)
    dataset_name = serializers.CharField(source="dataset.name", read_only=True)
    project = serializers.IntegerField(source="scenario.project_id", read_only=True)
    project_name = serializers.CharField(source="scenario.project.name", read_only=True)

    class Meta:
        model = UiRun
        fields = "__all__"


class CreateUiRunSerializer(serializers.Serializer):
    scenario = serializers.PrimaryKeyRelatedField(queryset=UiScenario.objects.all())
    dataset = serializers.PrimaryKeyRelatedField(queryset=UiDataset.objects.all())
    mode = serializers.ChoiceField(choices=UiTask.Mode.choices, default=UiTask.Mode.HEADLESS)


class UiStepSerializer(serializers.ModelSerializer):
    dependency_ids = serializers.PrimaryKeyRelatedField(
        source="dependencies", queryset=UiStep.objects.all(), many=True, required=False
    )
    dependency_names = serializers.SerializerMethodField()

    class Meta:
        model = UiStep
        fields = "__all__"

    def get_dependency_names(self, obj):
        return list(obj.dependencies.values_list("name", flat=True))

    def validate(self, attrs):
        scenario = attrs.get("scenario") or getattr(self.instance, "scenario", None)
        dependencies = attrs.get("dependencies", [])
        invalid = [step.id for step in dependencies if step.scenario_id != scenario.id]
        if invalid:
            raise serializers.ValidationError({"dependency_ids": f"依赖步骤不属于当前场景: {invalid}"})
        return attrs

    def create(self, validated_data):
        dependencies = validated_data.pop("dependencies", [])
        step = UiStep.objects.create(**validated_data)
        step.dependencies.set(dependencies)
        return step

    def update(self, instance, validated_data):
        dependencies = validated_data.pop("dependencies", None)
        step = super().update(instance, validated_data)
        if dependencies is not None:
            step.dependencies.set(dependencies)
        return step


class UiTaskSerializer(serializers.ModelSerializer):
    scenario_name = serializers.CharField(source="scenario.name", read_only=True)
    project = serializers.IntegerField(source="scenario.project_id", read_only=True)
    project_name = serializers.CharField(source="scenario.project.name", read_only=True)
    exec_task_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = UiTask
        fields = "__all__"


class CreateUiTaskSerializer(serializers.Serializer):
    scenario = serializers.PrimaryKeyRelatedField(queryset=UiScenario.objects.all())
    dataset = serializers.PrimaryKeyRelatedField(queryset=UiDataset.objects.all(), required=False, allow_null=True)
    mode = serializers.ChoiceField(choices=UiTask.Mode.choices, default=UiTask.Mode.HEADLESS)


class UiPlanSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    scenario_ids = serializers.PrimaryKeyRelatedField(source="scenarios", many=True, read_only=True)
    scenarios_count = serializers.IntegerField(source="scenarios.count", read_only=True)
    default_dataset_name = serializers.CharField(source="default_dataset.name", read_only=True)

    class Meta:
        model = UiPlan
        fields = "__all__"


class CreateUiPlanSerializer(serializers.ModelSerializer):
    scenario_ids = serializers.PrimaryKeyRelatedField(source="scenarios", queryset=UiScenario.objects.all(), many=True, required=False)

    class Meta:
        model = UiPlan
        fields = [
            "id",
            "name",
            "project",
            "scenario_ids",
            "default_dataset",
            "default_mode",
            "enabled",
        ]

    def validate(self, attrs):
        project = attrs.get("project") or getattr(self.instance, "project", None)
        scenarios = attrs.get("scenarios") or []
        invalid = [s.id for s in scenarios if s.project_id != project.id]
        if invalid:
            raise serializers.ValidationError({"scenario_ids": f"场景不属于当前项目: {invalid}"})
        return attrs

    def create(self, validated_data):
        scenarios = validated_data.pop("scenarios", [])
        plan = UiPlan.objects.create(**validated_data)
        if scenarios:
            plan.scenarios.set(scenarios)
        return plan

    def update(self, instance, validated_data):
        scenarios = validated_data.pop("scenarios", None)
        plan = super().update(instance, validated_data)
        if scenarios is not None:
            plan.scenarios.set(scenarios)
        return plan


class CreateUiExecTaskSerializer(serializers.Serializer):
    dataset = serializers.PrimaryKeyRelatedField(queryset=UiDataset.objects.all())
    mode = serializers.ChoiceField(choices=UiTask.Mode.choices)


class UiExecTaskSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    project = serializers.IntegerField(source="plan.project_id", read_only=True)
    project_name = serializers.CharField(source="plan.project.name", read_only=True)
    dataset_name = serializers.CharField(source="dataset.name", read_only=True)

    class Meta:
        model = UiExecTask
        fields = "__all__"


class UiStepResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = UiStepResult
        fields = "__all__"


class UiArtifactSerializer(serializers.ModelSerializer):
    class Meta:
        model = UiArtifact
        fields = "__all__"


class UiTaskEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = UiTaskEvent
        fields = "__all__"


class CreateTestTaskSerializer(serializers.Serializer):
    plan = serializers.PrimaryKeyRelatedField(queryset=TestPlan.objects.all())


class TestResultSerializer(serializers.ModelSerializer):
    api_path = serializers.CharField(source="case.api.path", read_only=True)
    api_method = serializers.CharField(source="case.api.method", read_only=True)
    module_name = serializers.CharField(source="case.api.module.name", read_only=True)

    class Meta:
        model = TestResult
        fields = "__all__"


class ScenarioStepResultSerializer(serializers.ModelSerializer):
    api_path = serializers.CharField(source="step.api.path", read_only=True)
    api_method = serializers.CharField(source="step.api.method", read_only=True)

    class Meta:
        model = ScenarioStepResult
        fields = "__all__"


class ScheduleSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    project = serializers.IntegerField(source="plan.project_id", read_only=True)

    class Meta:
        model = Schedule
        fields = "__all__"
        read_only_fields = ["next_run_at", "last_run_at", "created_by"]


def resolve_plan_cases(plan):
    if plan.scenarios.exists():
        return ApiCase.objects.none()
    queryset = ApiCase.objects.filter(api__module__project=plan.project, enabled=True, is_setup=False)
    if plan.cases.exists():
        queryset = queryset.filter(id__in=plan.cases.values("id"))
    elif plan.api_definitions.exists():
        queryset = queryset.filter(api__in=plan.api_definitions.all())
    elif plan.modules.exists():
        queryset = queryset.filter(api__module__in=plan.modules.all())
    if plan.levels:
        queryset = queryset.filter(level__in=plan.levels)
    if plan.tags:
        for tag in plan.tags:
            queryset = queryset.filter(tags__icontains=tag)
    if plan.suites:
        queryset = queryset.filter(suite__in=plan.suites)
    return queryset.select_related("api", "api__module").prefetch_related("dependencies").order_by(
        "sort_order", "id"
    )


def resolve_plan_scenarios(plan):
    if plan.scenarios.exists():
        queryset = ScenarioCase.objects.filter(
            project=plan.project, enabled=True, id__in=plan.scenarios.values("id")
        )
    elif plan.modules.exists():
        queryset = ScenarioCase.objects.filter(project=plan.project, enabled=True, module__in=plan.modules.all())
    else:
        queryset = ScenarioCase.objects.none()
    if plan.levels:
        queryset = queryset.filter(level__in=plan.levels)
    return queryset.select_related("module").prefetch_related("steps", "steps__dependencies").order_by(
        "sort_order", "id"
    )
