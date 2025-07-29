#!/bin/bash
set -o errexit
set -o nounset
set -o pipefail

export VIRTUAL_ENV=/app/.venv
export PATH="/app/.venv/bin:$PATH"

if [[ "$*" = *"/app/build/cto-tool/run.sh"* ]]; then
    /app/build/cto-tool/run.sh
fi

echo ""
exec "$@"
