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
E2E harness for af-component-agent.

This module intentionally consolidates E2E functionality into a single file to
keep maintenance overhead low:
render → install → build → validate → deploy → validate → destroy.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import uuid
from collections import deque
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


def _task_cmd(*args: str) -> list[str]:
    # `uvx --from go-task-bin task`.
    return ["uvx", "--from", "go-task-bin", "task"] + list(args)


def _cmd_timeout_seconds() -> int:
    """
    Default timeout for E2E external commands.

    E2E can take a while (pulumi up + build/deploy), but should not hang forever.
    Configure via E2E_CMD_TIMEOUT_SECONDS. Defaults to 20 minutes.
    """
    raw = os.environ.get("E2E_CMD_TIMEOUT_SECONDS", "").strip()
    if not raw:
        return 20 * 60

    try:
        value = int(raw)
    except ValueError as e:
        raise AssertionError(
            f"Invalid E2E_CMD_TIMEOUT_SECONDS={raw!r} (must be an integer number of seconds)"
        ) from e

    if value <= 0:
        raise AssertionError(
            f"Invalid E2E_CMD_TIMEOUT_SECONDS={raw!r} (must be > 0 seconds)"
        )

    return value


def _tail_text(lines: deque[str], *, max_chars: int) -> str:
    text = "\n".join(lines)
    if len(text) <= max_chars:
        return text

    return text[-max_chars:]


def _run_capture(
    cmd: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    check: bool = True,
    timeout_seconds: int | None = None,
) -> str:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    timeout = _cmd_timeout_seconds() if timeout_seconds is None else timeout_seconds
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=merged_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
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
    timeout_seconds: int | None = None,
) -> str:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    timeout = _cmd_timeout_seconds() if timeout_seconds is None else timeout_seconds
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

    # E2E commands (esp. `pulumi up`) can be very verbose. Keep a bounded in-memory
    # ring buffer so errors include useful context without unbounded memory growth.
    output_lines: deque[str] = deque(maxlen=2000)
    stdout = proc.stdout
    assert stdout is not None

    def _pump_stdout() -> None:
        for line in stdout:
            line = line.rstrip("\n")
            if line:
                print(line, flush=True)
            output_lines.append(line)

    t = threading.Thread(target=_pump_stdout, daemon=True)
    t.start()

    try:
        return_code = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired as e:
        # Best-effort terminate then kill, and include partial output for debugging.
        proc.terminate()
        try:
            return_code = proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            return_code = proc.wait(timeout=5)

        # Give the stdout pump a moment to drain any remaining buffered output.
        t.join(timeout=2)
        if t.is_alive():
            # Best-effort: close stdout to unblock the reader, then try again.
            try:
                stdout.close()
            except OSError:
                pass
            t.join(timeout=2)

        raise AssertionError(
            f"Command timed out after {timeout}s: {' '.join(cmd)}\n\n"
            f"Partial output (tail):\n{_tail_text(output_lines, max_chars=8000)}"
        ) from e

    # Give the stdout pump a moment to drain any remaining buffered output.
    t.join(timeout=2)
    if t.is_alive():
        # Best-effort: close stdout to unblock the reader, then try again.
        try:
            stdout.close()
        except OSError:
            pass
        t.join(timeout=2)

    output = "\n".join(output_lines)
    if check and return_code != 0:
        raise AssertionError(
            f"Command failed (exit {return_code}): {' '.join(cmd)}\n\n"
            f"Output (tail):\n{_tail_text(output_lines, max_chars=8000)}"
        )
    return output


@dataclass(frozen=True)
class RenderedProject:
    agent_framework: str
    repo_root: Path
    rendered_dir: Path
    infra_dir: Path
    agent_dir: Path  # The agent subdirectory within rendered_dir


