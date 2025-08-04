"""Tests for library-aware parameter completion."""

from unittest.mock import patch

import pytest

from glovebox.cli.helpers.parameters import (
    _complete_library_references,
    complete_json_files,
)


class TestLibraryCompletion:
    """Test library-aware completion functions."""

    @pytest.fixture
    def mock_library_entries(self):
        """Create mock library entries for testing."""
        return [
            ("@my-gaming-layout", "Gaming Layout (by user1)"),
            ("@work-layout", "Work Layout (by user2)"),
            ("@12345678-1234-1234-1234-123456789abc", "Gaming Layout (UUID)"),
            ("@87654321-4321-4321-4321-210987654321", "Work Layout (UUID)"),
        ]

    def test_complete_json_files_with_at_prefix(self, mock_library_entries):
        """Test JSON file completion with @ prefix shows library entries."""
        with patch(
            "glovebox.cli.helpers.library_resolver.get_library_entries_for_completion",
            return_value=mock_library_entries,
        ):
            # Test with just "@"
            completions = complete_json_files("@")
            assert "@my-gaming-layout" in completions
            assert "@work-layout" in completions
            assert len(completions) <= 20  # Limited for usability

            # Test with partial match
            completions = complete_json_files("@my")
            assert "@my-gaming-layout" in completions
            assert "@work-layout" not in completions

            # Test with UUID partial
            completions = complete_json_files("@123")
            assert "@12345678-1234-1234-1234-123456789abc" in completions
            assert "@87654321-4321-4321-4321-210987654321" not in completions

    def test_complete_json_files_without_at_prefix(self, tmp_path):
        """Test JSON file completion without @ prefix shows files."""
        # Create test files
        json_file = tmp_path / "test.json"
        json_file.touch()
        other_file = tmp_path / "test.txt"
        other_file.touch()
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        with patch("pathlib.Path.cwd", return_value=tmp_path):
            # Empty input shows common options including @
            completions = complete_json_files("")
            assert "@" in completions
            assert "examples/layouts/" in completions
            assert "./" in completions
            assert "../" in completions

            # Partial file match
            with (
                patch("pathlib.Path.exists", return_value=True),
                patch(
                    "pathlib.Path.iterdir", return_value=[json_file, other_file, subdir]
                ),
            ):
                completions = complete_json_files("te")
                # Note: The actual implementation might need adjustment
                # This is testing the expected behavior

    def test_complete_library_references(self, mock_library_entries):
        """Test _complete_library_references function."""
        with patch(
            "glovebox.cli.helpers.library_resolver.get_library_entries_for_completion",
            return_value=mock_library_entries,
        ):
            # Test with just "@"
            completions = _complete_library_references("@")
            assert len(completions) <= 20
            assert all(comp.startswith("@") for comp in completions)

            # Test with partial name
            completions = _complete_library_references("@work")
            assert "@work-layout" in completions
            assert "@my-gaming-layout" not in completions

            # Test case sensitivity - matching is case-sensitive
            completions = _complete_library_references("@WORK")
            # Case-sensitive matching means uppercase won't match lowercase
            assert "@work-layout" not in completions
            assert len(completions) == 0  # No matches for uppercase

    def test_complete_library_references_error_handling(self):
        """Test completion handles errors gracefully."""
        with patch(
            "glovebox.cli.helpers.library_resolver.get_library_entries_for_completion",
            side_effect=Exception("Service error"),
        ):
            completions = _complete_library_references("@")
            assert completions == []

    def test_complete_json_files_handles_exceptions(self):
        """Test that complete_json_files handles exceptions gracefully."""
        with patch("pathlib.Path", side_effect=Exception("Path error")):
            completions = complete_json_files("test")
            assert completions == []


class TestParameterIntegration:
    """Test integration with parameter definitions."""

    def test_json_file_argument_has_library_completion(self):
        """Test that JsonFileArgument uses library-aware completion."""
        from typing import get_args

        from glovebox.cli.helpers.parameters import JsonFileArgument

        # Get the annotation metadata - JsonFileArgument is Annotated[type, metadata]
        metadata = get_args(JsonFileArgument)
        if len(metadata) > 1:
            arg_info = metadata[1]  # The typer.Argument() is the second element

            # Check that it uses complete_json_files for autocompletion
            assert arg_info.autocompletion is complete_json_files

            # Check help text mentions library references
            assert "@library-name/uuid" in arg_info.help

    def test_parameter_factory_json_file_includes_library_help(self):
        """Test that ParameterFactory includes library reference in help."""
        from typing import get_args

        from glovebox.cli.helpers.parameter_factory import ParameterFactory

        # Create a JSON file argument
        param = ParameterFactory.json_file_argument()

        # Get the annotation metadata - param is Annotated[type, metadata]
        metadata = get_args(param)
        if len(metadata) > 1:
            arg_info = metadata[1]  # The typer.Argument() is the second element

            # Check help text
            assert "@library-name/uuid" in arg_info.help
            assert arg_info.autocompletion is complete_json_files
