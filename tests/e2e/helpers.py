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
Internal helpers for E2E tests.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ._process import fprint, is_truthy, response_snippet, run_cmd, task_cmd

ALL_FRAMEWORKS = ("base", "crewai", "langgraph", "llamaindex", "nat")
RESPONSE_SNIPPET_CHARS = 50


def render_project(*, repo_root: Path, agent_framework: str) -> tuple[Path, Path]:
    rendered_dir = repo_root / ".rendered" / f"agent_{agent_framework}"
    infra_dir = rendered_dir / "infra"

    run_cmd(task_cmd("render-template-e2e", f"AGENT={agent_framework}"), cwd=repo_root)

    if not infra_dir.exists():
        pytest.fail(f"Rendered infra dir missing: {infra_dir}")

    # Verify that the AGENTS.md file exists
    agents_md_file = rendered_dir / "agent" / "AGENTS.md"
    if not agents_md_file.exists():
        pytest.fail(f"Rendered AGENTS.md file missing: {agents_md_file}")

    # Verify that the agent directory exists
    # This directory is referenced in the AGENTS.md file
    # Make sure to update the AGENTS.md file if the structure changes
    agent_dir = rendered_dir / "agent" / "agent"
    if not agent_dir.exists():
        pytest.fail(f"Rendered agent dir missing: {agent_dir}")


    return rendered_dir, infra_dir


def extract_id_from_url(url: str, *, marker: str) -> str:
    parts = url.strip("/").split("/")
    try:
        idx = parts.index(marker)
    except ValueError:
        pytest.fail(f"URL does not contain '{marker}': {url}")
    if idx + 1 >= len(parts):
        pytest.fail(f"URL missing id after '{marker}': {url}")
    return parts[idx + 1]


def pulumi_stack_output_value(
    *,
    infra_dir: Path,
    pulumi_stack: str,
    pulumi_home: Path,
    contains: str,
) -> str:
    raw = run_cmd(
        ["uv", "run", "pulumi", "stack", "output", "--json", "--stack", pulumi_stack],
        cwd=infra_dir,
        env={"PULUMI_CONFIG_PASSPHRASE": "123", "PULUMI_HOME": str(pulumi_home)},
        capture=True,
    )

    try:
        outputs = json.loads((raw or "").strip() or "{}")
    except json.JSONDecodeError as e:
        pytest.fail(f"Failed to parse `pulumi stack output --json`: {e}\n{raw}")

    if not isinstance(outputs, dict):
        pytest.fail(f"Unexpected `pulumi stack output --json` shape.\nType: {type(outputs)}\n{raw}")

    matches = [k for k in outputs.keys() if contains in k]
    if not matches:
        pytest.fail(f"Could not find Pulumi stack output key containing {contains!r}.")

    val = outputs[matches[-1]]
    if not isinstance(val, str) or not val.strip():
        pytest.fail(
            f"Pulumi stack output value for {matches[-1]!r} was not a non-empty string: {val!r}"
        )
    return val.strip()


def extract_cli_response_after_wait(output: str) -> str:
    """
    Best-effort extraction of the "response" from the CLI output for custom-model execution.

    Supports both variants:
    - "Execution result:" JSON block
    - Text response after the last "Please wait" line
    """
    text = (output or "").strip()
    if not text:
        return ""

    if "Execution result:" in text:
        candidate = text.split("Execution result:", 1)[1]
    else:
        lines = text.splitlines()
        wait_idxs = [i for i, line in enumerate(lines) if "Please wait" in line]
        start = wait_idxs[-1] + 1 if wait_idxs else 0
        candidate = "\n".join(lines[start:])

    # Trim trailing footer lines commonly printed by the CLI wrappers.
    trimmed: list[str] = []
    for line in candidate.splitlines():
        if line.strip().startswith("CLI exited with"):
            break
        trimmed.append(line)

    return "\n".join(trimmed).strip()


def assert_response_text_ok(*, response_text: str, agent_framework: str, context: str) -> None:
    prefix = f"{context} [{agent_framework}]"

    text = (response_text or "").strip()
    if len(text) <= 5:
        pytest.fail(f"{prefix}: response too short: {text!r}")

    lowered = text.lower()
    if lowered.startswith("error:") or "failed to obtain agent chat response" in lowered:
        pytest.fail(f"{prefix}: agent execution returned an error:\n{text}")


def verify_openai_response(cli_output: str) -> None:
    """Verify the CLI output contains a JSON OpenAI-like response with message content."""
    marker = "Execution result:"
    if marker not in cli_output:
        pytest.fail(
            f"Expected CLI output to contain {marker!r} but it was missing.\n{cli_output}"
        )
    json_result = cli_output.split(marker, 1)[1]
    if "CLI exited with" in json_result:
        json_result = json_result.split("CLI exited with")[0]

    try:
        local_result = json.loads(json_result.strip())
    except json.JSONDecodeError as e:
        pytest.fail(f"Failed to parse CLI output as JSON: {e}\nOutput:\n{cli_output}")

    try:
        message_content = local_result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        pytest.fail(
            "Response JSON did not include choices[0].message.content.\n"
            f"Error: {e}\n"
            f"Top-level keys: {list(local_result.keys()) if isinstance(local_result, dict) else type(local_result)}"
        )

    if not isinstance(message_content, str) or len(message_content.strip()) <= 5:
        pytest.fail(f"Message content too short: {message_content!r}")

    fprint("Valid agent response")
    fprint(
        f"Response content (first {RESPONSE_SNIPPET_CHARS} chars): "
        f"{response_snippet(message_content, max_chars=RESPONSE_SNIPPET_CHARS)!r}"
    )
    if is_truthy(os.environ.get("E2E_DEBUG")):
        fprint(f"Full response content:\n{message_content}")


def require_e2e_enabled() -> None:
    if not is_truthy(os.environ.get("RUN_E2E")):
        pytest.skip("Set RUN_E2E=1 to enable full deployment E2E tests.")


def require_datarobot_env() -> tuple[str, str]:
    datarobot_endpoint = os.environ.get("DATAROBOT_ENDPOINT", "").strip()
    datarobot_api_token = os.environ.get("DATAROBOT_API_TOKEN", "").strip()
    missing: list[str] = []
    if not datarobot_endpoint:
        missing.append("DATAROBOT_ENDPOINT")
    if not datarobot_api_token:
        missing.append("DATAROBOT_API_TOKEN")
    if missing:
        pytest.fail(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Export them in your shell or run via `task test-e2e` (which can source a local `.env`)."
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


def write_testing_env(
    rendered_dir: Path,
    *,
    datarobot_endpoint: str,
    datarobot_api_token: str,
    pulumi_stack: str,
    pulumi_home: Path,
    extra_env: dict[str, str] | None = None,
) -> Path:
    # Our test Taskfile fixture loads `.env`.
    env_path = rendered_dir / ".env"

    lines = [
        f"DATAROBOT_ENDPOINT={datarobot_endpoint}",
        f"DATAROBOT_API_TOKEN={datarobot_api_token}",
        "DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT=Python 3.11 GenAI Agents",
        "SESSION_SECRET_KEY=test-secret-key",
        f"PULUMI_STACK={pulumi_stack}",
        "PULUMI_CONFIG_PASSPHRASE=123",
        f"PULUMI_HOME={pulumi_home}",
    ]
    if extra_env:
        for k, v in extra_env.items():
            lines.append(f"{k}={v}")

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return env_path
