# Generated by Django 4.2.4 on 2023-11-30 10:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mvp', '0048_alter_repository_unique_together'),
    ]

    operations = [
        migrations.AddField(
            model_name='repository',
            name='last_analysis_num_files',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
