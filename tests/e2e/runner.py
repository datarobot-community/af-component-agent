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
E2E orchestration (full lifecycle) for agent frameworks.

This module owns the "do the thing" flow:
render → install → build → validate → deploy → validate → destroy.
"""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from .cli_parsing import (
    assert_response_text_ok,
    extract_cli_response_after_wait,
    verify_openai_response,
)
from .constants import ALL_FRAMEWORKS
from .pulumi import extract_id_from_url, find_output, pulumi_stack_outputs_json
from .rendering import RenderedProject, render_project, validate_rendered_project
from .subprocess_utils import _run_capture, _run_live
from .task_runner import _task_cmd
from .utils import _is_truthy, _response_snippet, _truncate, fprint


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

    # IMPORTANT: default exec env prevents Pulumi from trying to build a docker_context.
    lines = [
        f"DATAROBOT_ENDPOINT={datarobot_endpoint}",
        f"DATAROBOT_API_TOKEN={datarobot_api_token}",
        "DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT=Python 3.11 GenAI Agents",
        "SESSION_SECRET_KEY=test-secret-key",
        f"PULUMI_STACK={pulumi_stack}",
        "PULUMI_CONFIG_PASSPHRASE=",
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
            project = render_project(
                repo_root=self.repo_root, agent_framework=self.agent_framework
            )
        else:
            validate_rendered_project(project, expected_framework=self.agent_framework)
            fprint(f"Using pre-rendered template at: {project.rendered_dir}")

        # Build extra environment variables for the rendered project
        extra_env: dict[str, str] = {
            # Enable DataRobot LLM Gateway for all agents (required for nat, helpful for others)
            # Keep convention consistent with runtime params fixture: "1" is treated as truthy.
            "USE_DATAROBOT_LLM_GATEWAY": "1",
        }
        if self.agent_framework == "crewai":
            extra_env["CREWAI_TESTING"] = "true"

        pulumi_home = project.rendered_dir / ".pulumi_home"
        pulumi_home.mkdir(parents=True, exist_ok=True)

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

        # Use local Pulumi backend to avoid requiring Pulumi Cloud credentials.
        _run_capture(
            ["uv", "run", "pulumi", "login", "--local"],
            cwd=project.infra_dir,
            env={"PULUMI_CONFIG_PASSPHRASE": "", "PULUMI_HOME": str(pulumi_home)},
        )

        try:
            # 1. Install dependencies
            _run_live(_task_cmd("install"), cwd=project.rendered_dir)

            # 2. Build custom model
            _run_live(
                _task_cmd("build", "--", "--yes", "--skip-preview"),
                cwd=project.rendered_dir,
            )

            # 3. Get custom model ID from Pulumi outputs
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

            # 4. Test custom model via CLI
            _retry(
                lambda: self.run_custom_model_execution(
                    user_prompt=user_prompt,
                    custom_model_id=custom_model_id,
                ),
                max_retries=3,
                delay_seconds=60,
                label="Custom model execution",
            )

            # 5. Deploy
            _run_live(
                _task_cmd("deploy", "--", "--yes", "--skip-preview"),
                cwd=project.rendered_dir,
            )

            # 6. Get deployment ID from Pulumi outputs
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

            # 7. Test deployment via CLI
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
        cleanup_env["PULUMI_CONFIG_PASSPHRASE"] = ""
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
                env={"PULUMI_CONFIG_PASSPHRASE": "", "PULUMI_HOME": str(pulumi_home)}
                if pulumi_home is not None
                else {"PULUMI_CONFIG_PASSPHRASE": ""},
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
                env={"PULUMI_CONFIG_PASSPHRASE": "", "PULUMI_HOME": str(pulumi_home)}
                if pulumi_home is not None
                else {"PULUMI_CONFIG_PASSPHRASE": ""},
                check=False,
            )
            if rm_out.strip():
                fprint("Pulumi stack rm output (best-effort):")
                fprint(rm_out.strip())
        finally:
            if env_file and env_file.exists():
                env_file.unlink()


