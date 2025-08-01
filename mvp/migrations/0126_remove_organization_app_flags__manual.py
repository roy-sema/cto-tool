# Generated by Django 4.2.11 on 2024-10-10 15:36

from django.db import migrations


def set_limits_for_ctod_organizations(apps, schema_editor):
    Organization = apps.get_model("mvp", "Organization")
    for org in Organization.objects.filter(ai_code_monitor_enabled=False):
        org.analysis_max_scans = 1
        org.analysis_max_repositories = 1
        org.analysis_max_lines_per_repository = 10000
        org.save()


class Migration(migrations.Migration):

    dependencies = [
        ("mvp", "0125_organization_avg_dev_annual_work_hours_and_more"),
    ]

    operations = [
        migrations.RunPython(
            set_limits_for_ctod_organizations,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name="organization",
            name="ai_code_monitor_enabled",
        ),
        migrations.RemoveField(
            model_name="organization",
            name="cto_dashboard_enabled",
        ),
    ]