def validate_rendered_project(project: RenderedProject, *, expected_framework: str) -> None:
    if project.agent_framework != expected_framework:
        raise AssertionError(
            "RenderedProject framework mismatch: "
            f"expected={expected_framework!r} got={project.agent_framework!r}"
        )
    if not project.rendered_dir.exists():
        raise AssertionError(f"Rendered dir missing: {project.rendered_dir}")
    if not project.infra_dir.exists():
        raise AssertionError(f"Rendered infra dir missing: {project.infra_dir}")
    if not project.agent_dir.exists():
        raise AssertionError(f"Rendered agent dir missing: {project.agent_dir}")


def render_project(*, repo_root: Path, agent_framework: str) -> RenderedProject:
    rendered_dir = repo_root / ".rendered" / f"agent_{agent_framework}"
    infra_dir = rendered_dir / "infra"
    agent_dir = rendered_dir / "agent"

    _run_live(_task_cmd("render-template-e2e", f"AGENT={agent_framework}"), cwd=repo_root)

    if not infra_dir.exists():
        raise AssertionError(f"Rendered infra dir missing: {infra_dir}")
    if not agent_dir.exists():
        raise AssertionError(f"Rendered agent dir missing: {agent_dir}")

    return RenderedProject(
        agent_framework=agent_framework,
        repo_root=repo_root,
        rendered_dir=rendered_dir,
        infra_dir=infra_dir,
        agent_dir=agent_dir,
    )


def extract_id_from_url(url: str, *, marker: str) -> str:
    parts = url.strip("/").split("/")
    try:
        idx = parts.index(marker)
    except ValueError as e:
        raise AssertionError(f"URL does not contain '{marker}': {url}") from e
    if idx + 1 >= len(parts):
        raise AssertionError(f"URL missing id after '{marker}': {url}")
    return parts[idx + 1]


def pulumi_stack_outputs_json(
    infra_dir: Path,
    *,
    stack: str,
    pulumi_home: Path | None = None,
) -> dict[str, Any]:
    """
    Read Pulumi stack outputs as JSON.

    IMPORTANT: keep stderr separate so uv/pulumi warnings don't break JSON parsing.
    """
    merged_env = os.environ.copy()
    merged_env.update({"PULUMI_CONFIG_PASSPHRASE": "123"})

    if pulumi_home is not None:
        merged_env["PULUMI_HOME"] = str(pulumi_home)

    proc = subprocess.run(
        ["uv", "run", "pulumi", "stack", "output", "--json", "--stack", stack],
        cwd=str(infra_dir),
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
            "Pulumi stack output returned empty stdout.\n" f"stderr:\n{proc.stderr}"
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
            f"stdout:\n{_truncate(proc.stdout)}\n\nstderr:\n{_truncate(proc.stderr)}"
        )


def find_output(outputs: dict[str, Any], *, contains: str) -> str:
    for key, value in outputs.items():
        if contains in key:
            if not isinstance(value, str):
                raise AssertionError(f"Unexpected output type for '{key}': {type(value)}")
            return value
    raise AssertionError(
        f"Pulumi output not found containing: {contains!r}. Keys: {list(outputs)}"
    )


def extract_cli_response_after_wait(output: str) -> str:
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


def assert_response_text_ok(
    *,
    response_text: str,
    agent_framework: str,
    context: str,
) -> None:
    """Shared validation for text-only responses (e.g., custom-model CLI output)."""
    prefix = f"{context} [{agent_framework}]"

    text = (response_text or "").strip()
    if len(text) <= 5:
        raise AssertionError(f"{prefix}: response too short: {text!r}")

    lowered = text.lower()
    if lowered.startswith("error:") or "failed to obtain agent chat response" in lowered:
        raise AssertionError(f"{prefix}: agent execution returned an error:\n{_truncate(text)}")


