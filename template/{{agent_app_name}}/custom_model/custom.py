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

from typing import Dict, Iterator, Union, cast

from helpers import (
    create_completion_from_response_text,
    create_inputs_from_completion_params,
)
from my_agent_class.agent import MyAgent
from tools.auth import initialize_authorization_context
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionChunk,
    CompletionCreateParams,
)


def load_model(code_dir: str) -> str:
    """The agent is instantiated in this function and returned."""
    _ = code_dir
    return "success"


def chat(
    completion_create_params: CompletionCreateParams,
    model: str,
) -> Union[ChatCompletion, Iterator[ChatCompletionChunk]]:
    """When using the chat endpoint, this function is called.

    Agent inputs are in OpenAI message format and defined as the 'user' portion
    of the input prompt.

    Example:
        prompt = {
            "topic": "Artificial Intelligence",
        }
        client = OpenAI(...)
        completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": f"{json.dumps(prompt)}"},
            ],
            extra_body = {
                "environment_var": True,
            },
            ...
        )
    """
    _ = model

    # Initialize the authorization context for downstream agents and tools to retrieve
    # access tokens for external services.
    initialize_authorization_context(completion_create_params)

    # Instantiate the agent, all fields from the completion_create_params are passed to the agent
    # allowing environment variables to be passed during execution
    agent = MyAgent(**completion_create_params)

    # Load the user prompt from the completion_create_params as JSON or a string
    inputs = create_inputs_from_completion_params(completion_create_params)

    # Execute the agent with the inputs
    response, usage_metrics = agent.run(inputs=inputs)
    response = str(response)
    usage_metrics = cast(Dict[str, int], usage_metrics)

    # Return the response as a ChatCompletion object
    response = create_completion_from_response_text(
        response_text=response, usage_metrics=usage_metrics
    )
    return response  # type: ignore[no-any-return]
