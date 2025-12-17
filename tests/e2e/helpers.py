# Copyright 2025 DataRobot, Inc.
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

"""
E2E test helpers for af-component-agent.

This implementation mirrors the approach used in recipe-datarobot-agent-templates:
- Uses CLI commands (task agent:cli) instead of direct HTTP calls
- Verifies OpenAI-compatible responses
- Retries on transient failures
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from .constants import ALL_FRAMEWORKS
from .rendering import RenderedProject, render_project
from .runner import AgentE2EHelper
from .utils import _is_truthy, fprint

__all__ = [
    "ALL_FRAMEWORKS",
    "AgentE2EHelper",
    "RenderedProject",
    "_is_truthy",
    "fprint",
    "render_all_selected_frameworks",
    "require_datarobot_env",
    "require_e2e_enabled",
    "selected_frameworks",
    "should_run_framework",
]


def _load_dotenv(path: Path) -> None:
    """
    Minimal .env loader (no extra dependencies).

    - Supports `KEY=VALUE` and `export KEY=VALUE`
    - Ignores blank lines and `#` comments
    - Does not override existing process env vars
    """
    if not path.exists():
        return

    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return

    # Collect values first so later lines override earlier ones (standard dotenv behavior).
    values: dict[str, str] = {}

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue

        # Strip simple quotes
        if len(value) >= 2 and (
            (value.startswith('"') and value.endswith('"'))
            or (value.startswith("'") and value.endswith("'"))
        ):
            value = value[1:-1]

        values[key] = value

    # Do not override existing environment variables.
    for key, value in values.items():
        os.environ.setdefault(key, value)


def require_e2e_enabled() -> None:
    if not _is_truthy(os.environ.get("RUN_E2E")):
        pytest.skip("Set RUN_E2E=1 to enable full deployment E2E tests.")


def require_datarobot_env() -> tuple[str, str]:
    # If not exported, try to load from repo-root `.env` (gitignored).
    repo_root = Path(__file__).resolve().parents[2]
    env_path = repo_root / ".env"

    before_endpoint = os.environ.get("DATAROBOT_ENDPOINT")
    before_token = os.environ.get("DATAROBOT_API_TOKEN")
    _load_dotenv(env_path)

    datarobot_endpoint = os.environ.get("DATAROBOT_ENDPOINT", "").strip()
    datarobot_api_token = os.environ.get("DATAROBOT_API_TOKEN", "").strip()
    missing: list[str] = []
    if not datarobot_endpoint:
        missing.append("DATAROBOT_ENDPOINT")
    if not datarobot_api_token:
        missing.append("DATAROBOT_API_TOKEN")
    if missing:
        if env_path.exists():
            pytest.fail(
                f"Missing required environment variables: {', '.join(missing)}. "
                f"Set them in the environment or add them to {env_path} (gitignored)."
            )
        pytest.fail(
            f"Missing required environment variables: {', '.join(missing)}. "
            f"No .env file found at {env_path}. Create it (gitignored) or export the variables."
        )

    # Fast-fail on common placeholder values so we don't spend minutes installing deps.
    endpoint_lower = datarobot_endpoint.lower()
    token_lower = datarobot_api_token.lower()
    if "test.com" in endpoint_lower or "example.com" in endpoint_lower:
        source = "process environment" if before_endpoint else str(env_path)
        pytest.fail(
            f"DATAROBOT_ENDPOINT looks like a placeholder ({datarobot_endpoint!r}). "
            f"Source: {source}. Set it to a real DataRobot API URL (must include '/api/v2')."
        )
    if not datarobot_endpoint.rstrip("/").endswith("/api/v2"):
        pytest.fail(
            f"DATAROBOT_ENDPOINT must include '/api/v2' (got {datarobot_endpoint!r})."
        )
    if token_lower in {"secret", "changeme", "your_token"}:
        source = "process environment" if before_token else str(env_path)
        pytest.fail(
            "DATAROBOT_API_TOKEN looks like a placeholder. "
            f"Source: {source}. Set it to a real API token with permissions to create custom models and deployments."
        )
    return datarobot_endpoint, datarobot_api_token


def selected_frameworks() -> list[str]:
    raw = os.environ.get("E2E_AGENT_FRAMEWORKS", "").strip()
    if not raw:
        return list(ALL_FRAMEWORKS)

    frameworks = [x.strip() for x in raw.split(",") if x.strip()]
    unknown = sorted(set(frameworks) - set(ALL_FRAMEWORKS))
    if unknown:
        raise ValueError(
            f"Unknown framework(s) in E2E_AGENT_FRAMEWORKS={raw!r}: {unknown}. "
            f"Valid: {list(ALL_FRAMEWORKS)}"
        )
    return frameworks


def should_run_framework(framework: str) -> bool:
    return framework in set(selected_frameworks())


def render_all_selected_frameworks() -> dict[str, RenderedProject]:
    """
    Pre-render all selected agent frameworks.

    This is called once at session start to validate all templates render
    successfully before any E2E tests begin. Returns a dict mapping
    framework name to its RenderedProject.
    """
    repo_root = Path(__file__).resolve().parents[2]
    frameworks = selected_frameworks()

    fprint("=" * 60)
    fprint(f"PRE-RENDERING ALL SELECTED FRAMEWORKS: {frameworks}")
    fprint("=" * 60)

    rendered: dict[str, RenderedProject] = {}
    for fw in frameworks:
        fprint(f"\n>>> Rendering template: {fw}")
        try:
            project = render_project(repo_root=repo_root, agent_framework=fw)
            rendered[fw] = project
            fprint(f"    ✓ {fw} rendered successfully")
        except Exception as e:
            fprint(f"    ✗ {fw} FAILED to render: {e}")
            raise AssertionError(f"Failed to render {fw}: {e}") from e

    fprint("\n" + "=" * 60)
    fprint(f"ALL {len(rendered)} FRAMEWORKS RENDERED SUCCESSFULLY")
    fprint("=" * 60 + "\n")

    return rendered
