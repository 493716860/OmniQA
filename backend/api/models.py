"""
backend/api/models.py

文件用途
-------
平台核心领域模型（Django ORM）。

这是整个系统的“数据骨架”，前端看到的大部分业务对象（项目、环境、用例、计划、任务、报告、UI 自动化等）
都由这里定义。其它模块的角色大致如下：

- serializers.py：把这些模型转换为 REST API 的输入/输出格式，并封装部分组合查询逻辑
- views.py：对外提供 CRUD / 业务动作（创建任务、预览范围、查看结果等）
- services/importer.py：把 Excel/cURL 等外部输入落库成这些模型
- services/db_runner.py：读取这些模型并执行，写回 TestResult/TaskEvent/报告
- services/scheduler.py：围绕 Schedule 计算 next_run_at、创建 TestTask

模型分层（面试讲解抓手）
-----------------------
1) 基础配置层：
   - Project：项目（用例与环境的顶层归属）
   - Environment：环境（base_url、默认 headers、SSL 校验、超时等）
   - ProjectVariable / EnvironmentVariable：变量（用于 ${var} 替换）
   - EnvironmentCookie：环境维度 Cookie（用于保持登录态/跨请求状态）
2) 用例资产层：
   - Module：模块（项目下的业务域分组）
   - ApiDefinition：接口定义（path/method/default_headers）
   - ApiCase：接口用例（header/payload/expect/extractors/rely/dependencies）
   - ScenarioCase / ScenarioStep：场景用例与步骤（步骤级依赖、变量提取、断言）
3) 执行与结果层：
   - TestPlan：计划（选择范围：模块/接口/用例/场景 + level/tags/suites 过滤）
   - TestTask：一次执行任务（进度、当前用例/步骤、报告路径等）
   - TestResult / ScenarioStepResult：执行结果（请求/响应、耗时、失败分类）
   - TaskEvent：结构化事件流（时间线/看板统计）
4) 定时层：
   - Schedule：计划的周期性触发（简单周期/cron、next_run_at/last_run_at）
5) UI 自动化（Playwright）层：
   - UiPage/UiElement/UiPageMethod/UiMethodStep：PO（页面对象）与可复用步骤
   - UiScenario/UiScenarioStep：可执行 UI 场景
   - UiDataset/UiDatasetRow：DDT 数据集（${field} 引用）
   - UiRun/UiTask/UiStep/UiStepResult/UiArtifact/UiTaskEvent：执行、结果与工件（trace/截图）
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Project(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Environment(TimeStampedModel):
    project = models.ForeignKey(Project, related_name="environments", on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    base_url = models.URLField(blank=True)
    headers = models.JSONField(default=dict, blank=True)
    verify_ssl = models.BooleanField(default=False)
    timeout_seconds = models.PositiveIntegerField(default=getattr(settings, "OMNIQA_REQUEST_TIMEOUT", 10))

    class Meta:
        unique_together = ("project", "name")

    def __str__(self):
        return f"{self.project} / {self.name}"


class ProjectVariable(TimeStampedModel):
    project = models.ForeignKey(Project, related_name="variables", on_delete=models.CASCADE)
    key = models.CharField(max_length=120)
    value = models.TextField(blank=True)
    description = models.CharField(max_length=300, blank=True)
    enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = ("project", "key")
        ordering = ["key"]

    def __str__(self):
        return f"{self.project} / {self.key}"


class EnvironmentVariable(TimeStampedModel):
    environment = models.ForeignKey(Environment, related_name="variables", on_delete=models.CASCADE)
    key = models.CharField(max_length=120)
    value = models.TextField(blank=True)
    description = models.CharField(max_length=300, blank=True)
    enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = ("environment", "key")
        ordering = ["key"]

    def __str__(self):
        return f"{self.environment} / {self.key}"


class EnvironmentCookie(TimeStampedModel):
    environment = models.ForeignKey(Environment, related_name="cookies", on_delete=models.CASCADE)
    domain = models.CharField(max_length=255)
    path = models.CharField(max_length=255, default="/")
    name = models.CharField(max_length=255)
    value = models.TextField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    secure = models.BooleanField(default=False)
    http_only = models.BooleanField(default=False)
    enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = ("environment", "domain", "path", "name")
        ordering = ["domain", "path", "name"]

    def __str__(self):
        return f"{self.environment} / {self.domain}{self.path} / {self.name}"


class Module(TimeStampedModel):
    project = models.ForeignKey(Project, related_name="modules", on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("project", "name")
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name


class ApiDefinition(TimeStampedModel):
    module = models.ForeignKey(Module, related_name="apis", on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    path = models.CharField(max_length=500)
    method = models.CharField(max_length=16)
    default_headers = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ("module", "path", "method")
        ordering = ["module_id", "id"]

    def __str__(self):
        return f"{self.method} {self.path}"


class ApiCase(TimeStampedModel):
    api = models.ForeignKey(ApiDefinition, related_name="cases", on_delete=models.CASCADE)
    case_code = models.CharField(max_length=80)
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=200, blank=True)
    session_key = models.CharField(
        max_length=64,
        default="default",
        blank=True,
        help_text="同一 session_key 的用例共享 Cookie 与运行时变量；不同 session_key 相互隔离。",
    )
    header = models.JSONField(default=dict, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    expect = models.JSONField(default=dict, blank=True)
    extractors = models.JSONField(default=list, blank=True)
    tags = models.JSONField(default=list, blank=True)
    suite = models.CharField(max_length=80, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    estimated_duration_ms = models.PositiveIntegerField(default=1000)
    level = models.PositiveIntegerField(default=1)
    rely = models.CharField(max_length=200, blank=True)
    dependencies = models.ManyToManyField("self", symmetrical=False, blank=True)
    is_setup = models.BooleanField(default=False)
    enabled = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("api", "case_code", "is_setup")
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.case_code} {self.subtitle or self.title}"


class TestPlan(TimeStampedModel):
    name = models.CharField(max_length=160)
    project = models.ForeignKey(Project, related_name="test_plans", on_delete=models.CASCADE)
    environment = models.ForeignKey(Environment, related_name="test_plans", on_delete=models.PROTECT)
    modules = models.ManyToManyField(Module, blank=True)
    api_definitions = models.ManyToManyField(ApiDefinition, blank=True)
    cases = models.ManyToManyField(ApiCase, blank=True)
    scenarios = models.ManyToManyField("ScenarioCase", blank=True)
    levels = models.JSONField(default=list, blank=True)
    tags = models.JSONField(default=list, blank=True)
    suites = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return self.name


class TestTask(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "待执行"
        RUNNING = "RUNNING", "执行中"
        PASSED = "PASSED", "通过"
        FAILED = "FAILED", "失败"
        CANCELED = "CANCELED", "已取消"

    plan = models.ForeignKey(TestPlan, related_name="tasks", on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    progress = models.PositiveIntegerField(default=0)
    total_count = models.PositiveIntegerField(default=0)
    passed_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    current_case = models.ForeignKey(
        ApiCase, null=True, blank=True, on_delete=models.SET_NULL, related_name="running_tasks"
    )
    current_case_code = models.CharField(max_length=80, blank=True)
    current_case_title = models.CharField(max_length=200, blank=True)
    current_object_type = models.CharField(max_length=30, blank=True)
    current_step_name = models.CharField(max_length=200, blank=True)
    current_step_message = models.CharField(max_length=300, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    report_xml_path = models.CharField(max_length=500, blank=True)
    report_html_path = models.CharField(max_length=500, blank=True)
    log = models.TextField(blank=True)
    failure_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-id"]

    def mark_running(self):
        self.status = self.Status.RUNNING
        self.started_at = timezone.now()
        self.save(update_fields=["status", "started_at", "updated_at"])


class TaskEvent(TimeStampedModel):
    """
    执行过程事件（结构化日志）

    设计目标：
    - 能在任务详情页按时间线回放（开始/结束/跳过/断言失败/请求异常等）
    - 用于失败原因聚合统计（看板）
    """

    class Level(models.TextChoices):
        INFO = "INFO", "信息"
        WARN = "WARN", "警告"
        ERROR = "ERROR", "错误"

    class Category(models.TextChoices):
        TASK = "TASK", "任务"
        REQUEST = "REQUEST", "请求"
        ASSERTION = "ASSERTION", "断言"
        EXTRACTOR = "EXTRACTOR", "变量提取"
        DEPENDENCY = "DEPENDENCY", "依赖"
        REPORT = "REPORT", "报告"
        SYSTEM = "SYSTEM", "系统"

    task = models.ForeignKey(TestTask, related_name="events", on_delete=models.CASCADE)
    level = models.CharField(max_length=10, choices=Level.choices, default=Level.INFO)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.TASK)
    message = models.CharField(max_length=300, blank=True)
    data = models.JSONField(default=dict, blank=True)

    # 关联上下文（便于筛选/定位）
    object_type = models.CharField(max_length=30, blank=True)  # API_CASE / SCENARIO_STEP / TASK ...
    case_code = models.CharField(max_length=80, blank=True)
    step_name = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["id"]


class TestResult(TimeStampedModel):
    class Status(models.TextChoices):
        PASSED = "PASSED", "通过"
        FAILED = "FAILED", "失败"
        ERROR = "ERROR", "错误"
        SKIPPED = "SKIPPED", "跳过"

    task = models.ForeignKey(TestTask, related_name="results", on_delete=models.CASCADE)
    case = models.ForeignKey(ApiCase, null=True, blank=True, on_delete=models.SET_NULL)
    case_code = models.CharField(max_length=80)
    title = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=Status.choices)
    duration_ms = models.PositiveIntegerField(default=0)
    request_data = models.JSONField(default=dict, blank=True)
    response_status = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    assertion_error = models.TextField(blank=True)
    failure_category = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["id"]


class ScenarioCase(TimeStampedModel):
    project = models.ForeignKey(Project, related_name="scenarios", on_delete=models.CASCADE)
    module = models.ForeignKey(Module, null=True, blank=True, related_name="scenarios", on_delete=models.SET_NULL)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    level = models.PositiveIntegerField(default=1)
    enabled = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name


class ScenarioStep(TimeStampedModel):
    scenario = models.ForeignKey(ScenarioCase, related_name="steps", on_delete=models.CASCADE)
    api = models.ForeignKey(ApiDefinition, related_name="scenario_steps", on_delete=models.PROTECT)
    case = models.ForeignKey(
        ApiCase,
        null=True,
        blank=True,
        related_name="scenario_steps",
        on_delete=models.PROTECT,
        help_text="可选：引用接口用例（ApiCase）。执行时将继承用例配置，并允许本步骤做覆盖。",
    )
    name = models.CharField(max_length=200)
    session_key = models.CharField(
        max_length=64,
        default="default",
        blank=True,
        help_text="同一 session_key 的步骤共享 Cookie 与运行时变量；不同 session_key 相互隔离。",
    )
    header = models.JSONField(default=dict, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    expect = models.JSONField(default=dict, blank=True)
    extractors = models.JSONField(default=list, blank=True)
    dependencies = models.ManyToManyField("self", symmetrical=False, blank=True)
    enabled = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.scenario.name} / {self.name}"


class ScenarioStepResult(TimeStampedModel):
    task = models.ForeignKey(TestTask, related_name="step_results", on_delete=models.CASCADE)
    scenario = models.ForeignKey(ScenarioCase, null=True, blank=True, on_delete=models.SET_NULL)
    step = models.ForeignKey(ScenarioStep, null=True, blank=True, on_delete=models.SET_NULL)
    scenario_name = models.CharField(max_length=200, null=True, blank=True)
    step_name = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=TestResult.Status.choices)
    duration_ms = models.PositiveIntegerField(default=0)
    request_data = models.JSONField(default=dict, blank=True)
    response_status = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    assertion_error = models.TextField(blank=True)
    failure_category = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["id"]


class Schedule(TimeStampedModel):
    class Mode(models.TextChoices):
        SIMPLE = "SIMPLE", "简单周期"
        CRON = "CRON", "Cron"

    class SimpleType(models.TextChoices):
        DAILY = "DAILY", "每天"
        WEEKLY = "WEEKLY", "每周"
        HOURLY = "HOURLY", "每 N 小时"

    name = models.CharField(max_length=160)
    plan = models.ForeignKey(TestPlan, related_name="schedules", on_delete=models.CASCADE)
    mode = models.CharField(max_length=20, choices=Mode.choices, default=Mode.SIMPLE)
    simple_type = models.CharField(max_length=20, choices=SimpleType.choices, default=SimpleType.DAILY)
    interval_hours = models.PositiveIntegerField(default=1)
    weekdays = models.JSONField(default=list, blank=True)
    run_time = models.TimeField(null=True, blank=True)
    cron = models.CharField(max_length=120, blank=True)
    enabled = models.BooleanField(default=False)
    next_run_at = models.DateTimeField(null=True, blank=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return self.name


# -----------------------------
# UI 自动化（Playwright）
# -----------------------------


class UiScenario(TimeStampedModel):
    project = models.ForeignKey(Project, related_name="ui_scenarios", on_delete=models.CASCADE)
    module = models.ForeignKey(
        Module, null=True, blank=True, related_name="ui_scenarios", on_delete=models.SET_NULL
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    level = models.PositiveIntegerField(default=1)
    tags = models.JSONField(default=list, blank=True)
    enabled = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name


class UiPage(TimeStampedModel):
    """
    UI 页面对象（PO 模式）
    - url: 完整 URL（例如 https://xxx/login）
    """

    project = models.ForeignKey(Project, related_name="ui_pages", on_delete=models.CASCADE)
    module = models.ForeignKey(
        Module, null=True, blank=True, related_name="ui_pages", on_delete=models.SET_NULL
    )
    name = models.CharField(max_length=200)
    url = models.URLField(blank=True)
    description = models.TextField(blank=True)
    enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = ("project", "name")
        ordering = ["-id"]

    def __str__(self):
        return self.name


class UiElement(TimeStampedModel):
    """
    元素库（PO 模式）
    locator 示例：
      {"strategy":"css","value":"#submit","strict":true,"nth":0}
    """

    page = models.ForeignKey(UiPage, related_name="elements", on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    locator = models.JSONField(default=dict, blank=True)
    description = models.CharField(max_length=300, blank=True)
    enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = ("page", "name")
        ordering = ["id"]

    def __str__(self):
        return f"{self.page.name} / {self.name}"


class UiPageMethod(TimeStampedModel):
    """
    页面方法（PO 模式）
    - 方法步骤 UiMethodStep 内支持 ${field} 数据引用（DDT）
    """

    page = models.ForeignKey(UiPage, related_name="methods", on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = ("page", "name")
        ordering = ["id"]

    def __str__(self):
        return f"{self.page.name} / {self.name}"


class UiMethodStep(TimeStampedModel):
    class Type(models.TextChoices):
        GOTO = "GOTO", "打开页面"
        CLICK = "CLICK", "点击"
        FILL = "FILL", "输入"
        PRESS = "PRESS", "按键"
        WAIT = "WAIT", "等待"
        ASSERT = "ASSERT", "断言"

    method = models.ForeignKey(UiPageMethod, related_name="steps", on_delete=models.CASCADE)
    sort_order = models.PositiveIntegerField(default=0)
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.CLICK)
    element = models.ForeignKey(UiElement, null=True, blank=True, on_delete=models.SET_NULL)
    params = models.JSONField(default=dict, blank=True)
    assertions = models.JSONField(default=dict, blank=True)
    enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.method} / {self.name}"


class UiDataset(TimeStampedModel):
    project = models.ForeignKey(Project, related_name="ui_datasets", on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    schema = models.JSONField(default=dict, blank=True)  # {sensitive_fields:[...], fields:[...]}
    enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = ("project", "name")
        ordering = ["-id"]

    def __str__(self):
        return self.name


class UiDatasetRow(TimeStampedModel):
    dataset = models.ForeignKey(UiDataset, related_name="rows", on_delete=models.CASCADE)
    row_key = models.CharField(max_length=200, blank=True)
    data = models.JSONField(default=dict, blank=True)
    enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["id"]


class UiScenarioStep(TimeStampedModel):
    class Type(models.TextChoices):
        CALL_METHOD = "CALL_METHOD", "调用页面方法"

    scenario = models.ForeignKey(UiScenario, related_name="scenario_steps", on_delete=models.CASCADE)
    sort_order = models.PositiveIntegerField(default=0)
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.CALL_METHOD)
    method = models.ForeignKey(UiPageMethod, null=True, blank=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=200, blank=True)
    enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "id"]


class UiPlan(TimeStampedModel):
    """
    UI 测试计划（任务中心维护）：
    - 只负责把已存在的 UI 场景关联成可运行计划
    - 计划执行时可选择 mode/dataset（也可用计划默认值作为预填）
    """

    name = models.CharField(max_length=200)
    project = models.ForeignKey(Project, related_name="ui_plans", on_delete=models.CASCADE)
    scenarios = models.ManyToManyField("UiScenario", related_name="plans", blank=True)
    default_dataset = models.ForeignKey(
        "UiDataset", null=True, blank=True, related_name="plans", on_delete=models.PROTECT
    )
    default_mode = models.CharField(
        max_length=10,
        choices=[("HEADLESS", "无头"), ("HEADED", "有头")],
        default="HEADLESS",
    )
    enabled = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-id"]


class UiExecTask(TimeStampedModel):
    """
    UI 计划执行记录（任务中心的“执行记录”展示对象）：
    - 一次执行记录对应一个 UI 计划的执行
    - 内部会生成多个 UiTask（每个场景一个），但这些属于执行细节
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "待执行"
        RUNNING = "RUNNING", "执行中"
        PASSED = "PASSED", "通过"
        FAILED = "FAILED", "失败"
        CANCELED = "CANCELED", "已取消"

    plan = models.ForeignKey(UiPlan, related_name="exec_tasks", on_delete=models.CASCADE)
    dataset = models.ForeignKey(UiDataset, null=True, blank=True, on_delete=models.PROTECT)
    mode = models.CharField(
        max_length=10,
        choices=[("HEADLESS", "无头"), ("HEADED", "有头")],
        default="HEADLESS",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    total = models.PositiveIntegerField(default=0)
    passed = models.PositiveIntegerField(default=0)
    failed = models.PositiveIntegerField(default=0)
    canceled = models.PositiveIntegerField(default=0)
    progress = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-id"]


class UiRun(TimeStampedModel):
    scenario = models.ForeignKey(UiScenario, related_name="runs", on_delete=models.CASCADE)
    dataset = models.ForeignKey(UiDataset, related_name="runs", on_delete=models.PROTECT)
    mode = models.CharField(
        max_length=10,
        choices=[("HEADLESS", "无头"), ("HEADED", "有头")],
        default="HEADLESS",
    )
    total = models.PositiveIntegerField(default=0)
    passed = models.PositiveIntegerField(default=0)
    failed = models.PositiveIntegerField(default=0)
    skipped = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-id"]


class UiStep(TimeStampedModel):
    class Type(models.TextChoices):
        GOTO = "GOTO", "打开页面"
        CLICK = "CLICK", "点击"
        FILL = "FILL", "输入"
        PRESS = "PRESS", "按键"
        WAIT = "WAIT", "等待"
        ASSERT = "ASSERT", "断言"

    scenario = models.ForeignKey(UiScenario, related_name="steps", on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.CLICK)
    # 定位器：{strategy: "css|text|role|xpath", value: "...", strict: true, nth: 0}
    target = models.JSONField(default=dict, blank=True)
    # 参数：如 {url, value, key, timeout_ms, state, expect}
    params = models.JSONField(default=dict, blank=True)
    # 断言规则（可复用 __assertions 结构）
    assertions = models.JSONField(default=dict, blank=True)
    # 步骤依赖
    dependencies = models.ManyToManyField("self", symmetrical=False, blank=True)
    enabled = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.scenario.name} / {self.name}"


