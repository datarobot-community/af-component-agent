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

"""
E2E for af-component-agent.
"""

from __future__ import annotations

import datetime as dt
import os
import time
import uuid
from pathlib import Path
from typing import cast

import backoff
import datarobot as dr
import pytest
import requests
from datarobot.errors import ClientError, ServerError
from datarobot.models.genai.comparison_chat import ComparisonChat
from datarobot.models.genai.comparison_prompt import ComparisonPrompt
from datarobot.models.genai.llm_blueprint import LLMBlueprint
from datarobot.rest import RESTClientObject
from openai.types.chat import ChatCompletion

from datarobot_genai.core.cli import AgentEnvironment

from .helpers import (
    ALL_FRAMEWORKS,
    extract_id_from_url,
    pulumi_stack_output_value,
    render_project,
    require_datarobot_env,
    require_e2e_enabled,
    should_run_framework,
    verify_openai_response,
    write_testing_env,
)
from ._process import (
    RETRYABLE_DR_STATUS_CODES,
    fprint,
    is_truthy,
    retry,
    run_cmd,
    task_cmd,
)


# Span every framework emits when the agent workflow runs (NAT's WORKFLOW_COMPONENT_NAME).
# Its presence in a trace proves the agent ran, regardless of the trace's root span.
_AGENT_WORKFLOW_SPAN = "<workflow>"


# backoff giveup: retry transient statuses and transport blips, stop on the rest.
@backoff.on_exception(
    backoff.expo,
    (ClientError, ServerError, requests.RequestException),
    max_tries=5,
    giveup=lambda exc: isinstance(exc, (ClientError, ServerError))
    and exc.status_code not in RETRYABLE_DR_STATUS_CODES,
)
def _trace_api_get(
    client: RESTClientObject, path: str, params: dict | None = None
) -> dict:
    """GET a trace endpoint -> parsed JSON, retrying transient errors (see decorator)."""
    return client.get(path, params=params, timeout=30).json()


def _trace_span_names(client: RESTClientObject, trace_path: str) -> list[str]:
    """Span names for one trace; [] if the detail fetch errors (skips the candidate)."""
    try:
        payload = _trace_api_get(client, trace_path)
    except (ClientError, ServerError, requests.RequestException):
        return []
    return [n for s in (payload.get("spans") or []) if (n := s.get("name")) is not None]


def _list_recent_traces(
    client: RESTClientObject, traces_path: str, start_time: str
) -> list[dict]:
    """Recent traces for an entity, newest first (GET health probes included)."""
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = _trace_api_get(
        client,
        traces_path,
        params={
            "startTime": start_time,
            "endTime": now,
            "sortBy": "timestamp",
            "sortDirection": "desc",
            "limit": 500,
        },
    )
    return payload.get("data") or []


def _assert_agent_workflow_trace(
    *,
    client: RESTClientObject,
    traces_path: str,
    entity: str,
    timeout_s: int = 300,
    poll_s: int = 15,
) -> None:
    """Poll an OTel traces endpoint until a non-probe trace has _AGENT_WORKFLOW_SPAN."""
    start_time = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    roots_seen: set[str] = set()
    deadline = time.monotonic() + timeout_s
    while True:
        traces = _list_recent_traces(client, traces_path, start_time)
        roots_seen.update(t.get("rootSpanName") or "" for t in traces)
        # The agent run traces under a non-GET root; GET roots are health probes.
        candidates = [
            t for t in traces if not (t.get("rootSpanName") or "").startswith("GET")
        ]
        fprint(f"{entity}: {len(traces)} traces, {len(candidates)} candidate(s)")
        for t in candidates:
            trace_id = t.get("traceId")
            if trace_id and _AGENT_WORKFLOW_SPAN in _trace_span_names(
                client, f"{traces_path}{trace_id}"
            ):
                fprint(f"{entity}: found {_AGENT_WORKFLOW_SPAN} in trace {trace_id}")
                return
        if time.monotonic() >= deadline:
            pytest.fail(
                f"No agent trace with {_AGENT_WORKFLOW_SPAN} for {entity} after {timeout_s}s "
                f"({traces_path}). Roots seen: {sorted(roots_seen)}."
            )
        time.sleep(poll_s)


def _assert_comparison_prompt_completed(prompt: ComparisonPrompt) -> None:
    """Fail unless a result reached COMPLETED without an error.

    result_text is just "streaming success" for streaming agents, so we key on the
    SDK's framework-agnostic execution_status / error_message instead.
    """
    results = prompt.results or []
    completed = [r for r in results if r.execution_status == "COMPLETED"]
    if not completed:
        statuses = [r.execution_status for r in results]
        pytest.fail(
            f"ComparisonPrompt {prompt.id} did not complete: statuses={statuses}"
        )

    for result in completed:
        meta = result.result_metadata
        if meta is not None and meta.error_message:
            pytest.fail(
                f"ComparisonPrompt {prompt.id} result {result.id} returned an error: "
                f"{meta.error_message}"
            )


