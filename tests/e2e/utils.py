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
Small pure helpers for E2E tests.

Keep this module dependency-free so it's easy to reuse across the E2E suite.
"""

from __future__ import annotations


def fprint(msg: str) -> None:
    print(msg, flush=True)


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _truncate(text: str, *, max_chars: int = 800) -> str:
    s = (text or "").strip()
    if len(s) <= max_chars:
        return s
    return s[:max_chars] + "…"


def _response_snippet(text: str, *, max_chars: int) -> str:
    """Return a compact one-line snippet for logs."""
    compact = " ".join((text or "").strip().split())
    return _truncate(compact, max_chars=max_chars)


