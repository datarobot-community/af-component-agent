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


DOTENV_CLI_TEMPLATES = list(
    (Path(__file__).resolve().parent.parent / "template" / ".datarobot" / "cli").glob(
        "*.jinja"
    )
)


def _dotenv_help_lines(content: str) -> list[str]:
    """Extract help text lines as they would appear in the terminal."""
    lines: list[str] = []
    in_block = False
    block_style: str | None = None
    folded_parts: list[str] = []

    def flush_folded() -> None:
        nonlocal folded_parts
        if folded_parts:
            lines.append(" ".join(folded_parts))
            folded_parts = []

    for raw_line in content.splitlines():
        if re.match(r"\s*help:\s*\|", raw_line):
            flush_folded()
            in_block = True
            block_style = "literal"
            continue
        if re.match(r"\s*help:\s*>", raw_line):
            flush_folded()
            in_block = True
            block_style = "folded"
            continue
        if re.match(r'\s*help:\s*"', raw_line):
            flush_folded()
            match = re.search(r'help:\s*"(.*)"', raw_line)
            if match:
                lines.append(match.group(1))
            in_block = False
            block_style = None
            continue

        if in_block:
            if raw_line and not raw_line[0].isspace():
                if block_style == "folded":
                    flush_folded()
                in_block = False
                block_style = None
            elif block_style == "literal":
                stripped = raw_line.strip()
                if stripped:
                    lines.append(stripped)
            elif block_style == "folded":
                stripped = raw_line.strip()
                if stripped:
                    folded_parts.append(stripped)

    if block_style == "folded":
        flush_folded()

    return lines


def test_dotenv_help_fits_standard_terminal() -> None:
    """All dotenv prompt help text should fit an 80-column terminal window."""
    max_width = 78

    for template_path in DOTENV_CLI_TEMPLATES:
        content = template_path.read_text(encoding="utf-8")
        for line in _dotenv_help_lines(content):
            assert len(line) <= max_width, (
                f"{template_path.name}: help line exceeds {max_width} columns "
                f"({len(line)}): {line!r}"
            )
