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
Low-level helpers for E2E tests.
"""

from __future__ import annotations

import os
import subprocess
import time
from collections import deque
from pathlib import Path
from threading import Thread
from typing import Any, Callable

import pytest
from _pytest.outcomes import Failed


def fprint(msg: str) -> None:
    print(msg, flush=True)


def is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def truncate(text: str, *, max_chars: int = 800) -> str:
    s = (text or "").strip()
    if len(s) <= max_chars:
        return s
    return s[:max_chars] + "…"


def response_snippet(text: str, *, max_chars: int) -> str:
    """Return a compact one-line snippet for logs."""
    compact = " ".join((text or "").strip().split())
    return truncate(compact, max_chars=max_chars)


def task_cmd(*args: str) -> list[str]:
    # `uvx --from go-task-bin task`.
    return ["uvx", "--from", "go-task-bin", "task", *args]


def cmd_timeout_seconds() -> int:
    """
    Default timeout for E2E external commands.

    E2E can take a while (pulumi up + build/deploy), but should not hang forever.
    Configure via E2E_CMD_TIMEOUT_SECONDS. Defaults to 20 minutes.
    """
    raw = os.environ.get("E2E_CMD_TIMEOUT_SECONDS", "").strip()
    if not raw:
        return 20 * 60

    return int(raw)


def _tail_text(lines: deque[str], *, max_chars: int) -> str:
    text = "\n".join(lines)
    if len(text) <= max_chars:
        return text

    return text[-max_chars:]


def run_capture(
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

    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=merged_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=cmd_timeout_seconds() if timeout_seconds is None else timeout_seconds,
    )

    if check and proc.returncode != 0:
        pytest.fail(
            f"Command failed (exit {proc.returncode}): {' '.join(cmd)}\n\n{proc.stdout}"
        )
    return proc.stdout


def run_live(
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

    fprint(f"$ {' '.join(cmd)}  (cwd={cwd})")
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=merged_env,
        text=True,
        bufsize=1,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
    )

    # E2E commands (esp. `pulumi up`) can be very verbose. Keep a bounded in-memory
    # ring buffer so errors include useful context without unbounded memory growth.
    output_lines: deque[str] = deque(maxlen=2000)
    stdout = proc.stdout
    if stdout is None:
        pytest.fail("Internal error: subprocess stdout was None")

    timeout = cmd_timeout_seconds() if timeout_seconds is None else timeout_seconds

    def _stream_stdout() -> None:
        # Stream output line-by-line (mirrors recipe-datarobot-agent-templates E2E style).
        for line in iter(stdout.readline, ""):
            line = line.rstrip("\n")
            if line:
                print(line, flush=True)

            output_lines.append(line)

    t = Thread(target=_stream_stdout, daemon=True)
    t.start()

    try:
        return_code = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        # Best-effort terminate then kill, and include partial output for debugging.
        proc.terminate()
        try:
            return_code = proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            return_code = proc.wait(timeout=5)

        pytest.fail(
            f"Command timed out after {timeout}s: {' '.join(cmd)}\n\n"
            f"Partial output (tail):\n{_tail_text(output_lines, max_chars=8000)}"
        )
    finally:
        # Ensure the stream thread has a chance to drain remaining output.
        t.join(timeout=5)

    output = "\n".join(output_lines)
    if check and return_code != 0:
        pytest.fail(
            f"Command failed (exit {return_code}): {' '.join(cmd)}\n\n"
            f"Output (tail):\n{_tail_text(output_lines, max_chars=8000)}"
        )
    return output


def retry(
    func: Callable[[], Any],
    *,
    max_retries: int,
    delay_seconds: int,
    label: str,
) -> Any:
    last_exc: BaseException | None = None
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                fprint(
                    f"Retrying {label} (attempt {attempt + 1}/{max_retries + 1})..."
                )
            return func()
        except (Failed, Exception) as e:
            last_exc = e
            if attempt >= max_retries:
                raise
            fprint(f"{label} failed: {e}")
            fprint(f"Waiting {delay_seconds}s before retry...")
            time.sleep(delay_seconds)
    raise last_exc or RuntimeError(f"{label} failed")


