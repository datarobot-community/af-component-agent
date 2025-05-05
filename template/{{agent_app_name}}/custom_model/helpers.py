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
import functools
import json
import time
import uuid
from typing import Any, Callable, Dict, Tuple, TypeVar, Union, cast

from crewai import CrewOutput
from openai.types import CompletionUsage
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionMessage,
    CompletionCreateParams,
)
from openai.types.chat.chat_completion import Choice

FuncT = TypeVar("FuncT", bound=Callable[..., Any])


def deployment_response_crewai(func: FuncT) -> FuncT:
    @functools.wraps(func)
    def wrapper_response_crewai(
        *args: Any, **kwargs: Any
    ) -> Tuple[str, Dict[str, int]]:
        value: CrewOutput = func(*args, **kwargs)

        usage_metrics: Dict[str, int] = {
            "completion_tokens": value.token_usage.completion_tokens,
            "prompt_tokens": value.token_usage.prompt_tokens,
            "total_tokens": value.token_usage.total_tokens,
        }
        return str(value.raw), usage_metrics

    return cast(FuncT, wrapper_response_crewai)


def create_inputs_from_completion_params(
    completion_create_params: CompletionCreateParams,
) -> Union[Dict[str, Any], str]:
    """Load the user prompt from a JSON string or file."""
    input_prompt: Any = next(
        (
            msg
            for msg in completion_create_params["messages"]
            if msg.get("role") == "user"
        ),
        {},
    )
    if len(input_prompt) == 0:
        raise ValueError("No user prompt found in the messages.")
    user_prompt = input_prompt.get("content")

    try:
        inputs = json.loads(user_prompt)
    except json.JSONDecodeError:
        inputs = user_prompt

    return inputs  # type: ignore[no-any-return]


def create_completion_from_response_text(
    response_text: str, usage_metrics: Dict[str, int]
) -> ChatCompletion:
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
        usage=CompletionUsage(**usage_metrics),
    )

    return completion
