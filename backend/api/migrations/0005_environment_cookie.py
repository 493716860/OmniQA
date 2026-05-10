from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0004_quality_governance"),
    ]

    operations = [
        migrations.CreateModel(
            name="EnvironmentCookie",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("domain", models.CharField(max_length=255)),
                ("path", models.CharField(default="/", max_length=255)),
                ("name", models.CharField(max_length=255)),
                ("value", models.TextField(blank=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("secure", models.BooleanField(default=False)),
                ("http_only", models.BooleanField(default=False)),
                ("enabled", models.BooleanField(default=True)),
                (
                    "environment",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="cookies", to="api.environment"),
                ),
            ],
            options={
                "ordering": ["domain", "path", "name"],
                "unique_together": {("environment", "domain", "path", "name")},
            },
        ),
    ]
