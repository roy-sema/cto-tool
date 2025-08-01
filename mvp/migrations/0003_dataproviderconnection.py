# Generated by Django 4.2.4 on 2023-08-28 08:30

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('mvp', '0002_organization_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='DataProviderConnection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data', models.JSONField(blank=True, default=None, null=True)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='mvp.organization')),
                ('provider', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='mvp.dataprovider')),
            ],
            options={
                'unique_together': {('organization', 'provider')},
            },
        ),
    ]
