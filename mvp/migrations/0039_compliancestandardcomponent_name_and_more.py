# Generated by Django 4.2.4 on 2023-11-20 10:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mvp', '0038_compliancestandardlink'),
    ]

    operations = [
        migrations.AddField(
            model_name='compliancestandardcomponent',
            name='name',
            field=models.CharField(blank=True, default=None, max_length=100, null=True),
        ),
        migrations.AlterUniqueTogether(
            name='compliancestandardcomponent',
            unique_together={('standard', 'name')},
        ),
    ]
