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

from unittest.mock import AsyncMock, patch

import pytest
from agent import MyAgent
from custom import chat, load_model


@pytest.fixture
def mock_agent():
    with patch("custom.MyAgent", autospec=MyAgent) as mock:
        mock_instance = mock.return_value
        mock_instance.invoke = AsyncMock(
            return_value=(
                "agent result",
                [],
                {"completion_tokens": 1, "prompt_tokens": 2, "total_tokens": 3},
            )
        )
        yield mock


@pytest.fixture
def load_model_result():
    result = load_model("")
    yield result
    thread_pool_executor, event_loop = result
    thread_pool_executor.shutdown(wait=True)


@pytest.fixture
def completion_params():
    return {
        "model": "test-model",
        "messages": [{"role": "user", "content": '{"topic": "test"}'}],
    }


class TestAuthorizationContextPropagation:
    def test_authorization_context_passed_to_agent(
        self, mock_agent, load_model_result, completion_params
    ):
        auth_context = {"token": "test-token", "user_id": "test-user"}

        with patch("custom.resolve_authorization_context", return_value=auth_context):
            chat(completion_params, load_model_result)

        mock_agent.assert_called_once()
        agent_instance = mock_agent.return_value
        # Check that authorization_context attribute was set
        assert hasattr(agent_instance, "authorization_context")
        assert agent_instance.authorization_context == auth_context

    def test_empty_authorization_context_handled(
        self, mock_agent, load_model_result, completion_params
    ):
        with patch("custom.resolve_authorization_context", return_value={}):
            response = chat(completion_params, load_model_result)

        assert response is not None
        agent_instance = mock_agent.return_value
        agent_instance.invoke.assert_called_once()
        # Check that empty authorization_context attribute was set
        assert hasattr(agent_instance, "authorization_context")
        assert agent_instance.authorization_context == {}



class TestHeaderForwarding:
    def test_forwarded_headers_whitelisted(
        self, mock_agent, load_model_result, completion_params
    ):
        headers = {
            "x-datarobot-api-key": "secret-key",
            "x-datarobot-api-token": "secret-token",
            "x-custom-header": "should-be-filtered",
        }

        with patch("custom.resolve_authorization_context", return_value={}):
            chat(completion_params, load_model_result, headers=headers)

        agent_instance = mock_agent.return_value
        # Check that forwarded_headers attribute was set
        assert hasattr(agent_instance, "forwarded_headers")
        forwarded = agent_instance.forwarded_headers
        assert forwarded["x-datarobot-api-key"] == "secret-key"
        assert forwarded["x-datarobot-api-token"] == "secret-token"
        assert "x-custom-header" not in forwarded

    def test_forwarded_headers_case_insensitive(
        self, mock_agent, load_model_result, completion_params
    ):
        headers = {
            "X-DataRobot-API-Key": "secret-key",
            "X-DATAROBOT-API-TOKEN": "secret-token",
        }

        with patch("custom.resolve_authorization_context", return_value={}):
            chat(completion_params, load_model_result, headers=headers)

        agent_instance = mock_agent.return_value
        # Check that headers are set in the agent
        assert hasattr(agent_instance, "forwarded_headers")
        forwarded = agent_instance.forwarded_headers
        assert len(forwarded) == 2
        assert forwarded["X-DataRobot-API-Key"] == "secret-key"
        assert forwarded["X-DATAROBOT-API-TOKEN"] == "secret-token"

    def test_forwarded_headers_empty_when_no_headers(
        self, mock_agent, load_model_result, completion_params
    ):
        with patch("custom.resolve_authorization_context", return_value={}):
            chat(completion_params, load_model_result)

        agent_instance = mock_agent.return_value
        # Check that empty forwarded_headers attribute was set
        assert hasattr(agent_instance, "forwarded_headers")
        assert agent_instance.forwarded_headers == {}

    def test_only_whitelisted_headers_forwarded(
        self, mock_agent, load_model_result, completion_params
    ):
        headers = {
            "Authorization": "Bearer token",
            "Content-Type": "application/json",
            "X-Custom": "value",
        }

        with patch("custom.resolve_authorization_context", return_value={}):
            chat(completion_params, load_model_result, headers=headers)

        agent_instance = mock_agent.return_value
        # Check that no headers were forwarded to the agent
        assert hasattr(agent_instance, "forwarded_headers")
        forwarded = agent_instance.forwarded_headers
        assert len(forwarded) == 0


