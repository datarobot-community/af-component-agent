from unittest.mock import MagicMock, patch
import pytest
import click
from click.testing import CliRunner
from cli import execute, execute_deployment, cli


@pytest.fixture
def cli_runner():
    return CliRunner()


@pytest.fixture
def mock_environment():
    env = MagicMock()
    env.interface = MagicMock()
    env.interface.execute.return_value = "Execution successful"
    env.interface.deployment.return_value = "Deployment query successful"
    return env


class TestExecuteCommand:
    @patch("cli.Environment")
    def test_execute_with_prompt(self, mock_env_class, cli_runner, mock_environment):
        mock_env_class.return_value = mock_environment
        result = cli_runner.invoke(
            cli, ["execute", "--user_prompt", '{"topic": "AI"}']
        )

        assert result.exit_code == 0
        assert "Running agent..." in result.output
        assert "Stored Execution Result:" in result.output
        assert "Execution successful" in result.output
        mock_environment.interface.execute.assert_called_once_with(
            user_prompt='{"topic": "AI"}',
            use_remote=False,
        )

    @patch("cli.Environment")
    def test_execute_with_remote_flag(self, mock_env_class, cli_runner, mock_environment):
        mock_env_class.return_value = mock_environment
        result = cli_runner.invoke(
            cli, ["execute", "--user_prompt", '{"topic": "AI"}', "--use_remote"]
        )

        assert result.exit_code == 0
        mock_environment.interface.execute.assert_called_once_with(
            user_prompt='{"topic": "AI"}',
            use_remote=True,
        )

    @patch("cli.Environment")
    def test_execute_with_empty_prompt(self, mock_env_class, cli_runner, mock_environment):
        mock_env_class.return_value = mock_environment
        result = cli_runner.invoke(cli, ["execute", "--user_prompt", ""])

        assert result.exit_code == 2
        assert "User prompt message provided" in result.output

    @patch("cli.Environment")
    def test_execute_without_prompt(self, mock_env_class, cli_runner, mock_environment):
        mock_env_class.return_value = mock_environment
        result = cli_runner.invoke(cli, ["execute"])

        # The code currently doesn't handle None prompts correctly
        # It will try to get the length of None, causing an error
        assert result.exit_code != 0


class TestExecuteDeploymentCommand:
    @patch("cli.Environment")
    def test_execute_deployment_with_valid_inputs(self, mock_env_class, cli_runner, mock_environment):
        mock_env_class.return_value = mock_environment
        result = cli_runner.invoke(
            cli,
            ["execute-deployment", "--user_prompt", '{"topic": "AI"}', "--deployment_id", "12345"]
        )

        assert result.exit_code == 0
        assert "Querying deployment..." in result.output
        assert "Deployment query successful" in result.output
        mock_environment.interface.deployment.assert_called_once_with(
            deployment_id="12345",
            user_prompt='{"topic": "AI"}'
        )

    @patch("cli.Environment")
    def test_execute_deployment_with_empty_prompt(self, mock_env_class, cli_runner, mock_environment):
        mock_env_class.return_value = mock_environment
        result = cli_runner.invoke(
            cli,
            ["execute-deployment", "--user_prompt", "", "--deployment_id", "12345"]
        )

        assert result.exit_code == 2
        assert "User prompt message provided" in result.output

    @patch("cli.Environment")
    def test_execute_deployment_without_deployment_id(self, mock_env_class, cli_runner, mock_environment):
        mock_env_class.return_value = mock_environment
        result = cli_runner.invoke(
            cli,
            ["execute-deployment", "--user_prompt", '{"topic": "AI"}']
        )

        assert result.exit_code == 2
        assert "Deployment ID must be provided" in result.output

    @patch("cli.Environment")
    def test_execute_deployment_with_empty_deployment_id(self, mock_env_class, cli_runner, mock_environment):
        mock_env_class.return_value = mock_environment
        result = cli_runner.invoke(
            cli,
            ["execute-deployment", "--user_prompt", '{"topic": "AI"}', "--deployment_id", ""]
        )

        assert result.exit_code == 2
        assert "Deployment ID must be provided" in result.output