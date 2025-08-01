# Generated by Django 4.2.11 on 2024-05-21 07:48

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import mvp.mixins


class Migration(migrations.Migration):

    dependencies = [
        ('mvp', '0102_remove_organization_jurisdictions_customers_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='repositoryfilechunk',
            name='code_hash',
            field=models.CharField(blank=True, default=None, max_length=64, null=True),
        ),
        migrations.CreateModel(
            name='RepositoryCodeAttestation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('code_hash', models.CharField(max_length=64)),
                ('label', models.CharField(choices=[('ai', 'PureAI'), ('blended', 'Blended'), ('human', 'NotGenAI'), ('not_evaluated', 'NotEvaluated')], max_length=20)),
                ('comment', models.TextField(blank=True, default=None, null=True)),
                ('attested_by', models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('repository', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='mvp.repository')),
            ],
            options={
                'unique_together': {('repository', 'code_hash')},
            },
            bases=(mvp.mixins.PublicIdMixin, models.Model),
        ),
        migrations.AddField(
            model_name='repositoryfilechunk',
            name='attestation',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.SET_NULL, to='mvp.repositorycodeattestation'),
        ),
    ]
