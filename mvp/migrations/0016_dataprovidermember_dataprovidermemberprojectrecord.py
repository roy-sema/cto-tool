# Generated by Django 4.2.4 on 2023-10-09 06:26

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("mvp", "0015_alter_submodulemetric_metric_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="DataProviderMember",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                ("external_id", models.CharField(max_length=100)),
                ("meta", models.JSONField(blank=True, default=None, null=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="mvp.organization",
                    ),
                ),
                (
                    "provider",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="mvp.dataprovider",
                    ),
                ),
            ],
            options={
                "unique_together": {("organization", "provider", "external_id")},
            },
        ),
        migrations.CreateModel(
            name="DataProviderMemberProjectRecord",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("value", models.IntegerField()),
                ("date_time", models.DateTimeField()),
                (
                    "field",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="mvp.dataproviderfield",
                    ),
                ),
                (
                    "member",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="mvp.dataprovidermember",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="mvp.dataproviderproject",
                    ),
                ),
            ],
        ),
    ]
