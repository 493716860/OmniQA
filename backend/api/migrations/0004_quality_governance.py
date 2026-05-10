from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("api", "0003_platform_upgrade"),
    ]

    operations = [
        migrations.AddField(
            model_name="apicase",
            name="tags",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="apicase",
            name="suite",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="apicase",
            name="owner",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="apicase",
            name="estimated_duration_ms",
            field=models.PositiveIntegerField(default=1000),
        ),
        migrations.AddField(
            model_name="testplan",
            name="api_definitions",
            field=models.ManyToManyField(blank=True, to="api.apidefinition"),
        ),
        migrations.AddField(
            model_name="testplan",
            name="tags",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="testplan",
            name="suites",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="testresult",
            name="failure_category",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="scenariostepresult",
            name="failure_category",
            field=models.CharField(blank=True, max_length=40),
        ),
    ]
