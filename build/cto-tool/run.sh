#!/bin/bash
set -o errexit
set -o nounset
set -o pipefail

export VIRTUAL_ENV=/app/.venv
export PATH="/app/.venv/bin:$PATH"

exec uv run --locked manage.py runserver 0.0.0.0:8000
