# syntax=docker/dockerfile:1
#
# Workload API "C2W + custom Dockerfile with a generic base image" scenario
# (see infra/{{agent_app_name}}_infra/workload.py and the agent README). Used only
# when ENABLE_AGENT_ON_WORKLOAD_API=true and this Dockerfile is present (or
# WORKLOAD_DOCKERFILE_PATH points elsewhere) -- the default Custom Models path
# never reads this file; its execution environment comes from ../docker_context
# (see the create-docker-context Task), not from here.

FROM python:3.11-slim

# Install uv (fast Python package manager) directly from its official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Basic system deps some Python packages (e.g. crewai/ragas transitive deps) may need at build time
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency manifests first for better layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies only, before copying source, to maximize Docker layer cache reuse
RUN uv sync --frozen --no-install-project

# Copy the rest of the agent component: source package, workflow config, entrypoint
COPY agent/ ./agent/
COPY workflow.yaml ./

# Now install the local 'agent' project itself (registers entry points, e.g. nat.plugins)
RUN uv sync --frozen

# The cluster runs this container as a non-root UID with no writable home directory.
# uv (and potentially other tools) default to caching under $HOME, which fails with
# "Permission denied" if $HOME is unset or unwritable for that UID. Pin both explicitly
# to a directory we own and make world-writable, so this works regardless of the UID
# the platform assigns at runtime.
ENV HOME=/app
ENV UV_CACHE_DIR=/app/.uv-cache
RUN mkdir -p /app/.uv-cache && chmod -R 777 /app

EXPOSE 8080

# IMPORTANT: invoke the venv's binary by absolute path, not via `uv run`.
# Some deployment platforms don't preserve the image's built-in $PATH at container
# runtime, which can make a bare `uv`/`nat` lookup fail with
# "exec: <binary>: executable file not found in $PATH" even though the same
# image runs fine locally with `docker run`. Absolute paths sidestep that
# entirely since they don't depend on $PATH resolution at exec time.
CMD ["/app/.venv/bin/nat", "dragent", "serve", "--config_file", "workflow.yaml", "--host", "0.0.0.0", "--port", "8080", "--use_gunicorn", "true"]
