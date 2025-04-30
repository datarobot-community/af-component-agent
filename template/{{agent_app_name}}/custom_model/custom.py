# Copyright 2025 DataRobot, Inc. and its affiliates.
#
# All rights reserved.
#
# This is proprietary source code of DataRobot, Inc. and its affiliates.
#
# Released under the terms of DataRobot Tool and Utility Agreement.
from typing import Iterator

from helpers import create_completion_from_response_text
from helpers import create_inputs_from_completion_params
from my_agent_class.agent import MyAgent
from openai.types.chat import ChatCompletion
from openai.types.chat import ChatCompletionChunk
from openai.types.chat import CompletionCreateParams


def load_model(code_dir: str) -> str:
    """The agent is instantiated in this function and returned."""
    _ = code_dir
    return "success"


def chat(
    completion_create_params: CompletionCreateParams,
    model: str,
) -> ChatCompletion | Iterator[ChatCompletionChunk]:
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

    # Instantiate the agent, all fields from the completion_create_params are passed to the agent
    # allowing environment variables to be passed during execution
    agent = MyAgent(**completion_create_params)

    # Load the user prompt from the completion_create_params as JSON or a string
    inputs = create_inputs_from_completion_params(completion_create_params)

    # Execute the agent with the inputs
    response = agent.run(inputs=inputs)

    # Return the response as a ChatCompletion object
    response = create_completion_from_response_text(response)
    return response
