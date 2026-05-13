"""
ScenarioStep 支持引用接口用例（ApiCase）：
- 新增 ScenarioStep.case 外键，用于继承用例配置并允许步骤覆盖。
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0005_add_session_key_to_case_and_step"),
    ]

    operations = [
        migrations.AddField(
            model_name="scenariostep",
            name="case",
            field=models.ForeignKey(
                blank=True,
                help_text="可选：引用接口用例（ApiCase）。执行时将继承用例配置，并允许本步骤做覆盖。",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="scenario_steps",
                to="api.apicase",
            ),
        ),
    ]

