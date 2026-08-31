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
"""Checks that start_server.sh hands DRAgent the right workflow.yaml.

start_server.sh is the custom model entrypoint: if it resolves the wrong config
path the deployment fails at container start, where it is expensive to notice.
Everything the script shells out to (uv, nat) is stubbed, so nothing is
installed and no server is started.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

START_SERVER = Path(__file__).parent.parent / "start_server.sh"

pytestmark = pytest.mark.skipif(
    os.name != "posix", reason="POSIX shell entrypoint, not used on Windows"
)


def run_start_server(
    code_dir: Path, tmp_path: Path
) -> subprocess.CompletedProcess[str]:
    """Run start_server.sh in `code_dir` with uv/nat stubbed out."""
    shutil.copy(START_SERVER, code_dir / "start_server.sh")

    # `nat` records its arguments instead of serving; `uv` does nothing.
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    nat_args = tmp_path / "nat_args"
    (bin_dir / "nat").write_text(f'#!/bin/sh\necho "$@" > "{nat_args}"\n')
    (bin_dir / "uv").write_text("#!/bin/sh\nexit 0\n")
    for stub in bin_dir.iterdir():
        stub.chmod(0o755)

    # The script sources the venv activate script, which our `uv venv` stub does
    # not create.
    venv_dir = tmp_path / "venv"
    (venv_dir / "bin").mkdir(parents=True)
    (venv_dir / "bin" / "activate").touch()

    result = subprocess.run(
        ["sh", str(code_dir / "start_server.sh")],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "VENV_DIR": str(venv_dir),
            "CODE_DIR": str(code_dir),
        },
    )
    result.stdout = nat_args.read_text() if nat_args.exists() else ""
    return result


def test_serves_workflow_yaml_from_the_app_root(tmp_path: Path) -> None:
    code_dir = tmp_path / "code"
    code_dir.mkdir()
    (code_dir / "workflow.yaml").touch()

    result = run_start_server(code_dir, tmp_path)

    assert result.returncode == 0, result.stderr
    assert f"--config_file {code_dir / 'workflow.yaml'}" in result.stdout


def test_falls_back_to_the_pre_11_9_3_agent_subdirectory(tmp_path: Path) -> None:
    code_dir = tmp_path / "code"
    (code_dir / "agent").mkdir(parents=True)
    (code_dir / "agent" / "workflow.yaml").touch()

    result = run_start_server(code_dir, tmp_path)

    assert result.returncode == 0, result.stderr
    assert f"--config_file {code_dir / 'agent' / 'workflow.yaml'}" in result.stdout


def test_fails_loudly_when_no_workflow_yaml_exists(tmp_path: Path) -> None:
    code_dir = tmp_path / "code"
    code_dir.mkdir()

    result = run_start_server(code_dir, tmp_path)

    assert result.returncode == 1
    assert "no workflow.yaml found" in result.stderr
