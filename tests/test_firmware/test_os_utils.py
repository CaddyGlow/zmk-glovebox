"""Tests for OS utilities module."""

import subprocess
from unittest.mock import Mock, mock_open, patch

import pytest

from glovebox.firmware.flash.adapters.os_utils import (
    is_wsl2,
    windows_to_wsl_path,
    wsl_to_windows_path,
)


class TestIsWsl2:
    """Test is_wsl2 function."""

    def test_is_wsl2_true_with_microsoft_in_version(self):
        """Test is_wsl2 returns True when 'microsoft' is in /proc/version."""
        mock_content = "Linux version 5.15.0-microsoft-standard-WSL2"

        with patch("pathlib.Path.open", mock_open(read_data=mock_content)):
            result = is_wsl2()

        assert result is True

    def test_is_wsl2_true_with_mixed_case_microsoft(self):
        """Test is_wsl2 returns True with mixed case 'Microsoft'."""
        mock_content = "Linux version 5.15.0-Microsoft-standard-WSL2"

        with patch("pathlib.Path.open", mock_open(read_data=mock_content)):
            result = is_wsl2()

        assert result is True

    def test_is_wsl2_false_without_microsoft(self):
        """Test is_wsl2 returns False when 'microsoft' is not in /proc/version."""
        mock_content = "Linux version 5.15.0-ubuntu #72-Ubuntu SMP"

        with patch("pathlib.Path.open", mock_open(read_data=mock_content)):
            result = is_wsl2()

        assert result is False

    def test_is_wsl2_false_on_file_not_found(self):
        """Test is_wsl2 returns False when /proc/version doesn't exist."""
        with patch("pathlib.Path.open", side_effect=FileNotFoundError()):
            result = is_wsl2()

        assert result is False

    def test_is_wsl2_false_on_os_error(self):
        """Test is_wsl2 returns False on OSError."""
        with patch("pathlib.Path.open", side_effect=OSError("Permission denied")):
            result = is_wsl2()

        assert result is False

    def test_is_wsl2_false_on_permission_error(self):
        """Test is_wsl2 returns False on PermissionError."""
        with patch("pathlib.Path.open", side_effect=PermissionError("Access denied")):
            result = is_wsl2()

        assert result is False

    def test_is_wsl2_empty_file(self):
        """Test is_wsl2 returns False with empty /proc/version."""
        with patch("pathlib.Path.open", mock_open(read_data="")):
            result = is_wsl2()

        assert result is False

    def test_is_wsl2_multiline_content(self):
        """Test is_wsl2 with multiline content containing microsoft."""
        mock_content = (
            "Linux version 5.15.0\nSome other info\nmicrosoft-standard-WSL2\nMore info"
        )

        with patch("pathlib.Path.open", mock_open(read_data=mock_content)):
            result = is_wsl2()

        assert result is True


