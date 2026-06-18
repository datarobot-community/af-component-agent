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

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "dotenv_has_key.py"
SRC_PATH = Path(__file__).resolve().parent.parent


def _run_dotenv_has_key(tmp_path: Path, env_contents: str | None) -> subprocess.CompletedProcess[str]:
    if env_contents is not None:
        (tmp_path / ".env").write_text(env_contents, encoding="utf-8")

    return subprocess.run(
        [sys.executable, str(SCRIPT), "MEM0_API_KEY"],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(SRC_PATH)},
        check=False,
        capture_output=True,
        text=True,
    )


def test_dotenv_has_key_exits_zero_when_key_set(tmp_path: Path) -> None:
    result = _run_dotenv_has_key(tmp_path, "MEM0_API_KEY=secret\n")

    assert result.returncode == 0


def test_dotenv_has_key_exits_one_when_key_missing(tmp_path: Path) -> None:
    result = _run_dotenv_has_key(tmp_path, "OTHER=value\n")

    assert result.returncode == 1


def test_dotenv_has_key_exits_one_when_key_empty(tmp_path: Path) -> None:
    result = _run_dotenv_has_key(tmp_path, "MEM0_API_KEY=\n")

    assert result.returncode == 1


def test_dotenv_has_key_exits_one_when_key_quoted_empty(tmp_path: Path) -> None:
    result = _run_dotenv_has_key(tmp_path, 'MEM0_API_KEY=""\n')

    assert result.returncode == 1
