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

from ..custom_model.my_agent_class.agent import MyAgent


class TestMyAgent:
    def test_init_with_string_verbose_true(self):
        # Test initialization with verbose as string "true"
        agent = MyAgent(api_key="test_key", api_base="test_base", verbose="true")
        assert agent.api_key == "test_key"
        assert agent.api_base == "test_base"
        assert agent.verbose is True

    def test_init_with_string_verbose_false(self):
        # Test initialization with verbose as string "false"
        agent = MyAgent(api_key="test_key", api_base="test_base", verbose="false")
        assert agent.api_key == "test_key"
        assert agent.api_base == "test_base"
        assert agent.verbose is False

    def test_init_with_bool_verbose(self):
        # Test initialization with verbose as boolean
        agent = MyAgent(api_key="test_key", api_base="test_base", verbose=True)
        assert agent.api_key == "test_key"
        assert agent.api_base == "test_base"
        assert agent.verbose is True

    def test_init_with_extra_kwargs(self):
        # Test initialization with extra kwargs
        agent = MyAgent(
            api_key="test_key",
            api_base="test_base",
            verbose=True,
            extra_param="extra_value",
        )
        assert agent.api_key == "test_key"
        assert agent.api_base == "test_base"
        assert agent.verbose is True

    def test_run_method_returns_success(self):
        # Test that run method returns "success"
        agent = MyAgent(api_key="test_key", api_base="test_base", verbose=True)
        inputs = {"prompt": "test prompt"}
        result = agent.run(inputs)
        assert result == "success"

    def test_run_with_empty_inputs(self):
        # Test run method with empty inputs dictionary
        agent = MyAgent(api_key="test_key", api_base="test_base", verbose=True)
        result = agent.run({})
        assert result == "success"