def verify_openai_response(cli_output: str) -> None:
    """Verify the CLI output contains a valid OpenAI response (mirrors templates repo)."""
    result = cast(str, cli_output)
    marker = "Execution result:"
    if marker not in result:
        raise AssertionError(
            f"Expected CLI output to contain {marker!r} but it was missing.\n"
            f"Output (truncated): {_truncate(result)}"
        )
    json_result = result.split(marker, 1)[1]
    if "CLI exited with" in json_result:
        json_result = json_result.split("CLI exited with")[0]

    try:
        local_result = cast(dict[str, Any], json.loads(json_result.strip()))
    except json.JSONDecodeError as e:
        raise AssertionError(
            f"Failed to parse CLI output as JSON: {e}\n" f"Output: {_truncate(cli_output)}"
        ) from e

    expected_keys = ["id", "choices", "created", "model", "object"]
    missing_keys = [k for k in expected_keys if k not in local_result]
    if missing_keys:
        raise AssertionError(
            f"Response missing expected keys: {missing_keys}\n"
            f"Got: {list(local_result.keys())}"
        )

    assert len(local_result.get("choices", [])) == 1, (
        f"Expected exactly 1 choice, got {len(local_result.get('choices', []))}"
    )

    message_content = (
        cast(dict[str, Any], local_result["choices"][0]).get("message", {}).get("content", "")
    )
    assert len(message_content) > 5, (f"Message content too short: {message_content!r}")

    fprint("Valid agent response")
    snippet_chars = int(os.environ.get("E2E_RESPONSE_SNIPPET_CHARS", "50"))
    fprint(
        f"Response content (first {snippet_chars} chars): "
        f"{_response_snippet(cast(str, message_content), max_chars=snippet_chars)!r}"
    )
    if _is_truthy(os.environ.get("E2E_DEBUG")):
        fprint(f"Full response content (truncated): {_truncate(cast(str, message_content))}")