class UiTask(TimeStampedModel):
    class Mode(models.TextChoices):
        HEADLESS = "HEADLESS", "无头"
        HEADED = "HEADED", "有头"

    class Status(models.TextChoices):
        PENDING = "PENDING", "待执行"
        RUNNING = "RUNNING", "执行中"
        PASSED = "PASSED", "通过"
        FAILED = "FAILED", "失败"
        CANCELED = "CANCELED", "已取消"

    scenario = models.ForeignKey(UiScenario, related_name="tasks", on_delete=models.CASCADE)
    run = models.ForeignKey(UiRun, null=True, blank=True, related_name="tasks", on_delete=models.SET_NULL)
    exec_task = models.ForeignKey(UiExecTask, null=True, blank=True, related_name="tasks", on_delete=models.SET_NULL)
    # “一次运行=一个任务”的批量执行（DDT 批次）支持：
    # - dataset 绑定数据集；Runner 会按 enabled 的数据行依次执行同一个场景
    # - dataset_row 为历史兼容：旧模式下一个数据行对应一个任务
    dataset = models.ForeignKey(UiDataset, null=True, blank=True, related_name="tasks", on_delete=models.PROTECT)
    dataset_row = models.ForeignKey(UiDatasetRow, null=True, blank=True, on_delete=models.SET_NULL)
    mode = models.CharField(max_length=10, choices=Mode.choices, default=Mode.HEADLESS)
    progress = models.PositiveIntegerField(default=0)
    total_steps = models.PositiveIntegerField(default=0)
    passed_steps = models.PositiveIntegerField(default=0)
    failed_steps = models.PositiveIntegerField(default=0)
    skipped_steps = models.PositiveIntegerField(default=0)
    # DDT 批次统计（dataset 模式下生效）
    total_rows = models.PositiveIntegerField(default=0)
    passed_rows = models.PositiveIntegerField(default=0)
    failed_rows = models.PositiveIntegerField(default=0)
    skipped_rows = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    # Celery 投递后的 task id（用于排障；不作为失败原因展示）
    celery_task_id = models.CharField(max_length=80, blank=True)
    failure_reason = models.TextField(blank=True)
    report_dir = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-id"]


