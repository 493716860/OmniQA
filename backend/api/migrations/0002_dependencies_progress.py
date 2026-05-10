from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="apicase",
            name="extractors",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="apicase",
            name="dependencies",
            field=models.ManyToManyField(blank=True, to="api.apicase"),
        ),
        migrations.AddField(
            model_name="testtask",
            name="current_case",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="running_tasks",
                to="api.apicase",
            ),
        ),
        migrations.AddField(
            model_name="testtask",
            name="current_case_code",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="testtask",
            name="current_case_title",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="testtask",
            name="current_step_message",
            field=models.CharField(blank=True, max_length=300),
        ),
        migrations.AddField(
            model_name="testtask",
            name="skipped_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="testresult",
            name="status",
            field=models.CharField(
                choices=[
                    ("PASSED", "通过"),
                    ("FAILED", "失败"),
                    ("ERROR", "错误"),
                    ("SKIPPED", "跳过"),
                ],
                max_length=20,
            ),
        ),
    ]
