# Generated by Django 4.2.21 on 2025-06-10 10:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mvp", "0144_dataproviderconnection_connected_at_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="repository",
            name="default_branch_name",
            field=models.CharField(blank=True, default=None, max_length=250, null=True),
        ),
    ]
