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
from typing import Any

from openai import OpenAI
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)
from openai.types.chat.completion_create_params import (
    CompletionCreateParamsNonStreaming,
)


class Kernel:
    def __init__(
        self,
        api_token: str,
        base_url: str,
    ):
        self.base_url = base_url
        self.api_token = api_token

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Token {self.api_token}",
        }

    @staticmethod
    def construct_prompt(user_prompt: str, extra_body: str) -> str:
        extra_body_params = json.loads(extra_body) if extra_body else {}
        completion_create_params = CompletionCreateParamsNonStreaming(
            model="datarobot-deployed-llm",
            messages=[
                ChatCompletionSystemMessageParam(
                    content="You are a helpful assistant",
                    role="system",
                ),
                ChatCompletionUserMessageParam(
                    content=user_prompt,
                    role="user",
                ),
            ],
            n=1,
            temperature=0.01,
            extra_body=extra_body_params,  # type: ignore[typeddict-unknown-key]
        )
        completion = json.dumps(completion_create_params)
        return completion

    def validate_and_create_execute_args(
        self,
        user_prompt: str,
        custom_model_dir: str = "",
        output_path: str = "",
    ) -> tuple[str, str]:
        if len(user_prompt) == 0:
            raise ValueError("user_prompt must be provided.")

        # Construct the raw prompt and headers
        extra_body = json.dumps(
            {
                "api_key": self.api_token,
                "api_base": self.base_url,
                "verbose": True,
            }
        )
        chat_completion = self.construct_prompt(user_prompt, extra_body)
        default_headers = "{}"

        if len(custom_model_dir) == 0:
            custom_model_dir = os.path.join(os.getcwd(), "custom_model")

        if len(output_path) == 0:
            output_path = os.path.join(os.getcwd(), "custom_model", "output.json")

        command_args = (
            f"--chat_completion '{chat_completion}' "
            f"--default_headers '{default_headers}'"
            f" --custom_model_dir '{custom_model_dir}'"
            f" --output_path '{output_path}'"
        )

        return command_args, output_path

    @staticmethod
    def get_output(output_path: str) -> Any:
        """Read the local output file and remove it."""
        with open(output_path, "r") as f:
            output = f.read()

        if os.path.exists(output_path):
            os.remove(output_path)
        return output

    def local(
        self,
        user_prompt: str,
        custom_model_dir: str = "",
        output_path: str = "",
    ) -> Any:
        command_args, output_path = self.validate_and_create_execute_args(
            user_prompt, custom_model_dir, output_path
        )

        local_cmd = f"python3 run_agent.py {command_args}"
        try:
            result = os.system(local_cmd)
            if result != 0:
                raise RuntimeError(f"Command failed with exit code {result}")
            return self.get_output(output_path)
        except Exception as e:
            print(f"Error executing command: {e}")
            raise

    def deployment(self, deployment_id: str, user_prompt: str) -> ChatCompletion:
        chat_api_url = f"{self.base_url}/api/v2/deployments/{deployment_id}/"
        print(chat_api_url)
        openai_client = OpenAI(
            base_url=chat_api_url,
            api_key=self.api_token,
            _strict_response_validation=False,
        )

        print(f'Querying deployment with prompt: "{user_prompt}"')
        completion = openai_client.chat.completions.create(
            model="datarobot-deployed-agent",
            messages=[
                {
                    "role": "system",
                    "content": "Explain your thoughts using at least 100 words.",
                },
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=512,  # omit if you want to use the model's default max
            extra_body={
                "api_key": self.api_token,
                "api_base": self.base_url,
                "verbose": False,
            },
        )
        return completion
