# Generated by Django 4.2.4 on 2024-01-29 15:49

from django.db import migrations, models


replacement_strings = [
    ("EU", "europe"),
    ("USA", "united states"),
    ("UK", "united kingdom"),
    ("Republic of Cyprus", "cyprus"),
    ("Baden-Württemberg", "baden-württemberg"),
]


class Migration(migrations.Migration):
    dependencies = [
        ("mvp", "0071_remove_repository_category_repositorygroup_and_more"),
    ]

    def migrate_jurisdictions_data_to_jsonfield(apps, schema_editor):
        Organization = apps.get_model("mvp", "Organization")
        ComplianceStandard = apps.get_model("mvp", "ComplianceStandard")
        replace_strs_data = {x: y for x, y in replacement_strings}

        def replace_str(key):
            return replace_strs_data.get(key, key.lower())

        for Model in [Organization, ComplianceStandard]:
            for model in Model.objects.all():
                # Convert existing jurisdiction names to a list of strings
                jurisdictions_customers = list(
                    map(
                        replace_str,
                        model.jurisdictions_customers.values_list("name", flat=True),
                    )
                )
                jurisdictions_developers = list(
                    map(
                        replace_str,
                        model.jurisdictions_developers.values_list("name", flat=True),
                    )
                )
                jurisdictions_headquarters = list(
                    map(
                        replace_str,
                        model.jurisdictions_headquarters.values_list("name", flat=True),
                    )
                )

                model.jurisdictions_customers_new = jurisdictions_customers
                model.jurisdictions_developers_new = jurisdictions_developers
                model.jurisdictions_headquarters_new = jurisdictions_headquarters

                model.save()

    def migrate_jsonfield_to_jurisdictions_data(apps, schema_editor):
        Organization = apps.get_model("mvp", "Organization")
        Jurisdiction = apps.get_model("mvp", "Jurisdiction")
        ComplianceStandard = apps.get_model("mvp", "ComplianceStandard")
        replace_strs_data = {y: x for x, y in replacement_strings}

        def replace_str(key):
            return replace_strs_data.get(key, key.title())

        for Model in [Organization, ComplianceStandard]:
            for model in Model.objects.all():
                # Convert existing jurisdiction names to a list of strings

                model.jurisdictions_customers.set(
                    Jurisdiction.objects.filter(
                        name__in=map(
                            replace_str, model.jurisdictions_customers_new or []
                        )
                    )
                )
                model.jurisdictions_developers.set(
                    Jurisdiction.objects.filter(
                        name__in=map(
                            replace_str, model.jurisdictions_developers_new or []
                        )
                    )
                )
                model.jurisdictions_headquarters.set(
                    Jurisdiction.objects.filter(
                        name__in=map(
                            replace_str, model.jurisdictions_headquarters_new or []
                        )
                    )
                )

                model.save()

    operations = [
        migrations.AddField(
            model_name="compliancestandard",
            name="jurisdictions_customers_new",
            field=models.JSONField(blank=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name="compliancestandard",
            name="jurisdictions_developers_new",
            field=models.JSONField(blank=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name="compliancestandard",
            name="jurisdictions_headquarters_new",
            field=models.JSONField(blank=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name="organization",
            name="jurisdictions_customers_new",
            field=models.JSONField(blank=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name="organization",
            name="jurisdictions_developers_new",
            field=models.JSONField(blank=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name="organization",
            name="jurisdictions_headquarters_new",
            field=models.JSONField(blank=True, default=None, null=True),
        ),
        migrations.RunPython(
            migrate_jurisdictions_data_to_jsonfield,
            migrate_jsonfield_to_jurisdictions_data,
        ),
        migrations.RemoveField(
            model_name="compliancestandard",
            name="jurisdictions_customers",
        ),
        migrations.RemoveField(
            model_name="compliancestandard",
            name="jurisdictions_developers",
        ),
        migrations.RemoveField(
            model_name="compliancestandard",
            name="jurisdictions_headquarters",
        ),
        migrations.RemoveField(
            model_name="organization",
            name="jurisdictions_customers",
        ),
        migrations.RemoveField(
            model_name="organization",
            name="jurisdictions_developers",
        ),
        migrations.RemoveField(
            model_name="organization",
            name="jurisdictions_headquarters",
        ),
        migrations.RenameField(
            model_name="compliancestandard",
            old_name="jurisdictions_customers_new",
            new_name="jurisdictions_customers",
        ),
        migrations.RenameField(
            model_name="compliancestandard",
            old_name="jurisdictions_developers_new",
            new_name="jurisdictions_developers",
        ),
        migrations.RenameField(
            model_name="compliancestandard",
            old_name="jurisdictions_headquarters_new",
            new_name="jurisdictions_headquarters",
        ),
        migrations.RenameField(
            model_name="organization",
            old_name="jurisdictions_customers_new",
            new_name="jurisdictions_customers",
        ),
        migrations.RenameField(
            model_name="organization",
            old_name="jurisdictions_developers_new",
            new_name="jurisdictions_developers",
        ),
        migrations.RenameField(
            model_name="organization",
            old_name="jurisdictions_headquarters_new",
            new_name="jurisdictions_headquarters",
        ),
    ]
