"""
新增 UI 计划与执行记录：
- UiPlan：任务中心维护的 UI 测试计划（关联既有 UiScenario）
- UiExecTask：一次执行记录（对应一个 UiPlan 的一次运行）
- UiTask.exec_task：把场景级 UiTask 关联到 UiExecTask，便于追溯与聚合
"""

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0003_ui_task_celery_task_id"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UiPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=200)),
                ("default_mode", models.CharField(choices=[("HEADLESS", "无头"), ("HEADED", "有头")], default="HEADLESS", max_length=10)),
                ("enabled", models.BooleanField(default=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("default_dataset", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="plans", to="api.uidataset")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ui_plans", to="api.project")),
            ],
            options={"ordering": ["-id"]},
        ),
        migrations.CreateModel(
            name="UiExecTask",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("mode", models.CharField(choices=[("HEADLESS", "无头"), ("HEADED", "有头")], default="HEADLESS", max_length=10)),
                ("status", models.CharField(choices=[("PENDING", "待执行"), ("RUNNING", "执行中"), ("PASSED", "通过"), ("FAILED", "失败"), ("CANCELED", "已取消")], default="PENDING", max_length=20)),
                ("total", models.PositiveIntegerField(default=0)),
                ("passed", models.PositiveIntegerField(default=0)),
                ("failed", models.PositiveIntegerField(default=0)),
                ("canceled", models.PositiveIntegerField(default=0)),
                ("progress", models.PositiveIntegerField(default=0)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("failure_reason", models.TextField(blank=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("dataset", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="api.uidataset")),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="exec_tasks", to="api.uiplan")),
            ],
            options={"ordering": ["-id"]},
        ),
        migrations.AddField(
            model_name="uiplan",
            name="scenarios",
            field=models.ManyToManyField(blank=True, related_name="plans", to="api.uiscenario"),
        ),
        migrations.AddField(
            model_name="uitask",
            name="exec_task",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="tasks", to="api.uiexectask"),
        ),
    ]

