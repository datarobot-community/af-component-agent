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
from unittest.mock import MagicMock, patch


class TestCustomModel:
    @staticmethod
    def assert_dict_equal_ignore_key(dict1, dict2, keys_to_ignore):
        # Create copies of dictionaries to avoid modifying originals
        temp_dict1 = dict1.copy()
        temp_dict2 = dict2.copy()

        # Remove the key to ignore from both dictionaries
        for key in keys_to_ignore:
            temp_dict1.pop(key, None)
            temp_dict2.pop(key, None)

        # Assert that the remaining parts are equal
        assert temp_dict1 == temp_dict2, (
            f"Dictionaries are not equal except for keys '{keys_to_ignore}'"
        )

    def test_load_model(self):
        from custom import load_model

        result = load_model("")
        assert result == "success"

    @patch("custom.MyAgent")
    def test_chat(self, mock_agent, mock_agent_response):
        from custom import chat

        # Setup mocks
        mock_agent_instance = MagicMock()
        mock_agent_instance.run.return_value = mock_agent_response
        mock_agent.return_value = mock_agent_instance

        completion_create_params = {
            "model": "test-model",
            "messages": [{"role": "user", "content": '{"topic": "test"}'}],
            "environment_var": True,
        }

        response = chat(completion_create_params, model="test-model")

        # Assert results
        self.assert_dict_equal_ignore_key(
            json.loads(response.json()),
            {
                "id": "3b6abcaa-fb8e-47e2-8ad5-f09cc922990b",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "index": 0,
                        "logprobs": None,
                        "message": {
                            "content": "agent result",
                            "refusal": None,
                            "role": "assistant",
                            "annotations": None,
                            "audio": None,
                            "function_call": None,
                            "tool_calls": None,
                        },
                    }
                ],
                "created": 1748464162,
                "model": "MODEL_NAME",
                "object": "chat.completion",
                "service_tier": None,
                "system_fingerprint": None,
                "usage": {
                    "completion_tokens": 1,
                    "prompt_tokens": 2,
                    "total_tokens": 3,
                    "completion_tokens_details": None,
                    "prompt_tokens_details": None,
                },
                "pipeline_interactions": None,
            },
            keys_to_ignore=["id", "created"],
        )

        # Verify mocks were called correctly
        mock_agent.assert_called_once_with(**completion_create_params)
        mock_agent_instance.run.assert_called_once_with(
            completion_create_params={
                "model": "test-model",
                "messages": [{"role": "user", "content": '{"topic": "test"}'}],
                "environment_var": True,
            }
        )
