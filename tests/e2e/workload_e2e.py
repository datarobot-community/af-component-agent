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
E2E for the Workload API deployment runtime (ENABLE_AGENT_ON_WORKLOAD_API=true).

Two tiers in one run, so a single render/install serves both:

* **Preview** (always): `pulumi preview` and assertions on the *plan*. Creates
  nothing on the platform, so it is cheap enough for every PR. Covers the whole
  Pulumi program -- imports, dynamic-provider pickling, provider-side argument
  validation, and the serving-only promise (no Custom Models resources).
* **Deploy** (`RUN_AGENT_WORKLOAD_DEPLOY_TESTS=1`, set by CI on pushes to main):
  a real `pulumi up` that builds the C2W image on the platform, then asserts the
  workload becomes ready, answers a chat completion, and re-plans clean.

Kept separate from `e2e.py` (the Custom Models runtime) rather than sharing a
driver: this runtime creates no Playground/LlmBlueprint/deployment, so none of
that module's verification applies. The ~40-line prelude is duplicated on
purpose -- the alternative was refactoring a path that can only be validated by
running the full 5-framework deployment E2E.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

import datarobot as dr
import pytest
import requests
from datarobot.rest import RESTClientObject

from ._process import (
    fprint,
    is_truthy,
    retry,
    run_cmd,
    task_cmd,
)
from .helpers import (
    ALL_FRAMEWORKS,
    pulumi_stack_output_value,
    render_project,
    write_testing_env,
)

# --- Pulumi resource type tokens --------------------------------------------

WORKLOAD_TYPE = "datarobot:index/workload:Workload"
ARTIFACT_TYPE = "datarobot:index/artifact:Artifact"
# `WorkloadGeneratedImageArtifact` subclasses `pulumi.dynamic.Resource` without
# module/name kwargs, so its type token is the dynamic default.
DYNAMIC_RESOURCE_TYPE = "pulumi-python:dynamic:Resource"

# Resources that only exist on the Custom Models runtime. `CustomModelDeployment`
# is a ComponentResource, so it shows up as its children (RegisteredModel +
# Deployment) rather than under its own token.
CUSTOM_MODELS_ONLY_TYPES = frozenset(
    {
        "datarobot:index/customModel:CustomModel",
        "datarobot:index/playground:Playground",
        "datarobot:index/llmBlueprint:LlmBlueprint",
        "datarobot:index/deployment:Deployment",
        "datarobot:index/predictionEnvironment:PredictionEnvironment",
        "datarobot:index/registeredModel:RegisteredModel",
    }
)

# Preview step ops that would change something. `same` and `read` are expected:
# the execution environment is resolved via `ExecutionEnvironment.get`, which
# plans as a read.
MUTATING_OPS = frozenset(
    {
        "create",
        "update",
        "replace",
        "delete",
        "create-replacement",
        "delete-replaced",
        "replace-target",
        "discard",
    }
)

# --- Timeouts ---------------------------------------------------------------
#
# Invariant, and the reason these are derived rather than two independent
# literals: BUILD_TIMEOUT_S < PULUMI_UP_TIMEOUT_S < (CI job timeout - teardown).
# `WorkloadClient.wait_for_build` raises a TimeoutError carrying the tail of the
# platform build log; a `run_cmd` subprocess kill throws all of that away. The
# in-program timeout must therefore always fire first.
#
# The shipped default (`DEFAULT_BUILD_TIMEOUT_S = 9000`, i.e. 2.5h) is a
# "never give up on a user's cold build" value. In CI it is longer than the job
# itself, so it could never fire -- hence the override.
BUILD_TIMEOUT_S = int(os.environ.get("E2E_WORKLOAD_BUILD_TIMEOUT_S", "2400"))
PULUMI_UP_TIMEOUT_S = BUILD_TIMEOUT_S + 600

PREVIEW_TIMEOUT_S = 600
INSTALL_TIMEOUT_S = 900
DESTROY_TIMEOUT_S = 1200

# The workload has to pull the freshly built image, start the container, and
# pass the /health readiness probe (10s delay + 6 x 10s = 70s at the earliest).
WORKLOAD_READY_TIMEOUT_S = 900
WORKLOAD_READY_POLL_S = 15

_TERMINAL_WORKLOAD_STATUSES = frozenset({"failed", "error", "stopped", "deleted"})
_RUNNING_WORKLOAD_STATUSES = frozenset({"running", "active", "ready"})


