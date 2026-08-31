#!/bin/sh
# Copyright 2026 DataRobot, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# =============================================================================
# Custom model entrypoint: syncs the agent's locked dependencies and starts the
# DRAgent front server.
#
# This ships with the agent instead of the execution environment so the startup
# contract stays versioned with the agent code. DataRobot unpacks the custom
# model files over ${CODE_DIR} (/opt/code) at container start, so this file
# replaces the start_server.sh baked into the execution environment image.
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Configure UV package manager
export UV_PROJECT="${CODE_DIR:-/opt/code}"
export UV_PROJECT_ENVIRONMENT="${VENV_DIR:-/opt/venv}"
export UV_COMPILE_BYTECODE=0  # Disable compilation
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"

uv venv "${UV_PROJECT_ENVIRONMENT}"
# shellcheck disable=SC1091
. "${UV_PROJECT_ENVIRONMENT}/bin/activate"

# Sync dependencies using UV
# --active: Install into the active venv instead of creating a new one
# --frozen: Skip dependency resolution, use exact versions from lock file
# Note: Compilation disabled since kernel venv is already compiled
# Does not fail on errors to avoid blocking the startup of the server
uv sync --frozen --active --no-progress --color never || true

# Optional: Dump environment variables for debugging
if [ "${ENABLE_CUSTOM_MODEL_RUNTIME_ENV_DUMP}" = "1" ]; then
    echo "Environment variables:"
    env
fi

CONFIG_FILE="$SCRIPT_DIR/workflow.yaml"
if [ ! -f "$CONFIG_FILE" ]; then
    # Layout used before agent component 11.9.3, kept working during migration.
    # See docs/agent/migration-workflow-yaml-path.md.
    CONFIG_FILE="$SCRIPT_DIR/agent/workflow.yaml"
fi
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: no workflow.yaml found in $SCRIPT_DIR or $SCRIPT_DIR/agent" >&2
    exit 1
fi

# When running in a DR deployment, all paths should be mounted below ${URL_PREFIX}/
ROOT_PATH_ARG=""
if [ -n "${URL_PREFIX:-}" ]; then
    ROOT_PATH_ARG="--root_path ${URL_PREFIX}"
fi

# Get the number of workers from the runtime parameter (defaults to 1)
CUSTOM_MODEL_WORKERS=$(python -c "from datarobot.core import getenv; print(int(getenv('CUSTOM_MODEL_WORKERS', '1')))")

echo "Executing command: nat dragent serve --config_file $CONFIG_FILE --host 0.0.0.0 --port 8080 --use_gunicorn true --workers $CUSTOM_MODEL_WORKERS $ROOT_PATH_ARG"
echo
# shellcheck disable=SC2086 # ROOT_PATH_ARG must word-split into two arguments
exec nat dragent serve --config_file "$CONFIG_FILE" --host 0.0.0.0 --port 8080 --use_gunicorn true --workers "$CUSTOM_MODEL_WORKERS" $ROOT_PATH_ARG
