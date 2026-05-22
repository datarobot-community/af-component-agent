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
Low-level helpers for E2E tests.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Callable

import backoff
import pytest
import requests
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    RateLimitError,
)

# HTTP status codes we consider transient infra failures worth retrying.
# Everything else (4xx, plain 500 with an agent error body) propagates so
# real bugs aren't masked.
_RETRYABLE_STATUS_CODES = frozenset({429, 502, 503, 504})

# Exception types that are always transient (no status code involved).
_ALWAYS_TRANSIENT: tuple[type[BaseException], ...] = (
    requests.ConnectionError,
    requests.Timeout,
    APITimeoutError,
    APIConnectionError,
    RateLimitError,
)


def _is_transient(exc: BaseException) -> bool:
    """Decide whether `exc` is a retryable infra failure.

    The library (datarobot-genai AgentKernel) raises underlying `requests` /
    `openai` exception types verbatim; this helper applies the retry policy.
    """
    if isinstance(exc, _ALWAYS_TRANSIENT):
        return True
    if isinstance(exc, requests.HTTPError):
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
        return status in _RETRYABLE_STATUS_CODES
    if isinstance(exc, APIStatusError):
        return exc.status_code in _RETRYABLE_STATUS_CODES
    return False


DEFAULT_CMD_TIMEOUT_SECONDS = 20 * 60


def fprint(msg: str) -> None:
    print(msg, flush=True)


def is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def response_snippet(text: str, *, max_chars: int) -> str:
    """Return a compact one-line snippet for logs."""
    compact = " ".join((text or "").strip().split())
    return compact


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

    timeout = (
        DEFAULT_CMD_TIMEOUT_SECONDS if timeout_seconds is None else timeout_seconds
    )
    try:
        if capture:
            proc = subprocess.run(
                cmd,
                cwd=str(cwd),
                env=merged_env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
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
        err = ""
        if capture:
            if isinstance(e.stdout, str):
                out = e.stdout

            if isinstance(e.stderr, str):
                err = e.stderr

        details = ""
        if out.strip():
            details += f"\n\nstdout:\n{out}".rstrip()
        if err.strip():
            details += f"\n\nstderr:\n{err}".rstrip()

        pytest.fail(
            f"Command timed out after {timeout}s: {' '.join(cmd)}{details}".rstrip()
        )
    except subprocess.CalledProcessError as e:
        out = ""
        err = ""
        if capture:
            if isinstance(e.stdout, str):
                out = e.stdout

            if isinstance(e.stderr, str):
                err = e.stderr

        details = ""
        if out.strip():
            details += f"\n\nstdout:\n{out}".rstrip()
        if err.strip():
            details += f"\n\nstderr:\n{err}".rstrip()

        pytest.fail(
            f"Command failed (exit {e.returncode}): {' '.join(cmd)}{details}".rstrip()
        )


def retry(
    func: Callable[[], Any],
    *,
    max_retries: int,
    delay_seconds: int,
    label: str,
) -> Any:
    """Retry `func` only on transient infra failures (see `_is_transient`).

    Application errors (agent bugs, 4xx responses, assertion failures, etc.)
    propagate immediately so real failures aren't masked. Uses
    `backoff.constant` to sleep `delay_seconds` between attempts.
    """

    def _on_backoff(details: dict[str, Any]) -> None:
        fprint(
            f"{label} failed with transient API error "
            f"(attempt {details['tries']}/{max_retries + 1}): {details['exception']}"
        )
        fprint(f"Waiting {details['wait']:.0f}s before retry...")

    @backoff.on_exception(
        backoff.constant,
        Exception,
        max_tries=max_retries + 1,
        interval=delay_seconds,
        jitter=None,
        giveup=lambda exc: not _is_transient(exc),
        on_backoff=_on_backoff,  # type: ignore[arg-type]
    )
    def _run() -> Any:
        return func()

    return _run()
