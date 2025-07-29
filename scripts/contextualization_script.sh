#!/bin/bash

CTO_TOOL_DIR=$(realpath "$(dirname "$0")/..")

cd $CTO_TOOL_DIR

set -a && source .env.production.opentelemetry && set +a
export OTEL_TRACES_SAMPLER="parentbased_always_on"
export OTEL_METRICS_EXPORTER="none"
export OTEL_RESOURCE_ATTRIBUTES="host.name=${HOSTNAME}"

uv run opentelemetry-instrument python3 manage.py experiment_contextualization_script $*