def _verify_codespace_run(
    *,
    playground_id: str,
    use_case_id: str,
    user_prompt: str,
    datarobot_endpoint: str,
    datarobot_api_token: str,
) -> None:
    """Run the agent via a playground ComparisonPrompt, then assert it completed and
    traced to the use-case OTel view (a ComparisonPrompt traces there; a direct chat
    endpoint call does not).
    """
    client = dr.Client(endpoint=datarobot_endpoint, token=datarobot_api_token)
    fprint("Verifying codespace (agentic-playground) run + traces")
    fprint("=====================================================")
    blueprints = LLMBlueprint.list(playground=playground_id)
    if not blueprints:
        pytest.fail(f"No LLM blueprint found in playground {playground_id}.")

    chat = ComparisonChat.create(
        name="e2e trace verification", playground=playground_id
    )
    try:
        prompt = ComparisonPrompt.create(
            llm_blueprints=[blueprints[0].id],
            text=user_prompt,
            comparison_chat=chat.id,
            wait_for_completion=True,
        )
        _assert_comparison_prompt_completed(prompt)
        _assert_agent_workflow_trace(
            client=client,
            traces_path=f"otel/use_case/{use_case_id}/traces/",
            entity=f"Codespace use_case {use_case_id}",
        )
    finally:
        try:
            chat.delete()
        except Exception as e:
            fprint(f"Best-effort ComparisonChat cleanup failed (ignored): {e}")


def _verify_deployment_run(
    *,
    user_prompt: str,
    deployment_id: str,
    datarobot_endpoint: str,
    datarobot_api_token: str,
) -> None:
    fprint("Running deployed agent execution")
    fprint("================================")
    client = dr.Client(endpoint=datarobot_endpoint, token=datarobot_api_token)
    kernel = AgentEnvironment(
        api_token=datarobot_api_token, base_url=datarobot_endpoint
    ).interface
    completion = cast(
        ChatCompletion,
        kernel.deployment(deployment_id=deployment_id, user_prompt=user_prompt),
    )
    verify_openai_response(completion)
    _assert_agent_workflow_trace(
        client=client,
        traces_path=f"otel/deployment/{deployment_id}/traces/",
        entity=f"Deployment {deployment_id}",
    )


def _cleanup_e2e(
    *,
    rendered_dir: Path | None,
    infra_dir: Path | None,
    pulumi_stack: str | None,
    pulumi_home: Path | None,
    env_file: Path | None,
    skip_cleanup: bool,
) -> None:
    try:
        if skip_cleanup:
            fprint("SKIP_CLEANUP is set, skipping Pulumi destroy/stack rm")
            return

        if not rendered_dir or not infra_dir or not pulumi_stack:
            return

        run_cmd(
            ["uv", "run", "pulumi", "cancel", "--yes", "--stack", pulumi_stack],
            cwd=infra_dir,
            env={"PULUMI_CONFIG_PASSPHRASE": "123", "PULUMI_HOME": str(pulumi_home)}
            if pulumi_home is not None
            else {"PULUMI_CONFIG_PASSPHRASE": "123"},
            capture=True,
            check=False,
        )
        run_cmd(
            task_cmd("destroy", "--", "--yes", "--skip-preview"),
            cwd=rendered_dir,
            check=False,
        )
        fprint(f"Attempting to remove Pulumi stack: {pulumi_stack}")
        rm_out = run_cmd(
            ["uv", "run", "pulumi", "stack", "rm", "-f", "-y", pulumi_stack],
            cwd=infra_dir,
            env={"PULUMI_CONFIG_PASSPHRASE": "123", "PULUMI_HOME": str(pulumi_home)}
            if pulumi_home is not None
            else {"PULUMI_CONFIG_PASSPHRASE": "123"},
            capture=True,
            check=False,
        )
        if rm_out.strip():
            fprint("Pulumi stack rm output (best-effort):")
            fprint(rm_out.strip())
    finally:
        if env_file and env_file.exists():
            env_file.unlink()


