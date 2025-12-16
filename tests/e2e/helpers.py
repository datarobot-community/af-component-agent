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

import json
import os
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, cast

import pytest

ALL_FRAMEWORKS = ("base", "crewai", "langgraph", "llamaindex", "nat")


def fprint(msg: str) -> None:
    print(msg, flush=True)


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _truncate(text: str, *, max_chars: int = 800) -> str:
    s = (text or "").strip()
    if len(s) <= max_chars:
        return s
    return s[:max_chars] + "…"


def _response_snippet(text: str, *, max_chars: int) -> str:
    """Return a compact one-line snippet for logs."""
    compact = " ".join((text or "").strip().split())
    return _truncate(compact, max_chars=max_chars)


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
    if datarobot_endpoint.rstrip("/").endswith("/api/v2") is False:
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
            project = _render_project(repo_root=repo_root, agent_framework=fw)
            rendered[fw] = project
            fprint(f"    ✓ {fw} rendered successfully")
        except Exception as e:
            fprint(f"    ✗ {fw} FAILED to render: {e}")
            raise AssertionError(f"Failed to render {fw}: {e}") from e

    fprint("\n" + "=" * 60)
    fprint(f"ALL {len(rendered)} FRAMEWORKS RENDERED SUCCESSFULLY")
    fprint("=" * 60 + "\n")

    return rendered


@dataclass(frozen=True)
class RenderedProject:
    repo_root: Path
    rendered_dir: Path
    infra_dir: Path
    agent_dir: Path  # The agent subdirectory within rendered_dir