# --- Pulumi preview digest --------------------------------------------------


def _preview_digest(raw: str) -> dict[str, Any]:
    """Extract the preview digest from `task preview -- --json` output.

    The task shells out to `install-pulumi-plugin` and `select-env-stack` first,
    both of which write to stdout, so the JSON is not alone on the stream. Scan
    line-initial `{`s and require a `steps` key so plugin chatter (or a config
    blob) can never be mistaken for the digest.
    """
    decoder = json.JSONDecoder()
    for match in re.finditer(r"(?m)^\{", raw or ""):
        try:
            digest, _ = decoder.raw_decode(raw[match.start() :])
        except json.JSONDecodeError:
            continue
        if isinstance(digest, dict) and "steps" in digest:
            return digest
    pytest.fail(
        "No Pulumi preview digest (a JSON object with a `steps` key) in "
        f"`task preview -- --json` output:\n{(raw or '')[-4000:]}"
    )


def _step_type(step: dict[str, Any]) -> str:
    """Resource type of a preview step.

    Prefers the explicit state type; falls back to the URN's type segment, whose
    last `$`-separated part is the resource's own type when it has a parent.
    """
    for state_key in ("newState", "oldState"):
        state = step.get(state_key) or {}
        type_name = state.get("type")
        if isinstance(type_name, str) and type_name:
            return type_name

    urn = str(step.get("urn", ""))
    parts = urn.split("::")
    return parts[2].split("$")[-1] if len(parts) > 2 else ""


def _planned_types(digest: dict[str, Any]) -> set[str]:
    """Types of every resource the plan touches, excluding the root stack."""
    return {
        type_name
        for step in digest.get("steps") or []
        if (type_name := _step_type(step)) and type_name != "pulumi:pulumi:Stack"
    }


def _preview_stack_outputs(digest: dict[str, Any]) -> dict[str, Any]:
    """Stack outputs from the plan's root step; empty when not planned yet."""
    for step in digest.get("steps") or []:
        if _step_type(step) == "pulumi:pulumi:Stack":
            outputs = (step.get("newState") or {}).get("outputs")
            if isinstance(outputs, dict):
                return outputs
    return {}


def _assert_serving_only_plan(digest: dict[str, Any]) -> None:
    """Assert the plan is the C2W Workload API shape and nothing else.

    The unit tests assert this for `provision_workload_agent` in isolation with
    `pulumi_datarobot` mocked out. This covers the whole program instead --
    `base.py`, the fixture `infra/__init__.py`, and the entry router -- so
    "someone added a Playground to the shared module" cannot slip through.
    """
    planned = _planned_types(digest)
    fprint(f"Planned resource types: {sorted(planned)}")

    custom_models = planned & CUSTOM_MODELS_ONLY_TYPES
    if custom_models:
        pytest.fail(
            "Workload API runtime planned Custom Models resources, but it is "
            f"serving-only: {sorted(custom_models)}. Planned: {sorted(planned)}"
        )

    # Checked before the "missing" case below, because taking the image-URI
    # branch by mistake also drops the dynamic resource -- and "an Artifact was
    # planned" is the diagnostic that names the actual cause.
    if ARTIFACT_TYPE in planned:
        pytest.fail(
            f"Plan contains {ARTIFACT_TYPE}, so the pre-built-image scenario was "
            "selected -- expected the C2W (platform-generated Dockerfile) path. "
            f"Is WORKLOAD_AGENT_IMAGE_URI set? Planned: {sorted(planned)}"
        )

    missing = {WORKLOAD_TYPE, DYNAMIC_RESOURCE_TYPE} - planned
    if missing:
        pytest.fail(
            f"Workload API plan is missing {sorted(missing)}. "
            f"Planned: {sorted(planned)}"
        )


def _assert_no_pending_changes(digest: dict[str, Any]) -> None:
    """Assert a re-plan of an unchanged deployment is a no-op.

    The only coverage of `_GENERATED_TRACKED_KEYS` / `_diff_changed` against
    real Pulumi state. Any non-deterministic resource input -- an unstable
    `source_hash`, env-var ordering churn, the readiness probe not surviving the
    state round-trip, execution-environment version re-resolution -- shows up
    here as a spurious replacement, which for a user means an unnecessary
    30-minute image rebuild on every `dr run deploy`.
    """
    offenders = [
        step
        for step in digest.get("steps") or []
        if str(step.get("op", "")) in MUTATING_OPS
    ]
    if offenders:
        details = "\n".join(
            f"  {step.get('op')} {step.get('urn')}"
            f" (diffReasons={step.get('diffReasons')})"
            for step in offenders
        )
        pytest.fail(
            "Re-planning an unchanged Workload API deployment is not a no-op; "
            f"these steps would change resources:\n{details}"
        )
    fprint("Re-plan is a no-op: no resource would be created, updated or replaced.")


