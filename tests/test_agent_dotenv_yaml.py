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
import re

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


def test_agent_dotenv_adds_memory_llm_prompts_to_external_llm_section() -> None:
    """Memory LLM prompts should extend the LLM component external_llm section only."""
    content = AGENT_DOTENV_TEMPLATE.read_text(encoding="utf-8")

    assert "use_agent_memory == 'datarobot_memory_service'" in content
    assert "external_llm:" in content
    assert "AGENT_MEMORY_LLM_MODEL_NAME" in content
    assert "AGENT_MEMORY_LLM_DEPLOYMENT_ID" in content
    assert "llmgw_catalog" in content
    assert "agent_memory_llm_gateway" in content
    assert "agent_memory_llm_deployed" in content
    assert "agent_llm_integration" not in content
    assert "agent_llm_integration" not in content


def test_copier_does_not_prompt_for_agent_llm_integration() -> None:
    """Suitability is inferred from the LLM component; Copier should not ask."""
    content = (
        Path(__file__).resolve().parent.parent / "copier.yml"
    ).read_text(encoding="utf-8")

    assert "agent_llm_integration:" not in content
    assert "agent_memory_llm_routing:" not in content
    assert "agent_memory_llm_model_name:" not in content
    assert "agent_memory_llm_deployment_id:" not in content


def _memory_llm_help_lines(content: str) -> list[str]:
    """Extract non-empty help lines from the memory LLM dotenv prompts."""
    memory_section = content.split("use_agent_memory == 'datarobot_memory_service'")[1]
    lines: list[str] = []
    in_help = False
    for raw_line in memory_section.splitlines():
        if re.match(r"\s*help:\s*\|", raw_line):
            in_help = True
            continue
        if re.match(r'\s*help:\s*"', raw_line):
            match = re.search(r'help:\s*"(.*)"', raw_line)
            if match:
                lines.append(match.group(1))
            continue
        if in_help:
            if raw_line and not raw_line[0].isspace():
                in_help = False
                continue
            stripped = raw_line.strip()
            if stripped:
                lines.append(stripped)
    return lines


def test_agent_memory_llm_help_fits_standard_terminal() -> None:
    """Help text should wrap to fit an 80-column terminal window."""
    content = AGENT_DOTENV_TEMPLATE.read_text(encoding="utf-8")
    max_width = 78

    for line in _memory_llm_help_lines(content):
        assert len(line) <= max_width, (
            f"Help line exceeds {max_width} columns ({len(line)}): {line!r}"
        )
