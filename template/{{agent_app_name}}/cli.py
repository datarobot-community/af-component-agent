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
import time
from typing import Any, Optional, cast

import click
import requests
from openai import OpenAI, Stream
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionChunk,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)
from openai.types.chat.completion_create_params import (
    CompletionCreateParamsNonStreaming,
    CompletionCreateParamsStreaming,
)

from custom_model.config import Config


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

    def load_completion_json(
        self, completion_json: str
    ) -> CompletionCreateParamsNonStreaming:
        """Load the completion JSON from a file or return an empty prompt."""
        if not os.path.exists(completion_json):
            raise FileNotFoundError(
                f"Completion JSON file not found: {completion_json}"
            )

        with open(completion_json, "r") as f:
            completion_data = json.load(f)

        completion_create_params = CompletionCreateParamsNonStreaming(
            **completion_data,  # type: ignore[typeddict-item]
        )
        return cast(CompletionCreateParamsNonStreaming, completion_create_params)

    def construct_prompt(
        self, user_prompt: str, verbose: bool, stream: bool = False
    ) -> CompletionCreateParamsNonStreaming | CompletionCreateParamsStreaming:
        extra_body = {
            "api_key": self.api_token,
            "api_base": self.base_url,
            "verbose": verbose,
        }
        if stream:
            return CompletionCreateParamsStreaming(
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
                stream=True,
                extra_body=extra_body,  # type: ignore[typeddict-unknown-key]
            )
        else:
            return CompletionCreateParamsNonStreaming(
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
                extra_body=extra_body,  # type: ignore[typeddict-unknown-key]
            )

    def local(
        self,
        user_prompt: str,
        completion_json: str = "",
        stream: bool = False,
    ) -> ChatCompletion | Stream[ChatCompletionChunk]:
        config = Config()
        chat_api_url = config.agent_endpoint
        print(chat_api_url)

        return self._do_chat_completion(
            chat_api_url, user_prompt, completion_json, stream=stream
        )

    def custom_model(self, custom_model_id: str, user_prompt: str) -> str:
        chat_api_url = f"{self.base_url}/api/v2/genai/agents/fromCustomModel/{custom_model_id}/chat/"
        print(chat_api_url)

        headers = {
            "Authorization": f"Bearer {os.environ['DATAROBOT_API_TOKEN']}",
            "Content-Type": "application/json",
        }
        data = {"messages": [{"role": "user", "content": user_prompt}]}

        print(f'Querying custom model with prompt: "{data}"')
        print(
            "Please wait... This may take 1-2 minutes the first time you run this as a codespace is provisioned "
            "for the custom model to execute."
        )
        response = requests.post(
            chat_api_url,
            headers=headers,
            json=data,
        )

        if not response.ok or not response.headers.get("Location"):
            raise Exception(response.text)
        # Wait for the agent to complete
        status_location = response.headers["Location"]
        while response.ok:
            time.sleep(1)
            response = requests.get(
                status_location, headers=headers, allow_redirects=False
            )
            if response.status_code == 303:
                agent_response = requests.get(
                    response.headers["Location"], headers=headers
                ).json()
                # Show the agent response
                break
            else:
                status_response = response.json()
                if status_response["status"] in ["ERROR", "ABORTED"]:
                    raise Exception(status_response)
        else:
            raise Exception(response.content)

        if "errorMessage" in agent_response and agent_response["errorMessage"]:
            return (
                f"Error: "
                f"{agent_response.get('errorMessage', 'No error message available')}"
                f"Error details:"
                f"{agent_response.get('errorDetails', 'No details available')}"
            )
        elif "choices" in agent_response:
            return str(agent_response["choices"][0]["message"]["content"])
        else:
            return str(agent_response)

    def deployment(
        self,
        deployment_id: str,
        user_prompt: str,
        completion_json: str = "",
        stream: bool = False,
    ) -> ChatCompletion | Stream[ChatCompletionChunk]:
        chat_api_url = f"{self.base_url}/api/v2/deployments/{deployment_id}/"
        print(chat_api_url)

        return self._do_chat_completion(
            chat_api_url, user_prompt, completion_json, stream=stream
        )

    def _do_chat_completion(
        self,
        url: str,
        user_prompt: str,
        completion_json: str = "",
        stream: bool = False,
    ) -> ChatCompletion | Stream[ChatCompletionChunk]:
        if len(user_prompt) > 0:
            completion_create_params = self.construct_prompt(
                user_prompt, stream=stream, verbose=True
            )
        else:
            completion_create_params = self.load_completion_json(completion_json)

        openai_client = OpenAI(
            base_url=url,
            api_key=self.api_token,
            _strict_response_validation=False,
        )

        print(f'Querying deployment with prompt: "{completion_create_params}"')
        print(
            "Please wait for the agent to complete the response. This may take a few seconds to minutes "
            "depending on the complexity of the agent workflow."
        )

        completion = openai_client.chat.completions.create(**completion_create_params)
        return completion


