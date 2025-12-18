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

from .e2e import (
    ALL_FRAMEWORKS,
    require_datarobot_env,
    require_e2e_enabled,
    run_agent_e2e,
    should_run_framework,
)


@pytest.mark.e2e
@pytest.mark.parametrize("framework", ALL_FRAMEWORKS, ids=list(ALL_FRAMEWORKS))
def test_e2e_agent_framework(framework: str) -> None:
    require_e2e_enabled()
    if not should_run_framework(framework):
        pytest.skip("Skipping due to E2E_AGENT_FRAMEWORKS selection")

    datarobot_endpoint, datarobot_api_token = require_datarobot_env()

    run_agent_e2e(
        agent_framework=framework,
        datarobot_endpoint=datarobot_endpoint,
        datarobot_api_token=datarobot_api_token,
    )


