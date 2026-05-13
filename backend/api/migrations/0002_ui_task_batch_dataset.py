"""
数据库迁移 `0002_ui_task_batch_dataset`：
让 UiTask 支持“一个任务绑定一个数据集（DDT 批次）”，并在任务内循环执行。

背景：
- 之前 UI 自动化采用 UiRun（批次）→ 多个 UiTask（每行数据一个任务）的结构，用户体验绕。
- 新目标：一次运行就是一个 UiTask，DDT 在任务内部循环执行；UiRun 仅保留历史兼容（不再作为主要交互对象）。
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0001_squashed_0011_po_ddt"),
    ]

    operations = [
        migrations.AddField(
            model_name="uitask",
            name="dataset",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="tasks",
                to="api.uidataset",
            ),
        ),
        migrations.AddField(model_name="uitask", name="total_rows", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="uitask", name="passed_rows", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="uitask", name="failed_rows", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="uitask", name="skipped_rows", field=models.PositiveIntegerField(default=0)),
    ]