class Environment:
    def __init__(
        self,
        api_token: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_token = os.environ.get("DATAROBOT_API_TOKEN") or api_token
        if not self.api_token:
            raise ValueError(
                "Missing DataRobot API token. Set the DATAROBOT_API_TOKEN "
                "environment variable or provide it explicitly."
            )
        self.base_url = (
            os.environ.get("DATAROBOT_ENDPOINT")
            or base_url
            or "https://app.datarobot.com"
        )
        if not self.base_url:
            raise ValueError(
                "Missing DataRobot endpoint. Set the DATAROBOT_ENDPOINT environment "
                "variable or provide it explicitly."
            )
        self.base_url = self.base_url.replace("/api/v2", "")

    @property
    def interface(self) -> Kernel:
        return Kernel(
            api_token=str(self.api_token),
            base_url=str(self.base_url),
        )


pass_environment = click.make_pass_decorator(Environment)


def display_response(response: ChatCompletion, show_output: bool) -> None:
    """Display the response in a formatted way."""
    response_dict = response.model_dump()
    if not show_output:
        with open("execute_output.json", "w") as f:
            json.dump(response_dict, f, indent=2)

    if "pipeline_interactions" in response_dict:
        response_dict["pipeline_interactions"] = "[Truncated for display]"

    if show_output:
        click.echo("\nExecution result:")
        click.echo(json.dumps(response_dict, indent=2))
    else:
        if "choices" in response_dict:
            response_dict["choices"] = "[Truncated for display]"

        # Show only first 200 characters of response
        click.echo("\nExecution result preview:")
        click.echo(json.dumps(response_dict, indent=2))
        click.echo("")
        click.echo("IMPORTANT")
        click.echo(
            "This is a preview of the json result, or only the final message if streaming is enabled."
        )
        click.echo(
            f"To view the full result (including all streaming responses) run "
            f"`cat {os.path.abspath('execute_output.json')}`."
        )
        click.echo(
            "To display the full result inline, rerun with the `--show_output` flag."
        )


def display_response_streaming(response: Stream[ChatCompletionChunk]) -> None:
    click.echo("\nStreaming response:")
    for chunk in response:
        chunk_dict = chunk.model_dump()
        if "pipeline_interactions" in chunk_dict:
            chunk_dict["pipeline_interactions"] = "[Truncated for display]"
        click.echo(json.dumps(chunk_dict, indent=2))


@click.group()
@click.option("--api_token", default=None, help="API token for authentication.")
@click.option("--base_url", default=None, help="Base URL for the API.")
@click.pass_context
def cli(
    ctx: Any,
    api_token: str | None,
    base_url: str | None,
) -> None:
    """A CLI for interacting executing agent custom models using the chat endpoint and OpenAI completions.

    For more information on the main CLI commands and all available options, run the help command:
    > task cli -- execute --help
    > task cli -- execute-deployment --help

    Common examples:

    # Run the agent with a string user prompt
    > task cli -- execute --user_prompt "Artificial Intelligence"

    # Run the agent with a JSON user prompt
    > task cli -- execute --user_prompt '{"topic": "Artificial Intelligence"}'

    # Run the agent with a JSON file containing the full chat completion json
    > task cli -- execute --completion_json "example-completion.json"

    # Run the deployed agent with a string user prompt [Other prompt methods are also supported similar to execute]
    > task cli -- execute-deployment --user_prompt "Artificial Intelligence" --deployment_id 680a77a9a3

    """
    ctx.obj = Environment(api_token, base_url)


@cli.command()
@pass_environment
@click.option("--user_prompt", default="", help="Input to use for chat.")
@click.option("--completion_json", default="", help="Path to json to use for chat.")
@click.option("--stream", is_flag=True, help="Enable streaming response.")
@click.option(
    "--show_output", is_flag=True, help="Show the full stored execution result."
)
def execute(
    environment: Any,
    user_prompt: str,
    completion_json: str,
    show_output: bool,
    stream: bool,
) -> None:
    """Execute agent code locally using OpenAI completions.

    Examples:

    # Run the agent with a string user prompt
    > task cli -- execute --user_prompt "Artificial Intelligence"

    # Run the agent with streaming enabled
    > task cli -- execute --user_prompt "Artificial Intelligence" --stream

    # Run the agent with a string user prompt and show full output
    > task cli -- execute --user_prompt "Artificial Intelligence" --show_output

    # Run the agent with a JSON user prompt
    > task cli -- execute --user_prompt '{"topic": "Artificial Intelligence"}'

    # Run the agent with a JSON file containing the full chat completion json
    > task cli -- execute --completion_json "example-completion.json"
    """
    if len(user_prompt) == 0 and len(completion_json) == 0:
        raise click.UsageError("User prompt message or completion json must provided.")

    click.echo("Running agent...")
    response = environment.interface.local(
        user_prompt=user_prompt,
        completion_json=completion_json,
        stream=stream,
    )
    if stream:
        display_response_streaming(response)
    else:
        display_response(response, show_output)


@cli.command()
@pass_environment
@click.option("--user_prompt", default="", help="Input to use for predict.")
@click.option("--custom_model_id", default="", help="ID for the deployment.")
def execute_custom_model(
    environment: Any, user_prompt: str, custom_model_id: str
) -> None:
    """Query a custom model using the command line for OpenAI completions. Custom models will execute inside an
    ephemeral CodeSpace environment. This can also be done through the DataRobot Playground UI.

    Example:

    # Run the agent with a string user prompt
    > task cli -- execute-custom-model --user_prompt "Artificial Intelligence" --custom_model_id 680a77a9a3

    # Run the agent with a JSON user prompt
    > task cli -- execute-custom-model --user_prompt '{"topic": "Artificial Intelligence"}' --custom_model_id 680a77a9a3
    """
    if len(user_prompt) == 0:
        raise click.UsageError("User prompt message must be provided.")
    if len(custom_model_id) == 0:
        raise click.UsageError("Custom Model ID must be provided.")

    click.echo("Querying deployment...")
    response = environment.interface.custom_model(
        custom_model_id=custom_model_id,
        user_prompt=user_prompt,
    )
    click.echo(response)


@cli.command()
@pass_environment
@click.option("--user_prompt", default="", help="Input to use for predict.")
@click.option("--completion_json", default="", help="Path to json to use for chat.")
@click.option("--deployment_id", default="", help="ID for the deployment.")
@click.option(
    "--show_output", is_flag=True, help="Show the full stored execution result."
)
@click.option("--stream", is_flag=True, help="Enable streaming response.")
def execute_deployment(
    environment: Any,
    user_prompt: str,
    completion_json: str,
    deployment_id: str,
    show_output: bool,
    stream: bool,
) -> None:
    """Query a deployed model using the command line for OpenAI completions.

    Example:

    # Run the agent with a string user prompt
    > task cli -- execute-deployment --user_prompt "Artificial Intelligence" --deployment_id 680a77a9a3

    # Run the agent with a string user prompt and show full output
    > task cli -- execute-deployment --user_prompt "Artificial Intelligence" --show_output --deployment_id 680a77a9a3

    # Run the agent with a string user prompt, streaming enabled
    > task cli -- execute-deployment --user_prompt "Artificial Intelligence" --stream --deployment_id 680a77a9a3

    # Run the agent with a JSON user prompt
    > task cli -- execute-deployment --user_prompt '{"topic": "Artificial Intelligence"}' --deployment_id 680a77a9a3

    # Run the agent with a JSON file containing the full chat completion json
    > task cli -- execute-deployment --completion_json "example-completion.json" --deployment_id 680a77a9a3
    """
    if len(user_prompt) == 0 and len(completion_json) == 0:
        raise click.UsageError("User prompt message or completion json must provided.")
    if len(deployment_id) == 0:
        raise click.UsageError("Deployment ID must be provided.")

    click.echo("Querying deployment...")
    response = environment.interface.deployment(
        deployment_id=deployment_id,
        user_prompt=user_prompt,
        completion_json=completion_json,
    )
    if stream:
        display_response_streaming(response)
    else:
        display_response(response, show_output)


if __name__ == "__main__":
    cli()
