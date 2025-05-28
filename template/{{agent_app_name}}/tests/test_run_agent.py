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
import os
from pathlib import Path
import tempfile
from unittest.mock import ANY, MagicMock, patch

import pytest
from pydantic import ValidationError

from run_agent import (
    DEFAULT_OUTPUT_LOG_PATH,
    execute_drum,
    main,
    setup_logging,
    construct_prompt,
    argparse_args,
    store_result,
)


class TestArgparseArgs:
    def test_argparse_args_custom_values(self):
        """Test that custom values are correctly parsed from command line arguments."""
        # Mock sys.argv to simulate passing command line arguments
        with patch(
            "sys.argv",
            [
                "run_agent.py",
                "--chat_completion",
                '{"messages": [{"role": "user", "content": "Hello"}]}',
                "--default_headers",
                '{"X-API-Key": "test-key"}',
                "--custom_model_dir",
                "/path/to/model",
                "--output_path",
                "/path/to/output",
            ],
        ):
            args = argparse_args()

            # Check custom values
            assert (
                args.chat_completion
                == '{"messages": [{"role": "user", "content": "Hello"}]}'
            )
            assert args.default_headers == '{"X-API-Key": "test-key"}'
            assert args.custom_model_dir == "/path/to/model"
            assert args.output_path == "/path/to/output"

    def test_argparse_args_partial_values(self):
        """Test that partial arguments work correctly with others taking default values."""
        # Mock sys.argv to simulate passing only some arguments
        with patch(
            "sys.argv",
            [
                "run_agent.py",
                "--chat_completion",
                '{"messages": []}',
                "--custom_model_dir",
                "/path/to/model",
            ],
        ):
            args = argparse_args()

            # Check mixture of custom and default values
            assert args.chat_completion == '{"messages": []}'
            assert args.default_headers == "{}"  # default
            assert args.custom_model_dir == "/path/to/model"
            assert args.output_path is None


class TestSetupLogging:
    @pytest.fixture
    def logger(self):
        logger = logging.getLogger("test_logger")
        # Clear any existing handlers
        logger.handlers = []
        return logger

    @patch("os.path.exists")
    @patch("os.remove")
    @patch("logging.StreamHandler")
    def test_setup_logging_with_empty_output_path(
        self, mock_stream_handler, mock_remove, mock_exists, logger
    ):
        # Set up mocks
        mock_stream = MagicMock()
        mock_stream_handler.return_value = mock_stream
        mock_exists.return_value = False

        # Call function with empty output path
        setup_logging(logger=logger, log_level=logging.INFO)

        # Verify logger configuration
        assert logger.level == logging.INFO
        assert len(logger.handlers) == 1
        mock_stream.setFormatter.assert_called_once()

        # Verify remove wasn't called since file doesn't exist
        mock_remove.assert_not_called()

    @patch("os.path.exists")
    @patch("logging.StreamHandler")
    def test_setup_logging_formatters(self, mock_stream_handler, mock_exists, logger):
        # Set up mocks
        mock_stream = MagicMock()
        mock_stream_handler.return_value = mock_stream
        mock_exists.return_value = False
        # Call function
        setup_logging(logger=logger, log_level=logging.INFO)

        # Verify formatters
        stream_formatter_call = mock_stream.setFormatter.call_args[0][0]
        assert stream_formatter_call._fmt == "%(asctime)s - %(levelname)s - %(message)s"


class TestConstructPrompt:
    def test_construct_prompt_valid_json(self):
        """Test that a valid JSON string is correctly parsed."""
        chat_completion = (
            '{"messages": [{"role": "user", "content": "Hello"}], "model": "gpt-4o"}'
        )
        result = construct_prompt(chat_completion)
        assert result["messages"] == [{"role": "user", "content": "Hello"}]
        assert result["model"] == "gpt-4o"

    def test_construct_prompt_adds_model_if_missing(self):
        """Test that a valid JSON string is correctly parsed."""
        chat_completion = '{"messages": [{"role": "user", "content": "Hello"}]}'
        result = construct_prompt(chat_completion)
        assert result["messages"] == [{"role": "user", "content": "Hello"}]
        assert result["model"] == "unknown"

    def test_construct_prompt_invalid_json(self):
        """Test that an invalid JSON string raises an error."""
        chat_completion = "invalid json"
        with pytest.raises(json.JSONDecodeError):
            construct_prompt(chat_completion)

    def test_construct_prompt_empty_json(self):
        """Test that an empty JSON string raises an error."""
        chat_completion = "{}"
        with pytest.raises(ValidationError):
            construct_prompt(chat_completion)

    def test_construct_prompt_unexpected_key(self):
        """Test that an unexpected key raises an error."""
        chat_completion = '{"messages": [{"role": "user", "content": "Hello"}], "unexpected_key": "value"}'

        # OpenAI interface accepts extra keys and ignores them
        prompt = construct_prompt(chat_completion)
        assert prompt["unexpected_key"] == "value"


class TestStoreResult:
    @patch("builtins.open")
    def test_store_result_success(self, mock_file_open):
        """Test that a result is correctly stored."""
        result = MagicMock()
        result.to_json.return_value = '{"id": "test-id", "choices": []}'
        store_result(result, "/path/to/output.json")
        mock_file_open.assert_called_once_with("/path/to/output.json", "w")
        mock_file_open.return_value.__enter__.return_value.write.assert_called_once_with(
            '{"id": "test-id", "choices": []}'
        )


