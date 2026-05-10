from django.db import migrations, models


def backfill_scenario_names(apps, schema_editor):
    ScenarioStepResult = apps.get_model("api", "ScenarioStepResult")
    for result in ScenarioStepResult.objects.select_related("scenario").iterator():
        if result.scenario_id and result.scenario and not result.scenario_name:
            result.scenario_name = result.scenario.name
            result.save(update_fields=["scenario_name"])


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0005_environment_cookie"),
    ]

    operations = [
        migrations.AddField(
            model_name="scenariostepresult",
            name="scenario_name",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.RunPython(backfill_scenario_names, migrations.RunPython.noop),
    ]
