"""
数据库迁移 `0003_ui_task_celery_task_id`：
为 UiTask 增加 celery_task_id 字段，用于记录 Celery 投递后的任务 id（仅排障，不作为失败原因展示）。
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0002_ui_task_batch_dataset"),
    ]

    operations = [
        migrations.AddField(
            model_name="uitask",
            name="celery_task_id",
            field=models.CharField(blank=True, max_length=80),
        ),
    ]

