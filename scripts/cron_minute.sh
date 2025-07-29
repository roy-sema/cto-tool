#!/bin/bash

CTO_TOOL_DIR=$(realpath "$(dirname "$0")/..")

cd $CTO_TOOL_DIR

set -a && source .env.production.opentelemetry && set +a
export OTEL_SERVICE_NAME=SEMA-SIP-recalculate-attested-ai-composition-cron
export OTEL_TRACES_SAMPLER="always_off"
export OTEL_METRICS_EXPORTER="none"

# Run Django tasks
uv run opentelemetry-instrument python3 manage.py recalculate_attested_ai_composition
