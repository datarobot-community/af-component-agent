import os
from unittest.mock import MagicMock, patch

from agent_cli.environment import Environment
from agent_cli.kernel import AgentKernel


class TestEnvironment:
    def test_init_default_values(self):
        """Test initialization with default values."""
        # Clear environment variables to test default behavior
        with patch.dict(os.environ, {}, clear=True):
            env = Environment()

            # Check default values
            assert env.codespace_id is None
            assert env.api_token is None
            assert env.base_url == "https://app.datarobot.com"

    def test_init_with_parameters(self):
        """Test initialization with explicitly provided parameters."""
        with patch.dict(os.environ, {}, clear=True):
            env = Environment(
                codespace_id="test-codespace",
                api_token="test-token",
                base_url="https://test.example.com",
            )

            assert env.codespace_id == "test-codespace"
            assert env.api_token == "test-token"
            assert env.base_url == "https://test.example.com"

    def test_init_with_environment_variables(self):
        """Test initialization with values from environment variables."""
        env_vars = {
            "DATAROBOT_CODESPACE_ID": "env-codespace",
            "DATAROBOT_API_TOKEN": "env-token",
            "DATAROBOT_ENDPOINT": "https://env.example.com",
        }

        with patch.dict(os.environ, env_vars):
            env = Environment()

            assert env.codespace_id == "env-codespace"
            assert env.api_token == "env-token"
            assert env.base_url == "https://env.example.com"

    def test_environment_variables_override_parameters(self):
        """Test that environment variables take precedence over parameters."""
        env_vars = {
            "DATAROBOT_CODESPACE_ID": "env-codespace",
            "DATAROBOT_API_TOKEN": "env-token",
            "DATAROBOT_ENDPOINT": "https://env.example.com",
        }

        with patch.dict(os.environ, env_vars):
            env = Environment(
                codespace_id="test-codespace",
                api_token="test-token",
                base_url="https://test.example.com",
            )

            assert env.codespace_id == "env-codespace"
            assert env.api_token == "env-token"
            assert env.base_url == "https://env.example.com"

    def test_api_v2_removed_from_base_url(self):
        """Test that '/api/v2' is removed from base_url."""
        with patch.dict(os.environ, {}, clear=True):
            env = Environment(base_url="https://test.example.com/api/v2")
            assert env.base_url == "https://test.example.com"

    @patch("agent_cli.environment.AgentKernel")
    def test_interface_property(self, mock_agent_kernel):
        """Test that the interface property returns an AgentKernel instance."""
        # Setup mock
        with patch.dict(os.environ, {}, clear=True):
            mock_kernel_instance = MagicMock(spec=AgentKernel)
            mock_agent_kernel.return_value = mock_kernel_instance

            # Create environment and access interface
            env = Environment(
                codespace_id="test-codespace",
                api_token="test-token",
                base_url="https://test.example.com",
            )
            interface = env.interface

            # Verify AgentKernel was created with correct parameters
            mock_agent_kernel.assert_called_once_with(
                codespace_id="test-codespace",
                api_token="test-token",
                base_url="https://test.example.com",
            )

            # Verify interface is the mock kernel
            assert interface == mock_kernel_instance

    def test_str_conversion_for_interface(self):
        """Test that None values are converted to strings for the AgentKernel."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("agent_cli.environment.AgentKernel") as mock_agent_kernel:
                # Create environment with None values
                env = Environment()

                # Access interface property
                _ = env.interface

                # Verify values were converted to strings
                mock_agent_kernel.assert_called_once_with(
                    codespace_id="None",
                    api_token="None",
                    base_url="https://app.datarobot.com",
                )
