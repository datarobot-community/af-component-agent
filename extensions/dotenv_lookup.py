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

import re
from pathlib import Path

from jinja2 import pass_context
from jinja2.ext import Extension

_UNQUOTED_DOTENV_VALUE = re.compile(r"[\w.-]+")


def _parse_dotenv_value(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {"'", '"'}:
        quote = raw[0]
        inner = raw[1:-1]
        if quote == "'":
            return inner
        chars: list[str] = []
        index = 0
        while index < len(inner):
            if inner[index] == "\\" and index + 1 < len(inner):
                next_char = inner[index + 1]
                if next_char == "n":
                    chars.append("\n")
                elif next_char == "r":
                    chars.append("\r")
                elif next_char == "t":
                    chars.append("\t")
                elif next_char in {'"', "\\"}:
                    chars.append(next_char)
                else:
                    chars.append(inner[index])
                    index += 1
                    continue
                index += 2
            else:
                chars.append(inner[index])
                index += 1
        return "".join(chars)
    return raw


def format_dotenv_value(value: str) -> str:
    """Format a value for a ``KEY=value`` line in a ``.env`` file."""
    if _UNQUOTED_DOTENV_VALUE.fullmatch(value):
        return value
    if "'" not in value:
        return f"'{value}'"
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def format_dotenv_assignment(key: str, value: str) -> str:
    """Format a complete ``KEY=value`` line for a ``.env`` file."""
    return f"{key}={format_dotenv_value(value)}"


def _dotenv_value(env_path: Path, key: str) -> str | None:
    if not env_path.is_file():
        return None

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not stripped.startswith(f"{key}="):
            continue
        value = _parse_dotenv_value(stripped.split("=", 1)[1])
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
