from django.db import migrations

from mvp.models import ReasonForMeasuringGenAIChoicesField


def migrate_reason_for_measuring_genai_data(apps, schema_editor):
    Organization = apps.get_model("mvp", "Organization")
    for org in Organization.objects.filter(reason_for_measuring_genai__isnull=False):
        if org.reason_for_measuring_genai:
            org.reasons_for_measuring_genai = [org.reason_for_measuring_genai]
            org.save()


class Migration(migrations.Migration):

    dependencies = [
        ("mvp", "0119_customuser_company_number_of_developers_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="reasons_for_measuring_genai",
            field=ReasonForMeasuringGenAIChoicesField(default=list),
        ),
        migrations.RunPython(
            migrate_reason_for_measuring_genai_data,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name="organization",
            name="reason_for_measuring_genai",
        ),
    ]
