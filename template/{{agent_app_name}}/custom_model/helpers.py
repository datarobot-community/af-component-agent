# Copyright 2025 DataRobot, Inc. and its affiliates.
#
# All rights reserved.
#
# This is proprietary source code of DataRobot, Inc. and its affiliates.
#
# Released under the terms of DataRobot Tool and Utility Agreement.
import json
import time
import uuid
from typing import Union

from openai.types.chat import ChatCompletion
from openai.types.chat import ChatCompletionMessage
from openai.types.chat import CompletionCreateParams
from openai.types.chat.chat_completion import Choice


def create_inputs_from_completion_params(
    completion_create_params: CompletionCreateParams,
) -> Union[dict, str]:
    """Load the user prompt from a JSON string or file."""
    input_prompt = next(
        (msg for msg in completion_create_params["messages"] if msg.get("role") == "user"),
        {},
    )
    if len(input_prompt) == 0:
        raise ValueError("No user prompt found in the messages.")
    user_prompt = input_prompt.get("content")

    try:
        inputs = json.loads(user_prompt)
    except json.JSONDecodeError:
        inputs = user_prompt

    return inputs


def create_completion_from_response_text(response_text: str) -> ChatCompletion:
    """Convert the text of the LLM response into a chat completion response."""
    completion_id = str(uuid.uuid4())
    completion_timestamp = int(time.time())

    choice = Choice(
        index=0,
        message=ChatCompletionMessage(role="assistant", content=response_text),
        finish_reason="stop",
    )
    completion = ChatCompletion(
        id=completion_id,
        object="chat.completion",
        choices=[choice],
        created=completion_timestamp,
        model="MODEL_NAME",
    )

    return completion
