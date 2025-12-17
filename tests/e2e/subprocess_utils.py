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
Subprocess helpers for E2E tests.

These helpers centralize logging + output capture to keep the main E2E flow readable.
"""

from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path

from utils import fprint


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

    output_lines: list[str] = []
    assert proc.stdout is not None

    def _pump_stdout() -> None:
        for line in proc.stdout:
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

        output = "\n".join(output_lines)
        raise AssertionError(
            f"Command timed out after {timeout}s: {' '.join(cmd)}\n\n"
            f"Partial output (truncated):\n{output[-8000:]}"
        ) from e

    output = "\n".join(output_lines)
    if check and return_code != 0:
        raise AssertionError(
            f"Command failed (exit {return_code}): {' '.join(cmd)}\n\n{output}"
        )
    return output


