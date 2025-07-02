"""Tests for config updates CLI commands."""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest


pytestmark = [pytest.mark.network, pytest.mark.integration]

from glovebox.cli.app import app
from glovebox.cli.commands import register_all_commands
from glovebox.core.version_check import VersionCheckResult


# Register commands with the app before running tests
register_all_commands(app)


@pytest.fixture
def mock_version_checker():
    """Create a mock version checker for testing."""
    checker = Mock()
    return checker


@pytest.fixture
def mock_version_check_result_no_update():
    """Create a mock version check result with no update."""
    return VersionCheckResult(
        has_update=False,
        current_version="stable",
        latest_version="v3.2.0",
        latest_url="https://github.com/zmkfirmware/zmk/releases/tag/v3.2.0",
        is_prerelease=False,
        check_disabled=False,
        last_check=datetime.now() - timedelta(hours=1),
    )


@pytest.fixture
def mock_version_check_result_with_update():
    """Create a mock version check result with update available."""
    return VersionCheckResult(
        has_update=True,
        current_version="v3.1.0",
        latest_version="v3.2.0",
        latest_url="https://github.com/zmkfirmware/zmk/releases/tag/v3.2.0",
        is_prerelease=False,
        check_disabled=False,
        last_check=datetime.now(),
    )


@pytest.fixture
def mock_version_check_result_prerelease():
    """Create a mock version check result with prerelease update."""
    return VersionCheckResult(
        has_update=True,
        current_version="v3.1.0",
        latest_version="v3.2.0-beta.1",
        latest_url="https://github.com/zmkfirmware/zmk/releases/tag/v3.2.0-beta.1",
        is_prerelease=True,
        check_disabled=False,
        last_check=datetime.now(),
    )


@pytest.fixture
def mock_version_check_result_disabled():
    """Create a mock version check result when checks are disabled."""
    return VersionCheckResult(
        has_update=False,
        current_version=None,
        latest_version=None,
        check_disabled=True,
    )


