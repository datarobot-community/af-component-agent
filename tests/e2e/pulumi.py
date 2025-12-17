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
Pulumi helper functions for E2E tests.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from utils import _truncate


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
    merged_env.update({"PULUMI_CONFIG_PASSPHRASE": ""})

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


