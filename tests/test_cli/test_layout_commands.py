"""Tests for refactored layout CLI commands."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.cli.app import app
from glovebox.cli.commands import register_all_commands


# Register commands with the app before running tests
register_all_commands(app)


@pytest.fixture
def sample_layout():
    """Create a sample layout for testing."""
    return {
        "title": "Test Layout",
        "keyboard": "glove80",
        "version": "1.0",
        "layer_names": ["Base", "Symbol"],
        "layers": [
            [
                {"value": "&kp Q", "params": []},
                {"value": "&kp W", "params": []},
            ],
            [
                {"value": "&kp EXCL", "params": []},
                {"value": "&kp AT", "params": []},
            ],
        ],
        "custom_defined_behaviors": "",
        "custom_devicetree": "",
    }


@pytest.fixture
def layout_file(tmp_path, sample_layout):
    """Create a temporary layout file for testing."""
    layout_path = tmp_path / "test_layout.json"
    with layout_path.open("w") as f:
        json.dump(sample_layout, f, indent=2)
    return layout_path


@pytest.fixture
def mock_layout_service():
    """Create a mock layout service."""
    with (
        patch(
            "glovebox.cli.commands.layout.core.create_layout_service"
        ) as mock_create_core,
        patch(
            "glovebox.cli.commands.layout.file_operations.create_layout_service"
        ) as mock_create_file,
    ):
        mock_service = Mock()
        mock_create_core.return_value = mock_service
        mock_create_file.return_value = mock_service
        yield mock_service


@pytest.fixture
def mock_layout_editor_service():
    """Create a mock layout editor service."""
    with patch(
        "glovebox.cli.commands.layout.edit.create_layout_editor_service"
    ) as mock_create:
        mock_service = Mock()
        mock_create.return_value = mock_service
        yield mock_service


@pytest.fixture
def mock_layout_layer_service():
    """Create a mock layout layer service."""
    with (
        patch(
            "glovebox.cli.commands.layout.edit.create_layout_layer_service"
        ) as mock_create_edit,
        patch(
            "glovebox.cli.commands.layout.file_operations.create_layout_layer_service"
        ) as mock_create_file,
    ):
        mock_service = Mock()
        mock_create_edit.return_value = mock_service
        mock_create_file.return_value = mock_service
        yield mock_service


@pytest.fixture
def mock_version_manager():
    """Create a mock version manager."""
    with (
        patch(
            "glovebox.cli.commands.layout.versions.create_version_manager"
        ) as mock_create_versions,
        patch(
            "glovebox.cli.commands.layout.upgrade.create_version_manager"
        ) as mock_create_upgrade,
    ):
        mock_manager = Mock()
        mock_create_versions.return_value = mock_manager
        mock_create_upgrade.return_value = mock_manager
        yield mock_manager


class TestLayoutCore:
    """Test core layout commands (compile, validate, show)."""

    def test_compile_command_success(
        self, cli_runner, layout_file, mock_layout_service
    ):
        """Test successful layout compilation."""
        # Mock successful compilation
        mock_result = Mock()
        mock_result.success = True
        mock_result.keymap_path = Path("/tmp/test.keymap")
        mock_result.conf_path = Path("/tmp/test.conf")
        mock_result.json_path = Path("/tmp/test.json")
        mock_result.get_output_files.return_value = {
            "keymap": Path("/tmp/test.keymap"),
            "conf": Path("/tmp/test.conf"),
            "json": Path("/tmp/test.json"),
        }
        mock_layout_service.generate_from_file.return_value = mock_result

        result = cli_runner.invoke(
            app,
            [
                "layout",
                "compile",
                str(layout_file),
                "/tmp/output",
                "--profile",
                "glove80/v25.05",
            ],
        )

        assert result.exit_code == 0
        assert "Layout generated successfully" in result.output
        mock_layout_service.generate_from_file.assert_called_once()

    def test_compile_command_failure(
        self, cli_runner, layout_file, mock_layout_service
    ):
        """Test layout compilation failure."""
        # Mock compilation failure
        mock_result = Mock()
        mock_result.success = False
        mock_result.errors = ["Invalid binding syntax"]
        mock_layout_service.generate_from_file.return_value = mock_result

        result = cli_runner.invoke(
            app,
            [
                "layout",
                "compile",
                str(layout_file),
                "/tmp/output",
                "--profile",
                "glove80/v25.05",
            ],
        )

        assert result.exit_code == 1
        assert "Layout generation failed" in result.output
        assert "Invalid binding syntax" in result.output

    def test_validate_command_success(
        self, cli_runner, layout_file, mock_layout_service
    ):
        """Test successful layout validation."""
        mock_layout_service.validate_from_file.return_value = True

        result = cli_runner.invoke(
            app, ["layout", "validate", str(layout_file), "--profile", "glove80/v25.05"]
        )

        assert result.exit_code == 0
        assert "Layout file" in result.output
        assert "is valid" in result.output

    def test_validate_command_failure(
        self, cli_runner, layout_file, mock_layout_service
    ):
        """Test layout validation failure."""
        mock_layout_service.validate_from_file.return_value = False

        result = cli_runner.invoke(
            app, ["layout", "validate", str(layout_file), "--profile", "glove80/v25.05"]
        )

        assert result.exit_code == 1
        assert "Layout file" in result.output
        assert "is invalid" in result.output

    def test_show_command(self, cli_runner, layout_file, mock_layout_service):
        """Test layout show command."""
        mock_layout_service.show_from_file.return_value = "Formatted layout output"

        result = cli_runner.invoke(app, ["layout", "show", str(layout_file)])

        assert result.exit_code == 0
        assert "Formatted layout output" in result.output
        mock_layout_service.show_from_file.assert_called_once()


class TestLayoutEdit:
    """Test unified layout edit command with batch operations."""

    def test_edit_get_field(self, cli_runner, layout_file):
        """Test getting a field value."""
        result = cli_runner.invoke(
            app, ["layout", "edit", str(layout_file), "--get", "title", "--no-save"]
        )

        assert result.exit_code == 0
        assert "title: Test Layout" in result.output

    def test_edit_get_multiple_fields(self, cli_runner, layout_file):
        """Test getting multiple field values."""
        result = cli_runner.invoke(
            app,
            [
                "layout",
                "edit",
                str(layout_file),
                "--get",
                "title",
                "--get",
                "keyboard",
                "--no-save",
            ],
        )

        assert result.exit_code == 0
        assert "title: Test Layout" in result.output
        assert "keyboard: glove80" in result.output

    def test_edit_set_field(self, cli_runner, layout_file, mock_layout_editor_service):
        """Test setting a field value."""
        output_path = layout_file.parent / "modified_layout.json"
        mock_layout_editor_service.set_field_value.return_value = output_path

        result = cli_runner.invoke(
            app, ["layout", "edit", str(layout_file), "--set", "title=New Title"]
        )

        assert result.exit_code == 0
        assert "Layout edited successfully (1 operations)" in result.output
        assert "Set title: New Title" in result.output
        mock_layout_editor_service.set_field_value.assert_called_once()

    def test_edit_set_multiple_fields(
        self, cli_runner, layout_file, mock_layout_editor_service
    ):
        """Test setting multiple field values."""
        output_path = layout_file.parent / "modified_layout.json"
        mock_layout_editor_service.set_field_value.return_value = output_path

        result = cli_runner.invoke(
            app,
            [
                "layout",
                "edit",
                str(layout_file),
                "--set",
                "title=New Title",
                "--set",
                "version=2.0",
            ],
        )

        assert result.exit_code == 0
        assert "Layout edited successfully (2 operations)" in result.output
        assert mock_layout_editor_service.set_field_value.call_count == 2

    def test_edit_add_layer(self, cli_runner, layout_file, mock_layout_layer_service):
        """Test adding a layer."""
        mock_result = {
            "output_path": layout_file.parent / "modified_layout.json",
            "position": 2,
        }
        mock_layout_layer_service.add_layer.return_value = mock_result

        result = cli_runner.invoke(
            app, ["layout", "edit", str(layout_file), "--add-layer", "Gaming"]
        )

        assert result.exit_code == 0
        assert "Layout edited successfully (1 operations)" in result.output
        assert "Added layer 'Gaming' at position 2" in result.output
        mock_layout_layer_service.add_layer.assert_called_once()

    def test_edit_remove_layer(
        self, cli_runner, layout_file, mock_layout_layer_service
    ):
        """Test removing a layer."""
        mock_result = {
            "output_path": layout_file.parent / "modified_layout.json",
            "removed_layers": [{"name": "Symbol", "position": 1}],
            "removed_count": 1,
            "remaining_layers": 1,
            "warnings": [],
            "had_matches": True,
        }
        mock_layout_layer_service.remove_layer.return_value = mock_result

        result = cli_runner.invoke(
            app, ["layout", "edit", str(layout_file), "--remove-layer", "Symbol"]
        )

        assert result.exit_code == 0
        assert "Layout edited successfully (1 operations)" in result.output
        assert "Removed layer 'Symbol' (position 1)" in result.output
        mock_layout_layer_service.remove_layer.assert_called_once()

    def test_edit_move_layer(self, cli_runner, layout_file, mock_layout_layer_service):
        """Test moving a layer."""
        mock_result = {
            "output_path": layout_file.parent / "modified_layout.json",
            "from_position": 1,
            "to_position": 0,
        }
        mock_layout_layer_service.move_layer.return_value = mock_result

        result = cli_runner.invoke(
            app, ["layout", "edit", str(layout_file), "--move-layer", "Symbol:0"]
        )

        assert result.exit_code == 0
        assert "Layout edited successfully (1 operations)" in result.output
        assert "Moved layer 'Symbol' from 1 to 0" in result.output
        mock_layout_layer_service.move_layer.assert_called_once()

    def test_edit_copy_layer(self, cli_runner, layout_file, mock_layout_layer_service):
        """Test copying a layer."""
        mock_result = {
            "output_path": layout_file.parent / "modified_layout.json",
            "position": 2,
        }
        mock_layout_layer_service.add_layer.return_value = mock_result

        result = cli_runner.invoke(
            app, ["layout", "edit", str(layout_file), "--copy-layer", "Base:Gaming"]
        )

        assert result.exit_code == 0
        assert "Layout edited successfully (1 operations)" in result.output
        assert "Copied layer 'Base' as 'Gaming'" in result.output
        mock_layout_layer_service.add_layer.assert_called_once()

    def test_edit_list_layers(self, cli_runner, layout_file, mock_layout_layer_service):
        """Test listing layers."""
        mock_result = {
            "total_layers": 2,
            "layers": [
                {"position": 0, "name": "Base", "binding_count": 2},
                {"position": 1, "name": "Symbol", "binding_count": 2},
            ],
        }
        mock_layout_layer_service.list_layers.return_value = mock_result

        result = cli_runner.invoke(
            app, ["layout", "edit", str(layout_file), "--list-layers", "--no-save"]
        )

        assert result.exit_code == 0
        assert "Layout has 2 layers:" in result.output
        assert " 0: Base (2 bindings)" in result.output
        assert " 1: Symbol (2 bindings)" in result.output
        mock_layout_layer_service.list_layers.assert_called_once()

    def test_edit_batch_operations(
        self,
        cli_runner,
        layout_file,
        mock_layout_editor_service,
        mock_layout_layer_service,
    ):
        """Test multiple operations in one command."""
        # Mock editor service
        output_path = layout_file.parent / "modified_layout.json"
        mock_layout_editor_service.set_field_value.return_value = output_path

        # Mock layer service
        mock_layer_result = {"output_path": output_path, "position": 2}
        mock_layout_layer_service.add_layer.return_value = mock_layer_result
        mock_layout_layer_service.remove_layer.return_value = {
            "output_path": output_path,
            "removed_layers": [{"name": "Symbol", "position": 1}],
            "removed_count": 1,
            "remaining_layers": 1,
            "warnings": [],
            "had_matches": True,
        }

        result = cli_runner.invoke(
            app,
            [
                "layout",
                "edit",
                str(layout_file),
                "--set",
                "title=Updated Layout",
                "--add-layer",
                "Gaming",
                "--remove-layer",
                "Symbol",
            ],
        )

        assert result.exit_code == 0
        assert "Layout edited successfully (3 operations)" in result.output
        assert "Set title: Updated Layout" in result.output
        assert "Added layer 'Gaming' at position 2" in result.output
        assert "Removed layer 'Symbol' (position 1)" in result.output

    def test_edit_batch_remove_with_warnings(
        self, cli_runner, layout_file, mock_layout_layer_service
    ):
        """Test batch remove operations with some successes and some warnings."""
        # Mock successful removal for one layer, warnings for others
        mock_layout_layer_service.remove_layer.side_effect = [
            {
                "output_path": layout_file.parent / "modified_layout.json",
                "removed_layers": [{"name": "Symbol", "position": 1}],
                "removed_count": 1,
                "remaining_layers": 1,
                "warnings": [],
                "had_matches": True,
            },
            {
                "output_path": layout_file,
                "removed_layers": [],
                "removed_count": 0,
                "remaining_layers": 2,
                "warnings": [
                    "No layers found matching identifier 'NonExistent'. Available layers: Base, Symbol"
                ],
                "had_matches": False,
            },
        ]

        result = cli_runner.invoke(
            app,
            [
                "layout",
                "edit",
                str(layout_file),
                "--remove-layer",
                "Symbol",
                "--remove-layer",
                "NonExistent",
            ],
        )

        assert result.exit_code == 0
        assert (
            "Layout edited successfully (1 operations) with 1 warnings" in result.output
        )
        assert "Removed layer 'Symbol' (position 1)" in result.output
        assert "No layers found matching identifier 'NonExistent'" in result.output

    def test_edit_remove_all_failed(
        self, cli_runner, layout_file, mock_layout_layer_service
    ):
        """Test remove operations where all identifiers fail to match."""
        # Mock all removals failing
        mock_layout_layer_service.remove_layer.return_value = {
            "output_path": layout_file,
            "removed_layers": [],
            "removed_count": 0,
            "remaining_layers": 2,
            "warnings": [
                "No layers found matching identifier 'NonExistent'. Available layers: Base, Symbol"
            ],
            "had_matches": False,
        }

        result = cli_runner.invoke(
            app,
            [
                "layout",
                "edit",
                str(layout_file),
                "--remove-layer",
                "NonExistent",
            ],
        )

        assert result.exit_code == 0
        assert (
            "No layers were removed - all identifiers failed to match" in result.output
        )
        assert "No layers found matching identifier 'NonExistent'" in result.output

    def test_edit_invalid_set_syntax(self, cli_runner, layout_file):
        """Test invalid set operation syntax."""
        result = cli_runner.invoke(
            app, ["layout", "edit", str(layout_file), "--set", "invalid_syntax"]
        )

        assert result.exit_code == 1
        assert "Invalid set syntax: invalid_syntax" in result.output
        assert "key=value" in result.output and "format" in result.output

    def test_edit_invalid_move_syntax(self, cli_runner, layout_file):
        """Test invalid move operation syntax."""
        result = cli_runner.invoke(
            app, ["layout", "edit", str(layout_file), "--move-layer", "invalid_syntax"]
        )

        assert result.exit_code == 1
        assert "Invalid move syntax: invalid_syntax" in result.output
        assert "LayerName:position" in result.output

    def test_edit_invalid_copy_syntax(self, cli_runner, layout_file):
        """Test invalid copy operation syntax."""
        result = cli_runner.invoke(
            app, ["layout", "edit", str(layout_file), "--copy-layer", "invalid_syntax"]
        )

        assert result.exit_code == 1
        assert "Invalid copy syntax: invalid_syntax" in result.output
        assert "SourceLayer:NewName" in result.output

    def test_edit_json_output(
        self, cli_runner, layout_file, mock_layout_editor_service
    ):
        """Test edit command with JSON output."""
        mock_layout_editor_service.get_field_value.return_value = "Test Layout"

        result = cli_runner.invoke(
            app,
            [
                "layout",
                "edit",
                str(layout_file),
                "--get",
                "title",
                "--output-format",
                "json",
                "--no-save",
            ],
        )

        assert result.exit_code == 0
        output_data = json.loads(result.output.strip())
        assert "get:title" in output_data
        assert output_data["get:title"] == "Test Layout"

    def test_edit_unset_field(self, cli_runner, layout_file):
        """Test removing a field value with --unset."""
        with patch(
            "glovebox.cli.commands.layout.edit._unset_field_value"
        ) as mock_unset:
            mock_unset.return_value = layout_file.parent / "modified_layout.json"

            result = cli_runner.invoke(
                app, ["layout", "edit", str(layout_file), "--unset", "variables.oldVar"]
            )

            assert result.exit_code == 0
            assert "Layout edited successfully (1 operations)" in result.output
            assert "Removed variables.oldVar" in result.output
            mock_unset.assert_called_once()

    def test_edit_unset_multiple_fields(self, cli_runner, layout_file):
        """Test removing multiple field values with --unset."""
        with patch(
            "glovebox.cli.commands.layout.edit._unset_field_value"
        ) as mock_unset:
            mock_unset.return_value = layout_file.parent / "modified_layout.json"

            result = cli_runner.invoke(
                app,
                [
                    "layout",
                    "edit",
                    str(layout_file),
                    "--unset",
                    "variables.oldVar",
                    "--unset",
                    "variables.unused",
                ],
            )

            assert result.exit_code == 0
            assert "Layout edited successfully (2 operations)" in result.output
            assert "Removed variables.oldVar" in result.output
            assert "Removed variables.unused" in result.output
            assert mock_unset.call_count == 2

    def test_edit_list_usage(self, cli_runner, layout_file):
        """Test listing variable usage with --list-usage."""
        with patch(
            "glovebox.cli.commands.layout.edit._get_variable_usage"
        ) as mock_usage:
            mock_usage.return_value = {
                "tapMs": [
                    "hold_taps[0].tapping_term_ms",
                    "hold_taps[1].tapping_term_ms",
                ],
                "flavor": ["hold_taps[0].flavor"],
            }

            result = cli_runner.invoke(
                app, ["layout", "edit", str(layout_file), "--list-usage", "--no-save"]
            )

            assert result.exit_code == 0
            assert "Variable Usage" in result.output or "tapMs" in result.output
            mock_usage.assert_called_once()

    def test_edit_set_creates_new_variable(
        self, cli_runner, layout_file, mock_layout_editor_service
    ):
        """Test that --set can create new dictionary keys."""
        output_path = layout_file.parent / "modified_layout.json"
        mock_layout_editor_service.set_field_value.return_value = output_path

        result = cli_runner.invoke(
            app,
            [
                "layout",
                "edit",
                str(layout_file),
                "--set",
                "variables.newVar=value",
            ],
        )

        assert result.exit_code == 0
        assert "Layout edited successfully (1 operations)" in result.output
        assert "Set variables.newVar: value" in result.output
        mock_layout_editor_service.set_field_value.assert_called_once()

    def test_edit_batch_with_unset(
        self, cli_runner, layout_file, mock_layout_editor_service
    ):
        """Test batch operations including unset."""
        output_path = layout_file.parent / "modified_layout.json"
        mock_layout_editor_service.set_field_value.return_value = output_path

        with patch(
            "glovebox.cli.commands.layout.edit._unset_field_value"
        ) as mock_unset:
            mock_unset.return_value = output_path

            result = cli_runner.invoke(
                app,
                [
                    "layout",
                    "edit",
                    str(layout_file),
                    "--set",
                    "variables.newVar=value",
                    "--unset",
                    "variables.oldVar",
                ],
            )

            assert result.exit_code == 0
            assert "Layout edited successfully (2 operations)" in result.output
            assert "Set variables.newVar: value" in result.output
            assert "Removed variables.oldVar" in result.output
            mock_layout_editor_service.set_field_value.assert_called_once()
            mock_unset.assert_called_once()

    def test_edit_complex_nested_set(
        self, cli_runner, layout_file, mock_layout_editor_service
    ):
        """Test setting complex nested fields with array indexing."""
        output_path = layout_file.parent / "modified_layout.json"
        mock_layout_editor_service.set_field_value.return_value = output_path

        result = cli_runner.invoke(
            app,
            [
                "layout",
                "edit",
                str(layout_file),
                "--set",
                'hold_taps[0].tapping_term_ms="${tapMs}"',
            ],
        )

        assert result.exit_code == 0
        assert "Layout edited successfully (1 operations)" in result.output
        assert "Set hold_taps[0].tapping_term_ms" in result.output
        mock_layout_editor_service.set_field_value.assert_called_once()

        # Verify the correct field path and value were passed
        call_args = mock_layout_editor_service.set_field_value.call_args[1]
        assert call_args["field_path"] == "hold_taps[0].tapping_term_ms"
        assert call_args["value"] == '"${tapMs}"'

    def test_edit_preserves_variables_regression_test(self, cli_runner, tmp_path):
        """Regression test: ensure variables are preserved during edit operations.

        This test specifically addresses the variable flattening issue where
        variable references like '${tapMs}' were being resolved to their values
        during edit operations, causing loss of variable references when saving.
        """
        # Create a layout with variable references
        layout_with_variables = {
            "keyboard": "test_keyboard",
            "title": "Variable Test Layout",
            "layer_names": ["base"],
            "layers": [
                [
                    {"value": "&kp", "params": [{"value": "Q"}]},
                    {"value": "&kp", "params": [{"value": "W"}]},
                    {"value": "&kp", "params": [{"value": "E"}]},
                ]
            ],
            "variables": {"tapMs": 150, "holdMs": 200, "flavor": "tap-preferred"},
            "hold_taps": [
                {
                    "name": "&ht_test",
                    "tapping_term_ms": "${tapMs}",
                    "quick_tap_ms": "${holdMs}",
                    "flavor": "${flavor}",
                }
            ],
            "behaviors": {
                "custom_tap": {
                    "type": "hold_tap",
                    "tapping_term_ms": "${tapMs}",
                    "flavor": "${flavor}",
                }
            },
            "combos": [
                {
                    "name": "esc_combo",
                    "timeout_ms": "${holdMs}",
                    "keyPositions": [0, 1],
                    "binding": {"value": "&kp", "params": [{"value": "ESC"}]},
                }
            ],
        }

        # Create temporary input and output files
        input_file = tmp_path / "input_variables.json"
        output_file = tmp_path / "output_variables.json"

        # Write the layout with variables
        input_file.write_text(json.dumps(layout_with_variables, indent=2))

        # Perform an edit operation that should preserve variables
        result = cli_runner.invoke(
            app,
            [
                "layout",
                "edit",
                str(input_file),
                "--set",
                "variables.newVar=999",
                "--output",
                str(output_file),
            ],
        )

        assert result.exit_code == 0
        assert "Layout edited successfully" in result.output

        # Read the output and verify variables are preserved
        output_content = json.loads(output_file.read_text())

        # New variable should be added
        assert output_content["variables"]["newVar"] == 999

        # Original variables should be preserved
        assert output_content["variables"]["tapMs"] == 150
        assert output_content["variables"]["holdMs"] == 200
        assert output_content["variables"]["flavor"] == "tap-preferred"

        # CRITICAL: Variable references should remain as references (not resolved to values)
        assert output_content["hold_taps"][0]["tapping_term_ms"] == "${tapMs}"
        assert output_content["hold_taps"][0]["quick_tap_ms"] == "${holdMs}"
        assert output_content["hold_taps"][0]["flavor"] == "${flavor}"

        assert (
            output_content["behaviors"]["custom_tap"]["tapping_term_ms"] == "${tapMs}"
        )
        assert output_content["behaviors"]["custom_tap"]["flavor"] == "${flavor}"

        assert output_content["combos"][0]["timeout_ms"] == "${holdMs}"

    def test_edit_unset_variable_preserves_remaining_references(
        self, cli_runner, isolated_cli_environment
    ):
        """Test that unsetting a variable preserves remaining variable references."""
        layout_with_variables = {
            "keyboard": "test_keyboard",
            "title": "Variable Test Layout",
            "layer_names": ["base"],
            "layers": [[{"value": "&kp", "params": [{"value": "Q"}]}]],
            "variables": {"tapMs": 150, "holdMs": 200, "flavor": "tap-preferred"},
            "hold_taps": [
                {
                    "name": "&ht_test",
                    "tapping_term_ms": "${tapMs}",
                    "quick_tap_ms": "${holdMs}",  # This reference will become invalid
                    "flavor": "${flavor}",
                }
            ],
        }

        input_file = isolated_cli_environment["temp_dir"] / "input_unset.json"
        output_file = isolated_cli_environment["temp_dir"] / "output_unset.json"

        input_file.write_text(json.dumps(layout_with_variables, indent=2))

        # Remove the holdMs variable
        result = cli_runner.invoke(
            app,
            [
                "layout",
                "edit",
                str(input_file),
                "--unset",
                "variables.holdMs",
                "--output",
                str(output_file),
            ],
        )

        assert result.exit_code == 0, f"Command failed with output: {result.output}"
        assert "Layout edited successfully" in result.output

        output_content = json.loads(output_file.read_text())

        # holdMs variable should be removed
        assert "holdMs" not in output_content["variables"]

        # Remaining variables should be preserved
        assert output_content["variables"]["tapMs"] == 150
        assert output_content["variables"]["flavor"] == "tap-preferred"

        # Variable references should remain as references
        assert output_content["hold_taps"][0]["tapping_term_ms"] == "${tapMs}"
        assert output_content["hold_taps"][0]["flavor"] == "${flavor}"

        # The reference to removed variable should remain (this is expected behavior)
        assert output_content["hold_taps"][0]["quick_tap_ms"] == "${holdMs}"

    def test_edit_multiple_operations_preserve_variables(
        self, cli_runner, isolated_cli_environment
    ):
        """Test that multiple edit operations in sequence preserve variables."""
        layout_with_variables = {
            "keyboard": "test_keyboard",
            "title": "Variable Test Layout",
            "layer_names": ["base"],
            "layers": [[{"value": "&kp", "params": [{"value": "Q"}]}]],
            "variables": {"tapMs": 150, "flavor": "tap-preferred"},
            "behaviors": {
                "custom_tap": {
                    "type": "hold_tap",
                    "tapping_term_ms": "${tapMs}",
                    "flavor": "${flavor}",
                    "bindings": ["&kp", "&mo"],
                }
            },
        }

        input_file = isolated_cli_environment["temp_dir"] / "input_multi.json"

        input_file.write_text(json.dumps(layout_with_variables, indent=2))

        # Perform multiple operations in a single command
        result = cli_runner.invoke(
            app,
            [
                "layout",
                "edit",
                str(input_file),
                "--set",
                "variables.newTiming=250",
                "--set",
                "variables.tapMs=175",  # Modify existing variable
                "--set",
                "title=Updated Layout",
                "--unset",
                "variables.flavor",  # Remove a variable
                "--add-layer",
                "gaming",
            ],
        )

        assert result.exit_code == 0
        assert "Layout edited successfully" in result.output

        output_content = json.loads(input_file.read_text())

        # Variables should be updated correctly
        assert output_content["variables"]["newTiming"] == 250
        assert output_content["variables"]["tapMs"] == 175  # Updated
        assert "flavor" not in output_content["variables"]  # Removed

        # Title should be updated
        assert output_content["title"] == "Updated Layout"

        # New layer should be added
        assert "gaming" in output_content["layer_names"]

        # CRITICAL: Remaining variable references should be preserved
        assert (
            output_content["behaviors"]["custom_tap"]["tapping_term_ms"] == "${tapMs}"
        )

        # Reference to removed variable should remain (expected behavior)
        assert output_content["behaviors"]["custom_tap"]["flavor"] == "${flavor}"


class TestLayoutFileOperations:
    """Test file operation commands (split, merge, export, import)."""

    def test_split_command(self, cli_runner, layout_file, mock_layout_service):
        """Test splitting layout into components."""
        mock_result = Mock()
        mock_result.success = True
        mock_layout_service.decompose_components_from_file.return_value = mock_result

        output_dir = layout_file.parent / "components"

        result = cli_runner.invoke(
            app,
            [
                "layout",
                "split",
                str(layout_file),
                str(output_dir),
                "--profile",
                "glove80/v25.05",
            ],
        )

        assert result.exit_code == 0
        assert "Layout split into components" in result.output
        mock_layout_service.decompose_components_from_file.assert_called_once()

    def test_split_command_failure(self, cli_runner, layout_file, mock_layout_service):
        """Test split command failure."""
        mock_result = Mock()
        mock_result.success = False
        mock_result.errors = ["Failed to create component files"]
        mock_layout_service.decompose_components_from_file.return_value = mock_result

        output_dir = layout_file.parent / "components"

        result = cli_runner.invoke(
            app,
            [
                "layout",
                "split",
                str(layout_file),
                str(output_dir),
                "--profile",
                "glove80/v25.05",
            ],
        )

        assert result.exit_code == 1
        assert "Layout split failed" in result.output
        assert "Failed to create component files" in result.output

    def test_merge_command(self, cli_runner, tmp_path, mock_layout_service):
        """Test merging components into layout."""
        mock_result = Mock()
        mock_result.success = True
        mock_layout_service.generate_from_directory.return_value = mock_result

        input_dir = tmp_path / "components"
        output_file = tmp_path / "merged_layout.json"

        result = cli_runner.invoke(
            app,
            [
                "layout",
                "merge",
                str(input_dir),
                str(output_file),
                "--profile",
                "glove80/v25.05",
            ],
        )

        assert result.exit_code == 0
        assert "Components merged into layout" in result.output
        mock_layout_service.generate_from_directory.assert_called_once()

    def test_merge_command_failure(self, cli_runner, tmp_path, mock_layout_service):
        """Test merge command failure."""
        mock_result = Mock()
        mock_result.success = False
        mock_result.errors = ["Missing metadata.json"]
        mock_layout_service.generate_from_directory.return_value = mock_result

        input_dir = tmp_path / "components"
        output_file = tmp_path / "merged_layout.json"

        result = cli_runner.invoke(
            app,
            [
                "layout",
                "merge",
                str(input_dir),
                str(output_file),
                "--profile",
                "glove80/v25.05",
            ],
        )

        assert result.exit_code == 1
        assert "Layout merge failed" in result.output
        assert "Missing metadata.json" in result.output

    def test_export_command(self, cli_runner, layout_file, mock_layout_layer_service):
        """Test exporting a layer."""
        mock_result = {
            "source_file": layout_file,
            "layer_name": "Symbol",
            "output_file": layout_file.parent / "symbol.json",
            "format": "bindings",
            "binding_count": 2,
        }
        mock_layout_layer_service.export_layer.return_value = mock_result

        output_file = layout_file.parent / "symbol.json"

        result = cli_runner.invoke(
            app, ["layout", "export", str(layout_file), "Symbol", str(output_file)]
        )

        assert result.exit_code == 0
        assert "Layer exported successfully" in result.output
        mock_layout_layer_service.export_layer.assert_called_once_with(
            layout_file=layout_file,
            layer_name="Symbol",
            output=output_file,
            format_type="bindings",
            force=False,
        )

    def test_export_command_different_formats(
        self, cli_runner, layout_file, mock_layout_layer_service
    ):
        """Test exporting layer in different formats."""
        formats = ["bindings", "layer", "full"]

        for format_type in formats:
            mock_result = {
                "source_file": layout_file,
                "layer_name": "Symbol",
                "output_file": layout_file.parent / f"symbol_{format_type}.json",
                "format": format_type,
                "binding_count": 2,
            }
            mock_layout_layer_service.export_layer.return_value = mock_result

            output_file = layout_file.parent / f"symbol_{format_type}.json"

            result = cli_runner.invoke(
                app,
                [
                    "layout",
                    "export",
                    str(layout_file),
                    "Symbol",
                    str(output_file),
                    "--format",
                    format_type,
                ],
            )

            assert result.exit_code == 0
            assert "Layer exported successfully" in result.output

    def test_import_command_basic(
        self, cli_runner, layout_file, mock_layout_layer_service
    ):
        """Test basic import functionality."""
        mock_result = {
            "output_path": layout_file.parent / "modified_layout.json",
            "position": 2,
        }
        mock_layout_layer_service.add_layer.return_value = mock_result

        source_file = layout_file.parent / "source.json"

        result = cli_runner.invoke(
            app,
            [
                "layout",
                "import",
                str(layout_file),
                "--add-from",
                f"{source_file}:Gaming",
            ],
        )

        assert result.exit_code == 0
        assert "Layout import completed" in result.output

    def test_import_command_multiple_sources(
        self, cli_runner, layout_file, mock_layout_layer_service
    ):
        """Test importing from multiple sources."""
        mock_result = {
            "output_path": layout_file.parent / "modified_layout.json",
            "position": 2,
        }
        mock_layout_layer_service.add_layer.return_value = mock_result

        source1 = layout_file.parent / "source1.json"
        source2 = layout_file.parent / "source2.json"

        result = cli_runner.invoke(
            app,
            [
                "layout",
                "import",
                str(layout_file),
                "--add-from",
                f"{source1}:Gaming",
                "--add-from",
                f"{source2}:Navigation",
            ],
        )

        assert result.exit_code == 0
        assert "Layout import completed" in result.output
        assert mock_layout_layer_service.add_layer.call_count == 2


class TestLayoutVersions:
    """Test version management subcommand group."""

    def test_versions_import_master(
        self, cli_runner, layout_file, mock_version_manager
    ):
        """Test importing a master version."""
        mock_result = {
            "keyboard": "glove80",
            "title": "Glorious v42",
            "path": "/home/user/.glovebox/masters/glove80/v42.json",
        }
        mock_version_manager.import_master.return_value = mock_result

        result = cli_runner.invoke(
            app, ["layout", "versions", "import", str(layout_file), "v42"]
        )

        assert result.exit_code == 0
        assert "Imported master version 'v42' for glove80" in result.output
        assert "Title: Glorious v42" in result.output
        mock_version_manager.import_master.assert_called_once_with(
            layout_file, "v42", False
        )

    def test_versions_import_master_force(
        self, cli_runner, layout_file, mock_version_manager
    ):
        """Test importing a master version with force flag."""
        mock_result = {
            "keyboard": "glove80",
            "title": "Glorious v42",
            "path": "/home/user/.glovebox/masters/glove80/v42.json",
        }
        mock_version_manager.import_master.return_value = mock_result

        result = cli_runner.invoke(
            app, ["layout", "versions", "import", str(layout_file), "v42", "--force"]
        )

        assert result.exit_code == 0
        assert "Imported master version 'v42' for glove80" in result.output
        mock_version_manager.import_master.assert_called_once_with(
            layout_file, "v42", True
        )

    def test_versions_list_specific_keyboard(self, cli_runner, mock_version_manager):
        """Test listing master versions for specific keyboard."""
        mock_masters = [
            {"name": "v41", "title": "Glorious v41", "date": "2025-01-01T10:00:00"},
            {"name": "v42", "title": "Glorious v42", "date": "2025-01-15T15:00:00"},
        ]
        mock_version_manager.list_masters.return_value = mock_masters

        result = cli_runner.invoke(app, ["layout", "versions", "list", "glove80"])

        assert result.exit_code == 0
        assert "Master versions for glove80:" in result.output
        assert "v41 - Glorious v41 (2025-01-01)" in result.output
        assert "v42 - Glorious v42 (2025-01-15)" in result.output
        mock_version_manager.list_masters.assert_called_once_with("glove80")

    def test_versions_list_no_masters(self, cli_runner, mock_version_manager):
        """Test listing when no masters exist."""
        mock_version_manager.list_masters.return_value = []

        result = cli_runner.invoke(app, ["layout", "versions", "list", "glove80"])

        assert result.exit_code == 0
        assert "No master versions found for keyboard 'glove80'" in result.output
        assert (
            "Import a master version with: glovebox layout versions import"
            in result.output
        )

    def test_versions_list_all_keyboards(self, cli_runner, mock_version_manager):
        """Test listing all keyboards (placeholder functionality)."""
        result = cli_runner.invoke(app, ["layout", "versions", "list"])

        assert result.exit_code == 0
        assert "No master versions found" in result.output

    def test_versions_show_placeholder(self, cli_runner, mock_version_manager):
        """Test show version command (placeholder functionality)."""
        result = cli_runner.invoke(
            app, ["layout", "versions", "show", "glove80", "v42"]
        )

        assert result.exit_code == 1
        assert "Master version 'v42' not found for keyboard 'glove80'" in result.output
        assert "get_master_info method needs to be implemented" in result.output

    def test_versions_remove_placeholder(self, cli_runner, mock_version_manager):
        """Test remove version command (placeholder functionality)."""
        result = cli_runner.invoke(
            app, ["layout", "versions", "remove", "glove80", "v42"]
        )

        assert result.exit_code == 1
        assert "Master version 'v42' not found for keyboard 'glove80'" in result.output
        assert (
            "get_master_info and remove_master methods need to be implemented"
            in result.output
        )


class TestLayoutUpgrade:
    """Test layout upgrade command."""

    def test_upgrade_command_success(
        self, cli_runner, layout_file, mock_version_manager
    ):
        """Test successful layout upgrade."""
        mock_result = {
            "from_version": "v41",
            "to_version": "v42",
            "output_path": layout_file.parent / "upgraded_layout.json",
            "preserved_customizations": {
                "custom_layers": ["Gaming", "Navigation"],
                "custom_behaviors": ["custom_tap_hold"],
                "custom_config": ["debug_mode"],
            },
        }
        mock_version_manager.upgrade_layout.return_value = mock_result

        result = cli_runner.invoke(
            app, ["layout", "upgrade", str(layout_file), "--to", "v42"]
        )

        assert result.exit_code == 0
        assert "Upgraded layout from v41 to v42" in result.output
        assert "Preserved custom layers: Gaming, Navigation" in result.output
        assert "Preserved behaviors: custom_tap_hold" in result.output
        assert "Preserved config: debug_mode" in result.output
        mock_version_manager.upgrade_layout.assert_called_once_with(
            layout_file, "v42", None, "preserve-custom", None
        )

    def test_upgrade_command_with_options(
        self, cli_runner, layout_file, mock_version_manager
    ):
        """Test upgrade command with all options."""
        mock_result = {
            "from_version": "v41",
            "to_version": "v42",
            "output_path": layout_file.parent / "custom_output.json",
            "preserved_customizations": {
                "custom_layers": [],
                "custom_behaviors": [],
                "custom_config": [],
            },
        }
        mock_version_manager.upgrade_layout.return_value = mock_result

        output_file = layout_file.parent / "custom_output.json"

        result = cli_runner.invoke(
            app,
            [
                "layout",
                "upgrade",
                str(layout_file),
                "--to",
                "v42",
                "--from",
                "v41",
                "--output",
                str(output_file),
                "--strategy",
                "merge-conflicts",
            ],
        )

        assert result.exit_code == 0
        assert "Upgraded layout from v41 to v42" in result.output
        mock_version_manager.upgrade_layout.assert_called_once_with(
            layout_file, "v42", output_file, "merge-conflicts", "v41"
        )

    def test_upgrade_command_json_output(
        self, cli_runner, layout_file, mock_version_manager
    ):
        """Test upgrade command with JSON output."""
        mock_result = {
            "from_version": "v41",
            "to_version": "v42",
            "output_path": layout_file.parent / "upgraded_layout.json",
            "preserved_customizations": {
                "custom_layers": ["Gaming"],
                "custom_behaviors": [],
                "custom_config": [],
            },
        }
        mock_version_manager.upgrade_layout.return_value = mock_result

        result = cli_runner.invoke(
            app,
            [
                "layout",
                "upgrade",
                str(layout_file),
                "--to",
                "v42",
                "--output-format",
                "json",
            ],
        )

        assert result.exit_code == 0
        output_data = json.loads(result.output.strip())
        assert output_data["from_version"] == "v41"
        assert output_data["to_version"] == "v42"


class TestLayoutComparison:
    """Test layout comparison commands (diff, patch)."""

    def test_diff_command_basic(self, cli_runner, layout_file, tmp_path):
        """Test basic diff command."""
        # Create a second layout file
        layout2_file = tmp_path / "layout2.json"
        layout2_data = {
            "title": "Modified Layout",
            "description": "Modified test layout",
            "keyboard": "glove80",
            "version": "1.1",
            "layers": [
                {
                    "name": "Base",
                    "bindings": [
                        {"id": 0, "binding": "&kp A"},  # Changed from Q
                        {"id": 1, "binding": "&kp W"},
                    ],
                }
            ],
            "custom_defined_behaviors": [],
            "custom_code": "",
        }
        with layout2_file.open("w") as f:
            json.dump(layout2_data, f, indent=2)

        with patch(
            "glovebox.cli.commands.layout.comparison.create_layout_comparison_service"
        ) as mock_create:
            mock_service = Mock()
            mock_create.return_value = mock_service
            mock_service.compare_layouts.return_value = {
                "differences": [
                    {
                        "field": "title",
                        "before": "Test Layout",
                        "after": "Modified Layout",
                    },
                    {"field": "version", "before": "1.0", "after": "1.1"},
                ],
                "summary": "2 differences found",
            }

            result = cli_runner.invoke(
                app, ["layout", "diff", str(layout_file), str(layout2_file)]
            )

            assert result.exit_code == 0
            mock_service.compare_layouts.assert_called_once()

    def test_diff_command_with_patch_output(self, cli_runner, layout_file, tmp_path):
        """Test diff command with patch file output."""
        layout2_file = tmp_path / "layout2.json"
        patch_file = tmp_path / "changes.patch"

        # Create minimal second layout
        layout2_data = {"title": "Modified Layout"}
        with layout2_file.open("w") as f:
            json.dump(layout2_data, f, indent=2)

        with patch(
            "glovebox.cli.commands.layout.comparison.create_layout_comparison_service"
        ) as mock_create:
            mock_service = Mock()
            mock_create.return_value = mock_service
            mock_service.compare_layouts.return_value = {
                "differences": [
                    {
                        "field": "title",
                        "before": "Test Layout",
                        "after": "Modified Layout",
                    }
                ],
                "patch": {"title": "Modified Layout"},
            }

            result = cli_runner.invoke(
                app,
                [
                    "layout",
                    "diff",
                    str(layout_file),
                    str(layout2_file),
                    "--output-patch",
                    str(patch_file),
                ],
            )

            assert result.exit_code == 0
            mock_service.compare_layouts.assert_called_once()

    def test_patch_command(self, cli_runner, layout_file, tmp_path):
        """Test patch command."""
        patch_file = tmp_path / "changes.patch"
        patch_data = {"title": "Patched Layout"}
        with patch_file.open("w") as f:
            json.dump(patch_data, f, indent=2)

        with patch(
            "glovebox.cli.commands.layout.comparison.create_layout_comparison_service"
        ) as mock_create:
            mock_service = Mock()
            mock_create.return_value = mock_service
            mock_service.apply_patch.return_value = {
                "source": str(layout_file),
                "patch": str(patch_file),
                "output": str(layout_file.parent / "patched_layout.json"),
                "total_changes": 1,
            }

            result = cli_runner.invoke(
                app, ["layout", "patch", str(layout_file), str(patch_file)]
            )

            assert result.exit_code == 0
            mock_service.apply_patch.assert_called_once()


class TestLayoutCommandHelp:
    """Test help text and command discovery."""

    def test_layout_help(self, cli_runner):
        """Test main layout command help."""
        result = cli_runner.invoke(app, ["layout", "--help"])

        assert result.exit_code == 0
        assert "Layout management commands" in result.output
        assert "NEW COMMAND STRUCTURE" in result.output
        assert "Core Operations:" in result.output
        assert "compile" in result.output
        assert "validate" in result.output
        assert "show" in result.output
        assert "Unified Editing:" in result.output
        assert "edit" in result.output
        assert "File Operations:" in result.output
        assert "split" in result.output
        assert "merge" in result.output
        assert "export" in result.output
        assert "import" in result.output
        assert "Version Management:" in result.output
        assert "versions" in result.output
        assert "upgrade" in result.output
        assert "Comparison:" in result.output
        assert "diff" in result.output
        assert "patch" in result.output

    def test_edit_command_help(self, cli_runner):
        """Test edit command help."""
        result = cli_runner.invoke(app, ["layout", "edit", "--help"])

        assert result.exit_code == 0
        assert "Unified layout editing command" in result.output
        assert "Field Operations:" in result.output
        assert "Layer Operations:" in result.output
        assert "JSON Path Support:" in result.output
        assert "Batch Operations:" in result.output
        assert "--get" in result.output
        assert "--set" in result.output
        assert "--add-layer" in result.output
        assert "--remove-layer" in result.output
        assert "--move-layer" in result.output
        assert "--copy-layer" in result.output
        assert "--list-layers" in result.output

    def test_versions_subcommand_help(self, cli_runner):
        """Test versions subcommand help."""
        result = cli_runner.invoke(app, ["layout", "versions", "--help"])

        assert result.exit_code == 0
        assert "Layout version management commands" in result.output
        assert "import" in result.output
        assert "list" in result.output
        assert "show" in result.output
        assert "remove" in result.output

    def test_file_operations_help(self, cli_runner):
        """Test file operation commands help."""
        commands = ["split", "merge", "export", "import"]

        for cmd in commands:
            result = cli_runner.invoke(app, ["layout", cmd, "--help"])
            assert result.exit_code == 0
            assert cmd in result.output.lower()


class TestLayoutCommandValidation:
    """Test input validation and error handling."""

    def test_nonexistent_layout_file(self, cli_runner):
        """Test commands with nonexistent layout file."""
        result = cli_runner.invoke(
            app,
            [
                "layout",
                "compile",
                "/nonexistent/layout.json",
                "/tmp/output",
                "--profile",
                "glove80/v25.05",
            ],
        )

        assert result.exit_code == 1
        assert "Failed to compile layout" in result.output

    def test_missing_required_arguments(self, cli_runner):
        """Test commands with missing required arguments."""
        # Test compile without output directory
        result = cli_runner.invoke(app, ["layout", "compile"])
        assert result.exit_code == 2  # Typer error for missing arguments

        # Test edit without layout file
        result = cli_runner.invoke(app, ["layout", "edit"])
        assert result.exit_code == 2  # Typer error for missing arguments

    def test_invalid_profile_format(self, cli_runner, layout_file):
        """Test commands with invalid profile format."""
        result = cli_runner.invoke(
            app,
            [
                "layout",
                "compile",
                str(layout_file),
                "/tmp/output",
                "--profile",
                "invalid_format",
            ],
        )

        assert result.exit_code == 1
        assert "Keyboard configuration not found" in result.output
