#!/bin/bash

CODE_DIR="/home/cto-tool/cto-tool/"

# Enable virtual env
cd $CODE_DIR

set -a && source .env.production.opentelemetry && set +a
export OTEL_TRACES_SAMPLER="parentbased_always_on"
export OTEL_METRICS_EXPORTER="none"
export OTEL_RESOURCE_ATTRIBUTES="host.name=${HOSTNAME}"

# Run Django tasks
uv run opentelemetry-instrument python3 manage.py sync_users_with_mailchimp
uv run opentelemetry-instrument python3 manage.py fetch_data GitHub
uv run opentelemetry-instrument python3 manage.py fetch_data Snyk
uv run opentelemetry-instrument python3 manage.py fetch_data IRadar
uv run opentelemetry-instrument python3 manage.py fetch_data Codacy
uv run opentelemetry-instrument python3 manage.py fetch_data BitBucket
uv run opentelemetry-instrument python3 manage.py fetch_data AzureDevOps
uv run opentelemetry-instrument python3 manage.py check_jira_connections_are_valid
uv run opentelemetry-instrument python3 manage.py fetch_data Jira
uv run opentelemetry-instrument python3 manage.py clear_cache
uv run opentelemetry-instrument python3 manage.py download_repositories
uv run opentelemetry-instrument python3 manage.py calculate_scores
uv run opentelemetry-instrument python3 manage.py experiment_contextualization_script --pipelines a anomaly_insights d jira_anomaly_insights insights_aggregation --day-interval 1
uv run opentelemetry-instrument python3 manage.py send_daily_message_email
# send teams notification to Sema-All
uv run opentelemetry-instrument python3 manage.py send_daily_message_notification --orgid 1479
uv run opentelemetry-instrument python3 manage.py experiment_contextualization_script --by-group --pipelines a bc anomaly_insights
uv run opentelemetry-instrument python3 manage.py shred_code
# uv run opentelemetry-instrument python3 manage.py delete_organization_data --delete-organization --no-input