def _run_preview(*, rendered_dir: Path, label: str) -> dict[str, Any]:
    fprint(f"Running `pulumi preview` ({label})")
    raw = run_cmd(
        task_cmd("preview", "--", "--json"),
        cwd=rendered_dir,
        capture=True,
        timeout_seconds=PREVIEW_TIMEOUT_S,
    )
    return _preview_digest(raw)


# --- Live workload ----------------------------------------------------------


def _wait_for_workload_running(
    *,
    client: RESTClientObject,
    workload_id: str,
    timeout_s: int = WORKLOAD_READY_TIMEOUT_S,
    poll_s: int = WORKLOAD_READY_POLL_S,
) -> None:
    """Poll the workload until it reports a running status.

    Deliberately separate from the chat assertion: "the container never came up"
    and "the agent answered wrong" are different bugs with different fixes, and
    conflating them makes the failure hard to read.
    """
    deadline = time.monotonic() + timeout_s
    last_status = "unknown"
    while True:
        response = client.get(f"workloads/{workload_id}/")
        response.raise_for_status()
        last_status = str((response.json() or {}).get("status", "unknown")).lower()
        fprint(f"Workload {workload_id} status: {last_status}")

        if last_status in _RUNNING_WORKLOAD_STATUSES:
            return
        if last_status in _TERMINAL_WORKLOAD_STATUSES:
            pytest.fail(
                f"Workload {workload_id} reached terminal status {last_status!r} "
                "instead of running."
            )
        if time.monotonic() >= deadline:
            pytest.fail(
                f"Workload {workload_id} not running after {timeout_s}s "
                f"(last status: {last_status!r})."
            )
        time.sleep(poll_s)


def _post_chat_completion(
    *,
    chat_endpoint: str,
    datarobot_api_token: str,
    user_prompt: str,
    read_timeout_s: int = 300,
) -> str:
    """POST an OpenAI-compatible completion to the workload; return its content.

    This is what proves the container is genuinely serving the agent: the
    `dr-credential` env-var references resolve at container start, the
    `{"source": "api-key"}` token injection works, and the LLM gateway is
    reachable from inside the workload.
    """
    response = requests.post(
        chat_endpoint,
        headers={
            "Authorization": f"Bearer {datarobot_api_token}",
            "Content-Type": "application/json",
        },
        json={
            "messages": [{"role": "user", "content": user_prompt}],
            # Explicit: a streamed body would arrive as SSE, not JSON.
            "stream": False,
        },
        timeout=(30, read_timeout_s),
    )
    response.raise_for_status()

    try:
        payload = response.json()
    except ValueError:
        pytest.fail(
            "Workload chat endpoint did not return JSON (streamed response?):\n"
            f"{response.text[:2000]}"
        )

    choices = payload.get("choices") or []
    if not choices:
        pytest.fail(f"Workload chat response has no choices: {payload}")
    content = ((choices[0] or {}).get("message") or {}).get("content")
    if not isinstance(content, str) or not content.strip():
        pytest.fail(f"Workload chat response content was empty: {payload}")
    return content


