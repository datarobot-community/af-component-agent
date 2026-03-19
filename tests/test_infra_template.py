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

"""Unit tests for logic in template/infra/infra/{{agent_app_name_file}}.py.jinja."""

import textwrap
from pathlib import Path

import pytest
import yaml


def is_a2a_server_enabled(project_dir: Path, agent_app_name: str) -> bool:
    """Mirrors _is_a2a_server_enabled() from the infra template."""
    workflow_yaml_path = project_dir.parent / agent_app_name / "agent" / "workflow.yaml"
    if not workflow_yaml_path.exists():
        return False
    with open(workflow_yaml_path) as f:
        workflow_config = yaml.safe_load(f) or {}
    a2a = workflow_config.get("general", {}).get("front_end", {}).get("a2a")
    return a2a is not None


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Create a fake project_dir/infra structure mirroring what Pulumi would see."""
    infra_dir = tmp_path / "myagent" / "infra"
    infra_dir.mkdir(parents=True)
    return infra_dir


def write_workflow_yaml(project_dir: Path, agent_app_name: str, content: str) -> None:
    agent_dir = project_dir.parent / agent_app_name / "agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "workflow.yaml").write_text(content)


class TestIsA2aServerEnabled:
    def test_returns_false_when_workflow_yaml_missing(
        self, project_dir: Path
    ) -> None:
        result = is_a2a_server_enabled(project_dir, "myagent")
        assert result is False

    def test_returns_false_when_a2a_absent(
        self, project_dir: Path
    ) -> None:
        write_workflow_yaml(
            project_dir,
            "myagent",
            textwrap.dedent("""\
                general:
                  front_end:
                    _type: dragent_fastapi
            """),
        )
        result = is_a2a_server_enabled(project_dir, "myagent")
        assert result is False

    def test_returns_true_when_a2a_present(
        self, project_dir: Path
    ) -> None:
        write_workflow_yaml(
            project_dir,
            "myagent",
            textwrap.dedent("""\
                general:
                  front_end:
                    _type: dragent_fastapi
                    a2a:
                      server:
                        name: "My Agent"
                        description: "Does things"
            """),
        )
        result = is_a2a_server_enabled(project_dir, "myagent")
        assert result is True

    def test_returns_false_when_front_end_section_absent(
        self, project_dir: Path
    ) -> None:
        write_workflow_yaml(
            project_dir,
            "myagent",
            textwrap.dedent("""\
                general: {}
            """),
        )
        result = is_a2a_server_enabled(project_dir, "myagent")
        assert result is False

    def test_returns_false_when_general_section_absent(
        self, project_dir: Path
    ) -> None:
        write_workflow_yaml(
            project_dir,
            "myagent",
            textwrap.dedent("""\
                workflow:
                  _type: tool_calling_agent
            """),
        )
        result = is_a2a_server_enabled(project_dir, "myagent")
        assert result is False
