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

from unittest.mock import MagicMock, Mock, patch

import pytest

from custom import chat, load_model


@pytest.fixture(autouse=True)
def mock_agent():
    with patch("agent.myagent.MyAgent") as mock:

        async def gen():
            yield (
                "agent result",
                [],
                {"completion_tokens": 1, "prompt_tokens": 2, "total_tokens": 3},
            )

        mock_instance = MagicMock()
        mock_instance.invoke = Mock(return_value=gen())
        mock.return_value = mock_instance
        yield mock, mock_instance


@pytest.fixture
def mock_mcp_config():
    with patch("agent.myagent.MCPConfig") as mock:
        mock_instance = MagicMock()
        mock_instance.server_config = {"headers": {"X-Test": "value"}}
        mock.return_value = mock_instance
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
    def test_authorization_context_set_in_params(
        self, mock_mcp_config, load_model_result, completion_params
    ):
        auth_context = {"token": "test-token", "user_id": "test-user"}

        with patch("custom.resolve_authorization_context", return_value=auth_context):
            chat(completion_params, load_model_result)

        call_kwargs = mock_mcp_config.call_args[1]
        assert call_kwargs["authorization_context"] == auth_context

    def test_authorization_context_passed_to_agent(
        self, mock_mcp_config, load_model_result, completion_params
    ):
        auth_context = {"token": "test-token", "user_id": "test-user"}

        with patch("custom.resolve_authorization_context", return_value=auth_context):
            chat(completion_params, load_model_result)

        mock_mcp_config.assert_called_once()
        call_kwargs = mock_mcp_config.call_args[1]
        assert call_kwargs["authorization_context"] == auth_context

    def test_empty_authorization_context_handled(
        self, mock_mcp_config, load_model_result, completion_params
    ):
        with patch("custom.resolve_authorization_context", return_value={}):
            response = chat(completion_params, load_model_result)

        assert response is not None
        mock_mcp_config.assert_called_once()
        call_kwargs = mock_mcp_config.call_args[1]
        assert call_kwargs["authorization_context"] == {}


class TestHeaderForwarding:
    """NAT agent merges whitelisted forwarded_headers with MCPConfig.server_config headers
    before passing them to MyAgent. This differs from other frameworks where only
    forwarded_headers are passed through and MCP tools are obtained via mcp_tools_context.
    """

    def test_forwarded_headers_whitelisted(
        self, mock_agent, mock_mcp_config, load_model_result, completion_params
    ):
        """Only x-datarobot-* headers pass through custom.py whitelisting;
        the agent receives them merged with MCP server_config headers."""
        headers = {
            "x-datarobot-api-key": "secret-key",
            "x-datarobot-api-token": "secret-token",
            "x-custom-header": "should-be-filtered",
        }

        with patch("custom.resolve_authorization_context", return_value={}):
            chat(completion_params, load_model_result, headers=headers)

        mock_class, _ = mock_agent
        agent_kwargs = mock_class.call_args[1]
        forwarded = agent_kwargs["forwarded_headers"]
        assert forwarded["x-datarobot-api-key"] == "secret-key"
        assert forwarded["x-datarobot-api-token"] == "secret-token"
        assert forwarded["X-Test"] == "value"
        assert "x-custom-header" not in forwarded

    def test_forwarded_headers_case_insensitive(
        self, mock_agent, mock_mcp_config, load_model_result, completion_params
    ):
        """Headers matching x-datarobot-* are filtered case-insensitively;
        the agent receives them merged with MCP server_config headers."""
        header1 = "X-DataRobot-API-Key"
        header2 = "X-DATAROBOT-API-TOKEN"

        headers = {
            header1: "secret-key",
            header2: "secret-token",
        }

        with patch("custom.resolve_authorization_context", return_value={}):
            chat(completion_params, load_model_result, headers=headers)

        mock_class, _ = mock_agent
        agent_kwargs = mock_class.call_args[1]
        forwarded = agent_kwargs["forwarded_headers"]
        assert len(forwarded) == 3
        assert header1 in forwarded
        assert header2 in forwarded
        assert "X-Test" in forwarded

    def test_forwarded_headers_only_mcp_when_no_incoming_headers(
        self, mock_agent, mock_mcp_config, load_model_result, completion_params
    ):
        """When no incoming headers, agent still gets MCP server_config headers."""
        with patch("custom.resolve_authorization_context", return_value={}):
            chat(completion_params, load_model_result)

        mock_class, _ = mock_agent
        agent_kwargs = mock_class.call_args[1]
        assert agent_kwargs["forwarded_headers"] == {"X-Test": "value"}

    def test_forwarded_headers_only_mcp_when_none(
        self, mock_agent, mock_mcp_config, load_model_result, completion_params
    ):
        """When headers is None, agent still gets MCP server_config headers."""
        with patch("custom.resolve_authorization_context", return_value={}):
            chat(completion_params, load_model_result, headers=None)

        mock_class, _ = mock_agent
        agent_kwargs = mock_class.call_args[1]
        assert agent_kwargs["forwarded_headers"] == {"X-Test": "value"}

    def test_only_whitelisted_headers_forwarded(
        self, mock_agent, mock_mcp_config, load_model_result, completion_params
    ):
        """Non-x-datarobot-* headers are filtered out; agent only gets MCP headers."""
        headers = {
            "Authorization": "Bearer token",
            "Content-Type": "application/json",
            "X-Custom": "value",
        }

        with patch("custom.resolve_authorization_context", return_value={}):
            chat(completion_params, load_model_result, headers=headers)

        mock_class, _ = mock_agent
        agent_kwargs = mock_class.call_args[1]
        forwarded = agent_kwargs["forwarded_headers"]
        assert forwarded == {"X-Test": "value"}
        assert "Authorization" not in forwarded
        assert "Content-Type" not in forwarded
        assert "X-Custom" not in forwarded

    def test_mcp_config_headers_passed_to_agent(
        self, mock_agent, mock_mcp_config, load_model_result, completion_params
    ):
        """Verify the full chain: custom.py headers -> MCPConfig -> server_config -> MyAgent."""
        mcp_headers = {"X-MCP-Auth": "token-123"}
        mock_mcp_config.return_value.server_config = {"headers": mcp_headers}

        with patch("custom.resolve_authorization_context", return_value={}):
            chat(completion_params, load_model_result)

        mock_class, _ = mock_agent
        agent_kwargs = mock_class.call_args[1]
        assert agent_kwargs["forwarded_headers"] == mcp_headers

    def test_agent_gets_empty_headers_when_no_server_config(
        self, mock_agent, mock_mcp_config, load_model_result, completion_params
    ):
        """When MCPConfig.server_config is None (no MCP configured), agent gets empty dict."""
        mock_mcp_config.return_value.server_config = None

        with patch("custom.resolve_authorization_context", return_value={}):
            chat(completion_params, load_model_result)

        mock_class, _ = mock_agent
        agent_kwargs = mock_class.call_args[1]
        assert agent_kwargs["forwarded_headers"] == {}
