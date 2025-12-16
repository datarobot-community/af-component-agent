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

import pytest

from .helpers import AgentE2EHelper
from .helpers import require_datarobot_env
from .helpers import require_e2e_enabled
from .helpers import should_run_framework


@pytest.mark.e2e
def test_e2e_agent_base() -> None:
    require_e2e_enabled()
    if not should_run_framework("base"):
        pytest.skip("Skipping due to E2E_AGENT_FRAMEWORKS selection")
    datarobot_endpoint, datarobot_api_token = require_datarobot_env()
    AgentE2EHelper(agent_framework="base").run(
        datarobot_endpoint=datarobot_endpoint,
        datarobot_api_token=datarobot_api_token,
    )


@pytest.mark.e2e
def test_e2e_agent_crewai() -> None:
    require_e2e_enabled()
    if not should_run_framework("crewai"):
        pytest.skip("Skipping due to E2E_AGENT_FRAMEWORKS selection")
    datarobot_endpoint, datarobot_api_token = require_datarobot_env()
    AgentE2EHelper(agent_framework="crewai").run(
        datarobot_endpoint=datarobot_endpoint,
        datarobot_api_token=datarobot_api_token,
    )


@pytest.mark.e2e
def test_e2e_agent_langgraph() -> None:
    require_e2e_enabled()
    if not should_run_framework("langgraph"):
        pytest.skip("Skipping due to E2E_AGENT_FRAMEWORKS selection")
    datarobot_endpoint, datarobot_api_token = require_datarobot_env()
    AgentE2EHelper(agent_framework="langgraph").run(
        datarobot_endpoint=datarobot_endpoint,
        datarobot_api_token=datarobot_api_token,
    )


@pytest.mark.e2e
def test_e2e_agent_llamaindex() -> None:
    require_e2e_enabled()
    if not should_run_framework("llamaindex"):
        pytest.skip("Skipping due to E2E_AGENT_FRAMEWORKS selection")
    datarobot_endpoint, datarobot_api_token = require_datarobot_env()
    AgentE2EHelper(agent_framework="llamaindex").run(
        datarobot_endpoint=datarobot_endpoint,
        datarobot_api_token=datarobot_api_token,
    )


@pytest.mark.e2e
def test_e2e_agent_nat() -> None:
    require_e2e_enabled()
    if not should_run_framework("nat"):
        pytest.skip("Skipping due to E2E_AGENT_FRAMEWORKS selection")
    datarobot_endpoint, datarobot_api_token = require_datarobot_env()
    AgentE2EHelper(agent_framework="nat").run(
        datarobot_endpoint=datarobot_endpoint,
        datarobot_api_token=datarobot_api_token,
    )


