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
from typing import Any, Optional

import click
from dotenv import load_dotenv

from agent_cli.environment import Environment

load_dotenv()

pass_environment = click.make_pass_decorator(Environment)


@click.group()
@click.option("--codespace_id", default=None, help="Codespace ID for the session.")
@click.option("--api_token", default=None, help="API token for authentication.")
@click.option("--base_url", default=None, help="Base URL for the API.")
@click.pass_context
def cli(
    ctx: Any,
    codespace_id: Optional[str],
    api_token: Optional[str],
    base_url: Optional[str],
) -> None:
    """A CLI for interacting executing agent custom models using the chat endpoint and OpenAI completions.

    Examples:

    > task cli -- execute --help

    > task cli -- execute-deployment --help

    > task cli -- execute --user_prompt '{"topic": "Artificial Intelligence"}'

    """
    ctx.obj = Environment(codespace_id, api_token, base_url)


@cli.command()
@pass_environment
@click.option("--user_prompt", default=None, help="Input to use for chat.")
@click.option("--use_remote", is_flag=True, help="Use remote codespace.")
def execute(environment: Any, user_prompt: Optional[str], use_remote: bool) -> None:
    """Execute agent code using OpenAI completions.

    Examples:

    > task cli -- execute --user_prompt '{"topic": "Artificial Intelligence"}'

    > task cli -- execute --user_prompt '{"topic": "Artificial Intelligence"}' --use_remote
    """
    click.echo("Running agent...")
    response = environment.interface.execute(
        user_prompt=user_prompt,
        use_remote=use_remote,
    )
    click.echo("\nStored Execution Result:")
    click.echo(response)


@cli.command()
@pass_environment
@click.option("--user_prompt", default=None, help="Input to use for predict.")
@click.option("--deployment_id", default=None, help="ID for the deployment.")
def execute_deployment(
    environment: Any, user_prompt: Optional[str], deployment_id: Optional[str]
) -> None:
    """Query a deployed model using the command line for OpenAI completions.

    Example:

    > task cli -- execute-deployment --user_prompt '{"topic": "Artificial Intelligence"}' --deployment_id 680a77a9a3
    """
    if len(str(deployment_id)) == 0:
        raise click.UsageError("Deployment ID must be provided.")

    click.echo("Querying deployment...")
    response = environment.interface.deployment(
        deployment_id=deployment_id, user_prompt=user_prompt
    )
    click.echo(response)


if __name__ == "__main__":
    cli()
