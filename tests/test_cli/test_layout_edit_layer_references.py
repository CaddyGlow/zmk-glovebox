"""Integration tests for layer reference handling in layout edit command."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from glovebox.cli import app
from glovebox.cli.commands import register_all_commands
from glovebox.layout.models import LayoutData
from glovebox.layout.utils.layer_references import find_layer_references


# Register commands with the app before running tests
register_all_commands(app)


@pytest.fixture
def cli_runner():
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def glove80_4layer_layout(tmp_path):
    """Create a test layout with 4 layers and various layer references."""
    layout_data = {
        "keyboard": "glove80",
        "title": "Test Layout with Layer References",
        "firmware_api_version": "1",
        "locale": "en-US",
        "creator": "Test Suite",
        "notes": "Test layout for layer reference handling",
        "version": "1.0.0",
        "layer_names": ["Base", "Navigation", "Numbers", "Symbols"],
        "config_parameters": [],
        "layers": [
            # Base layer with references to other layers
            [
                "&kp Q",
                "&kp W",
                "&kp E",
                "&kp R",
                "&kp T",
                "&mo 1",  # Momentary to Navigation
                "&lt 2 SPACE",  # Layer-tap to Numbers
                "&lt 3 ENTER",  # Layer-tap to Symbols
                "&mo 1",  # Another momentary to Navigation
                "&trans",
                "&trans",
                "&trans",
                "&trans",
                "&trans",
            ],
            # Navigation layer with layer switches
            [
                "&kp LEFT",
                "&kp DOWN",
                "&kp UP",
                "&kp RIGHT",
                "&trans",
                "&to 0",  # Back to Base
                "&tog 2",  # Toggle Numbers
                "&tog 3",  # Toggle Symbols
                "&trans",
                "&trans",
                "&trans",
                "&trans",
                "&trans",
                "&trans",
            ],
            # Numbers layer
            [
                "&kp N1",
                "&kp N2",
                "&kp N3",
                "&kp N4",
                "&kp N5",
                "&mo 3",  # Momentary to Symbols
                "&to 0",  # Back to Base
                "&trans",
                "&trans",
                "&trans",
                "&trans",
                "&trans",
                "&trans",
                "&trans",
            ],
            # Symbols layer
            [
                "&kp EXCL",
                "&kp AT",
                "&kp HASH",
                "&kp DOLLAR",
                "&kp PERCENT",
                "&to 0",  # Back to Base
                "&mo 1",  # Momentary to Navigation
                "&mo 2",  # Momentary to Numbers
                "&trans",
                "&trans",
                "&trans",
                "&trans",
                "&trans",
                "&trans",
            ],
        ],
        "holdTaps": [],
        "combos": [],
        "macros": [],
        "custom_defined_behaviors": "",
        "custom_devicetree": "",
    }

    layout_file = tmp_path / "test_layout.json"
    layout_file.write_text(json.dumps(layout_data, indent=2))
    return layout_file


class TestLayoutEditLayerReferences:
    """Test layer reference handling in layout edit operations."""

    def test_remove_layer_updates_references(self, cli_runner, glove80_4layer_layout):
        """Test that removing a layer updates all layer references correctly."""
        output_file = glove80_4layer_layout.parent / "output.json"

        # Remove Navigation layer (index 1)
        result = cli_runner.invoke(
            app,
            [
                "layout",
                "edit",
                str(glove80_4layer_layout),
                "--remove-layer",
                "Navigation",
                "--output",
                str(output_file),
            ],
        )

        assert result.exit_code == 0, f"Command failed with output: {result.output}"
        assert (
            "Warning: &mo in layer 'Base' references removed layer 1" in result.output
        )
        assert (
            "Warning: &mo in layer 'Symbols' references removed layer 1"
            in result.output
        )
        assert "Removed layers: Navigation" in result.output

        # Load the result and check references were updated
        with Path(output_file).open() as f:
            updated_data = json.load(f)

        layout = LayoutData.model_validate(updated_data)
        assert layout.layer_names == ["Base", "Numbers", "Symbols"]

        # Check that layer references were updated
        refs = find_layer_references(layout)
        ref_map = {(ref.layer_index, ref.binding_index): ref for ref in refs}

        # Base layer references should be updated
        # &lt 2 SPACE -> &lt 1 SPACE (Numbers moved from 2 to 1)
        base_lt_numbers = ref_map[(0, 6)]
        assert base_lt_numbers.behavior == "&lt"
        assert base_lt_numbers.layer_id == 1

        # &lt 3 ENTER -> &lt 2 ENTER (Symbols moved from 3 to 2)
        base_lt_symbols = ref_map[(0, 7)]
        assert base_lt_symbols.behavior == "&lt"
        assert base_lt_symbols.layer_id == 2

        # Numbers layer (now index 1) references
        # &mo 3 -> &mo 2 (Symbols moved from 3 to 2)
        numbers_mo_symbols = ref_map[(1, 5)]
        assert numbers_mo_symbols.behavior == "&mo"
        assert numbers_mo_symbols.layer_id == 2

    def test_add_layer_updates_references(self, cli_runner, glove80_4layer_layout):
        """Test that adding a layer updates references to layers after it."""
        output_file = glove80_4layer_layout.parent / "output.json"

        # First add a new layer at position 1
        result = cli_runner.invoke(
            app,
            [
                "layout",
                "edit",
                str(glove80_4layer_layout),
                "--add-layer",
                "Gaming",
                "--output",
                str(output_file),
            ],
        )

        assert result.exit_code == 0
        assert "Added layer 'Gaming'" in result.output

        # Load and check
        with Path(output_file).open() as f:
            data = json.load(f)
        layout = LayoutData.model_validate(data)

        assert layout.layer_names == [
            "Base",
            "Navigation",
            "Numbers",
            "Symbols",
            "Gaming",
        ]
        # References should not change when adding at the end

    def test_move_layer_updates_references(self, cli_runner, glove80_4layer_layout):
        """Test that moving a layer updates all affected references."""
        output_file = glove80_4layer_layout.parent / "output.json"

        # Move Numbers layer (index 2) to position 0
        result = cli_runner.invoke(
            app,
            [
                "layout",
                "edit",
                str(glove80_4layer_layout),
                "--move-layer",
                "Numbers:0",
                "--output",
                str(output_file),
            ],
        )

        assert result.exit_code == 0
        assert "Moved layer 'Numbers' from position 2 to 0" in result.output

        # Load and verify
        with Path(output_file).open() as f:
            data = json.load(f)
        layout = LayoutData.model_validate(data)

        assert layout.layer_names == ["Numbers", "Base", "Navigation", "Symbols"]

        # Check updated references
        refs = find_layer_references(layout)
        ref_map = {(ref.layer_index, ref.binding_index): ref for ref in refs}

        # Base layer (now index 1) references should be updated
        # &mo 1 -> &mo 2 (Navigation moved from 1 to 2)
        base_mo_nav = ref_map[(1, 5)]
        assert base_mo_nav.behavior == "&mo"
        assert base_mo_nav.layer_id == 2

        # &lt 2 SPACE -> &lt 0 SPACE (Numbers moved from 2 to 0)
        base_lt_numbers = ref_map[(1, 6)]
        assert base_lt_numbers.behavior == "&lt"
        assert base_lt_numbers.layer_id == 0

    def test_multiple_layer_operations(self, cli_runner, glove80_4layer_layout):
        """Test multiple layer operations in sequence."""
        # Remove two layers
        result = cli_runner.invoke(
            app,
            [
                "layout",
                "edit",
                str(glove80_4layer_layout),
                "--remove-layer",
                "Navigation",
                "--remove-layer",
                "Symbols",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        assert (
            "Warning:" in result.output
        )  # Should have warnings about removed references
        # Multiple remove operations log separately
        assert "Removed layers: Navigation" in result.output
        assert "Removed layers: Symbols" in result.output

    def test_remove_layer_by_index(self, cli_runner, glove80_4layer_layout):
        """Test removing layer by index updates references."""
        output_file = glove80_4layer_layout.parent / "output.json"

        # Remove layer at index 1 (Navigation)
        result = cli_runner.invoke(
            app,
            [
                "layout",
                "edit",
                str(glove80_4layer_layout),
                "--remove-layer",
                "1",
                "--output",
                str(output_file),
            ],
        )

        assert result.exit_code == 0
        assert "Removed layers: Navigation" in result.output

        # Verify references were updated
        with Path(output_file).open() as f:
            data = json.load(f)
        layout = LayoutData.model_validate(data)

        refs = find_layer_references(layout)
        # All references to layers > 1 should be decremented
        for ref in refs:
            if ref.behavior == "&lt" and ref.layer_index == 0:
                # Original &lt 2 and &lt 3 should now be &lt 1 and &lt 2
                assert ref.layer_id in [1, 2]

    def test_remove_layer_with_pattern(self, cli_runner, glove80_4layer_layout):
        """Test removing layers by pattern."""
        result = cli_runner.invoke(
            app,
            [
                "layout",
                "edit",
                str(glove80_4layer_layout),
                "--remove-layer",
                ".*tion",  # Matches Navigation
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        assert "Removed layers: Navigation" in result.output

    def test_layer_reference_preservation_with_variables(self, cli_runner, tmp_path):
        """Test that layer references work correctly with variable resolution disabled."""
        # Create layout with variables
        layout_data = {
            "keyboard": "glove80",
            "title": "Layout with Variables",
            "variables": {"layer_num": 2},
            "layer_names": ["Base", "Nav", "Num"],
            "layers": [
                ["&mo 1", "&lt ${layer_num} SPACE", "&trans"],
                ["&to 0", "&trans", "&trans"],
                ["&trans", "&trans", "&trans"],
            ],
        }

        layout_file = tmp_path / "var_layout.json"
        layout_file.write_text(json.dumps(layout_data))

        # Remove Nav layer
        output_file = tmp_path / "output.json"
        result = cli_runner.invoke(
            app,
            [
                "layout",
                "edit",
                str(layout_file),
                "--remove-layer",
                "Nav",
                "--output",
                str(output_file),
            ],
        )

        assert result.exit_code == 0

        # Check that variables are preserved
        with Path(output_file).open() as f:
            data = json.load(f)
        assert data["variables"]["layer_num"] == 2  # Variable unchanged

    def test_warnings_included_in_output(self, cli_runner, glove80_4layer_layout):
        """Test that warnings are properly displayed."""
        # Remove a layer that is referenced
        result = cli_runner.invoke(
            app,
            [
                "layout",
                "edit",
                str(glove80_4layer_layout),
                "--remove-layer",
                "Navigation",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        # Should have multiple warnings about removed layer references
        assert result.output.count("Warning:") >= 2
        assert "removed layer 1" in result.output

    def test_no_warnings_when_no_references(self, cli_runner, tmp_path):
        """Test that no warnings are shown when removed layer has no references."""
        # Create layout where no layer references the one being removed
        layout_data = {
            "keyboard": "test",
            "title": "Test",
            "layer_names": ["Base", "Unused", "Numbers"],
            "layers": [
                ["&mo 2", "&trans", "&trans"],  # References Numbers, not Unused
                ["&trans", "&trans", "&trans"],  # Unused layer
                ["&to 0", "&trans", "&trans"],  # References Base
            ],
        }

        layout_file = tmp_path / "test.json"
        layout_file.write_text(json.dumps(layout_data))

        result = cli_runner.invoke(
            app,
            [
                "layout",
                "edit",
                str(layout_file),
                "--remove-layer",
                "Unused",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        assert "Warning:" not in result.output
        assert "Removed layers: Unused" in result.output
