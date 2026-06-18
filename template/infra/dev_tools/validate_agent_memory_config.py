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

"""Validate agent memory provider settings before start/deploy.

DataRobot Memory Service and Mem0 SaaS use different credentials. When
``use_agent_memory`` is ``datarobot_memory_service``, a leftover ``MEM0_API_KEY``
in ``.env`` is ignored at runtime (``dr_mem0_memory`` suppresses ``api_key`` when
``agent_memory_space_id`` is set), which can surprise users. Fail early instead.

Also invoked from Copier ``_tasks`` immediately after the user selects
``datarobot_memory_service`` (see ``copier.yml``).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

DATAROBOT_MEMORY_SERVICE = "datarobot_memory_service"
MEM0_API_KEY_ENV = "MEM0_API_KEY"
USE_AGENT_MEMORY_RE = re.compile(r"^use_agent_memory:\s*(\S+)\s*$", re.MULTILINE)
_ENV_LINE_RE = re.compile(
    r"^\s*(?:export\s+)?(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<value>.*)\s*$"
)


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def read_use_agent_memory(repo_root: Path) -> str | None:
    answers_dir = repo_root / ".datarobot" / "answers"
    if not answers_dir.is_dir():
        return None

    for answers_file in sorted(answers_dir.glob("agent-*.yml")):
        text = answers_file.read_text(encoding="utf-8")
        match = USE_AGENT_MEMORY_RE.search(text)
        if match:
            return match.group(1).strip().strip('"').strip("'")
    return None


def _unquote_env_value(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def read_mem0_api_key_from_dotenv(repo_root: Path) -> str | None:
    env_file = repo_root / ".env"
    if not env_file.is_file():
        return None

    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _ENV_LINE_RE.match(line)
        if not match or match.group("key") != MEM0_API_KEY_ENV:
            continue
        value = _unquote_env_value(match.group("value"))
        return value or None
    return None


def resolve_mem0_api_key(repo_root: Path) -> str | None:
    from_env = os.environ.get(MEM0_API_KEY_ENV)
    if from_env is not None and from_env.strip():
        return from_env
    return read_mem0_api_key_from_dotenv(repo_root)


def validate_agent_memory_config(
    *,
    use_agent_memory: str | None,
    mem0_api_key: str | None,
) -> list[str]:
    key = (mem0_api_key or "").strip()
    if use_agent_memory == DATAROBOT_MEMORY_SERVICE and key:
        return [
            "Agent memory provider is DataRobot Memory Service "
            f"({DATAROBOT_MEMORY_SERVICE}), but {MEM0_API_KEY_ENV} is also set. "
            "These target different backends (DataRobot Memory Service vs Mem0 SaaS). "
            f"Unset {MEM0_API_KEY_ENV} in .env or change use_agent_memory to mem0 in "
            ".datarobot/answers/agent-agent.yml."
        ]
    return []


def main(argv: list[str] | None = None) -> int:
    repo_root = repo_root_from_module()
    use_agent_memory = read_use_agent_memory(repo_root)
    mem0_api_key = resolve_mem0_api_key(repo_root)

    errors = validate_agent_memory_config(
        use_agent_memory=use_agent_memory,
        mem0_api_key=mem0_api_key,
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
