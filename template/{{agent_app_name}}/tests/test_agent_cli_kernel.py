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

import json
import os
from unittest.mock import Mock, mock_open, patch

import pytest
from agent_cli.kernel import AgentKernel, Kernel
from openai.types.chat import ChatCompletion


class TestKernel:
    def test_init_default_values(self):
        """Test initialization with required values and default base_url."""
        kernel = Kernel(api_token="test-token", codespace_id="test-codespace")

        assert kernel.api_token == "test-token"
        assert kernel.codespace_id == "test-codespace"
        assert kernel.base_url == "https://staging.datarobot.com"

    def test_init_custom_base_url(self):
        """Test initialization with custom base_url."""
        kernel = Kernel(
            api_token="test-token",
            codespace_id="test-codespace",
            base_url="https://custom.example.com",
        )

        assert kernel.api_token == "test-token"
        assert kernel.codespace_id == "test-codespace"
        assert kernel.base_url == "https://custom.example.com"

    def test_headers_property(self):
        """Test headers property returns correct authorization header."""
        kernel = Kernel(api_token="api-123456", codespace_id="space-123")

        headers = kernel.headers

        assert headers == {"Authorization": "Token api-123456"}

    def test_nbx_session_url_property(self):
        """Test nbx_session_url property constructs the URL correctly."""
        kernel = Kernel(
            api_token="test-token",
            codespace_id="test-codespace",
            base_url="https://example.com",
        )

        url = kernel.nbx_session_url

        assert url == "https://example.com/api-gw/nbx/session"

    def test_nbx_orchestrator_url_property(self):
        """Test nbx_orchestrator_url property constructs the URL correctly."""
        kernel = Kernel(
            api_token="test-token",
            codespace_id="test-codespace",
            base_url="https://example.com",
        )

        url = kernel.nbx_orchestrator_url

        assert url == "https://example.com/api-gw/nbx/orchestrator/notebooks"

    @patch("requests.get")
    @patch("time.sleep")
    def test_await_kernel_execution_success_path(self, mock_sleep, mock_get):
        """Test when kernel execution completes (404 response received)"""
        # Setup
        kernel = Kernel(api_token="test-token", codespace_id="test-codespace")
        kernel_id = "test-kernel-id"

        # Mock responses: first two 200, then 404
        mock_response_ok = Mock()
        mock_response_ok.status_code = 200

        mock_response_not_found = Mock()
        mock_response_not_found.status_code = 404

        mock_get.side_effect = [
            mock_response_ok,
            mock_response_ok,
            mock_response_not_found,
        ]

        # Execute
        kernel.await_kernel_execution(kernel_id)

        # Assert
        assert mock_get.call_count == 3
        mock_sleep.assert_called_with(1)

        # Verify the URL used in the requests
        expected_url = (
            f"{kernel.nbx_session_url}/{kernel.codespace_id}/kernels/{kernel_id}"
        )
        for call in mock_get.call_args_list:
            args, kwargs = call
            assert args[0] == expected_url
            assert kwargs["headers"] == kernel.headers

    @patch("requests.get")
    @patch("time.sleep")
    def test_await_kernel_execution_timeout(self, mock_sleep, mock_get):
        """Test when kernel execution times out (max_wait reached)"""
        # Setup
        kernel = Kernel(api_token="test-token", codespace_id="test-codespace")
        kernel_id = "test-kernel-id"
        max_wait = 5  # Small value for testing

        # Mock response: always 200 (never completes)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # Execute
        kernel.await_kernel_execution(kernel_id, max_wait=max_wait)

        # Assert
        assert mock_get.call_count == max_wait
        assert mock_sleep.call_count == max_wait

    @patch("requests.get")
    def test_await_kernel_execution_error(self, mock_get):
        """Test when kernel execution returns an error status code"""
        # Setup
        kernel = Kernel(api_token="test-token", codespace_id="test-codespace")
        kernel_id = "test-kernel-id"

        # Mock error response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_get.return_value = mock_response

        # Execute and Assert
        with pytest.raises(AssertionError):
            kernel.await_kernel_execution(kernel_id)

        # Verify the request was made
        mock_get.assert_called_once()


