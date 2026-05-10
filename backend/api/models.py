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
    timeout_seconds = models.PositiveIntegerField(default=getattr(settings, "NEXUS_REQUEST_TIMEOUT", 10))

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
    name = models.CharField(max_length=200)
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
