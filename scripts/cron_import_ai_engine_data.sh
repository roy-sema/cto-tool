#!/bin/bash

# This is important because cto-tool user doesn't include this in the path by default
export PATH=/home/cto-tool/.local/bin/:$PATH

CTO_TOOL_DIR=$(realpath "$(dirname "$0")/..")

cd $CTO_TOOL_DIR

set -a && source .env.production.opentelemetry && set +a
export OTEL_SERVICE_NAME=SEMA-SIP-ai-engine-cron
export OTEL_TRACES_SAMPLER="always_off"
export OTEL_METRICS_EXPORTER="none"

# Import data (make sure it's accessible for cron and apache users)
uv run opentelemetry-instrument python3 manage.py import_ai_engine_data

# Change ownership of GBOM files
chown cto-tool:www-data $GBOM_PRECOMPUTED_DIRECTORY/*
chmod 664 $GBOM_PRECOMPUTED_DIRECTORY/*
