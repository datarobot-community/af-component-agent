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
    "--user_prompt", type=str, default="", help="user_prompt for chat endpoint"
)
parser.add_argument(
    "--extra_body", type=str, default="", help="extra_body for chat endpoint"
)
parser.add_argument(
    "--custom_model_dir",
    type=str,
    default="",
    help="directory containing custom.py location",
)
parser.add_argument(
    "--output_path", type=str, default="", help="json output file location"
)
args = parser.parse_args()


def construct_prompt(user_prompt: str, extra_body: str) -> Any:
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
    return completion_create_params


def execute_drum(
    user_prompt: str, extra_body: str, custom_model_dir: str, output_path: str
) -> ChatCompletion:
    print("Executing agent as [chat] endpoint. DRUM Executor.")
    print(
        "NOTE: Realtime logging may be delayed in terminal and displayed after execution."
    )
    with DrumServerRun(
        target_type=TargetType.TEXT_GENERATION.value,
        labels=None,
        custom_model_dir=custom_model_dir,
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
        completion_create_params = construct_prompt(user_prompt, extra_body)
        completion = client.chat.completions.create(**completion_create_params)

        print(f"Storing result: {output_path}")
        if len(output_path) == 0:
            output_path = os.path.join(custom_model_dir, "output.json")
        with open(output_path, "w") as fp:
            fp.write(completion.to_json())

        return cast(ChatCompletion, completion)


# Agent execution
if len(args.custom_model_dir) == 0:
    args.custom_model_dir = os.path.join(os.getcwd(), "custom_model")
result = execute_drum(
    user_prompt=args.user_prompt,
    extra_body=args.extra_body,
    custom_model_dir=args.custom_model_dir,
    output_path=args.output_path,
)