class TestCheckUpdatesCommand:
    """Test the check-updates command."""

    @patch("glovebox.core.version_check.create_zmk_version_checker")
    def test_check_updates_no_update_available(
        self,
        mock_create_checker,
        cli_runner,
        mock_version_checker,
        mock_version_check_result_no_update,
        isolated_cli_environment,
    ):
        """Test check-updates when no update is available."""
        mock_create_checker.return_value = mock_version_checker
        mock_version_checker.check_for_updates.return_value = (
            mock_version_check_result_no_update
        )

        result = cli_runner.invoke(app, ["config", "check-updates"])

        assert result.exit_code == 0
        assert "ZMK firmware is up to date" in result.output
        assert "Last checked:" in result.output
        # Verify that the command call was made (allow for startup call too)
        calls = mock_version_checker.check_for_updates.call_args_list
        assert any(
            call.kwargs == {"force": False, "include_prereleases": False}
            for call in calls
        )

    @patch("glovebox.core.version_check.create_zmk_version_checker")
    def test_check_updates_with_update_available(
        self,
        mock_create_checker,
        cli_runner,
        mock_version_checker,
        mock_version_check_result_with_update,
        isolated_cli_environment,
    ):
        """Test check-updates when an update is available."""
        mock_create_checker.return_value = mock_version_checker
        mock_version_checker.check_for_updates.return_value = (
            mock_version_check_result_with_update
        )

        result = cli_runner.invoke(app, ["config", "check-updates"])

        assert result.exit_code == 0
        assert "ZMK Firmware Update Available!" in result.output
        assert "Current: v3.1.0" in result.output
        assert "Latest:  v3.2.0" in result.output
        assert (
            "Details: https://github.com/zmkfirmware/zmk/releases/tag/v3.2.0"
            in result.output
        )
        # Verify that the command call was made (allow for startup call too)
        calls = mock_version_checker.check_for_updates.call_args_list
        assert any(
            call.kwargs == {"force": False, "include_prereleases": False}
            for call in calls
        )

    @patch("glovebox.core.version_check.create_zmk_version_checker")
    def test_check_updates_with_prerelease(
        self,
        mock_create_checker,
        cli_runner,
        mock_version_checker,
        mock_version_check_result_prerelease,
        isolated_cli_environment,
    ):
        """Test check-updates with prerelease update."""
        mock_create_checker.return_value = mock_version_checker
        mock_version_checker.check_for_updates.return_value = (
            mock_version_check_result_prerelease
        )

        result = cli_runner.invoke(
            app, ["config", "check-updates", "--include-prereleases"]
        )

        assert result.exit_code == 0
        assert "ZMK Firmware Update Available!" in result.output
        assert "Latest:  v3.2.0-beta.1" in result.output
        assert "Type:    Pre-release" in result.output
        # Verify that the command call was made (allow for startup call too)
        calls = mock_version_checker.check_for_updates.call_args_list
        assert any(
            call.kwargs == {"force": False, "include_prereleases": True}
            for call in calls
        )

    @patch("glovebox.core.version_check.create_zmk_version_checker")
    def test_check_updates_force_flag(
        self,
        mock_create_checker,
        cli_runner,
        mock_version_checker,
        mock_version_check_result_no_update,
        isolated_cli_environment,
    ):
        """Test check-updates with force flag."""
        mock_create_checker.return_value = mock_version_checker
        mock_version_checker.check_for_updates.return_value = (
            mock_version_check_result_no_update
        )

        result = cli_runner.invoke(app, ["config", "check-updates", "--force"])

        assert result.exit_code == 0
        assert "ZMK firmware is up to date" in result.output
        # Verify that the command call was made (allow for startup call too)
        calls = mock_version_checker.check_for_updates.call_args_list
        assert any(
            call.kwargs == {"force": True, "include_prereleases": False}
            for call in calls
        )

    @patch("glovebox.core.version_check.create_zmk_version_checker")
    def test_check_updates_disabled_without_force(
        self,
        mock_create_checker,
        cli_runner,
        mock_version_checker,
        mock_version_check_result_disabled,
        isolated_cli_environment,
    ):
        """Test check-updates when version checks are disabled."""
        mock_create_checker.return_value = mock_version_checker
        mock_version_checker.check_for_updates.return_value = (
            mock_version_check_result_disabled
        )

        result = cli_runner.invoke(app, ["config", "check-updates"])

        assert result.exit_code == 0
        assert "Version checks are disabled" in result.output
        assert (
            "glovebox config edit --set disable_version_checks=false" in result.output
        )
        # Verify that the command call was made (allow for startup call too)
        calls = mock_version_checker.check_for_updates.call_args_list
        assert any(
            call.kwargs == {"force": False, "include_prereleases": False}
            for call in calls
        )

    @patch("glovebox.core.version_check.create_zmk_version_checker")
    def test_check_updates_disabled_with_force(
        self,
        mock_create_checker,
        cli_runner,
        mock_version_checker,
        mock_version_check_result_no_update,
        isolated_cli_environment,
    ):
        """Test check-updates when disabled but forced."""
        mock_create_checker.return_value = mock_version_checker
        mock_version_checker.check_for_updates.return_value = (
            mock_version_check_result_no_update
        )

        result = cli_runner.invoke(app, ["config", "check-updates", "--force"])

        assert result.exit_code == 0
        assert "ZMK firmware is up to date" in result.output
        # Should not show disabled message when forced
        assert "Version checks are disabled" not in result.output
        # Verify that the command call was made (allow for startup call too)
        calls = mock_version_checker.check_for_updates.call_args_list
        assert any(
            call.kwargs == {"force": True, "include_prereleases": False}
            for call in calls
        )

    @patch("glovebox.core.version_check.create_zmk_version_checker")
    def test_check_updates_no_notes_or_tags(
        self,
        mock_create_checker,
        cli_runner,
        mock_version_checker,
        isolated_cli_environment,
    ):
        """Test check-updates with minimal version info (no notes/tags)."""
        # Create result without optional fields
        result_no_extras = VersionCheckResult(
            has_update=True,
            current_version="stable",
            latest_version="v3.2.0",
            latest_url="https://github.com/zmkfirmware/zmk/releases/tag/v3.2.0",
            is_prerelease=False,
            check_disabled=False,
            last_check=datetime.now(),
        )

        mock_create_checker.return_value = mock_version_checker
        mock_version_checker.check_for_updates.return_value = result_no_extras

        result = cli_runner.invoke(app, ["config", "check-updates"])

        assert result.exit_code == 0
        assert "ZMK Firmware Update Available!" in result.output
        assert "Current: stable" in result.output
        assert "Latest:  v3.2.0" in result.output
        # Should not show Type or Tags lines since they're not present
        assert "Type:" not in result.output

    @patch("glovebox.core.version_check.create_zmk_version_checker")
    def test_check_updates_combined_flags(
        self,
        mock_create_checker,
        cli_runner,
        mock_version_checker,
        mock_version_check_result_prerelease,
        isolated_cli_environment,
    ):
        """Test check-updates with both force and include-prereleases flags."""
        mock_create_checker.return_value = mock_version_checker
        mock_version_checker.check_for_updates.return_value = (
            mock_version_check_result_prerelease
        )

        result = cli_runner.invoke(
            app, ["config", "check-updates", "--force", "--include-prereleases"]
        )

        assert result.exit_code == 0
        assert "ZMK Firmware Update Available!" in result.output
        assert "Type:    Pre-release" in result.output
        # Verify that the command call was made (allow for startup call too)
        calls = mock_version_checker.check_for_updates.call_args_list
        assert any(
            call.kwargs == {"force": True, "include_prereleases": True}
            for call in calls
        )


