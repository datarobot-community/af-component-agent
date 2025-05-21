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
import logging
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from run_agent import execute_drum, setup_logging


class TestRunAgentConsistency:
    def test_run_agent_files_are_identical(self):
        """Test that run_agent.py and docker_context/run_agent.py have identical content."""
        # Get the project root directory (assumes test is running from project root or tests directory)
        project_root = Path(__file__).parent.parent

        # Define paths to both files
        main_file = project_root / "run_agent.py"
        docker_file = project_root / "docker_context" / "run_agent.py"

        # Assert both files exist
        assert main_file.exists(), f"Main file not found: {main_file}"
        assert docker_file.exists(), f"Docker file not found: {docker_file}"

        # Read content of both files
        with open(main_file, "r") as f1:
            main_content = f1.read()

        with open(docker_file, "r") as f2:
            docker_content = f2.read()

        # Assert contents are identical
        assert main_content == docker_content, "Files have different content"


class TestSetupLogging:
    @pytest.fixture
    def logger(self):
        logger = logging.getLogger("test_logger")
        # Clear any existing handlers
        logger.handlers = []
        return logger

    @patch("os.path.exists")
    @patch("os.remove")
    @patch("logging.FileHandler")
    @patch("logging.StreamHandler")
    def test_setup_logging_with_empty_output_path(
        self, mock_stream_handler, mock_file_handler, mock_remove, mock_exists, logger
    ):
        # Set up mocks
        mock_stream = MagicMock()
        mock_stream_handler.return_value = mock_stream
        mock_file = MagicMock()
        mock_file_handler.return_value = mock_file
        mock_exists.return_value = False

        # Call function with empty output path
        setup_logging(logger=logger, output_path="", log_level=logging.INFO)

        # Verify correct output_path is used
        mock_file_handler.assert_called_once_with("output.log")

        # Verify logger configuration
        assert logger.level == logging.INFO
        assert len(logger.handlers) == 2
        mock_stream.setFormatter.assert_called_once()
        mock_file.setFormatter.assert_called_once()

        # Verify remove wasn't called since file doesn't exist
        mock_remove.assert_not_called()

    @patch("os.path.exists")
    @patch("os.remove")
    @patch("logging.FileHandler")
    @patch("logging.StreamHandler")
    def test_setup_logging_with_custom_output_path(
        self, mock_stream_handler, mock_file_handler, mock_remove, mock_exists, logger
    ):
        # Set up mocks
        mock_stream = MagicMock()
        mock_stream_handler.return_value = mock_stream
        mock_file = MagicMock()
        mock_file_handler.return_value = mock_file
        mock_exists.return_value = True

        # Call function with custom output path
        setup_logging(logger=logger, output_path="custom_path", log_level=logging.DEBUG)

        # Verify correct output_path is used
        mock_file_handler.assert_called_once_with("custom_path.log")

        # Verify logger configuration
        assert logger.level == logging.DEBUG
        assert len(logger.handlers) == 2

        # Verify existing file was removed
        mock_exists.assert_called_once_with("custom_path.log")
        mock_remove.assert_called_once_with("custom_path.log")

    @patch("os.path.exists")
    @patch("logging.FileHandler")
    @patch("logging.StreamHandler")
    def test_setup_logging_formatters(
        self, mock_stream_handler, mock_file_handler, mock_exists, logger
    ):
        # Set up mocks
        mock_stream = MagicMock()
        mock_stream_handler.return_value = mock_stream
        mock_file = MagicMock()
        mock_file_handler.return_value = mock_file
        mock_exists.return_value = False

        # Call function
        setup_logging(logger=logger, output_path="test", log_level=logging.INFO)

        # Verify formatters
        stream_formatter_call = mock_stream.setFormatter.call_args[0][0]
        assert stream_formatter_call._fmt == "%(message)s"

        file_formatter_call = mock_file.setFormatter.call_args[0][0]
        assert file_formatter_call._fmt == "%(asctime)s - %(levelname)s - %(message)s"


