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

from pathlib import Path
from types import SimpleNamespace

from extensions.dotenv_lookup import _dotenv_value, dotenv_has


def test_dotenv_value_returns_none_when_file_missing(tmp_path: Path) -> None:
    assert _dotenv_value(tmp_path / ".env", "MEM0_API_KEY") is None


def test_dotenv_value_returns_none_when_key_missing(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("OTHER=value\n", encoding="utf-8")

    assert _dotenv_value(env_path, "MEM0_API_KEY") is None


def test_dotenv_value_returns_none_when_key_empty(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("MEM0_API_KEY=\n", encoding="utf-8")

    assert _dotenv_value(env_path, "MEM0_API_KEY") is None


def test_dotenv_value_returns_none_when_key_quoted_empty(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text('MEM0_API_KEY=""\n', encoding="utf-8")

    assert _dotenv_value(env_path, "MEM0_API_KEY") is None
    assert dotenv_has({"_copier_dst_path": tmp_path}, "MEM0_API_KEY") is False


def test_dotenv_value_reads_quoted_and_unquoted_values(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        'MEM0_API_KEY="quoted-secret"\nOTHER=value\n',
        encoding="utf-8",
    )

    assert _dotenv_value(env_path, "MEM0_API_KEY") == "quoted-secret"


def test_dotenv_has_uses_destination_env_file(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("MEM0_API_KEY=already-set\n", encoding="utf-8")
    context = {"_copier_conf": SimpleNamespace(dst_path=tmp_path)}

    assert dotenv_has(context, "MEM0_API_KEY") is True
