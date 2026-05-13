"""
为接口用例与场景步骤增加 session_key，用于同一任务内的多账号/多角色会话隔离。

- ApiCase.session_key
- ScenarioStep.session_key
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0004_ui_plan_and_exec_task"),
    ]

    operations = [
        migrations.AddField(
            model_name="apicase",
            name="session_key",
            field=models.CharField(
                blank=True,
                default="default",
                help_text="同一 session_key 的用例共享 Cookie 与运行时变量；不同 session_key 相互隔离。",
                max_length=64,
            ),
        ),
        migrations.AddField(
            model_name="scenariostep",
            name="session_key",
            field=models.CharField(
                blank=True,
                default="default",
                help_text="同一 session_key 的步骤共享 Cookie 与运行时变量；不同 session_key 相互隔离。",
                max_length=64,
            ),
        ),
    ]

