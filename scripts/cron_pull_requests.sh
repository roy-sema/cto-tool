#!/bin/bash

CTO_TOOL_DIR=$(realpath "$(dirname "$0")/..")

cd $CTO_TOOL_DIR

set -a && source .env.production.opentelemetry && set +a
export OTEL_SERVICE_NAME=SEMA-SIP-ai-engine-pull-requests-cron
export OTEL_TRACES_SAMPLER="parentbased_traceidratio"
export OTEL_TRACES_SAMPLER_ARG=0.005
export OTEL_METRICS_EXPORTER="none"

# Fetch any missed pull request
uv run opentelemetry-instrument python3 manage.py fetch_pull_requests
