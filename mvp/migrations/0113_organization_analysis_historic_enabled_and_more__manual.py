# Generated by Django 4.2.11 on 2024-08-14 18:18

from django.db import migrations, models
from django.db.migrations.operations import RunPython


def disable_history_analysis(apps, schema_editor):
    # We want new organizations to have this feature disabled by default,
    # but not existing ones to avoid overloading the system.
    Organization = apps.get_model("mvp", "Organization")
    Organization.objects.update(analysis_historic_enabled=False)


class Migration(migrations.Migration):

    dependencies = [
        ("mvp", "0112_organization_status_check_mark_as_failed"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="analysis_historic_enabled",
            field=models.BooleanField(
                default=True, help_text="Download commits before connection date"
            ),
        ),
        RunPython(disable_history_analysis),
        migrations.AddField(
            model_name="repository",
            name="analysis_historic_done",
            field=models.BooleanField(default=False),
        ),
    ]
