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
import calendar
import time
from typing import Any

from openai.types.chat import ChatCompletion
from openai.types.chat import ChatCompletionMessage
from openai.types.chat import CompletionCreateParams
from openai.types.chat.chat_completion import Choice


def load_model(code_dir: str) -> Any:
    _ = code_dir
    return "dummy"


def chat(completion_create_params: CompletionCreateParams, model: Any, **kwargs: Any):
    _ = completion_create_params
    _ = model

    # non-streaming
    return ChatCompletion(
        id="association_id",
        choices=[
            Choice(
                finish_reason="stop",
                index=0,
                message=ChatCompletionMessage(role="assistant", content="message_content"),
            )
        ],
        created=calendar.timegm(time.gmtime()),
        model="model_id",
        object="chat.completion",
    )