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
"""Copier Jinja helpers for reading values from the destination .env file."""

from __future__ import annotations

from pathlib import Path

from jinja2 import pass_context
from jinja2.ext import Extension


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _dotenv_value(env_path: Path, key: str) -> str | None:
    if not env_path.is_file():
        return None

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not stripped.startswith(f"{key}="):
            continue
        value = _strip_quotes(stripped.split("=", 1)[1].strip())
        return value or None
    return None


def _destination_path(context: dict) -> Path:
    conf = context.get("_copier_conf")
    if conf is not None:
        dst_path = getattr(conf, "dst_path", None)
        if dst_path:
            return Path(dst_path)
    return Path(context.get("_copier_dst_path", "."))


@pass_context
def dotenv_has(context: dict, key: str) -> bool:
    """Return True when ``key`` is set to a non-empty value in the destination .env."""
    return _dotenv_value(_destination_path(context) / ".env", key) is not None


class DotenvLookupExtension(Extension):
    """Expose ``dotenv_has`` to copier.yml ``when`` expressions and templates."""

    def __init__(self, environment) -> None:
        super().__init__(environment)
        environment.globals["dotenv_has"] = dotenv_has