class TestConfigUpdatesErrorHandling:
    """Test error handling in config updates commands."""

    @patch("glovebox.core.version_check.create_zmk_version_checker")
    def test_check_updates_version_checker_creation_error(
        self, mock_create_checker, cli_runner, isolated_cli_environment
    ):
        """Test check-updates when version checker creation fails."""
        mock_create_checker.side_effect = Exception("Failed to create version checker")

        result = cli_runner.invoke(app, ["config", "check-updates"])

        assert result.exit_code == 1
        assert "Failed to create version checker" in result.output

    @patch("glovebox.core.version_check.create_zmk_version_checker")
    def test_check_updates_internal_error(
        self,
        mock_create_checker,
        cli_runner,
        mock_version_checker,
        isolated_cli_environment,
    ):
        """Test check-updates when check_for_updates raises an exception."""
        mock_create_checker.return_value = mock_version_checker
        mock_version_checker.check_for_updates.side_effect = Exception("Network error")

        result = cli_runner.invoke(app, ["config", "check-updates"])

        assert result.exit_code == 1
        assert "Network error" in result.output


class TestVersionCheckResultEdgeCases:
    """Test edge cases in version check results."""

    @patch("glovebox.core.version_check.create_zmk_version_checker")
    def test_check_updates_unknown_current_version(
        self,
        mock_create_checker,
        cli_runner,
        mock_version_checker,
        isolated_cli_environment,
    ):
        """Test check-updates when current version is unknown."""
        result_unknown_current = VersionCheckResult(
            has_update=True,
            current_version=None,  # Unknown current version
            latest_version="v3.2.0",
            latest_url="https://github.com/zmkfirmware/zmk/releases/tag/v3.2.0",
            is_prerelease=False,
            check_disabled=False,
            last_check=datetime.now(),
        )

        mock_create_checker.return_value = mock_version_checker
        mock_version_checker.check_for_updates.return_value = result_unknown_current

        result = cli_runner.invoke(app, ["config", "check-updates"])

        assert result.exit_code == 0
        assert "ZMK Firmware Update Available!" in result.output
        assert "Current: unknown" in result.output
        assert "Latest:  v3.2.0" in result.output

    @patch("glovebox.core.version_check.create_zmk_version_checker")
    def test_check_updates_no_last_check(
        self,
        mock_create_checker,
        cli_runner,
        mock_version_checker,
        isolated_cli_environment,
    ):
        """Test check-updates when there's no last check timestamp."""
        result_no_timestamp = VersionCheckResult(
            has_update=False,
            current_version="stable",
            latest_version="v3.2.0",
            check_disabled=False,
            last_check=None,  # No last check
        )

        mock_create_checker.return_value = mock_version_checker
        mock_version_checker.check_for_updates.return_value = result_no_timestamp

        result = cli_runner.invoke(app, ["config", "check-updates"])

        assert result.exit_code == 0
        assert "ZMK firmware is up to date" in result.output
        # Should not show "Last checked" line when last_check is None
        assert "Last checked:" not in result.output

    @patch("glovebox.core.version_check.create_zmk_version_checker")
    def test_check_updates_no_url(
        self,
        mock_create_checker,
        cli_runner,
        mock_version_checker,
        isolated_cli_environment,
    ):
        """Test check-updates when latest_url is not available."""
        result_no_url = VersionCheckResult(
            has_update=True,
            current_version="v3.1.0",
            latest_version="v3.2.0",
            latest_url=None,  # No URL available
            is_prerelease=False,
            check_disabled=False,
            last_check=datetime.now(),
        )

        mock_create_checker.return_value = mock_version_checker
        mock_version_checker.check_for_updates.return_value = result_no_url

        result = cli_runner.invoke(app, ["config", "check-updates"])

        assert result.exit_code == 0
        assert "ZMK Firmware Update Available!" in result.output
        assert "Latest:  v3.2.0" in result.output
        # Should not show Details line when URL is None
        assert "Details:" not in result.output
