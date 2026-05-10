from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0006_scenario_step_result_snapshot"),
    ]

    operations = [
        migrations.AlterField(
            model_name="scenariostepresult",
            name="scenario_name",
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
    ]