def _run_capture(
    cmd: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> str:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=merged_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if check and proc.returncode != 0:
        raise AssertionError(
            f"Command failed (exit {proc.returncode}): {' '.join(cmd)}\n\n{proc.stdout}"
        )
    return proc.stdout


def _run_live(
    cmd: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> str:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    fprint(f"$ {' '.join(cmd)}  (cwd={cwd})")
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=merged_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
    )

    output_lines: list[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip("\n")
        if line:
            print(line, flush=True)
        output_lines.append(line)

    return_code = proc.wait()
    output = "\n".join(output_lines)
    if check and return_code != 0:
        raise AssertionError(
            f"Command failed (exit {return_code}): {' '.join(cmd)}\n\n{output}"
        )
    return output


def _extract_cli_response_after_wait(output: str) -> str:
    """
    Best-effort extraction of the "response" from the CLI output for custom-model execution.

    The `task agent:cli -- execute-custom-model` command prints a preamble, then the model
    output, then an exit message. We treat everything after the last "Please wait" line
    as the response body (excluding trailing "CLI exited with ..." lines if present).
    """
    lines = (output or "").splitlines()
    if not lines:
        return ""

    wait_idx = -1
    for i, line in enumerate(lines):
        if "Please wait" in line:
            wait_idx = i
    candidate = lines[wait_idx + 1 :] if wait_idx != -1 else lines

    # Trim trailing footer lines commonly printed by the CLI wrappers.
    trimmed: list[str] = []
    for line in candidate:
        if line.strip().startswith("CLI exited with"):
            break
        trimmed.append(line)

    return "\n".join(trimmed).strip()


def _assert_response_text_ok(
    *,
    response_text: str,
    agent_framework: str,
    context: str,
) -> None:
    """
    Shared validation for text-only responses (e.g., custom-model CLI output).
    """
    text = (response_text or "").strip()
    if len(text) <= 5:
        raise AssertionError(f"{context}: response too short: {text!r}")

    # Templates-style: fail on actual execution errors (even if the wrapper exits 0).
    # We still allow placeholders like "Not written yet." to match recipe templates behavior.
    lowered = text.lower()
    if lowered.startswith("error:") or "failed to obtain agent chat response" in lowered:
        raise AssertionError(f"{context}: agent execution returned an error:\n{_truncate(text)}")
def _extract_id_from_url(url: str, *, marker: str) -> str:
    parts = url.strip("/").split("/")
    try:
        idx = parts.index(marker)
    except ValueError as e:
        raise AssertionError(f"URL does not contain '{marker}': {url}") from e
    if idx + 1 >= len(parts):
        raise AssertionError(f"URL missing id after '{marker}': {url}")
    return parts[idx + 1]


def _pulumi_stack_outputs_json(project: RenderedProject, *, stack: str) -> dict[str, Any]:
    # IMPORTANT: keep stderr separate so uv/pulumi warnings don't break JSON parsing.
    merged_env = os.environ.copy()
    merged_env.update({"PULUMI_CONFIG_PASSPHRASE": ""})

    proc = subprocess.run(
        ["uv", "run", "pulumi", "stack", "output", "--json", "--stack", stack],
        cwd=str(project.infra_dir),
        env=merged_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise AssertionError(
            "Failed to read pulumi stack outputs.\n"
            f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
        )

    stdout = (proc.stdout or "").strip()
    if not stdout:
        raise AssertionError(
            "Pulumi stack output returned empty stdout.\n"
            f"stderr:\n{proc.stderr}"
        )

    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        # Fallback: try to extract the JSON object from noisy stdout.
        start = stdout.find("{")
        end = stdout.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(stdout[start : end + 1])
            except json.JSONDecodeError:
                pass
        raise AssertionError(
            "Failed to parse pulumi outputs JSON.\n"
            f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
        )


def _find_output(outputs: dict[str, Any], *, contains: str) -> str:
    for key, value in outputs.items():
        if contains in key:
            if not isinstance(value, str):
                raise AssertionError(f"Unexpected output type for '{key}': {type(value)}")
            return value
    raise AssertionError(
        f"Pulumi output not found containing: {contains!r}. Keys: {list(outputs)}"
    )


def _render_project(*, repo_root: Path, agent_framework: str) -> RenderedProject:
    rendered_dir = repo_root / ".rendered" / f"agent_{agent_framework}"
    infra_dir = rendered_dir / "infra"
    agent_dir = rendered_dir / "agent"

    _run_live(
        ["task", "render-template", f"AGENT={agent_framework}"],
        cwd=repo_root,
        env=None,
    )

    if not infra_dir.exists():
        raise AssertionError(f"Rendered infra dir missing: {infra_dir}")
    if not agent_dir.exists():
        raise AssertionError(f"Rendered agent dir missing: {agent_dir}")

    return RenderedProject(
        repo_root=repo_root,
        rendered_dir=rendered_dir,
        infra_dir=infra_dir,
        agent_dir=agent_dir,
    )


def _write_testing_env(
    project: RenderedProject,
    *,
    datarobot_endpoint: str,
    datarobot_api_token: str,
    pulumi_stack: str,
    extra_env: dict[str, str] | None = None,
) -> Path:
    # Our test Taskfile fixture loads `.env`.
    env_path = project.rendered_dir / ".env"

    # IMPORTANT: default exec env prevents Pulumi from trying to build a docker_context.
    lines = [
        f"DATAROBOT_ENDPOINT={datarobot_endpoint}",
        f"DATAROBOT_API_TOKEN={datarobot_api_token}",
        "DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT=Python 3.11 GenAI Agents",
        "SESSION_SECRET_KEY=test-secret-key",
        f"PULUMI_STACK={pulumi_stack}",
        "PULUMI_CONFIG_PASSPHRASE=",
    ]
    if extra_env:
        for k, v in extra_env.items():
            lines.append(f"{k}={v}")

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return env_path


def _retry(
    func: Callable[[], Any],
    *,
    max_retries: int,
    delay_seconds: int,
    label: str,
) -> Any:
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                fprint(f"Retrying {label} (attempt {attempt + 1}/{max_retries + 1})...")
            return func()
        except Exception as e:
            last_exc = e
            if attempt >= max_retries:
                raise
            fprint(f"{label} failed: {e}")
            fprint(f"Waiting {delay_seconds}s before retry...")
            time.sleep(delay_seconds)
    raise last_exc or RuntimeError(f"{label} failed")


class AgentE2EHelper:
    """
    E2E test helper for agent frameworks.

    This implementation mirrors recipe-datarobot-agent-templates by using CLI commands
    (task agent:cli) to execute and test agents, rather than direct HTTP calls.
    """

    def __init__(
        self,
        *,
        agent_framework: str,
        repo_root: Path | None = None,
        skip_cleanup: bool | None = None,
    ) -> None:
        if agent_framework not in ALL_FRAMEWORKS:
            raise ValueError(
                f"Unknown agent_framework={agent_framework!r}. Valid: {list(ALL_FRAMEWORKS)}"
            )
        self.agent_framework = agent_framework
        self.repo_root = repo_root or Path(__file__).resolve().parents[2]
        self.skip_cleanup = (
            _is_truthy(os.environ.get("SKIP_CLEANUP"))
            if skip_cleanup is None
            else skip_cleanup
        )

        # filled in during run()
        self._project: RenderedProject | None = None
        self._env_file: Path | None = None
        self._pulumi_stack: str | None = None
        self._datarobot_endpoint: str | None = None
        self._datarobot_api_token: str | None = None

    def run(self, *, datarobot_endpoint: str, datarobot_api_token: str) -> None:
        """
        Run the full E2E test flow:
        1. Render template
        2. Install dependencies
        3. Build (create custom model)
        4. Test custom model via CLI
        5. Deploy (create deployment)
        6. Test deployment via CLI
        7. Cleanup
        """
        # Framework-specific default prompts:
        # - llamaindex: needs a TOPIC (wrapped in "write a detailed report about {topic}")
        # - others: can handle direct instructions
        default_prompts = {
            "llamaindex": "AI trends in 2025",  # Topic for report-style workflow
            "default": "Write a single tweet (under 280 characters) about AI.",
        }
        user_prompt = os.environ.get(
            "E2E_USER_PROMPT",
            default_prompts.get(self.agent_framework, default_prompts["default"]),
        )

        pulumi_stack = (
            f"af-component-agent-e2e-{self.agent_framework}-{int(time.time())}-{uuid.uuid4().hex[:8]}"
        )

        fprint("==================================================")
        fprint(f"Running Full Deployment E2E for: {self.agent_framework}")
        fprint(f"Pulumi stack: {pulumi_stack}")
        fprint("==================================================")

        project = _render_project(repo_root=self.repo_root, agent_framework=self.agent_framework)

        # Build extra environment variables for the rendered project
        extra_env: dict[str, str] = {
            # Enable DataRobot LLM Gateway for all agents (required for nat, helpful for others)
            # Keep convention consistent with runtime params fixture: "1" is treated as truthy.
            "USE_DATAROBOT_LLM_GATEWAY": "1",
        }
        if self.agent_framework == "crewai":
            extra_env["CREWAI_TESTING"] = "true"

        env_file = _write_testing_env(
            project,
            datarobot_endpoint=datarobot_endpoint,
            datarobot_api_token=datarobot_api_token,
            pulumi_stack=pulumi_stack,
            extra_env=extra_env,
        )

        self._project = project
        self._env_file = env_file
        self._pulumi_stack = pulumi_stack
        self._datarobot_endpoint = datarobot_endpoint
        self._datarobot_api_token = datarobot_api_token

        # Use local Pulumi backend to avoid requiring Pulumi Cloud credentials in Codespaces.
        _run_capture(
            ["uv", "run", "pulumi", "login", "--local"],
            cwd=project.infra_dir,
            env={"PULUMI_CONFIG_PASSPHRASE": ""},
        )

        try:
            # 1. Install dependencies
            _run_live(["task", "install"], cwd=project.rendered_dir, env=None)

            # 2. Build custom model
            _run_live(
                ["task", "build", "--", "--yes", "--skip-preview"],
                cwd=project.rendered_dir,
                env=None,
            )

            # 3. Get custom model ID from Pulumi outputs
            outputs = _pulumi_stack_outputs_json(project, stack=pulumi_stack)
            custom_model_chat_endpoint = _find_output(
                outputs, contains="Agent Custom Model Chat Endpoint"
            )
            custom_model_id = _extract_id_from_url(
                custom_model_chat_endpoint, marker="fromCustomModel"
            )
            fprint(f"Custom Model ID: {custom_model_id}")

            # 4. Test custom model via CLI (like templates repo)
            custom_model_retries = 3
            _retry(
                lambda: self.run_custom_model_execution(
                    user_prompt=user_prompt,
                    custom_model_id=custom_model_id,
                ),
                max_retries=custom_model_retries,
                delay_seconds=60,
                label="Custom model execution",
            )

            # 5. Deploy
            _run_live(
                ["task", "deploy", "--", "--yes", "--skip-preview"],
                cwd=project.rendered_dir,
                env=None,
            )

            # 6. Get deployment ID from Pulumi outputs
            outputs = _pulumi_stack_outputs_json(project, stack=pulumi_stack)
            deployment_chat_endpoint = _find_output(
                outputs, contains="Agent Deployment Chat Endpoint"
            )
            deployment_id = _extract_id_from_url(
                deployment_chat_endpoint, marker="deployments"
            )
            fprint(f"Deployment ID: {deployment_id}")

            # 7. Test deployment via CLI (like templates repo)
            deployment_retries = 3
            _retry(
                lambda: self.run_deployment_execution(
                    user_prompt=user_prompt,
                    deployment_id=deployment_id,
                ),
                max_retries=deployment_retries,
                delay_seconds=30,
                label="Deployment execution",
            )

            fprint("Agent execution completed successfully")

        finally:
            self.cleanup()

    def run_custom_model_execution(self, user_prompt: str, custom_model_id: str) -> None:
        """
        Execute the custom model via CLI (mirrors templates repo).

        Uses: task agent:cli -- execute-custom-model --user_prompt "..." --custom_model_id XXX
        """
        fprint("Running custom model agent execution")
        fprint("====================================")

        assert self._project is not None
        # Avoid dumping large model outputs to logs; capture and print a short snippet instead.
        result = _run_capture(
            [
                "task", "agent:cli", "--",
                "execute-custom-model",
                "--user_prompt", user_prompt,
                "--custom_model_id", custom_model_id,
            ],
            cwd=self._project.rendered_dir,
        )

        snippet_chars = int(os.environ.get("E2E_RESPONSE_SNIPPET_CHARS", "50"))
        response_text = _extract_cli_response_after_wait(result)

        # Validate the response (previously this step could silently "pass")
        _assert_response_text_ok(
            response_text=response_text,
            agent_framework=self.agent_framework,
            context="Custom model execution",
        )

        fprint("Custom model execution completed")
        fprint(
            f"Custom model response (first {snippet_chars} chars): "
            f"{_response_snippet(response_text, max_chars=snippet_chars)!r}"
        )
        if _is_truthy(os.environ.get("E2E_DEBUG")):
            fprint(f"CLI output (truncated): {_truncate(result)}")

    def run_deployment_execution(self, user_prompt: str, deployment_id: str) -> None:
        """
        Execute the deployment via CLI (mirrors templates repo).

        Uses: task agent:cli -- execute-deployment --user_prompt "..." --deployment_id XXX --show_output
        """
        fprint("Running deployed agent execution")
        fprint("================================")

        assert self._project is not None
        # Avoid dumping the full OpenAI JSON (which can be huge); capture and print a short snippet instead.
        result = _run_capture(
            [
                "task", "agent:cli", "--",
                "execute-deployment",
                "--user_prompt", user_prompt,
                "--deployment_id", deployment_id,
                "--show_output",
            ],
            cwd=self._project.rendered_dir,
        )

        # Verify the OpenAI response format
        self.verify_openai_response(result)

    def verify_openai_response(self, cli_output: str) -> None:
        """
        Verify the CLI output contains a valid OpenAI response (mirrors templates repo).
        """
        result = cast(str, cli_output)
        json_result = result.split("Execution result:")[-1]
        if "CLI exited with" in json_result:
            json_result = json_result.split("CLI exited with")[0]

        try:
            local_result = json.loads(json_result.strip())
        except json.JSONDecodeError as e:
            raise AssertionError(
                f"Failed to parse CLI output as JSON: {e}\n"
                f"Output: {_truncate(cli_output)}"
            ) from e

        # Verify expected keys
        expected_keys = ["id", "choices", "created", "model", "object"]
        missing_keys = [k for k in expected_keys if k not in local_result]
        if missing_keys:
            raise AssertionError(
                f"Response missing expected keys: {missing_keys}\n"
                f"Got: {list(local_result.keys())}"
            )

        # Check that there are choices in the response
        assert len(local_result.get("choices", [])) == 1, (
            f"Expected exactly 1 choice, got {len(local_result.get('choices', []))}"
        )

        # Check that the message content is non-empty and not an error
        message_content = local_result["choices"][0].get("message", {}).get("content", "")
        assert len(message_content) > 5, (
            f"Message content too short: {message_content!r}"
        )

        fprint("Valid agent response")
        snippet_chars = int(os.environ.get("E2E_RESPONSE_SNIPPET_CHARS", "50"))
        fprint(
            f"Response content (first {snippet_chars} chars): "
            f"{_response_snippet(message_content, max_chars=snippet_chars)!r}"
        )
        if _is_truthy(os.environ.get("E2E_DEBUG")):
            fprint(f"Full response content (truncated): {_truncate(message_content)}")

    def cleanup(self) -> None:
        project = self._project
        pulumi_stack = self._pulumi_stack
        datarobot_endpoint = self._datarobot_endpoint
        datarobot_api_token = self._datarobot_api_token
        env_file = self._env_file

        cleanup_env: dict[str, str] = {}
        if pulumi_stack:
            cleanup_env["PULUMI_STACK"] = pulumi_stack
        # Pulumi local secrets manager needs the passphrase variable present.
        cleanup_env["PULUMI_CONFIG_PASSPHRASE"] = ""
        if datarobot_endpoint:
            cleanup_env["DATAROBOT_ENDPOINT"] = datarobot_endpoint
        if datarobot_api_token:
            cleanup_env["DATAROBOT_API_TOKEN"] = datarobot_api_token
        cleanup_env.setdefault(
            "DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT", "Python 3.11 GenAI Agents"
        )
        cleanup_env.setdefault("SESSION_SECRET_KEY", "test-secret-key")
        if self.agent_framework == "crewai":
            cleanup_env.setdefault("CREWAI_TESTING", "true")

        try:
            if self.skip_cleanup:
                fprint("SKIP_CLEANUP is set, skipping Pulumi destroy/stack rm")
                return

            if not project or not pulumi_stack:
                return

            # Best-effort cleanup; avoid leaking resources even if assertions fail.
            _run_capture(
                ["uv", "run", "pulumi", "cancel", "--yes", "--stack", pulumi_stack],
                cwd=project.infra_dir,
                env={"PULUMI_CONFIG_PASSPHRASE": ""},
                check=False,
            )
            _run_live(
                ["task", "destroy", "--", "--yes", "--skip-preview"],
                cwd=project.rendered_dir,
                env=cleanup_env,
                check=False,
            )
            _run_capture(
                ["uv", "run", "pulumi", "stack", "rm", "-f", "-y", pulumi_stack],
                cwd=project.infra_dir,
                env={"PULUMI_CONFIG_PASSPHRASE": ""},
                check=False,
            )
        finally:
            # Always remove rendered .env to avoid leaving credentials on disk.
            if env_file and env_file.exists():
                env_file.unlink()


