# Generated by Django 4.2.4 on 2024-04-01 14:50

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("mvp", "0093_rename_is_predefined_rule_is_preset"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="compliancestandard",
            name="geographies",
        ),
        migrations.RemoveField(
            model_name="organization",
            name="geographies",
        ),
        migrations.DeleteModel(
            name="Geography",
        ),
    ]
