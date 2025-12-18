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
from pathlib import Path
from typing import Any, Callable

import pytest
from _pytest.outcomes import Failed

DEFAULT_CMD_TIMEOUT_SECONDS = 20 * 60


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


def run_cmd(
    cmd: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    capture: bool = False,
    check: bool = True,
    timeout_seconds: int | None = None,
) -> str:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    fprint(f"$ {' '.join(cmd)}  (cwd={cwd})")

    timeout = DEFAULT_CMD_TIMEOUT_SECONDS if timeout_seconds is None else timeout_seconds
    try:
        if capture:
            proc = subprocess.run(
                cmd,
                cwd=str(cwd),
                env=merged_env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=check,
            )
            return proc.stdout or ""

        subprocess.run(
            cmd,
            cwd=str(cwd),
            env=merged_env,
            text=True,
            timeout=timeout,
            check=check,
        )
        return ""
    except subprocess.TimeoutExpired as e:
        out = ""
        if capture and isinstance(e.stdout, str):
            out = e.stdout
        pytest.fail(
            f"Command timed out after {timeout}s: {' '.join(cmd)}\n\n{out}".rstrip()
        )
    except subprocess.CalledProcessError as e:
        out = ""
        if capture:
            if isinstance(e.stdout, str) and e.stdout.strip():
                out = e.stdout
            elif isinstance(e.output, str) and e.output.strip():
                out = e.output
        pytest.fail(
            f"Command failed (exit {e.returncode}): {' '.join(cmd)}\n\n{out}".rstrip()
        )


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