def _cleanup_workload_e2e(
    *,
    rendered_dir: Path | None,
    infra_dir: Path | None,
    pulumi_stack: str | None,
    pulumi_home: Path | None,
    env_file: Path | None,
    skip_cleanup: bool,
) -> None:
    """Best-effort teardown, mirroring `e2e._cleanup_e2e`.

    Ordering is load-bearing on this runtime: `pulumi destroy` deletes the
    Workload before its Artifact (the workload `depends_on` the artifact), and
    the platform refuses to delete an artifact that still backs a live workload.
    `DATAROBOT_API_TOKEN` must be present in the rendered `.env` for any of it to
    work -- the artifact provider reads the token from the environment inside
    `delete()`, and it is deliberately never stored in Pulumi state.
    """
    try:
        if skip_cleanup:
            fprint("SKIP_CLEANUP is set, skipping Pulumi destroy/stack rm")
            return

        if not rendered_dir or not infra_dir or not pulumi_stack:
            return

        pulumi_env = {"PULUMI_CONFIG_PASSPHRASE": "123"}
        if pulumi_home is not None:
            pulumi_env["PULUMI_HOME"] = str(pulumi_home)

        # Releases the stack lock left behind by a `pulumi up` that was killed
        # mid-build -- far likelier here than on the Custom Models path, where
        # no single operation blocks for tens of minutes.
        run_cmd(
            ["uv", "run", "pulumi", "cancel", "--yes", "--stack", pulumi_stack],
            cwd=infra_dir,
            env=pulumi_env,
            capture=True,
            check=False,
        )
        run_cmd(
            task_cmd("destroy", "--", "--yes", "--skip-preview"),
            cwd=rendered_dir,
            check=False,
            timeout_seconds=DESTROY_TIMEOUT_S,
        )
        fprint(f"Attempting to remove Pulumi stack: {pulumi_stack}")
        rm_out = run_cmd(
            ["uv", "run", "pulumi", "stack", "rm", "-f", "-y", pulumi_stack],
            cwd=infra_dir,
            env=pulumi_env,
            capture=True,
            check=False,
        )
        if rm_out.strip():
            fprint("Pulumi stack rm output (best-effort):")
            fprint(rm_out.strip())
    finally:
        if env_file and env_file.exists():
            env_file.unlink()


