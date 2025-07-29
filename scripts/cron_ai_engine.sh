#!/bin/bash

# This is important because cto-tool user doesn't include this in the path by default
export PATH=/home/cto-tool/.local/bin/:$PATH

CTO_TOOL_DIR=$(realpath "$(dirname "$0")/..")

cd $CTO_TOOL_DIR

set -a && source .env.production && set +a

cd $AI_ENGINE_DIRECTORY

# Run analysis on pending tasks
poetry run python3 analyze_aicm_pending.py $AI_CODE_REPOSITORY_DIRECTORY
