from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("api", "0002_dependencies_progress"),
    ]

    operations = [
        migrations.AddField(
            model_name="apidefinition",
            name="default_headers",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.CreateModel(
            name="ProjectVariable",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("key", models.CharField(max_length=120)),
                ("value", models.TextField(blank=True)),
                ("description", models.CharField(blank=True, max_length=300)),
                ("enabled", models.BooleanField(default=True)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="variables", to="api.project")),
            ],
            options={"ordering": ["key"], "unique_together": {("project", "key")}},
        ),
        migrations.CreateModel(
            name="EnvironmentVariable",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("key", models.CharField(max_length=120)),
                ("value", models.TextField(blank=True)),
                ("description", models.CharField(blank=True, max_length=300)),
                ("enabled", models.BooleanField(default=True)),
                ("environment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="variables", to="api.environment")),
            ],
            options={"ordering": ["key"], "unique_together": {("environment", "key")}},
        ),
        migrations.CreateModel(
            name="ScenarioCase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("level", models.PositiveIntegerField(default=1)),
                ("enabled", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("module", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="scenarios", to="api.module")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="scenarios", to="api.project")),
            ],
            options={"ordering": ["sort_order", "id"]},
        ),
        migrations.CreateModel(
            name="ScenarioStep",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=200)),
                ("header", models.JSONField(blank=True, default=dict)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("expect", models.JSONField(blank=True, default=dict)),
                ("extractors", models.JSONField(blank=True, default=list)),
                ("enabled", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("api", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="scenario_steps", to="api.apidefinition")),
                ("dependencies", models.ManyToManyField(blank=True, to="api.scenariostep")),
                ("scenario", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="steps", to="api.scenariocase")),
            ],
            options={"ordering": ["sort_order", "id"]},
        ),
        migrations.CreateModel(
            name="ScenarioStepResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("step_name", models.CharField(max_length=200)),
                ("status", models.CharField(choices=[("PASSED", "通过"), ("FAILED", "失败"), ("ERROR", "错误"), ("SKIPPED", "跳过")], max_length=20)),
                ("duration_ms", models.PositiveIntegerField(default=0)),
                ("request_data", models.JSONField(blank=True, default=dict)),
                ("response_status", models.IntegerField(blank=True, null=True)),
                ("response_body", models.TextField(blank=True)),
                ("assertion_error", models.TextField(blank=True)),
                ("scenario", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="api.scenariocase")),
                ("step", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="api.scenariostep")),
                ("task", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="step_results", to="api.testtask")),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.CreateModel(
            name="Schedule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=160)),
                ("mode", models.CharField(choices=[("SIMPLE", "简单周期"), ("CRON", "Cron")], default="SIMPLE", max_length=20)),
                ("simple_type", models.CharField(choices=[("DAILY", "每天"), ("WEEKLY", "每周"), ("HOURLY", "每 N 小时")], default="DAILY", max_length=20)),
                ("interval_hours", models.PositiveIntegerField(default=1)),
                ("weekdays", models.JSONField(blank=True, default=list)),
                ("run_time", models.TimeField(blank=True, null=True)),
                ("cron", models.CharField(blank=True, max_length=120)),
                ("enabled", models.BooleanField(default=False)),
                ("next_run_at", models.DateTimeField(blank=True, null=True)),
                ("last_run_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="schedules", to="api.testplan")),
            ],
            options={"ordering": ["-id"]},
        ),
        migrations.AddField(
            model_name="testplan",
            name="scenarios",
            field=models.ManyToManyField(blank=True, to="api.scenariocase"),
        ),
        migrations.AddField(
            model_name="testtask",
            name="current_object_type",
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name="testtask",
            name="current_step_name",
            field=models.CharField(blank=True, max_length=200),
        ),
    ]
