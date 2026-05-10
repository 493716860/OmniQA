from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Project",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=120, unique=True)),
                ("description", models.TextField(blank=True)),
            ],
            options={"abstract": False},
        ),
        migrations.CreateModel(
            name="Environment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=120)),
                ("base_url", models.URLField(blank=True)),
                ("headers", models.JSONField(blank=True, default=dict)),
                ("verify_ssl", models.BooleanField(default=False)),
                ("timeout_seconds", models.PositiveIntegerField(default=10)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="environments", to="api.project")),
            ],
            options={"unique_together": {("project", "name")}},
        ),
        migrations.CreateModel(
            name="Module",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=120)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="modules", to="api.project")),
            ],
            options={"ordering": ["sort_order", "id"], "unique_together": {("project", "name")}},
        ),
        migrations.CreateModel(
            name="ApiDefinition",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=200)),
                ("path", models.CharField(max_length=500)),
                ("method", models.CharField(max_length=16)),
                ("module", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="apis", to="api.module")),
            ],
            options={"ordering": ["module_id", "id"], "unique_together": {("module", "path", "method")}},
        ),
        migrations.CreateModel(
            name="ApiCase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("case_code", models.CharField(max_length=80)),
                ("title", models.CharField(max_length=200)),
                ("subtitle", models.CharField(blank=True, max_length=200)),
                ("header", models.JSONField(blank=True, default=dict)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("expect", models.JSONField(blank=True, default=dict)),
                ("level", models.PositiveIntegerField(default=1)),
                ("rely", models.CharField(blank=True, max_length=200)),
                ("is_setup", models.BooleanField(default=False)),
                ("enabled", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("api", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="cases", to="api.apidefinition")),
            ],
            options={"ordering": ["sort_order", "id"], "unique_together": {("api", "case_code", "is_setup")}},
        ),
        migrations.CreateModel(
            name="TestPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=160)),
                ("levels", models.JSONField(blank=True, default=list)),
                ("cases", models.ManyToManyField(blank=True, to="api.apicase")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("environment", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="test_plans", to="api.environment")),
                ("modules", models.ManyToManyField(blank=True, to="api.module")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="test_plans", to="api.project")),
            ],
            options={"ordering": ["-id"]},
        ),
        migrations.CreateModel(
            name="TestTask",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("status", models.CharField(choices=[("PENDING", "待执行"), ("RUNNING", "执行中"), ("PASSED", "通过"), ("FAILED", "失败"), ("CANCELED", "已取消")], default="PENDING", max_length=20)),
                ("progress", models.PositiveIntegerField(default=0)),
                ("total_count", models.PositiveIntegerField(default=0)),
                ("passed_count", models.PositiveIntegerField(default=0)),
                ("failed_count", models.PositiveIntegerField(default=0)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("report_xml_path", models.CharField(blank=True, max_length=500)),
                ("report_html_path", models.CharField(blank=True, max_length=500)),
                ("log", models.TextField(blank=True)),
                ("failure_reason", models.TextField(blank=True)),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tasks", to="api.testplan")),
            ],
            options={"ordering": ["-id"]},
        ),
        migrations.CreateModel(
            name="TestResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("case_code", models.CharField(max_length=80)),
                ("title", models.CharField(max_length=200)),
                ("status", models.CharField(choices=[("PASSED", "通过"), ("FAILED", "失败"), ("ERROR", "错误")], max_length=20)),
                ("duration_ms", models.PositiveIntegerField(default=0)),
                ("request_data", models.JSONField(blank=True, default=dict)),
                ("response_status", models.IntegerField(blank=True, null=True)),
                ("response_body", models.TextField(blank=True)),
                ("assertion_error", models.TextField(blank=True)),
                ("case", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="api.apicase")),
                ("task", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="results", to="api.testtask")),
            ],
            options={"ordering": ["id"]},
        ),
    ]
