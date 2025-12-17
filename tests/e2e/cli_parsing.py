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
CLI output parsing/validation helpers for E2E tests.
"""

from __future__ import annotations

import json
import os
from typing import Any, cast

from utils import _is_truthy, _response_snippet, _truncate, fprint


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


def verify_openai_response(cli_output: str) -> None:
    """
    Verify the CLI output contains a valid OpenAI response (mirrors templates repo).
    """
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

    # Check that the message content is non-empty
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