class TestWindowsToWslPath:
    """Test windows_to_wsl_path function."""

    def test_windows_to_wsl_path_success(self):
        """Test successful Windows to WSL path conversion."""
        mock_result = Mock()
        mock_result.stdout = "/mnt/e/\n"

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = windows_to_wsl_path("E:\\")

        assert result == "/mnt/e/"
        mock_run.assert_called_once_with(
            ["wslpath", "-u", "E:\\"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )

    def test_windows_to_wsl_path_strips_whitespace(self):
        """Test that output whitespace is stripped."""
        mock_result = Mock()
        mock_result.stdout = "  /mnt/c/Users/test  \n\n"

        with patch("subprocess.run", return_value=mock_result):
            result = windows_to_wsl_path("C:\\Users\\test")

        assert result == "/mnt/c/Users/test"

    def test_windows_to_wsl_path_called_process_error_fallback(self):
        """Test fallback when wslpath command fails."""
        with patch(
            "subprocess.run", side_effect=subprocess.CalledProcessError(1, "wslpath")
        ):
            result = windows_to_wsl_path("E:\\")

        assert result == "/mnt/e/"

    def test_windows_to_wsl_path_timeout_fallback(self):
        """Test fallback when wslpath command times out."""
        with patch(
            "subprocess.run", side_effect=subprocess.TimeoutExpired("wslpath", 5)
        ):
            result = windows_to_wsl_path("C:\\")

        assert result == "/mnt/c/"

    def test_windows_to_wsl_path_fallback_various_drives(self):
        """Test fallback conversion for various drive letters."""
        with patch(
            "subprocess.run", side_effect=subprocess.CalledProcessError(1, "wslpath")
        ):
            assert windows_to_wsl_path("A:\\") == "/mnt/a/"
            assert windows_to_wsl_path("Z:\\") == "/mnt/z/"
            assert windows_to_wsl_path("D:\\test") == "/mnt/d/"

    def test_windows_to_wsl_path_fallback_mixed_case(self):
        """Test fallback with mixed case drive letters."""
        with patch(
            "subprocess.run", side_effect=subprocess.CalledProcessError(1, "wslpath")
        ):
            result = windows_to_wsl_path("E:\\Some\\Path")

        assert result == "/mnt/e/"

    def test_windows_to_wsl_path_no_fallback_for_invalid_path(self):
        """Test that invalid paths without drive letters raise OSError."""
        with (
            patch(
                "subprocess.run",
                side_effect=subprocess.CalledProcessError(1, "wslpath"),
            ),
            pytest.raises(OSError, match="Failed to convert Windows path"),
        ):
            windows_to_wsl_path("invalid_path")

    def test_windows_to_wsl_path_no_fallback_for_short_path(self):
        """Test that paths too short for drive letter raise OSError."""
        with (
            patch(
                "subprocess.run",
                side_effect=subprocess.CalledProcessError(1, "wslpath"),
            ),
            pytest.raises(OSError, match="Failed to convert Windows path"),
        ):
            windows_to_wsl_path("E")

    def test_windows_to_wsl_path_no_fallback_for_no_colon(self):
        """Test that paths without colon raise OSError."""
        with (
            patch(
                "subprocess.run",
                side_effect=subprocess.CalledProcessError(1, "wslpath"),
            ),
            pytest.raises(OSError, match="Failed to convert Windows path"),
        ):
            windows_to_wsl_path("E\\test")

    def test_windows_to_wsl_path_timeout_expired_message(self):
        """Test error message includes timeout information."""
        timeout_error = subprocess.TimeoutExpired("wslpath", 5)

        with (
            patch("subprocess.run", side_effect=timeout_error),
            pytest.raises(OSError, match="Failed to convert Windows path invalid: .*"),
        ):
            windows_to_wsl_path("invalid")

    def test_windows_to_wsl_path_called_process_error_message(self):
        """Test error message includes process error information."""
        process_error = subprocess.CalledProcessError(1, "wslpath", "error output")

        with (
            patch("subprocess.run", side_effect=process_error),
            pytest.raises(OSError, match="Failed to convert Windows path invalid: .*"),
        ):
            windows_to_wsl_path("invalid")


class TestWslToWindowsPath:
    """Test wsl_to_windows_path function."""

    def test_wsl_to_windows_path_success(self):
        """Test successful WSL to Windows path conversion."""
        mock_result = Mock()
        mock_result.stdout = "E:\\\n"

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = wsl_to_windows_path("/mnt/e/")

        assert result == "E:\\"
        mock_run.assert_called_once_with(
            ["wslpath", "-w", "/mnt/e/"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )

    def test_wsl_to_windows_path_strips_whitespace(self):
        """Test that output whitespace is stripped."""
        mock_result = Mock()
        mock_result.stdout = "  C:\\Users\\test  \n\n"

        with patch("subprocess.run", return_value=mock_result):
            result = wsl_to_windows_path("/mnt/c/Users/test")

        assert result == "C:\\Users\\test"

    def test_wsl_to_windows_path_called_process_error(self):
        """Test OSError raised when wslpath command fails."""
        process_error = subprocess.CalledProcessError(1, "wslpath", "error output")

        with (
            patch("subprocess.run", side_effect=process_error),
            pytest.raises(
                OSError, match="Failed to convert WSL path /invalid/path: .*"
            ),
        ):
            wsl_to_windows_path("/invalid/path")

    def test_wsl_to_windows_path_timeout_expired(self):
        """Test OSError raised when wslpath command times out."""
        timeout_error = subprocess.TimeoutExpired("wslpath", 5)

        with (
            patch("subprocess.run", side_effect=timeout_error),
            pytest.raises(OSError, match="Failed to convert WSL path /mnt/c/: .*"),
        ):
            wsl_to_windows_path("/mnt/c/")

    def test_wsl_to_windows_path_various_paths(self):
        """Test conversion with various WSL paths."""
        test_cases = [
            ("/mnt/c/", "C:\\"),
            ("/mnt/d/Users", "D:\\Users"),
            ("/home/user/file.txt", "/home/user/file.txt"),
        ]

        for wsl_path, expected_windows in test_cases:
            mock_result = Mock()
            mock_result.stdout = f"{expected_windows}\n"

            with patch("subprocess.run", return_value=mock_result):
                result = wsl_to_windows_path(wsl_path)
                assert result == expected_windows

    def test_wsl_to_windows_path_empty_output(self):
        """Test conversion with empty output from wslpath."""
        mock_result = Mock()
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            result = wsl_to_windows_path("/mnt/c/")

        assert result == ""

    def test_wsl_to_windows_path_multiline_output(self):
        """Test that only the main output line is returned."""
        mock_result = Mock()
        mock_result.stdout = "C:\\Users\\test\nExtra line\n"

        with patch("subprocess.run", return_value=mock_result):
            result = wsl_to_windows_path("/mnt/c/Users/test")

        assert result == "C:\\Users\\test\nExtra line"

    def test_wsl_to_windows_path_subprocess_run_parameters(self):
        """Test that subprocess.run is called with correct parameters."""
        mock_result = Mock()
        mock_result.stdout = "C:\\"

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            wsl_to_windows_path("/mnt/c/")

        mock_run.assert_called_once_with(
            ["wslpath", "-w", "/mnt/c/"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )


class TestOsUtilsIntegration:
    """Integration tests for OS utilities."""

    def test_round_trip_conversion_fallback(self):
        """Test round-trip conversion using fallback mechanism."""

        # Simulate wslpath not available for windows_to_wsl_path but available for wsl_to_windows_path
        def mock_subprocess_run(cmd, **kwargs):
            if cmd[1] == "-u":  # windows_to_wsl_path
                raise subprocess.CalledProcessError(1, "wslpath")
            else:  # wsl_to_windows_path
                mock_result = Mock()
                mock_result.stdout = "E:\\\n"
                return mock_result

        with patch("subprocess.run", side_effect=mock_subprocess_run):
            # Convert Windows to WSL using fallback
            wsl_path = windows_to_wsl_path("E:\\")
            assert wsl_path == "/mnt/e/"

            # Convert back to Windows using wslpath
            windows_path = wsl_to_windows_path(wsl_path)
            assert windows_path == "E:\\"

    def test_all_functions_handle_edge_cases(self):
        """Test that all functions properly handle their respective edge cases."""
        # Test is_wsl2 with various error conditions
        with patch("pathlib.Path.open", side_effect=FileNotFoundError()):
            assert is_wsl2() is False

        # Test windows_to_wsl_path with subprocess error and invalid fallback
        with (
            patch(
                "subprocess.run",
                side_effect=subprocess.CalledProcessError(1, "wslpath"),
            ),
            pytest.raises(OSError),
        ):
            windows_to_wsl_path("invalid")

        # Test wsl_to_windows_path with subprocess error
        with (
            patch(
                "subprocess.run",
                side_effect=subprocess.CalledProcessError(1, "wslpath"),
            ),
            pytest.raises(OSError),
        ):
            wsl_to_windows_path("/invalid/path")
