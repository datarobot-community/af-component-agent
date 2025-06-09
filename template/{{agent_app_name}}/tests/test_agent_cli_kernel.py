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
from openai.types.chat import ChatCompletion

from agent_cli.kernel import AgentKernel, Kernel


class TestKernel:
    def test_headers_property(self):
        """Test headers property returns correct authorization header."""
        kernel = Kernel(api_token="api-123456")

        headers = kernel.headers

        assert headers == {"Authorization": "Token api-123456"}

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
    def test_get_output_success(self, mock_file, mock_remove, mock_exists):
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
    def test_get_output_file_not_exists(
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
    def test_get_output_file_not_found(self, mock_file):
        """Test get_output_local raises FileNotFoundError if file doesn't exist."""
        # Setup
        output_path = "/test/output/path.json"

        # Execute and Assert
        with pytest.raises(FileNotFoundError):
            Kernel.get_output(output_path)
        mock_file.assert_called_once_with(output_path, "r")

    def test_validate_execute_args_empty_prompt(self):
        """Test validate_execute_args raises ValueError with empty prompt."""
        # Setup
        kernel = Kernel(
            api_token="test-token",
            base_url="https://test.example.com",
        )

        # Execute and Assert
        with pytest.raises(ValueError, match="user_prompt must be provided."):
            kernel.validate_and_create_execute_args(user_prompt="")

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
        command_args, output_path = kernel.validate_and_create_execute_args(user_prompt)

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

    @patch.object(Kernel, "construct_prompt")
    def test_validate_execute_args_remote(self, mock_construct_prompt):
        """Test validate_execute_args with remote execution."""
        # Setup
        kernel = Kernel(
            api_token="test-token",
            base_url="https://test.example.com",
        )
        user_prompt = "Hello, assistant!"
        expected_chat_completion = '{"content": "test completion"}'
        mock_construct_prompt.return_value = expected_chat_completion

        # Execute
        command_args, output_path = kernel.validate_and_create_execute_args(
            user_prompt
        )

        # Assert
        # Verify remote paths are used
        expected_model_dir = "/home/notebooks/storage/custom_model"
        expected_output_path = "/home/notebooks/storage/custom_model/output.json"
        assert output_path == expected_output_path

        # Verify command_args contains all parameters with remote paths
        assert f"--custom_model_dir '{expected_model_dir}'" in command_args
        assert f"--output_path '{expected_output_path}'" in command_args

    @patch.object(Kernel, "construct_prompt")
    def test_validate_execute_args_custom_paths(self, mock_construct_prompt):
        """Test validate_execute_args with custom model_dir and output_path."""
        # Setup
        kernel = Kernel(
            api_token="test-token",
            base_url="https://test.example.com",
        )
        user_prompt = "Hello, assistant!"
        custom_model_dir = "/custom/path/model"
        custom_output_path = "/custom/path/output.json"
        expected_chat_completion = '{"content": "test completion"}'
        mock_construct_prompt.return_value = expected_chat_completion

        # Execute
        command_args, output_path = kernel.validate_and_create_execute_args(
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

    @patch.object(Kernel, "construct_prompt")
    def test_validate_execute_args_output_format(self, mock_construct_prompt):
        """Test validate_execute_args returns correctly formatted command arguments."""
        # Setup
        kernel = Kernel(
            api_token="test-token",
            base_url="https://test.example.com",
        )
        user_prompt = "Hello, assistant!"
        expected_chat_completion = '{"content": "test completion"}'
        mock_construct_prompt.return_value = expected_chat_completion

        # Execute
        command_args, _ = kernel.validate_and_create_execute_args(user_prompt)

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
        kernel = Kernel(
            api_token="test-token",
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
        kernel = Kernel(
            api_token="test-token",
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
        kernel = Kernel(
            api_token="test-token",
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

    @patch.object(Kernel, "validate_execute_args")
    @patch.object(Kernel, "get_output_local")
    @patch("os.system")
    def test_local_success(self, mock_system, mock_get_output, mock_validate):
        """Test successful local execution path."""
        # Setup
        kernel = Kernel(
            api_token="test-token",
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
        result = kernel.local("Test prompt", use_remote=False)

        # Assert
        mock_validate.assert_called_once_with("Test prompt", False, "", "")

        # Verify system command was executed correctly
        mock_system.assert_called_once_with("python3 run_agent.py --test-args")

        # Verify output was retrieved
        mock_get_output.assert_called_once_with("/local/output/path.json")

        # Verify correct result returned
        assert result == expected_output

    @patch.object(Kernel, "validate_execute_args")
    @patch("os.system")
    def test_local_command_error(self, mock_system, mock_validate):
        """Test local execution with command error."""
        # Setup
        kernel = Kernel(
            api_token="test-token",
            base_url="https://test.example.com",
        )

        # Mock validate_execute_args return values
        mock_validate.return_value = ("--test-args", "/local/output/path.json")

        # Mock failed command execution
        mock_system.return_value = 1

        # Execute and Assert
        with pytest.raises(RuntimeError, match="Command failed with exit code 1"):
            kernel.local("Test prompt", use_remote=False)

    @patch.object(Kernel, "validate_execute_args")
    @patch("os.system")
    @patch("builtins.print")
    def test_local_other_exception(
        self, mock_print, mock_system, mock_validate
    ):
        """Test local execution with unexpected exception."""
        # Setup
        kernel = Kernel(
            api_token="test-token",
            base_url="https://test.example.com",
        )

        # Mock validate_execute_args return values
        mock_validate.return_value = ("--test-args", "/local/output/path.json")

        # Mock system call throwing exception
        mock_system.side_effect = FileNotFoundError("Command not found")

        # Execute and Assert
        with pytest.raises(FileNotFoundError, match="Command not found"):
            kernel.local("Test prompt", use_remote=False)

        # Verify error message was printed
        mock_print.assert_called_with("Error executing command: Command not found")