class TestExecuteDrum:
    @patch("run_agent.DrumServerRun")
    @patch("run_agent.requests.get")
    @patch("run_agent.OpenAI")
    @patch("run_agent.root")
    def test_execute_drum_success(
        self,
        mock_root,
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
        mock_client.chat.completions.create.return_value = "result"
        mock_openai.return_value = mock_client

        # Call function
        result = execute_drum(
            chat_completion={"messages": [{"role": "user", "content": "Hello"}]},
            default_headers={"X-Custom": "value"},
            custom_model_dir="/path/to/model",
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

        # Verify result
        assert result == "result"

    @patch("run_agent.DrumServerRun")
    @patch("run_agent.requests.get")
    @patch("run_agent.OpenAI")
    @patch("run_agent.root")
    def test_execute_drum_default_output_path(
        self,
        mock_root,
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
        mock_client.chat.completions.create.return_value = "return_value"
        mock_openai.return_value = mock_client

        # Call function with empty output_path
        execute_drum(
            chat_completion={},
            default_headers={},
            custom_model_dir="/path/to/model",
        )

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
        mock_requests_get.return_value = mock_response

        # Call function and expect exception
        with pytest.raises(RuntimeError, match="Server failed to start"):
            execute_drum(
                chat_completion="{}",
                default_headers="{}",
                custom_model_dir="/path/to/model",
            )

        # Verify error logging
        mock_root.error.assert_any_call("Server failed to start")
        mock_root.error.assert_any_call("Server error")


class TestMain:
    @patch("run_agent.argparse_args")
    @patch("run_agent.construct_prompt")
    @patch("run_agent.execute_drum")
    @patch("run_agent.setup_logging")
    @patch("run_agent.store_result")
    @patch("builtins.open")
    def test_main_with_custom_model_dir(
        self,
        mock_file_open,
        mock_store_result,
        mock_setup_logging,
        mock_execute_drum,
        mock_construct_prompt,
        mock_argparse_args,
    ):
        """Test main function when custom_model_dir is provided."""
        # GIVEN simple input arguments
        mock_args = MagicMock()
        mock_args.chat_completion = '{"messages": []}'
        mock_args.default_headers = "{}"
        mock_args.custom_model_dir = "/path/to/custom/model"
        mock_args.output_path = "/path/to/output"
        mock_argparse_args.return_value = mock_args

        # GIVEN a mock completion
        mock_completion = MagicMock()
        mock_execute_drum.return_value = mock_completion

        # GIVEN mock_construct_prompt returns a dict
        mock_construct_prompt.return_value = {"messages": []}

        # WHEN main is called
        main()

        # THEN argparse_args was called
        mock_argparse_args.assert_called_once()

        # THEN setup_logging was called with correct parameters
        mock_setup_logging.assert_called_once_with(logger=ANY, log_level=logging.INFO)

        # THEN execute_drum was called with correct parameters
        mock_execute_drum.assert_called_once_with(
            chat_completion={"messages": []},
            default_headers={},
            custom_model_dir="/path/to/custom/model",
        )

        # THEN store_result was called with correct parameters
        mock_store_result.assert_called_once_with(
            mock_completion,
            "/path/to/output",
        )

        # THEN file open was called with correct parameters
        mock_file_open.assert_any_call(Path("/path/to/output.log"), "a")
        mock_file_open.assert_any_call(Path(DEFAULT_OUTPUT_LOG_PATH), "w")

    @pytest.fixture
    def tempdir_and_cleanup(self):
        with tempfile.TemporaryDirectory() as tempdir:
            yield Path(tempdir)
        # Also remove the default output log path
        os.remove(DEFAULT_OUTPUT_LOG_PATH)

    @patch("run_agent.argparse_args")
    @patch("run_agent.execute_drum")
    def test_main_integration(
        self, mock_execute_drum, mock_argparse_args, tempdir_and_cleanup
    ):
        """Test main function with a more integrated approach."""
        # GIVEN valid input arguments
        mock_args = MagicMock()
        mock_args.chat_completion = (
            '{"messages": [{"role": "user", "content": "Hello"}]}'
        )
        mock_args.default_headers = '{"X-Custom": "value"}'
        mock_args.custom_model_dir = "/path/to/model"
        # GIVEN a temporary directory for the output path
        mock_args.output_path = str(tempdir_and_cleanup / "output.json")
        mock_argparse_args.return_value = mock_args

        # GIVEN a mock completion returned from execute_drum
        mock_completion = MagicMock()
        mock_completion.to_json.return_value = '{"id": "test-id", "choices": []}'
        mock_execute_drum.return_value = mock_completion

        # WHEN main is called
        main()

        # THEN execute_drum was called with correct parsed parameters
        mock_execute_drum.assert_called_once_with(
            chat_completion={
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "unknown",
            },
            default_headers={"X-Custom": "value"},
            custom_model_dir="/path/to/model",
        )

        # THEN results were stored in the temporary directory
        assert os.path.exists(tempdir_and_cleanup / "output.json")
        with open(tempdir_and_cleanup / "output.json", "r") as f:
            assert f.read() == mock_completion.to_json.return_value

        # THEN the output log was stored in the temporary directory
        assert os.path.exists(tempdir_and_cleanup / "output.json.log")
        with open(tempdir_and_cleanup / "output.json.log", "r") as f:
            assert "Setting up logging" in f.read()

        # THEN the default output log path was created and used for the args processing
        assert os.path.exists(DEFAULT_OUTPUT_LOG_PATH)
        with open(DEFAULT_OUTPUT_LOG_PATH, "r") as f:
            assert f.read() == "Parsing args\n"