def require_e2e_enabled() -> None:
    if not _is_truthy(os.environ.get("RUN_E2E")):
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

    endpoint_lower = datarobot_endpoint.lower()
    token_lower = datarobot_api_token.lower()
    if "test.com" in endpoint_lower or "example.com" in endpoint_lower:
        pytest.fail(
            f"DATAROBOT_ENDPOINT looks like a placeholder ({datarobot_endpoint!r}). "
            "Set it to a real DataRobot API URL (must include '/api/v2')."
        )
    if not datarobot_endpoint.rstrip("/").endswith("/api/v2"):
        pytest.fail(
            f"DATAROBOT_ENDPOINT must include '/api/v2' (got {datarobot_endpoint!r})."
        )
    if token_lower in {"secret", "changeme", "your_token"}:
        pytest.fail(
            "DATAROBOT_API_TOKEN looks like a placeholder. "
            "Set it to a real API token with permissions to create custom models and deployments."
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


def _write_testing_env(
    project: RenderedProject,
    *,
    datarobot_endpoint: str,
    datarobot_api_token: str,
    pulumi_stack: str,
    pulumi_home: Path,
    extra_env: dict[str, str] | None = None,
) -> Path:
    # Our test Taskfile fixture loads `.env`.
    env_path = project.rendered_dir / ".env"

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

    Uses CLI commands (task agent:cli) to execute and test agents.
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

        self._project: RenderedProject | None = None
        self._env_file: Path | None = None
        self._pulumi_stack: str | None = None
        self._pulumi_home: Path | None = None
        self._datarobot_endpoint: str | None = None
        self._datarobot_api_token: str | None = None

    def run(
        self,
        *,
        datarobot_endpoint: str,
        datarobot_api_token: str,
        project: RenderedProject | None = None,
    ) -> None:
        # Step 0: Select prompt + allocate a unique Pulumi stack for this run.
        default_user_prompt = "Write a single tweet (under 280 characters) about AI."
        user_prompt = os.environ.get("E2E_USER_PROMPT", default_user_prompt)

        pulumi_stack = (
            f"af-component-agent-e2e-{self.agent_framework}-{int(time.time())}-{uuid.uuid4().hex[:8]}"
        )

        fprint("==================================================")
        fprint(f"Running Full Deployment E2E for: {self.agent_framework}")
        fprint(f"Pulumi stack: {pulumi_stack}")
        fprint("==================================================")

        if project is None:
            # Step 1: Render template for the selected agent framework.
            project = render_project(
                repo_root=self.repo_root, agent_framework=self.agent_framework
            )
        else:
            # Step 1 (alt): Use a pre-rendered template from the session pre-flight.
            validate_rendered_project(project, expected_framework=self.agent_framework)
            fprint(f"Using pre-rendered template at: {project.rendered_dir}")

        # Step 2: Prepare E2E-specific runtime env (written into rendered project's `.env`).
        extra_env: dict[str, str] = {
            "USE_DATAROBOT_LLM_GATEWAY": "1",
        }
        if self.agent_framework == "crewai":
            extra_env["CREWAI_TESTING"] = "true"

        # Step 3: Create an isolated Pulumi home under the rendered project to avoid
        # shared state and to keep the run self-contained.
        pulumi_home = project.rendered_dir / ".pulumi_home"
        pulumi_home.mkdir(parents=True, exist_ok=True)

        # Step 4: Write the rendered project's `.env` file (Taskfile loads this).
        env_file = _write_testing_env(
            project,
            datarobot_endpoint=datarobot_endpoint,
            datarobot_api_token=datarobot_api_token,
            pulumi_stack=pulumi_stack,
            pulumi_home=pulumi_home,
            extra_env=extra_env,
        )

        self._project = project
        self._env_file = env_file
        self._pulumi_stack = pulumi_stack
        self._pulumi_home = pulumi_home
        self._datarobot_endpoint = datarobot_endpoint
        self._datarobot_api_token = datarobot_api_token

        # Step 5: Ensure Pulumi uses the local backend (no Pulumi Cloud auth needed).
        _run_capture(
            ["uv", "run", "pulumi", "login", "--local"],
            cwd=project.infra_dir,
            env={"PULUMI_CONFIG_PASSPHRASE": "123", "PULUMI_HOME": str(pulumi_home)},
        )

        try:
            # Step 6: Install dependencies in the rendered project (agent + infra).
            _run_live(_task_cmd("install"), cwd=project.rendered_dir)

            # Step 7: Build phase (Pulumi up with AGENT_DEPLOY=0).
            # Creates the Custom Model (and other baseline infra) but not the Deployment.
            _run_live(
                _task_cmd("build", "--", "--yes", "--skip-preview"),
                cwd=project.rendered_dir,
            )

            # Step 8: Read outputs from Pulumi to locate the Custom Model ID.
            outputs = pulumi_stack_outputs_json(
                project.infra_dir,
                stack=pulumi_stack,
                pulumi_home=pulumi_home,
            )
            custom_model_chat_endpoint = find_output(
                outputs, contains="Agent Custom Model Chat Endpoint"
            )
            custom_model_id = extract_id_from_url(
                custom_model_chat_endpoint, marker="fromCustomModel"
            )
            fprint(f"Custom Model ID: {custom_model_id}")

            # Step 9: Execute the Custom Model via CLI and validate response.
            _retry(
                lambda: self.run_custom_model_execution(
                    user_prompt=user_prompt,
                    custom_model_id=custom_model_id,
                ),
                max_retries=3,
                delay_seconds=60,
                label="Custom model execution",
            )

            # Step 10: Deploy phase (Pulumi up with AGENT_DEPLOY=1).
            # Creates the Deployment for the Custom Model.
            _run_live(
                _task_cmd("deploy", "--", "--yes", "--skip-preview"),
                cwd=project.rendered_dir,
            )

            # Step 11: Read outputs from Pulumi to locate the Deployment ID.
            outputs = pulumi_stack_outputs_json(
                project.infra_dir,
                stack=pulumi_stack,
                pulumi_home=pulumi_home,
            )
            deployment_chat_endpoint = find_output(
                outputs, contains="Agent Deployment Chat Endpoint"
            )
            deployment_id = extract_id_from_url(
                deployment_chat_endpoint, marker="deployments"
            )
            fprint(f"Deployment ID: {deployment_id}")

            # Step 12: Execute the Deployment via CLI and validate OpenAI response shape.
            _retry(
                lambda: self.run_deployment_execution(
                    user_prompt=user_prompt,
                    deployment_id=deployment_id,
                ),
                max_retries=3,
                delay_seconds=30,
                label="Deployment execution",
            )

            fprint("Agent execution completed successfully")

        finally:
            # Step 13: Cleanup (Pulumi cancel + destroy + stack rm, and delete rendered `.env`).
            self.cleanup()

    def run_custom_model_execution(self, user_prompt: str, custom_model_id: str) -> None:
        fprint("Running custom model agent execution")
        fprint("====================================")

        assert self._project is not None
        result = _run_capture(
            _task_cmd(
                "agent:cli",
                "--",
                "execute-custom-model",
                "--user_prompt",
                user_prompt,
                "--custom_model_id",
                custom_model_id,
            ),
            cwd=self._project.rendered_dir,
        )

        snippet_chars = int(os.environ.get("E2E_RESPONSE_SNIPPET_CHARS", "50"))
        response_text = extract_cli_response_after_wait(result)
        if not response_text.strip():
            raise AssertionError(
                "Custom model execution: could not extract response text from CLI output. "
                f"Output (truncated): {_truncate(result)}"
            )

        assert_response_text_ok(
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
        fprint("Running deployed agent execution")
        fprint("================================")

        assert self._project is not None
        result = _run_capture(
            _task_cmd(
                "agent:cli",
                "--",
                "execute-deployment",
                "--user_prompt",
                user_prompt,
                "--deployment_id",
                deployment_id,
                "--show_output",
            ),
            cwd=self._project.rendered_dir,
        )

        verify_openai_response(result)

    def cleanup(self) -> None:
        project = self._project
        pulumi_stack = self._pulumi_stack
        pulumi_home = self._pulumi_home
        datarobot_endpoint = self._datarobot_endpoint
        datarobot_api_token = self._datarobot_api_token
        env_file = self._env_file

        cleanup_env: dict[str, str] = {}
        if pulumi_stack:
            cleanup_env["PULUMI_STACK"] = pulumi_stack
        cleanup_env["PULUMI_CONFIG_PASSPHRASE"] = "123"
        if pulumi_home is not None:
            cleanup_env["PULUMI_HOME"] = str(pulumi_home)
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

            _run_capture(
                ["uv", "run", "pulumi", "cancel", "--yes", "--stack", pulumi_stack],
                cwd=project.infra_dir,
                env={"PULUMI_CONFIG_PASSPHRASE": "123", "PULUMI_HOME": str(pulumi_home)}
                if pulumi_home is not None
                else {"PULUMI_CONFIG_PASSPHRASE": "123"},
                check=False,
            )
            _run_live(
                _task_cmd("destroy", "--", "--yes", "--skip-preview"),
                cwd=project.rendered_dir,
                env=cleanup_env,
                check=False,
            )
            fprint(f"Attempting to remove Pulumi stack: {pulumi_stack}")
            rm_out = _run_capture(
                ["uv", "run", "pulumi", "stack", "rm", "-f", "-y", pulumi_stack],
                cwd=project.infra_dir,
                env={"PULUMI_CONFIG_PASSPHRASE": "123", "PULUMI_HOME": str(pulumi_home)}
                if pulumi_home is not None
                else {"PULUMI_CONFIG_PASSPHRASE": "123"},
                check=False,
            )
            if rm_out.strip():
                fprint("Pulumi stack rm output (best-effort):")
                fprint(rm_out.strip())
        finally:
            if env_file and env_file.exists():
                env_file.unlink()