class TestAgentKernel:
    def test_init(self):
        """Test AgentKernel initialization passes parameters to parent class."""
        # Setup
        with patch.object(Kernel, "__init__") as mock_init:
            mock_init.return_value = None

            # Execute
            AgentKernel(
                api_token="test-token",
                codespace_id="test-codespace",
                base_url="https://test.example.com",
            )

            # Assert
            mock_init.assert_called_once_with(
                api_token="test-token",
                codespace_id="test-codespace",
                base_url="https://test.example.com",
            )

    def test_construct_prompt_with_extra_body(self):
        """Test construct_prompt with extra_body provided."""
        # Setup
        user_prompt = "Hello, how are you?"
        extra_body = json.dumps(
            {
                "api_key": "test-key",
                "api_base": "https://test.example.com",
                "verbose": True,
            }
        )

        # Execute
        result = AgentKernel.construct_prompt(user_prompt, extra_body)

        # Parse the result to verify structure
        result_dict = json.loads(result)

        # Assert
        assert result_dict["model"] == "datarobot-deployed-llm"
        assert len(result_dict["messages"]) == 2
        assert result_dict["messages"][0]["content"] == "You are a helpful assistant"
        assert result_dict["messages"][0]["role"] == "system"
        assert result_dict["messages"][1]["content"] == "Hello, how are you?"
        assert result_dict["messages"][1]["role"] == "user"
        assert result_dict["n"] == 1
        assert result_dict["temperature"] == 0.01
        assert result_dict["extra_body"]["api_key"] == "test-key"
        assert result_dict["extra_body"]["api_base"] == "https://test.example.com"
        assert result_dict["extra_body"]["verbose"] is True

    def test_construct_prompt_without_extra_body(self):
        """Test construct_prompt with empty extra_body."""
        # Setup
        user_prompt = "Tell me about Python"
        extra_body = ""

        # Execute
        result = AgentKernel.construct_prompt(user_prompt, extra_body)

        # Parse the result to verify structure
        result_dict = json.loads(result)

        # Assert
        assert result_dict["model"] == "datarobot-deployed-llm"
        assert len(result_dict["messages"]) == 2
        assert result_dict["messages"][0]["content"] == "You are a helpful assistant"
        assert result_dict["messages"][1]["content"] == "Tell me about Python"
        assert result_dict["n"] == 1
        assert result_dict["temperature"] == 0.01
        assert result_dict["extra_body"] == {}

    @patch("os.path.exists")
    @patch("os.remove")
    @patch("builtins.open", new_callable=mock_open, read_data="test output data")
    def test_get_output_local_success(self, mock_file, mock_remove, mock_exists):
        """Test get_output_local reads and removes the file successfully."""
        # Setup
        mock_exists.return_value = True
        output_path = "/test/output/path.json"

        # Execute
        result = AgentKernel.get_output_local(output_path)

        # Assert
        mock_file.assert_called_once_with(output_path, "r")
        mock_exists.assert_called_once_with(output_path)
        mock_remove.assert_called_once_with(output_path)
        assert result == "test output data"

    @patch("os.path.exists")
    @patch("os.remove")
    @patch("builtins.open", new_callable=mock_open, read_data="test output data")
    def test_get_output_local_file_not_exists(
        self, mock_file, mock_remove, mock_exists
    ):
        """Test get_output_local when file doesn't exist after reading."""
        # Setup
        mock_exists.return_value = False
        output_path = "/test/output/path.json"

        # Execute
        result = AgentKernel.get_output_local(output_path)

        # Assert
        mock_file.assert_called_once_with(output_path, "r")
        mock_exists.assert_called_once_with(output_path)
        mock_remove.assert_not_called()
        assert result == "test output data"

    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_get_output_local_file_not_found(self, mock_file):
        """Test get_output_local raises FileNotFoundError if file doesn't exist."""
        # Setup
        output_path = "/test/output/path.json"

        # Execute and Assert
        with pytest.raises(FileNotFoundError):
            AgentKernel.get_output_local(output_path)
        mock_file.assert_called_once_with(output_path, "r")

    @patch("requests.post")
    @patch("requests.delete")
    def test_get_output_remote_success(self, mock_delete, mock_post):
        """Test get_output_remote downloads and deletes the file successfully."""
        # Setup
        kernel = AgentKernel(
            api_token="test-token",
            codespace_id="test-codespace",
            base_url="https://test.example.com",
        )

        output_path = "/test/remote/output.json"
        expected_output = {"result": "test data"}

        # Mock the POST response
        mock_post_response = Mock()
        mock_post_response.status_code = 200
        mock_post_response.json.return_value = expected_output
        mock_post.return_value = mock_post_response

        # Mock the DELETE response
        mock_delete_response = Mock()
        mock_delete_response.status_code = 204
        mock_delete.return_value = mock_delete_response

        # Execute
        result = kernel.get_output_remote(output_path)

        # Assert
        # Verify POST request for downloading
        mock_post.assert_called_once_with(
            f"{kernel.nbx_session_url}/{kernel.codespace_id}/filesystem/objects/download/",
            json={"paths": [output_path]},
            headers=kernel.headers,
        )

        # Verify DELETE request for removing file
        mock_delete.assert_called_once_with(
            f"{kernel.nbx_session_url}/{kernel.codespace_id}/filesystem/objects/delete/",
            headers=kernel.headers,
            json={"paths": [output_path]},
        )

        assert result == expected_output

    @patch("requests.post")
    def test_get_output_remote_download_failed(self, mock_post):
        """Test get_output_remote raises AssertionError when download fails."""
        # Setup
        kernel = AgentKernel(
            api_token="test-token",
            codespace_id="test-codespace",
            base_url="https://test.example.com",
        )

        output_path = "/test/remote/output.json"

        # Mock the POST response to simulate a failure
        mock_post_response = Mock()
        mock_post_response.status_code = 404
        mock_post_response.text = "Not found"
        mock_post.return_value = mock_post_response

        # Execute and Assert
        with pytest.raises(AssertionError):
            kernel.get_output_remote(output_path)

    @patch("requests.post")
    @patch("requests.delete")
    def test_get_output_remote_delete_failed(self, mock_delete, mock_post):
        """Test get_output_remote raises AssertionError when deletion fails."""
        # Setup
        kernel = AgentKernel(
            api_token="test-token",
            codespace_id="test-codespace",
            base_url="https://test.example.com",
        )

        output_path = "/test/remote/output.json"
        expected_output = {"result": "test data"}

        # Mock the POST response for successful download
        mock_post_response = Mock()
        mock_post_response.status_code = 200
        mock_post_response.json.return_value = expected_output
        mock_post.return_value = mock_post_response

        # Mock the DELETE response to simulate a failure
        mock_delete_response = Mock()
        mock_delete_response.status_code = 500
        mock_delete_response.text = "Server error"
        mock_delete.return_value = mock_delete_response

        # Execute and Assert
        with pytest.raises(AssertionError):
            kernel.get_output_remote(output_path)

    def test_validate_execute_args_empty_prompt(self):
        """Test validate_execute_args raises ValueError with empty prompt."""
        # Setup
        kernel = AgentKernel(
            api_token="test-token",
            codespace_id="test-codespace",
            base_url="https://test.example.com",
        )

        # Execute and Assert
        with pytest.raises(ValueError, match="user_prompt must be provided."):
            kernel.validate_execute_args(user_prompt="")

    @patch.object(AgentKernel, "construct_prompt")
    def test_validate_execute_args_basic(self, mock_construct_prompt):
        """Test validate_execute_args with minimal parameters."""
        # Setup
        kernel = AgentKernel(
            api_token="test-token",
            codespace_id="test-codespace",
            base_url="https://test.example.com",
        )
        user_prompt = "Hello, assistant!"
        expected_chat_completion = '{"content": "test completion"}'
        mock_construct_prompt.return_value = expected_chat_completion

        # Execute
        command_args, output_path = kernel.validate_execute_args(user_prompt)

        # Assert
        mock_construct_prompt.assert_called_once()
        # Verify the extra_body contains the correct API details
        extra_body_arg = mock_construct_prompt.call_args[0][1]
        extra_body = json.loads(extra_body_arg)
        assert extra_body["api_key"] == "test-token"
        assert extra_body["api_base"] == "https://test.example.com"
        assert extra_body["verbose"] is True

        # Verify output path uses current directory
        expected_output_path = os.path.join(os.getcwd(), "custom_model", "output.json")
        assert output_path == expected_output_path

        # Verify command_args contains all parameters
        assert f"--chat_completion '{expected_chat_completion}'" in command_args
        assert "--default_headers '{}'" in command_args
        assert (
            f"--custom_model_dir '{os.path.join(os.getcwd(), 'custom_model')}'"
            in command_args
        )
        assert f"--output_path '{expected_output_path}'" in command_args

    @patch.object(AgentKernel, "construct_prompt")
    def test_validate_execute_args_remote(self, mock_construct_prompt):
        """Test validate_execute_args with remote execution."""
        # Setup
        kernel = AgentKernel(
            api_token="test-token",
            codespace_id="test-codespace",
            base_url="https://test.example.com",
        )
        user_prompt = "Hello, assistant!"
        expected_chat_completion = '{"content": "test completion"}'
        mock_construct_prompt.return_value = expected_chat_completion

        # Execute
        command_args, output_path = kernel.validate_execute_args(
            user_prompt, use_remote=True
        )

        # Assert
        # Verify remote paths are used
        expected_model_dir = "/home/notebooks/storage/custom_model"
        expected_output_path = "/home/notebooks/storage/custom_model/output.json"
        assert output_path == expected_output_path

        # Verify command_args contains all parameters with remote paths
        assert f"--custom_model_dir '{expected_model_dir}'" in command_args
        assert f"--output_path '{expected_output_path}'" in command_args

    @patch.object(AgentKernel, "construct_prompt")
    def test_validate_execute_args_custom_paths(self, mock_construct_prompt):
        """Test validate_execute_args with custom model_dir and output_path."""
        # Setup
        kernel = AgentKernel(
            api_token="test-token",
            codespace_id="test-codespace",
            base_url="https://test.example.com",
        )
        user_prompt = "Hello, assistant!"
        custom_model_dir = "/custom/path/model"
        custom_output_path = "/custom/path/output.json"
        expected_chat_completion = '{"content": "test completion"}'
        mock_construct_prompt.return_value = expected_chat_completion

        # Execute
        command_args, output_path = kernel.validate_execute_args(
            user_prompt,
            custom_model_dir=custom_model_dir,
            output_path=custom_output_path,
        )

        # Assert
        # Verify custom paths are used
        assert output_path == custom_output_path

        # Verify command_args contains custom paths
        assert f"--custom_model_dir '{custom_model_dir}'" in command_args
        assert f"--output_path '{custom_output_path}'" in command_args

    @patch.object(AgentKernel, "construct_prompt")
    def test_validate_execute_args_output_format(self, mock_construct_prompt):
        """Test validate_execute_args returns correctly formatted command arguments."""
        # Setup
        kernel = AgentKernel(
            api_token="test-token",
            codespace_id="test-codespace",
            base_url="https://test.example.com",
        )
        user_prompt = "Hello, assistant!"
        expected_chat_completion = '{"content": "test completion"}'
        mock_construct_prompt.return_value = expected_chat_completion

        # Execute
        command_args, _ = kernel.validate_execute_args(user_prompt)

        # Assert
        # Verify command_args structure with single quotes for arguments
        assert command_args.startswith("--chat_completion '")
        assert "--default_headers '{}'" in command_args
        assert "--custom_model_dir '" in command_args
        assert "--output_path '" in command_args

    @patch("agent_cli.kernel.OpenAI")
    def test_deployment_basic_functionality(self, mock_openai):
        """Test deployment method creates OpenAI client and calls chat.completions.create correctly."""
        # Setup
        kernel = AgentKernel(
            api_token="test-token",
            codespace_id="test-codespace",
            base_url="https://test.example.com",
        )
        deployment_id = "test-deployment-id"
        user_prompt = "Hello, assistant!"

        # Mock the OpenAI client and its methods
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_completions = Mock()
        mock_client.chat.completions = mock_completions
        mock_completion_obj = Mock(spec=ChatCompletion)
        mock_completions.create.return_value = mock_completion_obj

        # Execute
        result = kernel.deployment(deployment_id, user_prompt)

        # Assert
        # Verify OpenAI client was created with correct parameters
        mock_openai.assert_called_once_with(
            base_url=f"https://test.example.com/api/v2/deployments/{deployment_id}/",
            api_key="test-token",
            _strict_response_validation=False,
        )

        # Verify chat.completions.create was called with correct parameters
        mock_completions.create.assert_called_once_with(
            model="datarobot-deployed-agent",
            messages=[
                {
                    "role": "system",
                    "content": "Explain your thoughts using at least 100 words.",
                },
                {"role": "user", "content": "Hello, assistant!"},
            ],
            max_tokens=512,
            extra_body={
                "api_key": "test-token",
                "api_base": "https://test.example.com",
                "verbose": False,
            },
        )

        # Verify the result is the completion object
        assert result == mock_completion_obj

    @patch("agent_cli.kernel.OpenAI")
    @patch("builtins.print")
    def test_deployment_prints_debug_info(self, mock_print, mock_openai):
        """Test deployment method prints debug info."""
        # Setup
        kernel = AgentKernel(
            api_token="test-token",
            codespace_id="test-codespace",
            base_url="https://test.example.com",
        )
        deployment_id = "test-deployment-id"
        user_prompt = "Hello, assistant!"

        # Mock the OpenAI client
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_completions = Mock()
        mock_client.chat.completions = mock_completions
        mock_completions.create.return_value = Mock(spec=ChatCompletion)

        # Execute
        kernel.deployment(deployment_id, user_prompt)

        # Assert print statements were called with expected arguments
        expected_api_url = (
            "https://test.example.com/api/v2/deployments/test-deployment-id/"
        )
        mock_print.assert_any_call(expected_api_url)
        mock_print.assert_any_call(
            'Querying deployment with prompt: "Hello, assistant!"'
        )

    @patch("agent_cli.kernel.OpenAI")
    def test_deployment_error_handling(self, mock_openai):
        """Test deployment method propagates errors from OpenAI client."""
        # Setup
        kernel = AgentKernel(
            api_token="test-token",
            codespace_id="test-codespace",
            base_url="https://test.example.com",
        )
        deployment_id = "test-deployment-id"
        user_prompt = "Hello, assistant!"

        # Mock the OpenAI client to raise an exception
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_completions = Mock()
        mock_client.chat.completions = mock_completions
        mock_completions.create.side_effect = ValueError("Test error")

        # Execute and Assert
        with pytest.raises(ValueError, match="Test error"):
            kernel.deployment(deployment_id, user_prompt)

    @patch.object(AgentKernel, "validate_execute_args")
    @patch.object(AgentKernel, "await_kernel_execution")
    @patch.object(AgentKernel, "get_output_remote")
    @patch("requests.post")
    def test_execute_remote_success(
        self, mock_post, mock_get_output, mock_await, mock_validate
    ):
        """Test successful remote execution path."""
        # Setup
        kernel = AgentKernel(
            api_token="test-token",
            codespace_id="test-codespace",
            base_url="https://test.example.com",
        )

        # Mock validate_execute_args return values
        mock_validate.return_value = ("--test-args", "/test/output/path.json")

        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "kernelId": "test-kernel-id",
            "status": "executing",
        }
        mock_post.return_value = mock_response

        # Mock successful remote output retrieval
        expected_output = {"result": "success"}
        mock_get_output.return_value = expected_output

        # Execute
        result = kernel.execute("Test prompt", use_remote=True)

        # Assert
        mock_validate.assert_called_once_with("Test prompt", True, "", "")

        # Verify POST request was made correctly
        mock_post.assert_called_once_with(
            f"{kernel.nbx_session_url}/{kernel.codespace_id}/scripts/execute/",
            json={
                "filePath": "/home/notebooks/storage/run_agent.py",
                "commandType": "python",
                "commandArgs": "--test-args",
            },
            headers=kernel.headers,
        )

        # Verify kernel execution was awaited
        mock_await.assert_called_once_with("test-kernel-id")

        # Verify output was retrieved
        mock_get_output.assert_called_once_with("/test/output/path.json")

        # Verify correct result returned
        assert result == expected_output

    @patch.object(AgentKernel, "validate_execute_args")
    @patch("requests.post")
    def test_execute_remote_api_error(self, mock_post, mock_validate):
        """Test remote execution with API error."""
        # Setup
        kernel = AgentKernel(
            api_token="test-token",
            codespace_id="test-codespace",
            base_url="https://test.example.com",
        )

        # Mock validate_execute_args return values
        mock_validate.return_value = ("--test-args", "/test/output/path.json")

        # Mock API error response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Server error"
        mock_post.return_value = mock_response

        # Execute and Assert
        with pytest.raises(AssertionError):
            kernel.execute("Test prompt", use_remote=True)

    @patch.object(AgentKernel, "validate_execute_args")
    @patch.object(AgentKernel, "get_output_local")
    @patch("os.system")
    def test_execute_local_success(self, mock_system, mock_get_output, mock_validate):
        """Test successful local execution path."""
        # Setup
        kernel = AgentKernel(
            api_token="test-token",
            codespace_id="test-codespace",
            base_url="https://test.example.com",
        )

        # Mock validate_execute_args return values
        mock_validate.return_value = ("--test-args", "/local/output/path.json")

        # Mock successful command execution
        mock_system.return_value = 0

        # Mock successful local output retrieval
        expected_output = '{"result": "success"}'
        mock_get_output.return_value = expected_output

        # Execute
        result = kernel.execute("Test prompt", use_remote=False)

        # Assert
        mock_validate.assert_called_once_with("Test prompt", False, "", "")

        # Verify system command was executed correctly
        mock_system.assert_called_once_with("python3 run_agent.py --test-args")

        # Verify output was retrieved
        mock_get_output.assert_called_once_with("/local/output/path.json")

        # Verify correct result returned
        assert result == expected_output

    @patch.object(AgentKernel, "validate_execute_args")
    @patch("os.system")
    @patch("builtins.print")
    def test_execute_local_command_error(self, mock_print, mock_system, mock_validate):
        """Test local execution with command error."""
        # Setup
        kernel = AgentKernel(
            api_token="test-token",
            codespace_id="test-codespace",
            base_url="https://test.example.com",
        )

        # Mock validate_execute_args return values
        mock_validate.return_value = ("--test-args", "/local/output/path.json")

        # Mock failed command execution
        mock_system.return_value = 1

        # Execute and Assert
        with pytest.raises(RuntimeError, match="Command failed with exit code 1"):
            kernel.execute("Test prompt", use_remote=False)

    @patch.object(AgentKernel, "validate_execute_args")
    @patch("os.system")
    @patch("builtins.print")
    def test_execute_local_other_exception(
        self, mock_print, mock_system, mock_validate
    ):
        """Test local execution with unexpected exception."""
        # Setup
        kernel = AgentKernel(
            api_token="test-token",
            codespace_id="test-codespace",
            base_url="https://test.example.com",
        )

        # Mock validate_execute_args return values
        mock_validate.return_value = ("--test-args", "/local/output/path.json")

        # Mock system call throwing exception
        mock_system.side_effect = FileNotFoundError("Command not found")

        # Execute and Assert
        with pytest.raises(FileNotFoundError, match="Command not found"):
            kernel.execute("Test prompt", use_remote=False)

        # Verify error message was printed
        mock_print.assert_called_with("Error executing command: Command not found")

    @patch.object(AgentKernel, "validate_execute_args")
    @patch.object(AgentKernel, "await_kernel_execution")
    @patch.object(AgentKernel, "get_output_remote")
    @patch("requests.post")
    @patch("builtins.print")
    def test_execute_remote_with_custom_parameters(
        self, mock_print, mock_post, mock_get_output, mock_await, mock_validate
    ):
        """Test remote execution with custom parameters."""
        # Setup
        kernel = AgentKernel(
            api_token="test-token",
            codespace_id="test-codespace",
            base_url="https://test.example.com",
        )

        custom_model_dir = "/custom/model/dir"
        custom_output_path = "/custom/output/path.json"

        # Mock validate_execute_args return values
        mock_validate.return_value = ("--custom-args", custom_output_path)

        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "kernelId": "test-kernel-id",
            "status": "executing",
        }
        mock_post.return_value = mock_response

        # Mock successful remote output retrieval
        expected_output = {"result": "success"}
        mock_get_output.return_value = expected_output

        # Execute
        result = kernel.execute(
            "Test prompt",
            use_remote=True,
            custom_model_dir=custom_model_dir,
            output_path=custom_output_path,
        )

        # Assert
        mock_validate.assert_called_once_with(
            "Test prompt", True, custom_model_dir, custom_output_path
        )

        # Verify correct result returned
        assert result == expected_output