def run_workload_agent_e2e(
    *,
    agent_framework: str,
    datarobot_endpoint: str,
    datarobot_api_token: str,
    repo_root: Path | None = None,
    skip_cleanup: bool | None = None,
) -> None:
    """Run the Workload API E2E for the given agent framework.

    Always previews and asserts the plan. Additionally deploys for real, and
    calls the served agent, when `RUN_AGENT_WORKLOAD_DEPLOY_TESTS=1` (CI sets
    this on pushes to main, mirroring `RUN_AGENT_DEPLOYMENT_TESTS`).
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
    # The stack name is also the DataRobot asset-name prefix (PROJECT_NAME is
    # the stack name), so it identifies everything this run creates.
    default_user_prompt = "Write a single tweet (under 280 characters) about AI."
    user_prompt = os.environ.get("E2E_USER_PROMPT", default_user_prompt)

    pulumi_stack = os.environ.get(
        "E2E_PULUMI_STACK",
        f"af-component-agent-e2e-wapi-{agent_framework}-{int(time.time())}-{uuid.uuid4().hex[:8]}",
    )

    # Control whether we run the real deploy phase after the plan assertions.
    run_deploy_tests = os.environ.get("RUN_AGENT_WORKLOAD_DEPLOY_TESTS", "1") == "1"

    fprint("==================================================")
    fprint(f"Running Workload API E2E for: {agent_framework}")
    fprint(f"Pulumi stack: {pulumi_stack}")
    fprint(
        f"Deploy phase: {'enabled' if run_deploy_tests else 'disabled (preview only)'}"
    )
    fprint("==================================================")

    # Step 1: Render the template for the selected agent framework.
    rendered_dir, infra_dir = render_project(
        repo_root=repo_root, agent_framework=agent_framework
    )

    # Step 2: Prepare E2E-specific runtime env (written into rendered project's `.env`).
    extra_env: dict[str, str] = {
        "USE_DATAROBOT_LLM_GATEWAY": "1",
        # The one switch under test: the entry router branches on this.
        "ENABLE_AGENT_ON_WORKLOAD_API": "true",
        # Keep the platform build inside the subprocess/job budget (see the
        # timeout invariant at the top of this module).
        "WORKLOAD_BUILD_TIMEOUT_S": str(BUILD_TIMEOUT_S),
    }
    if agent_framework == "crewai":
        extra_env["CREWAI_TESTING"] = "true"

    # Step 3: Create an isolated Pulumi home under the rendered project to avoid shared state.
    pulumi_home = rendered_dir / ".pulumi_home"
    pulumi_home.mkdir(parents=True, exist_ok=True)

    # Step 4: Write the rendered project's `.env` file (Taskfile loads this).
    # `write_testing_env` sets DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT to the
    # GenAI Agents drop-in, which is what keeps the C2W build off the 10-20min
    # execution-environment build path.
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

    try:
        # Step 6: Install dependencies in the rendered project (agent + infra).
        run_cmd(
            task_cmd("install"), cwd=rendered_dir, timeout_seconds=INSTALL_TIMEOUT_S
        )

        # Step 7: Preview. Creates nothing, but runs the whole Pulumi program:
        # module imports, dynamic-provider pickling, the execution-environment
        # read, and provider-side validation of the Workload/Artifact arguments.
        digest = _run_preview(rendered_dir=rendered_dir, label="initial plan")
        _assert_serving_only_plan(digest)

        # The router exports the resolved runtime. Asserting it turns a baffling
        # "unexpected CustomModel in plan" into "the flag did not take effect".
        # Soft: stack outputs are not always populated in a preview digest, and
        # this must never be the flaky assertion.
        runtime_outputs = {
            key: value
            for key, value in _preview_stack_outputs(digest).items()
            if key.startswith("Agent Runtime ")
        }
        if runtime_outputs:
            for key, value in runtime_outputs.items():
                assert value == "workload-api", (
                    f"Stack output {key!r} is {value!r}, expected 'workload-api'. "
                    "ENABLE_AGENT_ON_WORKLOAD_API did not take effect."
                )
        else:
            fprint(
                "Note: no 'Agent Runtime' output in the preview digest; runtime "
                "selection is covered by the plan-shape assertions above."
            )

        if not run_deploy_tests:
            fprint("Workload API preview completed successfully (deploy phase skipped)")
            return

        # Step 8: Deploy for real. This is the only thing that exercises the
        # full C2W chain: source archive -> upload -> artifact create -> build
        # trigger -> build poll -> workload create.
        run_cmd(
            task_cmd("deploy", "--", "--yes", "--skip-preview"),
            cwd=rendered_dir,
            timeout_seconds=PULUMI_UP_TIMEOUT_S,
        )

        # Step 9: Assert the exported outputs. Cheap, so it runs before the slow
        # checks; other components consume these values as runtime parameters.
        def _output(contains: str) -> str:
            return pulumi_stack_output_value(
                infra_dir=infra_dir,
                pulumi_stack=pulumi_stack,
                pulumi_home=pulumi_home,
                contains=contains,
            )

        runtime = _output("Agent Runtime ")
        assert runtime == "workload-api", (
            f"Expected the workload-api runtime, got {runtime!r}."
        )

        workload_id = _output("Agent Workload Id ")
        artifact_id = _output("Agent Workload Artifact Id ")
        endpoint = _output("Agent Workload Endpoint ")
        chat_endpoint = _output("Agent Workload Chat Endpoint ")
        fprint(f"Workload ID: {workload_id}  Artifact ID: {artifact_id}")
        fprint(f"Workload endpoint: {endpoint}")

        assert endpoint.startswith("https://"), (
            f"Workload endpoint is not an absolute https URL: {endpoint!r}"
        )
        assert chat_endpoint == f"{endpoint.rstrip('/')}/chat/completions", (
            f"Chat endpoint {chat_endpoint!r} is not the workload endpoint "
            f"{endpoint!r} plus '/chat/completions'."
        )

        # Step 10: Wait for the replica to pass its /health readiness probe.
        client = dr.Client(endpoint=datarobot_endpoint, token=datarobot_api_token)
        _wait_for_workload_running(client=client, workload_id=workload_id)

        # Step 11: Call the served agent through its chat endpoint.
        content = retry(
            lambda: _post_chat_completion(
                chat_endpoint=chat_endpoint,
                datarobot_api_token=datarobot_api_token,
                user_prompt=user_prompt,
            ),
            max_retries=2,
            delay_seconds=30,
            label="Workload chat completion",
        )
        fprint(f"Workload chat completion returned {len(content)} chars")

        # Step 12: Re-plan. Nothing changed, so nothing may be replaced -- see
        # `_assert_no_pending_changes` for why this matters to users.
        _assert_no_pending_changes(
            _run_preview(rendered_dir=rendered_dir, label="idempotency re-plan")
        )

        fprint("Workload API deployment completed successfully")
    finally:
        # Step 13: Cleanup (Pulumi cancel + destroy + stack rm, and delete rendered `.env`).
        _cleanup_workload_e2e(
            rendered_dir=rendered_dir,
            infra_dir=infra_dir,
            pulumi_stack=pulumi_stack,
            pulumi_home=pulumi_home,
            env_file=env_file,
            skip_cleanup=skip_cleanup,
        )


__all__ = ["run_workload_agent_e2e"]
