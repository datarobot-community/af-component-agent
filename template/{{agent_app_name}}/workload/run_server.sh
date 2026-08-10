#!/bin/sh
# Entrypoint for the Workload API C2W scenario with a platform-generated
# Dockerfile (see infra/{{agent_app_name}}_infra/workload.py). The generated
# Dockerfile runs `uv sync` against uv.lock to install this agent's *dependencies*
# into the dropin execution environment's venv, but does not install the agent
# package itself -- that happens here, at container start, because the agent's
# source only lands in the image via this build.
#
# Lives under workload/ (not the application root) to make explicit that it
# only applies to this scenario. Invoked as `sh workload/run_server.sh` with
# the application root as the working directory, so relative paths below
# (e.g. `.` for `uv pip install`, `workflow.yaml`) still resolve there.
#
# Not used by the default Custom Models path.
set -eu

AGENT_PKG_DIR="/tmp/agent-pkgs"
mkdir -p "$AGENT_PKG_DIR"

echo "Installing agent"
# No root access in the dropin execution environment at deploy time, and no
# writable uv cache there either -- UV_NO_CACHE=1 plus an explicit --target
# avoid both. --no-deps is safe: all other dependencies were already
# installed into the image at build time from uv.lock.
UV_NO_CACHE=1 uv pip install --no-deps \
    --python /app/.venv/bin/python \
    --target "$AGENT_PKG_DIR" \
    .

export PYTHONPATH="${AGENT_PKG_DIR}${PYTHONPATH:+:${PYTHONPATH}}"

echo "Running nat dragent serve"
exec nat dragent serve --config_file workflow.yaml --host 0.0.0.0 --port "${WORKLOAD_CONTAINER_PORT:-8080}" --use_gunicorn true