class TestExecuteDrum:
    @patch("run_agent.DrumServerRun")
    @patch("run_agent.requests.get")
    @patch("run_agent.OpenAI")
    @patch("builtins.open", new_callable=mock_open)
    @patch("run_agent.root")
    def test_execute_drum_success(
        self,
        mock_root,
        mock_file_open,
        mock_openai,
        mock_requests_get,
        mock_drum_server,
    ):
        # Setup mocks
        mock_drum_instance = MagicMock()
        mock_drum_instance.url_server_address = "http://localhost:8191"
        mock_drum_server.return_value.__enter__.return_value = mock_drum_instance

        mock_response = MagicMock()
        mock_response.ok = True
        mock_requests_get.return_value = mock_response

        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.to_json.return_value = '{"id": "test-id", "choices": []}'
        mock_client.chat.completions.create.return_value = mock_completion
        mock_openai.return_value = mock_client

        # Call function
        result = execute_drum(
            chat_completion='{"messages": [{"role": "user", "content": "Hello"}]}',
            default_headers='{"X-Custom": "value"}',
            custom_model_dir="/path/to/model",
            output_path="/path/to/output.json",
        )

        # Verify DrumServerRun was called with correct parameters
        mock_drum_server.assert_called_once_with(
            target_type="textgeneration",
            labels=None,
            custom_model_dir="/path/to/model",
            with_error_server=True,
            production=False,
            verbose=True,
            logging_level="info",
            target_name="response",
            wait_for_server_timeout=360,
            port=8191,
            stream_output=True,
        )

        # Verify server verification was performed
        mock_requests_get.assert_called_once_with("http://localhost:8191")

        # Verify OpenAI client was created with correct params
        mock_openai.assert_called_once_with(
            base_url="http://localhost:8191",
            api_key="not-required",
            default_headers={"X-Custom": "value"},
            max_retries=0,
        )

        # Verify completion creation
        mock_client.chat.completions.create.assert_called_once_with(
            messages=[{"role": "user", "content": "Hello"}]
        )

        # Verify file output
        mock_file_open.assert_called_once_with("/path/to/output.json", "w")
        mock_file_open().write.assert_called_once_with(
            '{"id": "test-id", "choices": []}'
        )

        # Verify result
        assert result == mock_completion

    @patch("run_agent.DrumServerRun")
    @patch("run_agent.requests.get")
    @patch("run_agent.OpenAI")
    @patch("builtins.open", new_callable=mock_open)
    @patch("run_agent.root")
    @patch("os.path.join")
    def test_execute_drum_default_output_path(
        self,
        mock_path_join,
        mock_root,
        mock_file_open,
        mock_openai,
        mock_requests_get,
        mock_drum_server,
    ):
        # Setup mocks
        mock_drum_instance = MagicMock()
        mock_drum_instance.url_server_address = "http://localhost:8191"
        mock_drum_server.return_value.__enter__.return_value = mock_drum_instance

        mock_response = MagicMock()
        mock_response.ok = True
        mock_requests_get.return_value = mock_response

        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.to_json.return_value = '{"id": "test-id", "choices": []}'
        mock_client.chat.completions.create.return_value = mock_completion
        mock_openai.return_value = mock_client

        mock_path_join.return_value = "/path/to/model/output.json"

        # Call function with empty output_path
        execute_drum(
            chat_completion="{}",
            default_headers="{}",
            custom_model_dir="/path/to/model",
            output_path="",
        )

        # Verify path joining for default output path
        mock_path_join.assert_called_once_with("/path/to/model", "output.json")

        # Verify file output used default path
        mock_file_open.assert_called_once_with("/path/to/model/output.json", "w")

    @patch("run_agent.DrumServerRun")
    @patch("run_agent.requests.get")
    @patch("run_agent.root")
    def test_execute_drum_server_failure(
        self, mock_root, mock_requests_get, mock_drum_server
    ):
        # Setup mocks
        mock_drum_instance = MagicMock()
        mock_drum_instance.url_server_address = "http://localhost:8191"
        mock_drum_server.return_value.__enter__.return_value = mock_drum_instance

        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.text = "Server error"
        mock_response.json.return_value = {"error": "Failed to start"}
        mock_requests_get.return_value = mock_response

        # Call function and expect exception
        with pytest.raises(RuntimeError, match="Server failed to start"):
            execute_drum(
                chat_completion="{}",
                default_headers="{}",
                custom_model_dir="/path/to/model",
                output_path="/path/to/output.json",
            )

        # Verify error logging
        mock_root.error.assert_any_call("Server failed to start")
        mock_root.error.assert_any_call("Server error")
        mock_root.error.assert_any_call({"error": "Failed to start"})

    @patch("run_agent.DrumServerRun")
    @patch("run_agent.requests.get")
    @patch("run_agent.root")
    def test_execute_drum_server_failure_json_error(
        self, mock_root, mock_requests_get, mock_drum_server
    ):
        # Setup mocks
        mock_drum_instance = MagicMock()
        mock_drum_instance.url_server_address = "http://localhost:8191"
        mock_drum_server.return_value.__enter__.return_value = mock_drum_instance

        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.text = "Server error"
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_requests_get.return_value = mock_response

        # Call function and expect exception
        with pytest.raises(RuntimeError, match="Server failed to start"):
            execute_drum(
                chat_completion="{}",
                default_headers="{}",
                custom_model_dir="/path/to/model",
                output_path="/path/to/output.json",
            )

        # Verify error logging - should only log text not JSON
        mock_root.error.assert_any_call("Server failed to start")
        mock_root.error.assert_any_call("Server error")
