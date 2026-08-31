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

import pytest

from .helpers import (
    ALL_FRAMEWORKS,
    require_datarobot_env,
    require_e2e_enabled,
    should_run_framework,
)
from .workload_e2e import run_workload_agent_e2e

# A matrix, same knob and same coverage as test_agent_e2e.py's Custom Models
# one: unset E2E_AGENT_FRAMEWORKS runs all five, or set it (e.g. "base,crewai")
# to run a subset. CI's `e2e-workload-api` job uses the same resolved matrix as
# `e2e-custom-models` -- full five on push, path-narrowed on PRs.


@pytest.mark.e2e
@pytest.mark.parametrize("framework", ALL_FRAMEWORKS, ids=list(ALL_FRAMEWORKS))
def test_e2e_agent_workload_api(framework: str) -> None:
    """Workload API runtime: plan on every run, real deploy when CI asks for it.

    See `workload_e2e.run_workload_agent_e2e` for the two tiers and the
    `RUN_AGENT_WORKLOAD_DEPLOY_TESTS` gate.
    """
    require_e2e_enabled()
    if not should_run_framework(framework):
        pytest.skip("Skipping due to E2E_AGENT_FRAMEWORKS selection")

    datarobot_endpoint, datarobot_api_token = require_datarobot_env()

    run_workload_agent_e2e(
        agent_framework=framework,
        datarobot_endpoint=datarobot_endpoint,
        datarobot_api_token=datarobot_api_token,
    )
