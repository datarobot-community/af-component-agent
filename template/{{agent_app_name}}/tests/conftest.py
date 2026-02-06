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


@pytest.fixture
def mock_agent_response():
    """
    Fixture to return a mock agent response based on the agent template framework.
    """
    return (
        "agent result",
        [],
        {
            "completion_tokens": 1,
            "prompt_tokens": 2,
            "total_tokens": 3,
        },
    )


@pytest.fixture()
def load_model_result():
    """Fixture for DRUM load_model_result argument (currently unused by agent)."""
    from custom import load_model

    return load_model("")
