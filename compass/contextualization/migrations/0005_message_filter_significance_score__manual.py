import multiselectfield.db.fields
from django.db import migrations

LEVEL_MAP = {
    "attention_level_ceo": "10",
    "attention_level_cto_or_cpo": "9",
    "attention_level_director_or_manager": "8",
    "attention_level_team_lead": "7",
}

REVERSE_LEVEL_MAP = {v: k for k, v in LEVEL_MAP.items()}


def migrate_attention_to_significance(apps, schema_editor):
    MessageFilter = apps.get_model("contextualization", "MessageFilter")
    DailyMessage = apps.get_model("contextualization", "DailyMessage")

    for message_filter in MessageFilter.objects.all():
        if message_filter.attention_level:
            message_filter.significance_levels = [
                LEVEL_MAP[a] for a in message_filter.attention_level
            ]
            message_filter.save()

    for daily_message in DailyMessage.objects.all():
        anomaly_insights_and_risks = daily_message.raw_json.get(
            "anomaly_insights_and_risks"
        )
        if not anomaly_insights_and_risks:
            continue

        daily_message.raw_json["anomaly_insights_and_risks"] = {
            LEVEL_MAP.get(key, key): value
            for key, value in anomaly_insights_and_risks.items()
        }
        daily_message.save()


def reverse_significance_to_attention(apps, schema_editor):
    MessageFilter = apps.get_model("contextualization", "MessageFilter")
    DailyMessage = apps.get_model("contextualization", "DailyMessage")

    for message_filter in MessageFilter.objects.all():
        if message_filter.significance_levels:
            message_filter.attention_level = [
                REVERSE_LEVEL_MAP.get(level)
                for level in message_filter.significance_levels
                if level in REVERSE_LEVEL_MAP
            ]
            message_filter.save()

    for daily_message in DailyMessage.objects.all():
        anomaly_insights_and_risks = daily_message.raw_json.get(
            "anomaly_insights_and_risks"
        )
        if not anomaly_insights_and_risks:
            continue

        daily_message.raw_json["anomaly_insights_and_risks"] = {
            REVERSE_LEVEL_MAP.get(key, key): value
            for key, value in anomaly_insights_and_risks.items()
        }
        daily_message.save()


class Migration(migrations.Migration):
    dependencies = [
        (
            "contextualization",
            "0004_remove_initiative_estimated_end_date_insights_and_more",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="messagefilter",
            name="significance_levels",
            field=multiselectfield.db.fields.MultiSelectField(
                blank=True,
                choices=[(10, "10"), (9, "9"), (8, "8"), (7, "7")],
                default=list,
                max_length=8,
            ),
        ),
        migrations.RunPython(
            migrate_attention_to_significance,
            reverse_code=reverse_significance_to_attention,
        ),
        migrations.RemoveField(
            model_name="messagefilter",
            name="attention_level",
        ),
    ]
