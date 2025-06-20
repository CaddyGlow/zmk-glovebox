"""Tests for MoErgo CLI commands."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.cli.app import app
from glovebox.cli.commands import register_all_commands
from glovebox.moergo.client import AuthenticationError, NetworkError


# Register commands with the app before running tests
register_all_commands(app)


@pytest.fixture
def mock_moergo_client():
    """Create a mock MoErgo client for testing."""
    client = Mock()
    client.login.return_value = None
    client.logout.return_value = None
    client.is_authenticated.return_value = True
    client.validate_authentication.return_value = True
    client.get_credential_info.return_value = {
        "has_credentials": True,
        "keyring_available": True,
        "platform": "Linux",
        "config_dir": "/home/user/.config/glovebox",
        "keyring_backend": "SecretStorage",
    }
    client.get_token_info.return_value = {
        "expires_in_minutes": 120,
        "needs_renewal": False,
    }
    return client


@pytest.fixture
def mock_layout_data():
    """Create mock layout data for testing."""
    layout_meta = Mock()
    layout_meta.uuid = "test-uuid-123"
    layout_meta.title = "Test Layout"
    layout_meta.creator = "Test User"
    layout_meta.date = "2025-01-15"
    layout_meta.created_datetime = "2025-01-15T10:30:00Z"
    layout_meta.notes = "Test layout notes"
    layout_meta.tags = ["test", "sample"]

    layout_config = Mock()
    layout_config.model_dump.return_value = {
        "title": "Test Layout",
        "keyboard": "glove80",
        "layers": [["&kp Q", "&kp W", "&kp E"]],
        "layer_names": ["Base"],
    }

    layout = Mock()
    layout.layout_meta = layout_meta
    layout.config = layout_config

    return layout


class TestMoErgoLogin:
    """Test MoErgo login command."""

    @patch("glovebox.cli.commands.moergo.create_moergo_client")
    def test_login_with_username_password(
        self, mock_create_client, cli_runner, mock_moergo_client
    ):
        """Test login with username and password parameters."""
        mock_create_client.return_value = mock_moergo_client
        mock_moergo_client.get_credential_info.return_value = {
            "keyring_available": True
        }

        result = cli_runner.invoke(
            app,
            [
                "moergo",
                "login",
                "--username",
                "test@example.com",
                "--password",
                "testpass",
            ],
        )

        assert result.exit_code == 0
        assert "Successfully logged in" in result.output
        assert "OS keyring" in result.output
        mock_moergo_client.login.assert_called_once_with("test@example.com", "testpass")

    @patch("glovebox.cli.commands.moergo.create_moergo_client")
    @patch("glovebox.cli.commands.moergo.typer.prompt")
    def test_login_interactive(
        self, mock_prompt, mock_create_client, cli_runner, mock_moergo_client
    ):
        """Test interactive login."""
        mock_create_client.return_value = mock_moergo_client
        mock_moergo_client.get_credential_info.return_value = {
            "keyring_available": False
        }
        mock_prompt.side_effect = ["test@example.com", "testpass"]

        result = cli_runner.invoke(app, ["moergo", "login"])

        assert result.exit_code == 0
        assert "Successfully logged in" in result.output
        assert "file with basic obfuscation" in result.output
        assert "pip install keyring" in result.output
        mock_moergo_client.login.assert_called_once_with("test@example.com", "testpass")

    @patch("glovebox.cli.commands.moergo.create_moergo_client")
    @patch.dict(
        "os.environ",
        {"MOERGO_USERNAME": "env@example.com", "MOERGO_PASSWORD": "envpass"},
    )
    def test_login_environment_variables(
        self, mock_create_client, cli_runner, mock_moergo_client
    ):
        """Test login with environment variables."""
        mock_create_client.return_value = mock_moergo_client
        mock_moergo_client.get_credential_info.return_value = {
            "keyring_available": True
        }

        result = cli_runner.invoke(app, ["moergo", "login"])

        assert result.exit_code == 0
        assert "Successfully logged in" in result.output
        mock_moergo_client.login.assert_called_once_with("env@example.com", "envpass")

    @patch("glovebox.cli.commands.moergo.create_moergo_client")
    def test_login_authentication_error(
        self, mock_create_client, cli_runner, mock_moergo_client
    ):
        """Test login with authentication error."""
        mock_create_client.return_value = mock_moergo_client
        mock_moergo_client.login.side_effect = AuthenticationError(
            "Invalid credentials"
        )

        result = cli_runner.invoke(
            app,
            [
                "moergo",
                "login",
                "--username",
                "bad@example.com",
                "--password",
                "badpass",
            ],
        )

        assert result.exit_code == 1
        assert "Login failed: Invalid credentials" in result.output

    @patch("glovebox.cli.commands.moergo.create_moergo_client")
    def test_login_unexpected_error(
        self, mock_create_client, cli_runner, mock_moergo_client
    ):
        """Test login with unexpected error."""
        mock_create_client.return_value = mock_moergo_client
        mock_moergo_client.login.side_effect = Exception("Network timeout")

        result = cli_runner.invoke(
            app,
            [
                "moergo",
                "login",
                "--username",
                "test@example.com",
                "--password",
                "testpass",
            ],
        )

        assert result.exit_code == 1
        assert "Unexpected error: Network timeout" in result.output


class TestMoErgoLogout:
    """Test MoErgo logout command."""

    @patch("glovebox.cli.commands.moergo.create_moergo_client")
    def test_logout_success(self, mock_create_client, cli_runner, mock_moergo_client):
        """Test successful logout."""
        mock_create_client.return_value = mock_moergo_client

        result = cli_runner.invoke(app, ["moergo", "logout"])

        assert result.exit_code == 0
        assert "Successfully logged out" in result.output
        mock_moergo_client.logout.assert_called_once()

    @patch("glovebox.cli.commands.moergo.create_moergo_client")
    def test_logout_error(self, mock_create_client, cli_runner, mock_moergo_client):
        """Test logout with error."""
        mock_create_client.return_value = mock_moergo_client
        mock_moergo_client.logout.side_effect = Exception("Logout failed")

        result = cli_runner.invoke(app, ["moergo", "logout"])

        assert result.exit_code == 1
        assert "Error during logout: Logout failed" in result.output


class TestMoErgoDownload:
    """Test MoErgo download command."""

    @patch("glovebox.cli.commands.moergo.create_moergo_client")
    def test_download_success(
        self,
        mock_create_client,
        cli_runner,
        mock_moergo_client,
        mock_layout_data,
        tmp_path,
    ):
        """Test successful layout download."""
        mock_create_client.return_value = mock_moergo_client
        mock_moergo_client.get_layout.return_value = mock_layout_data

        output_file = tmp_path / "downloaded_layout.json"

        result = cli_runner.invoke(
            app,
            ["moergo", "download", "test-uuid-123", "--output", str(output_file)],
        )

        assert result.exit_code == 0
        assert "Layout 'Test Layout' saved" in result.output
        assert "Creator: Test User" in result.output
        assert output_file.exists()

        # Check saved file content
        with output_file.open() as f:
            saved_data = json.load(f)

        assert saved_data["title"] == "Test Layout"
        assert saved_data["_moergo_meta"]["uuid"] == "test-uuid-123"
        assert saved_data["_moergo_meta"]["title"] == "Test Layout"
        mock_moergo_client.get_layout.assert_called_once_with("test-uuid-123")

    @patch("glovebox.cli.commands.moergo.create_moergo_client")
    def test_download_default_filename(
        self,
        mock_create_client,
        cli_runner,
        mock_moergo_client,
        mock_layout_data,
        tmp_path,
    ):
        """Test download with default filename."""
        mock_create_client.return_value = mock_moergo_client
        mock_moergo_client.get_layout.return_value = mock_layout_data

        # Change to temp directory for test
        import os

        original_cwd = Path.cwd()
        os.chdir(tmp_path)

        try:
            result = cli_runner.invoke(app, ["moergo", "download", "test-uuid-123"])

            assert result.exit_code == 0
            assert "Layout 'Test Layout' saved to test-uuid-123.json" in result.output
            assert (tmp_path / "test-uuid-123.json").exists()
        finally:
            os.chdir(original_cwd)

    @patch("glovebox.cli.commands.moergo.create_moergo_client")
    def test_download_not_authenticated(
        self, mock_create_client, cli_runner, mock_moergo_client
    ):
        """Test download when not authenticated."""
        mock_create_client.return_value = mock_moergo_client
        mock_moergo_client.validate_authentication.return_value = False

        result = cli_runner.invoke(app, ["moergo", "download", "test-uuid-123"])

        assert result.exit_code == 1
        assert "Authentication failed" in result.output
        assert "glovebox moergo login" in result.output

    @patch("glovebox.cli.commands.moergo.create_moergo_client")
    def test_download_file_exists_no_force(
        self, mock_create_client, cli_runner, mock_moergo_client, tmp_path
    ):
        """Test download when file exists without force flag."""
        mock_create_client.return_value = mock_moergo_client

        existing_file = tmp_path / "existing.json"
        existing_file.write_text('{"existing": "content"}')

        result = cli_runner.invoke(
            app,
            ["moergo", "download", "test-uuid-123", "--output", str(existing_file)],
        )

        assert result.exit_code == 1
        assert "already exists" in result.output
        assert "Use --force to overwrite" in result.output

    @patch("glovebox.cli.commands.moergo.create_moergo_client")
    def test_download_file_exists_with_force(
        self,
        mock_create_client,
        cli_runner,
        mock_moergo_client,
        mock_layout_data,
        tmp_path,
    ):
        """Test download when file exists with force flag."""
        mock_create_client.return_value = mock_moergo_client
        mock_moergo_client.get_layout.return_value = mock_layout_data

        existing_file = tmp_path / "existing.json"
        existing_file.write_text('{"existing": "content"}')

        result = cli_runner.invoke(
            app,
            [
                "moergo",
                "download",
                "test-uuid-123",
                "--output",
                str(existing_file),
                "--force",
            ],
        )

        assert result.exit_code == 0
        assert "Layout 'Test Layout' saved" in result.output

    @patch("glovebox.cli.commands.moergo.create_moergo_client")
    def test_download_authentication_error(
        self, mock_create_client, cli_runner, mock_moergo_client
    ):
        """Test download with authentication error."""
        mock_create_client.return_value = mock_moergo_client
        mock_moergo_client.get_layout.side_effect = AuthenticationError("Token expired")

        result = cli_runner.invoke(app, ["moergo", "download", "test-uuid-123"])

        assert result.exit_code == 1
        assert "Authentication error: Token expired" in result.output
        assert "glovebox moergo login" in result.output

    @patch("glovebox.cli.commands.moergo.create_moergo_client")
    def test_download_network_error(
        self, mock_create_client, cli_runner, mock_moergo_client
    ):
        """Test download with network error."""
        mock_create_client.return_value = mock_moergo_client
        mock_moergo_client.get_layout.side_effect = NetworkError("Connection timeout")

        result = cli_runner.invoke(app, ["moergo", "download", "test-uuid-123"])

        assert result.exit_code == 1
        assert "Network error: Connection timeout" in result.output


class TestMoErgoStatus:
    """Test MoErgo status command."""

    @patch("glovebox.cli.commands.moergo.create_moergo_client")
    def test_status_authenticated_with_keyring(
        self,
        mock_create_client,
        cli_runner,
        mock_moergo_client,
        isolated_cli_environment,
    ):
        """Test status when authenticated with keyring."""
        mock_create_client.return_value = mock_moergo_client
        mock_moergo_client.is_authenticated.return_value = True
        mock_moergo_client.get_credential_info.return_value = {
            "has_credentials": True,
            "keyring_available": True,
            "platform": "Linux",
            "keyring_backend": "SecretStorage",
        }
        mock_moergo_client.get_token_info.return_value = {
            "expires_in_minutes": 120,
            "needs_renewal": False,
        }

        result = cli_runner.invoke(app, ["moergo", "status"])

        assert result.exit_code == 0
        assert "MoErgo Authentication Status:" in result.output
        assert "Authenticated:" in result.output and "Yes" in result.output
        assert "Token expires in: 2.0 hours" in result.output
        assert "Credentials stored:" in result.output and "Yes" in result.output
        assert "Storage method: OS keyring" in result.output
        assert "Keyring available:" in result.output and "Yes" in result.output
        assert "Platform: Linux" in result.output
        assert "Keyring backend: SecretStorage" in result.output

    @patch("glovebox.cli.commands.moergo.create_moergo_client")
    def test_status_not_authenticated(
        self,
        mock_create_client,
        cli_runner,
        mock_moergo_client,
        isolated_cli_environment,
    ):
        """Test status when not authenticated."""
        mock_create_client.return_value = mock_moergo_client
        mock_moergo_client.is_authenticated.return_value = False
        mock_moergo_client.get_credential_info.return_value = {
            "has_credentials": False,
            "keyring_available": False,
            "platform": "Linux",
        }

        result = cli_runner.invoke(app, ["moergo", "status"])

        assert result.exit_code == 0
        assert "Authenticated:" in result.output and "No" in result.output
        assert "Credentials stored:" in result.output and "No" in result.output
        assert "Keyring available:" in result.output and "No" in result.output
        assert "To authenticate:" in result.output
        assert "glovebox moergo login" in result.output

    @patch("glovebox.cli.commands.moergo.create_moergo_client")
    def test_status_token_needs_renewal(
        self, mock_create_client, cli_runner, mock_moergo_client
    ):
        """Test status when token needs renewal."""
        mock_create_client.return_value = mock_moergo_client
        mock_moergo_client.is_authenticated.return_value = True
        mock_moergo_client.get_credential_info.return_value = {
            "has_credentials": True,
            "keyring_available": True,
            "platform": "Linux",
        }
        mock_moergo_client.get_token_info.return_value = {
            "expires_in_minutes": 30,
            "needs_renewal": True,
        }

        result = cli_runner.invoke(app, ["moergo", "status"])

        assert result.exit_code == 0
        assert "Token expires in: 30.0 minutes" in result.output
        assert "Token needs renewal soon" in result.output

    @patch("glovebox.cli.commands.moergo.create_moergo_client")
    def test_status_error(self, mock_create_client, cli_runner, mock_moergo_client):
        """Test status with error."""
        mock_create_client.return_value = mock_moergo_client
        mock_moergo_client.get_credential_info.side_effect = Exception(
            "Connection failed"
        )

        result = cli_runner.invoke(app, ["moergo", "status"])

        assert result.exit_code == 1
        assert "Error checking status: Connection failed" in result.output


class TestMoErgoKeystore:
    """Test MoErgo keystore command."""

    @patch("glovebox.cli.commands.moergo.create_moergo_client")
    def test_keystore_with_keyring(
        self, mock_create_client, cli_runner, mock_moergo_client
    ):
        """Test keystore info with keyring available."""
        mock_create_client.return_value = mock_moergo_client
        mock_moergo_client.get_credential_info.return_value = {
            "has_credentials": True,
            "keyring_available": True,
            "platform": "Darwin",
            "config_dir": "/Users/test/.config/glovebox",
            "keyring_backend": "macOS Keychain",
        }

        result = cli_runner.invoke(app, ["moergo", "keystore"])

        assert result.exit_code == 0
        assert "Keystore Information" in result.output
        assert "Platform: Darwin" in result.output
        assert "OS Keyring: Available" in result.output
        assert "Backend: macOS Keychain" in result.output
        assert "Using macOS Keychain" in result.output
        assert "Current storage method: OS keyring" in result.output
        assert "Your credentials are stored securely" in result.output

    @patch("glovebox.cli.commands.moergo.create_moergo_client")
    def test_keystore_without_keyring(
        self, mock_create_client, cli_runner, mock_moergo_client
    ):
        """Test keystore info without keyring."""
        mock_create_client.return_value = mock_moergo_client
        mock_moergo_client.get_credential_info.return_value = {
            "has_credentials": True,
            "keyring_available": False,
            "platform": "Linux",
            "config_dir": "/home/test/.config/glovebox",
        }

        result = cli_runner.invoke(app, ["moergo", "keystore"])

        assert result.exit_code == 0
        assert "❌ OS Keyring: Not available" in result.output
        assert "Install keyring package" in result.output
        assert "Current storage method: file with obfuscation" in result.output
        assert "File storage provides basic obfuscation only" in result.output

    @patch("glovebox.cli.commands.moergo.create_moergo_client")
    def test_keystore_no_credentials(
        self, mock_create_client, cli_runner, mock_moergo_client
    ):
        """Test keystore info with no credentials stored."""
        mock_create_client.return_value = mock_moergo_client
        mock_moergo_client.get_credential_info.return_value = {
            "has_credentials": False,
            "keyring_available": True,
            "platform": "Windows",
        }

        result = cli_runner.invoke(app, ["moergo", "keystore"])

        assert result.exit_code == 0
        assert "No credentials currently stored" in result.output
        assert "Using Windows Credential Manager" in result.output

    @patch("glovebox.cli.commands.moergo.create_moergo_client")
    def test_keystore_error(self, mock_create_client, cli_runner, mock_moergo_client):
        """Test keystore info with error."""
        mock_create_client.return_value = mock_moergo_client
        mock_moergo_client.get_credential_info.side_effect = Exception("Keystore error")

        result = cli_runner.invoke(app, ["moergo", "keystore"])

        assert result.exit_code == 1
        assert "Error getting keystore info: Keystore error" in result.output


class TestMoErgoCommandRegistration:
    """Test MoErgo command registration."""

    def test_register_commands(self):
        """Test that MoErgo commands are properly registered."""
        from glovebox.cli.commands.moergo import register_commands

        test_app = Mock()
        register_commands(test_app)

        test_app.add_typer.assert_called_once()
        args, kwargs = test_app.add_typer.call_args
        assert kwargs["name"] == "moergo"


class TestMoErgoIntegration:
    """Integration tests for MoErgo commands."""

    @patch("glovebox.cli.commands.moergo.create_moergo_client")
    def test_login_download_workflow(
        self,
        mock_create_client,
        cli_runner,
        mock_moergo_client,
        mock_layout_data,
        tmp_path,
    ):
        """Test complete login and download workflow."""
        mock_create_client.return_value = mock_moergo_client
        mock_moergo_client.get_credential_info.return_value = {
            "keyring_available": True
        }
        mock_moergo_client.get_layout.return_value = mock_layout_data

        # First login
        login_result = cli_runner.invoke(
            app,
            [
                "moergo",
                "login",
                "--username",
                "test@example.com",
                "--password",
                "testpass",
            ],
        )
        assert login_result.exit_code == 0

        # Then download
        output_file = tmp_path / "test_layout.json"
        download_result = cli_runner.invoke(
            app,
            ["moergo", "download", "test-uuid-123", "--output", str(output_file)],
        )
        assert download_result.exit_code == 0
        assert output_file.exists()

        # Verify login was called
        mock_moergo_client.login.assert_called_once_with("test@example.com", "testpass")
        mock_moergo_client.get_layout.assert_called_once_with("test-uuid-123")
