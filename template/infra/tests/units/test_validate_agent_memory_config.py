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

from dev_tools.validate_agent_memory_config import (
    read_mem0_api_key_from_dotenv,
    validate_agent_memory_config,
)


def test_no_error_when_datarobot_memory_service_without_mem0_key():
    assert (
        validate_agent_memory_config(
            use_agent_memory="datarobot_memory_service",
            mem0_api_key=None,
        )
        == []
    )


def test_no_error_when_mem0_provider_with_mem0_key():
    assert (
        validate_agent_memory_config(
            use_agent_memory="mem0",
            mem0_api_key="secret",
        )
        == []
    )


def test_no_error_when_memory_disabled_with_mem0_key():
    assert (
        validate_agent_memory_config(
            use_agent_memory="none",
            mem0_api_key="secret",
        )
        == []
    )


def test_error_when_datarobot_memory_service_with_mem0_key():
    errors = validate_agent_memory_config(
        use_agent_memory="datarobot_memory_service",
        mem0_api_key="secret",
    )
    assert len(errors) == 1
    assert "MEM0_API_KEY" in errors[0]
    assert "datarobot_memory_service" in errors[0]


def test_error_ignores_whitespace_only_mem0_key():
    assert (
        validate_agent_memory_config(
            use_agent_memory="datarobot_memory_service",
            mem0_api_key="   ",
        )
        == []
    )


def test_read_mem0_api_key_from_dotenv(tmp_path):
    (tmp_path / ".env").write_text(
        'MEM0_API_KEY="secret-from-file"\nAGENT_PORT=8842\n',
        encoding="utf-8",
    )
    assert read_mem0_api_key_from_dotenv(tmp_path) == "secret-from-file"
