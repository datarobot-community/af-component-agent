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

COPIER_CONFIG = Path(__file__).resolve().parent.parent / "copier.yml"

AGENT_DOTENV_TEMPLATE = (
    Path(__file__).resolve().parent.parent
    / "template"
    / ".datarobot"
    / "cli"
    / "{{agent_app_name}}.yaml.jinja"
)


def test_agent_dotenv_template_prompts_for_mem0_api_key_when_mem0_selected() -> None:
    """Mem0 selection should add a required MEM0_API_KEY dotenv prompt for dr start."""
    content = AGENT_DOTENV_TEMPLATE.read_text(encoding="utf-8")

    assert "use_agent_memory == 'mem0'" in content
    assert "MEM0_API_KEY" in content
    assert "secret_string" in content
    assert "optional: false" in content


def test_copier_prompts_for_mem0_api_key_when_mem0_newly_enabled() -> None:
    """Copier should ask for Mem0 API key when Mem0 is newly enabled."""
    content = COPIER_CONFIG.read_text(encoding="utf-8")

    assert "mem0_api_key:" in content
    assert "secret: true" in content
    assert "_copier_operation == 'copy'" in content
    assert "use_agent_memory == 'mem0'" in content


def test_copier_writes_mem0_api_key_to_env_when_provided() -> None:
    """Copier task should persist a provided Mem0 API key into .env."""
    content = COPIER_CONFIG.read_text(encoding="utf-8")

    assert "write_mem0_env.py" in content
    assert "MEM0_API_KEY_VALUE" in content
    assert "dr dotenv setup --if-needed" in content
