# Generated by Django 4.2.4 on 2024-04-10 13:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mvp', '0095_geography_compliancestandard_geographies_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='repository',
            name='not_evaluated_num_lines',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='repositorycommit',
            name='not_evaluated_num_files',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='repositorycommit',
            name='not_evaluated_num_lines',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