class UiStepResult(TimeStampedModel):
    class Status(models.TextChoices):
        PASSED = "PASSED", "通过"
        FAILED = "FAILED", "失败"
        ERROR = "ERROR", "错误"
        SKIPPED = "SKIPPED", "跳过"

    task = models.ForeignKey(UiTask, related_name="results", on_delete=models.CASCADE)
    step = models.ForeignKey(UiStep, null=True, blank=True, on_delete=models.SET_NULL)
    step_name = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=Status.choices)
    duration_ms = models.PositiveIntegerField(default=0)
    failure_category = models.CharField(max_length=40, blank=True)
    error_message = models.TextField(blank=True)
    data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["id"]


class UiArtifact(TimeStampedModel):
    class Type(models.TextChoices):
        SCREENSHOT = "SCREENSHOT", "截图"
        TRACE = "TRACE", "Trace"

    task = models.ForeignKey(UiTask, related_name="artifacts", on_delete=models.CASCADE)
    result = models.ForeignKey(UiStepResult, null=True, blank=True, on_delete=models.SET_NULL)
    type = models.CharField(max_length=20, choices=Type.choices)
    name = models.CharField(max_length=200, blank=True)
    path = models.CharField(max_length=800)
    url = models.CharField(max_length=800, blank=True)
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["id"]


class UiTaskEvent(TimeStampedModel):
    class Level(models.TextChoices):
        INFO = "INFO", "信息"
        WARN = "WARN", "警告"
        ERROR = "ERROR", "错误"

    class Category(models.TextChoices):
        TASK = "TASK", "任务"
        STEP = "STEP", "步骤"
        ACTION = "ACTION", "动作"
        ASSERTION = "ASSERTION", "断言"
        ARTIFACT = "ARTIFACT", "工件"
        SYSTEM = "SYSTEM", "系统"

    task = models.ForeignKey(UiTask, related_name="events", on_delete=models.CASCADE)
    level = models.CharField(max_length=10, choices=Level.choices, default=Level.INFO)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.TASK)
    message = models.CharField(max_length=300, blank=True)
    data = models.JSONField(default=dict, blank=True)
    step_name = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["id"]
