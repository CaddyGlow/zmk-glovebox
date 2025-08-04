"""Tests for layout CLI formatters with IconMode integration."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from glovebox.cli.commands.layout.formatters import (
    LayoutOutputFormatter,
    create_layout_output_formatter,
)
from glovebox.cli.helpers.theme import IconMode


class TestLayoutOutputFormatter:
    """Tests for LayoutOutputFormatter with icon mode support."""

    def test_formatter_creation_with_icon_mode(self):
        """Test creating formatter with different icon modes."""
        # Test with enum
        formatter = LayoutOutputFormatter(icon_mode=IconMode.EMOJI)
        assert formatter.icon_mode == IconMode.EMOJI

        formatter = LayoutOutputFormatter(icon_mode=IconMode.NERDFONT)
        assert formatter.icon_mode == IconMode.NERDFONT

        formatter = LayoutOutputFormatter(icon_mode=IconMode.TEXT)
        assert formatter.icon_mode == IconMode.TEXT

    def test_formatter_creation_with_string_mode(self):
        """Test creating formatter with string icon mode."""
        formatter = LayoutOutputFormatter(icon_mode="emoji")
        assert formatter.icon_mode == "emoji"

        formatter = LayoutOutputFormatter(icon_mode="nerdfont")
        assert formatter.icon_mode == "nerdfont"

        formatter = LayoutOutputFormatter(icon_mode="text")
        assert formatter.icon_mode == "text"

    def test_factory_function(self):
        """Test create_layout_output_formatter factory function."""
        formatter = create_layout_output_formatter(icon_mode="nerdfont")
        assert isinstance(formatter, LayoutOutputFormatter)
        assert formatter.icon_mode == "nerdfont"

        formatter = create_layout_output_formatter()
        assert formatter.icon_mode == "emoji"  # Default

    @patch("glovebox.cli.commands.layout.formatters.print_success_message")
    def test_format_comparison_text_uses_icon_mode(self, mock_print_success):
        """Test that format_comparison_text passes icon_mode to print_success_message."""
        formatter = LayoutOutputFormatter(icon_mode="nerdfont")

        # Mock comparison results
        diff_results = {
            "has_changes": True,
            "summary": {"layers": {"added": 1, "removed": 0, "modified": 2}},
            "source_file": "layout1.json",
            "target_file": "layout2.json",
            "detailed": False,
        }

        formatter._format_comparison_text(diff_results)

        # Should call print_success_message with icon_mode
        mock_print_success.assert_called_with(
            "Layout comparison results:", icon_mode="nerdfont"
        )

    def test_format_text_uses_icon_mode(self):
        """Test that _format_text respects icon_mode setting."""
        formatter = LayoutOutputFormatter(icon_mode="text")

        # Test that the formatter stores the icon_mode
        assert formatter.icon_mode == "text"

        # The actual formatting behavior will be tested through integration

    @patch("glovebox.cli.commands.layout.formatters.print_success_message")
    def test_format_field_text_uses_icon_mode(self, mock_print_success):
        """Test that _format_field_text passes icon_mode to print_success_message."""
        formatter = LayoutOutputFormatter(icon_mode="emoji")

        results = {"operations": ["test operation"]}
        formatter._format_field_text(results)

        # Should call print_success_message with icon_mode
        mock_print_success.assert_called_with(
            "Field operation results:", icon_mode="emoji"
        )

    def test_format_summary_changes_respects_icon_mode(self):
        """Test that formatter stores icon_mode for summary changes."""
        formatter = LayoutOutputFormatter(icon_mode="nerdfont")
        assert formatter.icon_mode == "nerdfont"

        # Test the method exists and doesn't crash
        summary = {
            "layers": {"added": 1, "removed": 0, "modified": 2},
            "metadata_changes": 5,
            "dtsi_changes": 2,
        }

        # Should not raise an exception
        formatter._format_summary_changes(summary)

    def test_format_detailed_layer_changes_respects_icon_mode(self):
        """Test that formatter processes layer changes correctly."""
        formatter = LayoutOutputFormatter(icon_mode="text")

        layer_changes = {
            "added": [{"name": "NewLayer", "new_position": 5}],
            "removed": [],
            "modified": [],
        }

        # Should not raise an exception
        formatter._format_detailed_layer_changes(layer_changes)

    def test_format_file_operation_results_respects_icon_mode(self):
        """Test that format_file_operation_results works with icon_mode."""
        formatter = LayoutOutputFormatter(icon_mode="nerdfont")

        # Should not raise an exception
        formatter.format_file_operation_results(
            operation="save",
            input_file=Path("input.json"),
            output_file=Path("output.json"),
            output_format="text",
        )

    def test_format_validation_text_respects_icon_mode(self):
        """Test that _format_validation_text works with icon_mode."""
        formatter = LayoutOutputFormatter(icon_mode="emoji")

        # Test valid result
        result = {"valid": True, "file": "test.json"}

        # Should not raise an exception
        formatter._format_validation_text(result)

    def test_format_compilation_text_respects_icon_mode(self):
        """Test that _format_compilation_text works with icon_mode."""
        formatter = LayoutOutputFormatter(icon_mode="text")

        # Test successful compilation
        result = {"success": True, "output_files": {"keymap": "output.keymap"}}

        # Should not raise an exception
        formatter._format_compilation_text(result)

    def test_json_format_not_affected_by_icon_mode(self):
        """Test that JSON output format is not affected by icon_mode."""
        formatter = LayoutOutputFormatter(icon_mode="nerdfont")

        results = {"test": "data", "success": True}

        with patch("builtins.print") as mock_print:
            formatter._format_json(results)

            # Should print JSON regardless of icon mode
            printed_output = mock_print.call_args[0][0]
            parsed = json.loads(printed_output)
            assert parsed == results

    @patch("glovebox.cli.commands.layout.formatters.print_success_message")
    def test_no_differences_message_uses_icon_mode(self, mock_print_success):
        """Test that 'no differences' messages use the correct icon_mode."""
        formatter = LayoutOutputFormatter(icon_mode="text")

        # Test empty diff results
        diff_results: dict[str, Any] = {}
        formatter._format_comparison_text(diff_results)

        # Should call print_success_message with icon_mode
        mock_print_success.assert_called_with("No differences found", icon_mode="text")

    def test_diff_file_creation_respects_icon_mode(self):
        """Test that diff file creation works with icon_mode."""
        formatter = LayoutOutputFormatter(icon_mode="emoji")

        diff_results = {
            "has_changes": True,
            "summary": {},
            "source_file": "layout1.json",
            "target_file": "layout2.json",
            "detailed": False,
            "diff_file_created": {"diff_file": "changes.json"},
        }

        # Should not raise an exception
        formatter._format_comparison_text(diff_results)
