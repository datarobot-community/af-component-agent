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
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))


@pytest.fixture(autouse=True)
def pulumi_mocks(monkeypatch, tmp_path):
    monkeypatch.setenv("PULUMI_STACK_CONTEXT", "unittest")
    monkeypatch.setattr("datarobot_pulumi_utils.pulumi.export", MagicMock())


def test_memory_space_llm_model_name_strips_datarobot_prefix() -> None:
    from infra.memory_space_config import memory_space_llm_model_name

    assert (
        memory_space_llm_model_name("datarobot/azure/gpt-5-mini-2025-08-07")
        == "azure/gpt-5-mini-2025-08-07"
    )


def test_memory_space_llm_model_name_leaves_unprefixed_model_unchanged() -> None:
    from infra.memory_space_config import memory_space_llm_model_name

    assert memory_space_llm_model_name("azure/gpt-5-mini-2025-08-07") == (
        "azure/gpt-5-mini-2025-08-07"
    )


def test_build_configure_command_uses_memory_space_update() -> None:
    from infra.memory_space_config import _build_configure_command

    command = _build_configure_command(
        "space-id-123",
        "azure/gpt-5-mini-2025-08-07",
    )

    assert "space-id-123" in command
    assert "azure/gpt-5-mini-2025-08-07" in command
    assert "configure_memory_space_llm.py" in command
