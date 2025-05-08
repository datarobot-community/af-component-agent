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

# pylint: skip-file

import argparse
import json
import os
from typing import Any, cast

import requests
from custom import chat, load_model
from datarobot_drum.drum.enum import TargetType
from datarobot_drum.drum.root_predictors.drum_server_utils import DrumServerRun
from openai import OpenAI
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)
from openai.types.chat.completion_create_params import (
    CompletionCreateParamsNonStreaming,
)

parser = argparse.ArgumentParser()
parser.add_argument(
    "--store_output", action="store_true", help="Store output in a file"
)
parser.add_argument(
    "--use_drum",
    action="store_true",
    help="Use DRUM for execution instead of direct execution",
)
parser.add_argument(
    "--user_prompt", type=str, default="", help="user_prompt for chat endpoint"
)
parser.add_argument(
    "--extra_body", type=str, default="", help="extra_body for chat endpoint"
)
args = parser.parse_args()


class RunAgent:
    """
    This class is responsible for running the agent. It can run in two modes:
        - :code:`execute_direct`: Directly using the chat endpoint.
        - :code:`execute_drum`: Using the DRUM server.
    """

    @property
    def code_dir(self) -> str:
        return os.path.split(os.path.abspath(__file__))[0]

    @staticmethod
    def construct_prompt(
        user_prompt: str, extra_body: str, merge_extra_body: bool = True
    ) -> Any:
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
        if merge_extra_body:
            completion_create_params.update(**extra_body_params)  # type: ignore[call-arg]
        return completion_create_params

    def execute_direct(self, user_prompt: str, extra_body: str) -> ChatCompletion:
        print("Executing agent as [chat] endpoint. Local Executor.")
        completion_create_params = self.construct_prompt(user_prompt, extra_body)

        # Use direct execution of the agent. This is more straightforward to debug agent code related issues.
        model = load_model(code_dir=self.code_dir)
        completion = chat(completion_create_params, model)

        return cast(ChatCompletion, completion)

    def execute_drum(self, user_prompt: str, extra_body: str) -> ChatCompletion:
        print("Executing agent as [chat] endpoint. DRUM Executor.")
        print(
            "NOTE: Realtime logging will be delayed in terminal and displayed after execution."
        )

        with DrumServerRun(
            target_type=TargetType.TEXT_GENERATION.value,
            labels=None,
            custom_model_dir=self.code_dir,
            with_error_server=True,
            production=False,
            verbose=True,
            logging_level="info",
            target_name="response",
            wait_for_server_timeout=360,
            port=8191,
        ) as drum_runner:
            response = requests.get(drum_runner.url_server_address)
            if not response.ok:
                raise RuntimeError("Server failed to start")

            # Use a standard OpenAI client to call the DRUM server. This mirrors the behavior of a deployed agent.
            client = OpenAI(
                base_url=drum_runner.url_server_address,
                api_key="not-required",
                max_retries=0,
            )
            completion_create_params = self.construct_prompt(
                user_prompt, extra_body, merge_extra_body=False
            )
            completion = client.chat.completions.create(**completion_create_params)

            return cast(ChatCompletion, completion)

    def store_output(self, chat_result: ChatCompletion) -> None:
        print(f"Storing result: {self.code_dir}/output.json")
        with open(os.path.join(self.code_dir, "output.json"), "w") as fp:
            fp.write(chat_result.to_json())


# This is the main entry point for the script
runner = RunAgent()
if args.use_drum:
    result = runner.execute_drum(
        user_prompt=args.user_prompt, extra_body=args.extra_body
    )
else:
    result = runner.execute_direct(
        user_prompt=args.user_prompt, extra_body=args.extra_body
    )

# Store results to file if requested
if args.store_output:
    runner.store_output(result)
