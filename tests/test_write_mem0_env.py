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

import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "write_mem0_env.py"


def test_write_mem0_env_appends_key_when_missing(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("DATAROBOT_API_TOKEN=test\n", encoding="utf-8")

    subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=tmp_path,
        env={**os.environ, "MEM0_API_KEY_VALUE": "mem0-secret"},
        check=True,
    )

    assert env_path.read_text(encoding="utf-8") == (
        "DATAROBOT_API_TOKEN=test\n\nMEM0_API_KEY=mem0-secret\n"
    )


def test_write_mem0_env_updates_existing_key(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("MEM0_API_KEY=old\nOTHER=value\n", encoding="utf-8")

    subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=tmp_path,
        env={**os.environ, "MEM0_API_KEY_VALUE": "new-secret"},
        check=True,
    )

    assert env_path.read_text(encoding="utf-8") == "MEM0_API_KEY=new-secret\nOTHER=value\n"


def test_write_mem0_env_noop_when_value_empty(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("EXISTING=value\n", encoding="utf-8")

    subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=tmp_path,
        env={**os.environ, "MEM0_API_KEY_VALUE": ""},
        check=True,
    )

    assert env_path.read_text(encoding="utf-8") == "EXISTING=value\n"


def test_write_mem0_env_noop_when_value_whitespace_only(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("EXISTING=value\n", encoding="utf-8")

    subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=tmp_path,
        env={**os.environ, "MEM0_API_KEY_VALUE": "   "},
        check=True,
    )

    assert env_path.read_text(encoding="utf-8") == "EXISTING=value\n"
