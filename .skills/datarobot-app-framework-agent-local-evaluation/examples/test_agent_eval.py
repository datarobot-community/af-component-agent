# Copyright 2026 DataRobot, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Copy this file to agent/tests/test_agent_eval.py and replace the placeholder
# prompts and contexts with content relevant to your agent's domain.
#
# NAT/DRAgent prerequisites:
# - Copy examples/moderation.yaml to agent/moderation.yaml and fill in
#   deployment IDs.
# - Add to .env (or export before running):
#     TARGET_NAME=resultText
# - Register the eval marker in pyproject.toml:
#   [tool.pytest.ini_options]
#   markers = ["eval: live evaluation tests requiring DataRobot credentials"]
#
# Run evaluation tests:
#   cd agent && uv run pytest tests/test_agent_eval.py -m eval -v
#
# Skip evaluation tests (no credentials needed):
#   cd agent && uv run pytest tests/ -m "not eval"

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pytest
from datarobot_dome.api import ModerationPipeline

AGENT_DIR = Path(__file__).resolve().parents[1]


def _parse_cli_response(stdout: str) -> str:
    """Extract agent response text from `task agent:cli` output."""
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]

    # Non-streaming frameworks print: Workflow Result: ['...']
    for line in reversed(lines):
        if line.startswith("Workflow Result:"):
            payload = line.split("Workflow Result:", 1)[1].strip()
            try:
                parsed = ast.literal_eval(payload)
            except (SyntaxError, ValueError):
                return payload
            if isinstance(parsed, list):
                return "".join(str(item) for item in parsed)
            return str(parsed)

    # Streaming frameworks may emit text and then print "Run finished."
    if "Run finished." in lines:
        stop_idx = lines.index("Run finished.")
        candidate_lines = []
        for line in lines[:stop_idx]:
            if line.startswith("task:"):
                continue
            if line.startswith("Running CLI"):
                continue
            if line.startswith("Running agent with user prompt:"):
                continue
            if line.startswith("Checking authentication"):
                continue
            if "Skipping auth check" in line:
                continue
            candidate_lines.append(line)
        if candidate_lines:
            return "\n".join(candidate_lines).strip()

    raise AssertionError(
        "Could not parse agent response from CLI output.\n\n"
        f"CLI output:\n{stdout}"
    )


def run_agent_via_cli(user_prompt: str) -> str:
    """Run local NAT/DRAgent agent and return response text."""
    cmd = [
        "uvx",
        "--from",
        "go-task-bin",
        "task",
        "agent:cli",
        "--",
        "execute",
        "--user_prompt",
        user_prompt,
    ]
    result = subprocess.run(
        cmd,
        cwd=AGENT_DIR,
        check=True,
        text=True,
        capture_output=True,
    )
    return _parse_cli_response(result.stdout)


# --- Fixtures -----------------------------------------------------------------


@pytest.fixture(scope="session")
def pipeline():
    """Load ModerationPipeline once per test session."""
    moderation_path = AGENT_DIR / "moderation.yaml"
    return ModerationPipeline.from_yaml(str(moderation_path))


# --- Basic goal accuracy -------------------------------------------------------


@pytest.mark.eval
def test_agent_goal_accuracy(pipeline):
    """Agent response should achieve the user's stated goal."""
    user_prompt = "What is the return policy?"
    response_text = run_agent_via_cli(user_prompt)

    result, _ = pipeline.evaluate_response(
        response_text,
        prompt=user_prompt,
    )

    # result.blocked is True when any guard threshold is breached
    assert not result.blocked, (
        f"Eval failed: {result.blocked_message} | Metrics: {result.metrics}"
    )


# --- Faithfulness (RAG hallucination detection) -------------------------------


@pytest.mark.eval
def test_agent_faithfulness(pipeline):
    """Agent response should not hallucinate facts outside retrieved context."""
    user_prompt = "What is the return policy?"
    retrieved_context = ["Returns are accepted within 30 days of purchase."]
    response_text = run_agent_via_cli(user_prompt)

    result, _ = pipeline.evaluate_response(
        response_text,
        prompt=user_prompt,
        retrieved_contexts=retrieved_context,  # required for faithfulness
    )

    assert not result.blocked, f"Hallucination detected: {result.blocked_message}"


# --- Parametrized evaluation dataset ------------------------------------------


TEST_CASES = [
    # Replace with prompt/context pairs relevant to your agent's domain.
    {
        "prompt": "What is the return policy?",
        "context": ["Returns are accepted within 30 days of purchase."],
    },
    {
        "prompt": "How do I reset my password?",
        "context": ["Click 'Forgot password' on the login page."],
    },
]


@pytest.mark.eval
@pytest.mark.parametrize("case", TEST_CASES)
def test_faithfulness_parametrized(pipeline, case):
    """All test cases should pass faithfulness evaluation."""
    response_text = run_agent_via_cli(case["prompt"])

    result, _ = pipeline.evaluate_response(
        response_text,
        prompt=case["prompt"],
        retrieved_contexts=case["context"],
    )
    assert not result.blocked, (
        f"Failed on prompt '{case['prompt']}': {result.blocked_message}"
    )


# --- Negative test -------------------------------------------------------------


@pytest.mark.eval
def test_pipeline_catches_hallucination(pipeline):
    """The evaluation pipeline should catch a deliberately wrong response."""
    result, _ = pipeline.evaluate_response(
        "Returns are not accepted under any circumstances.",  # deliberately wrong
        prompt="What is the return policy?",
        retrieved_contexts=["Returns are accepted within 30 days of purchase."],
    )
    assert result.blocked, "The evaluation pipeline should have caught the hallucination."
