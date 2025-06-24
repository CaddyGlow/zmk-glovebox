"""Tests for variable preservation during edit operations and flattening during compilation.

This test file ensures that:
1. Variables are preserved during edit operations (no regression on flattening fix)
2. Variables are properly flattened during compilation operations
3. All edge cases are handled correctly
"""

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from glovebox.adapters import create_file_adapter
from glovebox.layout.editor import create_layout_editor_service
from glovebox.layout.layer import create_layout_layer_service
from glovebox.layout.models import LayoutData
from glovebox.layout.utils.json_operations import load_layout_file


class TestVariablePreservation:
    """Test variable preservation during edit operations."""

    @pytest.fixture
    def sample_layout_with_variables(self) -> dict[str, Any]:
        """Sample layout with variable references."""
        return {
            "keyboard": "test_keyboard",
            "title": "Test Variables Layout",
            "layer_names": ["base", "sym"],
            "layers": [
                [
                    {"value": "&kp", "params": [{"value": "Q"}]},
                    {"value": "&kp", "params": [{"value": "W"}]},
                    {"value": "&kp", "params": [{"value": "E"}]},
                ],
                [
                    {"value": "&kp", "params": [{"value": "1"}]},
                    {"value": "&kp", "params": [{"value": "2"}]},
                    {"value": "&kp", "params": [{"value": "3"}]},
                ],
            ],
            "variables": {
                "tapMs": 150,
                "holdMs": 200,
                "flavor": "tap-preferred",
                "quickTap": 100,
            },
            "hold_taps": [
                {
                    "name": "&ht_tap",
                    "tapping_term_ms": "${tapMs}",
                    "quick_tap_ms": "${quickTap}",
                    "flavor": "${flavor}",
                },
                {
                    "name": "&ht_hold",
                    "tapping_term_ms": "${holdMs}",
                    "quick_tap_ms": "${quickTap}",
                    "flavor": "${flavor}",
                },
            ],
            "behaviors": {
                "custom_tap": {
                    "type": "hold_tap",
                    "tapping_term_ms": "${tapMs}",
                    "flavor": "${flavor}",
                    "bindings": ["&kp", "&mo"],
                },
                "custom_hold": {
                    "type": "hold_tap",
                    "tapping_term_ms": "${holdMs}",
                    "flavor": "${flavor}",
                    "bindings": ["&kp", "&sl"],
                },
            },
            "combos": [
                {
                    "name": "esc_combo",
                    "timeout_ms": "${quickTap}",
                    "keyPositions": [0, 1],
                    "binding": {"value": "&kp", "params": [{"value": "ESC"}]},
                }
            ],
            "macros": [
                {
                    "name": "test_macro",
                    "wait_ms": "${quickTap}",
                    "tap_ms": "${tapMs}",
                    "bindings": [
                        {"value": "&kp", "params": [{"value": "A"}]},
                        {"value": "&kp", "params": [{"value": "B"}]},
                    ],
                }
            ],
        }

    @pytest.fixture
    def layout_file_with_variables(self, sample_layout_with_variables) -> Path:
        """Create a temporary layout file with variables."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(sample_layout_with_variables, f, indent=2)
            return Path(f.name)

    def test_load_layout_preserves_variables_with_skip_flag(
        self, layout_file_with_variables
    ):
        """Test that loading with skip_variable_resolution=True preserves variables."""
        file_adapter = create_file_adapter()

        # Load with variable resolution skipped (for editing)
        layout_data = load_layout_file(
            layout_file_with_variables, file_adapter, skip_variable_resolution=True
        )

        # Convert back to dict to check variables are preserved
        data = layout_data.model_dump(mode="json", by_alias=True, exclude_unset=True)

        # Variables section should exist and be preserved
        assert "variables" in data
        assert data["variables"]["tapMs"] == 150
        assert data["variables"]["holdMs"] == 200
        assert data["variables"]["flavor"] == "tap-preferred"

        # Variable references should be preserved (not resolved)
        assert data["hold_taps"][0]["tapping_term_ms"] == "${tapMs}"
        assert data["hold_taps"][0]["flavor"] == "${flavor}"
        assert data["hold_taps"][1]["tapping_term_ms"] == "${holdMs}"
        assert data["behaviors"]["custom_tap"]["tapping_term_ms"] == "${tapMs}"
        assert data["behaviors"]["custom_hold"]["tapping_term_ms"] == "${holdMs}"
        assert data["combos"][0]["timeout_ms"] == "${quickTap}"
        assert data["macros"][0]["wait_ms"] == "${quickTap}"

    def test_load_layout_resolves_variables_without_skip_flag(
        self, layout_file_with_variables
    ):
        """Test that loading without skip flag resolves variables (normal behavior)."""
        file_adapter = create_file_adapter()

        # Load with normal variable resolution (for display/compilation)
        layout_data = load_layout_file(layout_file_with_variables, file_adapter)

        # Convert back to dict to check variables are resolved
        data = layout_data.model_dump(mode="json", by_alias=True, exclude_unset=True)

        # Variables section should still exist
        assert "variables" in data
        assert data["variables"]["tapMs"] == 150

        # Variable references should be resolved to their values
        assert data["hold_taps"][0]["tapping_term_ms"] == 150  # ${tapMs} → 150
        assert (
            data["hold_taps"][0]["flavor"] == "tap-preferred"
        )  # ${flavor} → "tap-preferred"
        assert data["hold_taps"][1]["tapping_term_ms"] == 200  # ${holdMs} → 200
        assert data["behaviors"]["custom_tap"]["tapping_term_ms"] == 150
        assert data["behaviors"]["custom_hold"]["tapping_term_ms"] == 200
        assert data["combos"][0]["timeout_ms"] == 100  # ${quickTap} → 100
        assert data["macros"][0]["wait_ms"] == 100

    def test_editor_service_preserves_variables(self, layout_file_with_variables):
        """Test that editor service operations preserve variable references."""
        file_adapter = create_file_adapter()
        editor_service = create_layout_editor_service(file_adapter)

        # Create a temporary output file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            output_file = Path(f.name)

        try:
            # Set a new variable value
            result_path = editor_service.set_field_value(
                layout_file=layout_file_with_variables,
                field_path="variables.newVar",
                value="999",
                output=output_file,
                force=True,
            )

            # Read the result and verify variables are preserved
            content = file_adapter.read_text(result_path)
            data = json.loads(content)

            # New variable should be added
            assert data["variables"]["newVar"] == 999

            # Original variables should be preserved
            assert data["variables"]["tapMs"] == 150
            assert data["variables"]["holdMs"] == 200

            # Variable references should remain as references (not resolved)
            assert data["hold_taps"][0]["tapping_term_ms"] == "${tapMs}"
            assert data["hold_taps"][0]["flavor"] == "${flavor}"
            assert data["behaviors"]["custom_tap"]["tapping_term_ms"] == "${tapMs}"
            assert data["combos"][0]["timeout_ms"] == "${quickTap}"

        finally:
            # Cleanup
            if output_file.exists():
                output_file.unlink()

    def test_layer_service_preserves_variables(self, layout_file_with_variables):
        """Test that layer service operations preserve variable references."""
        file_adapter = create_file_adapter()
        layer_service = create_layout_layer_service(file_adapter)

        # Create a temporary output file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            output_file = Path(f.name)

        try:
            # Add a new layer
            result = layer_service.add_layer(
                layout_file=layout_file_with_variables,
                layer_name="gaming",
                output=output_file,
                force=True,
            )

            # Read the result and verify variables are preserved
            content = file_adapter.read_text(result["output_path"])
            data = json.loads(content)

            # New layer should be added
            assert "gaming" in data["layer_names"]
            assert len(data["layers"]) == 3  # base, sym, gaming

            # Variable references should remain as references (not resolved)
            assert data["hold_taps"][0]["tapping_term_ms"] == "${tapMs}"
            assert data["hold_taps"][0]["flavor"] == "${flavor}"
            assert data["behaviors"]["custom_tap"]["tapping_term_ms"] == "${tapMs}"
            assert data["combos"][0]["timeout_ms"] == "${quickTap}"

        finally:
            # Cleanup
            if output_file.exists():
                output_file.unlink()

    def test_multiple_edit_operations_preserve_variables(
        self, layout_file_with_variables
    ):
        """Test that multiple edit operations preserve variables correctly."""
        file_adapter = create_file_adapter()
        editor_service = create_layout_editor_service(file_adapter)

        # Create a temporary output file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            output_file = Path(f.name)

        try:
            # Perform multiple edit operations
            current_file = layout_file_with_variables

            # 1. Add a new variable
            current_file = editor_service.set_field_value(
                layout_file=current_file,
                field_path="variables.newTiming",
                value="250",
                output=output_file,
                force=True,
            )

            # 2. Modify an existing variable
            current_file = editor_service.set_field_value(
                layout_file=current_file,
                field_path="variables.tapMs",
                value="175",
                force=True,
            )

            # 3. Add a new behavior that uses variables
            current_file = editor_service.set_field_value(
                layout_file=current_file,
                field_path="behaviors.new_behavior",
                value='{"type": "hold_tap", "tapping_term_ms": "${newTiming}", "flavor": "${flavor}"}',
                value_type="json",
                force=True,
            )

            # Read final result and verify all variables are preserved
            content = file_adapter.read_text(current_file)
            data = json.loads(content)

            # Variables should be updated correctly
            assert data["variables"]["newTiming"] == 250
            assert data["variables"]["tapMs"] == 175  # Updated value
            assert data["variables"]["holdMs"] == 200  # Unchanged

            # All variable references should remain as references
            assert data["hold_taps"][0]["tapping_term_ms"] == "${tapMs}"
            assert data["hold_taps"][0]["flavor"] == "${flavor}"
            assert data["behaviors"]["custom_tap"]["tapping_term_ms"] == "${tapMs}"
            assert (
                data["behaviors"]["new_behavior"]["tapping_term_ms"] == "${newTiming}"
            )
            assert data["behaviors"]["new_behavior"]["flavor"] == "${flavor}"

        finally:
            # Cleanup
            if output_file.exists():
                output_file.unlink()


class TestVariableFlattening:
    """Test variable flattening during compilation operations."""

    @pytest.fixture
    def layout_data_with_variables(self) -> LayoutData:
        """Create LayoutData instance with variables for flattening tests."""
        data = {
            "keyboard": "test_keyboard",
            "title": "Test Layout",
            "layer_names": ["base"],
            "layers": [
                [
                    {"value": "&kp", "params": [{"value": "Q"}]},
                    {"value": "&kp", "params": [{"value": "W"}]},
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
                "custom_behavior": {
                    "type": "hold_tap",
                    "tapping_term_ms": "${tapMs}",
                    "flavor": "${flavor}",
                }
            },
        }

        # Load WITHOUT variable resolution to preserve variables
        from glovebox.layout.utils.json_operations import _skip_variable_resolution

        old_skip = _skip_variable_resolution
        from glovebox.layout.utils import json_operations

        json_operations._skip_variable_resolution = True

        try:
            return LayoutData.model_validate(data)
        finally:
            json_operations._skip_variable_resolution = old_skip

    def test_to_flattened_dict_resolves_variables(self, layout_data_with_variables):
        """Test that to_flattened_dict() resolves all variables and removes variables section."""
        flattened = layout_data_with_variables.to_flattened_dict()

        # Variables section should be removed
        assert "variables" not in flattened

        # All variable references should be resolved
        assert flattened["hold_taps"][0]["tapping_term_ms"] == 150  # ${tapMs} → 150
        assert flattened["hold_taps"][0]["quick_tap_ms"] == 200  # ${holdMs} → 200
        assert (
            flattened["hold_taps"][0]["flavor"] == "tap-preferred"
        )  # ${flavor} → "tap-preferred"

        assert flattened["behaviors"]["custom_behavior"]["tapping_term_ms"] == 150
        assert flattened["behaviors"]["custom_behavior"]["flavor"] == "tap-preferred"

        # Other fields should be preserved
        assert flattened["keyboard"] == "test_keyboard"
        assert flattened["title"] == "Test Layout"
        assert flattened["layer_names"] == ["base"]

    def test_to_flattened_dict_without_variables(self):
        """Test that to_flattened_dict() works correctly when no variables are present."""
        data = {
            "keyboard": "test_keyboard",
            "title": "Test Layout",
            "layer_names": ["base"],
            "layers": [
                [
                    {"value": "&kp", "params": [{"value": "Q"}]},
                    {"value": "&kp", "params": [{"value": "W"}]},
                ]
            ],
            "hold_taps": [
                {
                    "name": "&ht_test",
                    "tapping_term_ms": 150,  # Direct value, not variable
                    "flavor": "tap-preferred",
                }
            ],
        }

        layout_data = LayoutData.model_validate(data)
        flattened = layout_data.to_flattened_dict()

        # No variables section should exist
        assert "variables" not in flattened

        # Values should remain unchanged
        assert flattened["hold_taps"][0]["tapping_term_ms"] == 150
        assert flattened["hold_taps"][0]["flavor"] == "tap-preferred"

    def test_to_flattened_dict_with_complex_variables(self):
        """Test flattening with complex variable scenarios."""
        data = {
            "keyboard": "test_keyboard",
            "title": "Test Layout",
            "layer_names": ["base"],
            "layers": [[{"value": "&kp", "params": [{"value": "Q"}]}]],
            "variables": {
                "base_timing": 200,
                "fast_timing": "${base_timing}",  # Variable references another variable
                "display_text": "Timing: ${fast_timing}ms",  # String interpolation
                "positions": [0, 1, 2],  # Array value
                "config": {"timeout": "${base_timing}"},  # Object value
            },
            "combos": [
                {
                    "name": "test_combo",
                    "timeout_ms": "${fast_timing}",
                    "keyPositions": [
                        0,
                        1,
                        2,
                    ],  # Direct values to avoid validation issues
                    "binding": {"value": "&kp", "params": [{"value": "ESC"}]},
                }
            ],
            "behaviors": {
                "test_behavior": {
                    "type": "hold_tap",
                    "tapping_term_ms": "${config.timeout}",  # Nested property access
                    "flavor": "tap-preferred",
                }
            },
        }

        # Load without variable resolution to preserve the structure
        from glovebox.layout.utils.json_operations import _skip_variable_resolution

        old_skip = _skip_variable_resolution
        from glovebox.layout.utils import json_operations

        json_operations._skip_variable_resolution = True

        try:
            layout_data = LayoutData.model_validate(data)
        finally:
            json_operations._skip_variable_resolution = old_skip

        flattened = layout_data.to_flattened_dict()

        # Variables section should be removed
        assert "variables" not in flattened

        # Complex variable resolution should work
        assert (
            flattened["combos"][0]["timeout_ms"] == 200
        )  # ${fast_timing} → ${base_timing} → 200
        assert flattened["combos"][0]["keyPositions"] == [
            0,
            1,
            2,
        ]  # Direct values preserved
        assert (
            flattened["behaviors"]["test_behavior"]["tapping_term_ms"] == 200
        )  # Nested access

    def test_normal_model_dump_preserves_variables(self, layout_data_with_variables):
        """Test that normal model_dump preserves variables (not flattened)."""
        normal_dict = layout_data_with_variables.model_dump(
            mode="json", by_alias=True, exclude_unset=True
        )

        # Variables section should be present
        assert "variables" in normal_dict
        assert normal_dict["variables"]["tapMs"] == 150
        assert normal_dict["variables"]["holdMs"] == 200

        # Variable references should be preserved (not resolved)
        assert normal_dict["hold_taps"][0]["tapping_term_ms"] == "${tapMs}"
        assert normal_dict["hold_taps"][0]["flavor"] == "${flavor}"
        assert (
            normal_dict["behaviors"]["custom_behavior"]["tapping_term_ms"] == "${tapMs}"
        )


class TestVariableEdgeCases:
    """Test edge cases for variable preservation and flattening."""

    def test_empty_variables_section(self):
        """Test behavior with empty variables section."""
        data = {
            "keyboard": "test_keyboard",
            "title": "Test Layout",
            "layer_names": ["base"],
            "layers": [[{"value": "&kp", "params": [{"value": "Q"}]}]],
            "variables": {},  # Empty variables
            "hold_taps": [
                {
                    "name": "&ht_test",
                    "tapping_term_ms": 150,  # Direct value
                    "flavor": "tap-preferred",
                }
            ],
        }

        layout_data = LayoutData.model_validate(data)
        flattened = layout_data.to_flattened_dict()

        # Empty variables section should be removed
        assert "variables" not in flattened

        # Values should remain unchanged
        assert flattened["hold_taps"][0]["tapping_term_ms"] == 150

    def test_mixed_variable_and_direct_values(self):
        """Test layout with both variable references and direct values."""
        data = {
            "keyboard": "test_keyboard",
            "title": "Test Layout",
            "layer_names": ["base"],
            "layers": [[{"value": "&kp", "params": [{"value": "Q"}]}]],
            "variables": {"tapMs": 150, "flavor": "tap-preferred"},
            "hold_taps": [
                {
                    "name": "&ht_var",
                    "tapping_term_ms": "${tapMs}",  # Variable reference
                    "flavor": "${flavor}",  # Variable reference
                },
                {
                    "name": "&ht_direct",
                    "tapping_term_ms": 200,  # Direct value
                    "flavor": "balanced",  # Direct value
                },
            ],
        }

        # Load without variable resolution
        from glovebox.layout.utils.json_operations import _skip_variable_resolution

        old_skip = _skip_variable_resolution
        from glovebox.layout.utils import json_operations

        json_operations._skip_variable_resolution = True

        try:
            layout_data = LayoutData.model_validate(data)
        finally:
            json_operations._skip_variable_resolution = old_skip

        # Test normal dump preserves variables
        normal_dict = layout_data.model_dump(
            mode="json", by_alias=True, exclude_unset=True
        )
        assert normal_dict["hold_taps"][0]["tapping_term_ms"] == "${tapMs}"  # Preserved
        assert (
            normal_dict["hold_taps"][1]["tapping_term_ms"] == 200
        )  # Direct value unchanged

        # Test flattened resolves variables but keeps direct values
        flattened = layout_data.to_flattened_dict()
        assert "variables" not in flattened
        assert flattened["hold_taps"][0]["tapping_term_ms"] == 150  # Variable resolved
        assert (
            flattened["hold_taps"][0]["flavor"] == "tap-preferred"
        )  # Variable resolved
        assert (
            flattened["hold_taps"][1]["tapping_term_ms"] == 200
        )  # Direct value unchanged
        assert (
            flattened["hold_taps"][1]["flavor"] == "balanced"
        )  # Direct value unchanged

    def test_undefined_variable_in_flattening(self):
        """Test that flattening handles undefined variables gracefully."""
        data = {
            "keyboard": "test_keyboard",
            "title": "Test Layout",
            "layer_names": ["base"],
            "layers": [[{"value": "&kp", "params": [{"value": "Q"}]}]],
            "variables": {
                "tapMs": 150
                # Missing 'flavor' variable
            },
            "hold_taps": [
                {
                    "name": "&ht_test",
                    "tapping_term_ms": "${tapMs}",  # Defined variable
                    "flavor": "${undefined_flavor}",  # Undefined variable
                }
            ],
        }

        # Load without variable resolution
        from glovebox.layout.utils.json_operations import _skip_variable_resolution

        old_skip = _skip_variable_resolution
        from glovebox.layout.utils import json_operations

        json_operations._skip_variable_resolution = True

        try:
            layout_data = LayoutData.model_validate(data)
        finally:
            json_operations._skip_variable_resolution = old_skip

        # Flattening should handle undefined variables by raising an error
        # (this is the expected behavior for undefined variables)
        from glovebox.layout.utils.variable_resolver import UndefinedVariableError

        with pytest.raises(
            UndefinedVariableError, match="Variable 'undefined_flavor' not found"
        ):
            layout_data.to_flattened_dict()
