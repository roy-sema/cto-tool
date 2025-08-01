# Generated by Django 4.2.4 on 2024-02-22 20:02

import api.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="genaifeedback",
            name="file",
            field=models.FileField(
                max_length=255,
                storage=api.models.OverwriteStorage(),
                upload_to=api.models.GenAIFeedback.get_filename_path,
            ),
        ),
    ]
