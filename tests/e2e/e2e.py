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
E2E for af-component-agent.
"""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

import pytest

from .helpers import (
    ALL_FRAMEWORKS,
    assert_response_text_ok,
    extract_cli_response_after_wait,
    extract_id_from_url,
    extract_output_url,
    render_project,
    require_datarobot_env,
    require_e2e_enabled,
    should_run_framework,
    verify_openai_response,
    write_testing_env,
)
from ._process import (
    fprint,
    is_truthy,
    response_snippet,
    retry,
    run_capture,
    run_live,
    task_cmd,
    truncate,
)


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
            is_truthy(os.environ.get("SKIP_CLEANUP")) if skip_cleanup is None else skip_cleanup
        )

        self._rendered_dir: Path | None = None
        self._infra_dir: Path | None = None
        self._env_file: Path | None = None
        self._pulumi_stack: str | None = None
        self._pulumi_home: Path | None = None
        self._datarobot_endpoint: str | None = None
        self._datarobot_api_token: str | None = None

    def run(self, *, datarobot_endpoint: str, datarobot_api_token: str) -> None:
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

        # Step 1: Render the template for the selected agent framework.
        rendered_dir, infra_dir = render_project(
            repo_root=self.repo_root, agent_framework=self.agent_framework
        )

        # Step 2: Prepare E2E-specific runtime env (written into rendered project's `.env`).
        extra_env: dict[str, str] = {"USE_DATAROBOT_LLM_GATEWAY": "1"}
        if self.agent_framework == "crewai":
            extra_env["CREWAI_TESTING"] = "true"

        # Step 3: Create an isolated Pulumi home under the rendered project to avoid shared state.
        pulumi_home = rendered_dir / ".pulumi_home"
        pulumi_home.mkdir(parents=True, exist_ok=True)

        # Step 4: Write the rendered project's `.env` file (Taskfile loads this).
        env_file = write_testing_env(
            rendered_dir,
            datarobot_endpoint=datarobot_endpoint,
            datarobot_api_token=datarobot_api_token,
            pulumi_stack=pulumi_stack,
            pulumi_home=pulumi_home,
            extra_env=extra_env,
        )

        self._rendered_dir = rendered_dir
        self._infra_dir = infra_dir
        self._env_file = env_file
        self._pulumi_stack = pulumi_stack
        self._pulumi_home = pulumi_home
        self._datarobot_endpoint = datarobot_endpoint
        self._datarobot_api_token = datarobot_api_token

        # Step 5: Ensure Pulumi uses the local backend (no Pulumi Cloud auth needed).
        run_capture(
            ["uv", "run", "pulumi", "login", "--local"],
            cwd=infra_dir,
            env={"PULUMI_CONFIG_PASSPHRASE": "123", "PULUMI_HOME": str(pulumi_home)},
        )

        try:
            # Step 6: Install dependencies in the rendered project (agent + infra).
            run_live(task_cmd("install"), cwd=rendered_dir)

            # Step 7: Build phase (Pulumi up with AGENT_DEPLOY=0).
            # Creates the Custom Model (and baseline infra) but not the Deployment.
            build_output = run_live(
                task_cmd("build", "--", "--yes", "--skip-preview"),
                cwd=rendered_dir,
            )

            # Step 8: Parse the Custom Model ID from `task build` stdout (templates-style shortcut).
            custom_model_chat_endpoint = extract_output_url(
                build_output, contains="Custom Model Chat Endpoint"
            )
            custom_model_id = extract_id_from_url(custom_model_chat_endpoint, marker="fromCustomModel")
            fprint(f"Custom Model ID: {custom_model_id}")

            # Step 9: Execute the Custom Model and validate the response.
            retry(
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
            deploy_output = run_live(
                task_cmd("deploy", "--", "--yes", "--skip-preview"),
                cwd=rendered_dir,
            )

            # Step 11: Parse the Deployment ID from `task deploy` stdout (templates-style shortcut).
            deployment_chat_endpoint = extract_output_url(
                deploy_output, contains="Deployment Chat Endpoint"
            )
            deployment_id = extract_id_from_url(deployment_chat_endpoint, marker="deployments")
            fprint(f"Deployment ID: {deployment_id}")

            # Step 12: Execute the Deployment and validate OpenAI response shape.
            retry(
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

        rendered_dir = self._rendered_dir
        if rendered_dir is None:
            pytest.fail("Internal error: rendered_dir missing")
        result = run_capture(
            task_cmd(
                "agent:cli",
                "--",
                "execute-custom-model",
                "--user_prompt",
                user_prompt,
                "--custom_model_id",
                custom_model_id,
            ),
            cwd=rendered_dir,
        )

        snippet_chars = int(os.environ.get("E2E_RESPONSE_SNIPPET_CHARS", "50"))
        response_text = extract_cli_response_after_wait(result)
        if not response_text.strip():
            pytest.fail(
                "Custom model execution: could not extract response text from CLI output. "
                f"Output (truncated): {truncate(result)}"
            )

        assert_response_text_ok(
            response_text=response_text,
            agent_framework=self.agent_framework,
            context="Custom model execution",
        )

        fprint("Custom model execution completed")
        fprint(
            f"Custom model response (first {snippet_chars} chars): "
            f"{response_snippet(response_text, max_chars=snippet_chars)!r}"
        )
        if is_truthy(os.environ.get("E2E_DEBUG")):
            fprint(f"CLI output (truncated): {truncate(result)}")

    def run_deployment_execution(self, user_prompt: str, deployment_id: str) -> None:
        fprint("Running deployed agent execution")
        fprint("================================")

        rendered_dir = self._rendered_dir
        if rendered_dir is None:
            pytest.fail("Internal error: rendered_dir missing")
        result = run_capture(
            task_cmd(
                "agent:cli",
                "--",
                "execute-deployment",
                "--user_prompt",
                user_prompt,
                "--deployment_id",
                deployment_id,
                "--show_output",
            ),
            cwd=rendered_dir,
        )

        verify_openai_response(result)

    def cleanup(self) -> None:
        rendered_dir = self._rendered_dir
        infra_dir = self._infra_dir
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

            if not rendered_dir or not infra_dir or not pulumi_stack:
                return

            run_capture(
                ["uv", "run", "pulumi", "cancel", "--yes", "--stack", pulumi_stack],
                cwd=infra_dir,
                env={"PULUMI_CONFIG_PASSPHRASE": "123", "PULUMI_HOME": str(pulumi_home)}
                if pulumi_home is not None
                else {"PULUMI_CONFIG_PASSPHRASE": "123"},
                check=False,
            )
            run_live(
                task_cmd("destroy", "--", "--yes", "--skip-preview"),
                cwd=rendered_dir,
                env=cleanup_env,
                check=False,
            )
            fprint(f"Attempting to remove Pulumi stack: {pulumi_stack}")
            rm_out = run_capture(
                ["uv", "run", "pulumi", "stack", "rm", "-f", "-y", pulumi_stack],
                cwd=infra_dir,
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

__all__ = [
    "ALL_FRAMEWORKS",
    "AgentE2EHelper",
    "fprint",
    "require_datarobot_env",
    "require_e2e_enabled",
    "should_run_framework",
]


