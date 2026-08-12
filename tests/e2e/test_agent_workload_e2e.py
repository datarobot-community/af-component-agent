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
    require_datarobot_env,
    require_e2e_enabled,
    should_run_framework,
)
from .workload_e2e import run_workload_agent_e2e

# One framework, not a matrix. The Workload API code path has no
# framework-specific branching -- `workload.py` and `workload_api/` never look at
# the framework, and only the agent's dependency set differs -- so the other four
# would cost 5x (including 5x platform image builds) for no extra signal. `base`
# has the smallest dependency set, hence the fastest C2W build.
WORKLOAD_FRAMEWORK = "base"


@pytest.mark.e2e
def test_e2e_agent_workload_api() -> None:
    """Workload API runtime: plan on every run, real deploy when CI asks for it.

    See `workload_e2e.run_workload_agent_e2e` for the two tiers and the
    `RUN_AGENT_WORKLOAD_DEPLOY_TESTS` gate.
    """
    require_e2e_enabled()
    if not should_run_framework(WORKLOAD_FRAMEWORK):
        pytest.skip("Skipping due to E2E_AGENT_FRAMEWORKS selection")

    datarobot_endpoint, datarobot_api_token = require_datarobot_env()

    run_workload_agent_e2e(
        agent_framework=WORKLOAD_FRAMEWORK,
        datarobot_endpoint=datarobot_endpoint,
        datarobot_api_token=datarobot_api_token,
    )