def run_agent_e2e(
    *,
    agent_framework: str,
    datarobot_endpoint: str,
    datarobot_api_token: str,
    repo_root: Path | None = None,
    skip_cleanup: bool | None = None,
) -> None:
    """
    Run full deployment E2E for the given agent framework.

    Uses CLI commands (task agent:cli) to execute and test agents.
    """
    if agent_framework not in ALL_FRAMEWORKS:
        raise ValueError(
            f"Unknown agent_framework={agent_framework!r}. Valid: {list(ALL_FRAMEWORKS)}"
        )

    repo_root = repo_root or Path(__file__).resolve().parents[2]
    skip_cleanup = (
        is_truthy(os.environ.get("SKIP_CLEANUP"))
        if skip_cleanup is None
        else skip_cleanup
    )

    # Step 0: Select prompt + allocate a unique Pulumi stack for this run.
    default_user_prompt = "Write a single tweet (under 280 characters) about AI."
    user_prompt = os.environ.get("E2E_USER_PROMPT", default_user_prompt)

    pulumi_stack = os.environ.get(
        "E2E_PULUMI_STACK",
        f"af-component-agent-e2e-{agent_framework}-{int(time.time())}-{uuid.uuid4().hex[:8]}",
    )

    fprint("==================================================")
    fprint(f"Running Full Deployment E2E for: {agent_framework}")
    fprint(f"Pulumi stack: {pulumi_stack}")
    fprint("==================================================")

    # Step 1: Render the template for the selected agent framework.
    rendered_dir, infra_dir = render_project(
        repo_root=repo_root, agent_framework=agent_framework
    )

    # Step 2: Prepare E2E-specific runtime env (written into rendered project's `.env`).
    extra_env: dict[str, str] = {"USE_DATAROBOT_LLM_GATEWAY": "1"}
    if agent_framework == "crewai":
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

    # Step 5: Ensure Pulumi uses the local backend (no Pulumi Cloud auth needed).
    run_cmd(
        ["uv", "run", "pulumi", "login", "--local"],
        cwd=infra_dir,
        env={"PULUMI_CONFIG_PASSPHRASE": "123", "PULUMI_HOME": str(pulumi_home)},
        capture=True,
    )

    # Control whether we run the deployment phase (AGENT_DEPLOY=1) after custom-model tests.
    run_deployment_tests = os.environ.get("RUN_AGENT_DEPLOYMENT_TESTS", "1") == "1"

    try:
        # Step 6: Install dependencies in the rendered project (agent + infra).
        run_cmd(task_cmd("install"), cwd=rendered_dir)

        # Step 7: Build phase (Pulumi up with AGENT_DEPLOY=0).
        # Creates the Custom Model (and baseline infra) but not the Deployment.
        run_cmd(
            task_cmd("build", "--", "--yes", "--skip-preview"),
            cwd=rendered_dir,
        )

        # Step 8: Run the agent in a codespace and verify its trace lands in the
        # use-case OTel view. IDs come from the "Agent Playground URL" stack output.
        playground_url = pulumi_stack_output_value(
            infra_dir=infra_dir,
            pulumi_stack=pulumi_stack,
            pulumi_home=pulumi_home,
            contains="Agent Playground URL",
        )
        playground_id = extract_id_from_url(
            playground_url, marker="agentic-playgrounds"
        )
        use_case_id = extract_id_from_url(playground_url, marker="usecases")
        fprint(f"Playground ID: {playground_id}  Use case ID: {use_case_id}")
        retry(
            lambda: _verify_codespace_run(
                playground_id=playground_id,
                use_case_id=use_case_id,
                user_prompt=user_prompt,
                datarobot_endpoint=datarobot_endpoint,
                datarobot_api_token=datarobot_api_token,
            ),
            max_retries=3,
            delay_seconds=60,
            label="Codespace run + trace verification",
        )

        if run_deployment_tests:
            # Step 9: Deploy phase (Pulumi up with AGENT_DEPLOY=1).
            # Creates the Deployment for the Custom Model.
            run_cmd(
                task_cmd("deploy", "--", "--yes", "--skip-preview"),
                cwd=rendered_dir,
            )

            # Step 10: Fetch the Deployment endpoint from Pulumi stack outputs.
            deployment_chat_endpoint = pulumi_stack_output_value(
                infra_dir=infra_dir,
                pulumi_stack=pulumi_stack,
                pulumi_home=pulumi_home,
                contains="Deployment Chat Endpoint",
            )
            deployment_id = extract_id_from_url(
                deployment_chat_endpoint, marker="deployments"
            )
            fprint(f"Deployment ID: {deployment_id}")

            # Step 11: Run the deployed agent and verify its reply + trace.
            retry(
                lambda: _verify_deployment_run(
                    user_prompt=user_prompt,
                    deployment_id=deployment_id,
                    datarobot_endpoint=datarobot_endpoint,
                    datarobot_api_token=datarobot_api_token,
                ),
                max_retries=3,
                delay_seconds=30,
                label="Deployment execution",
            )

        fprint("Agent execution completed successfully")
    finally:
        # Step 12: Cleanup (Pulumi cancel + destroy + stack rm, and delete rendered `.env`).
        _cleanup_e2e(
            rendered_dir=rendered_dir,
            infra_dir=infra_dir,
            pulumi_stack=pulumi_stack,
            pulumi_home=pulumi_home,
            env_file=env_file,
            skip_cleanup=skip_cleanup,
        )


__all__ = [
    "ALL_FRAMEWORKS",
    "fprint",
    "require_datarobot_env",
    "require_e2e_enabled",
    "run_agent_e2e",
    "should_run_framework",
]
