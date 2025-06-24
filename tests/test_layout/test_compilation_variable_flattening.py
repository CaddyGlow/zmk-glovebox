"""Tests to ensure compilation properly flattens variables in JSON output.

This test file verifies that:
1. Layout compilation flattens variables when generating JSON files
2. The to_flattened_dict() method is used correctly during compilation
3. Compiled JSON files don't contain variable references
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.adapters import create_file_adapter
from glovebox.layout import create_layout_service
from glovebox.layout.models import LayoutData


class TestCompilationVariableFlattening:
    """Test that compilation properly flattens variables in JSON output."""

    @pytest.fixture
    def sample_layout_with_variables(self) -> dict:
        """Sample layout with variables that should be flattened during compilation."""
        return {
            "keyboard": "test_keyboard",
            "title": "Compilation Test Layout",
            "layer_names": ["base", "sym"],
            "layers": [
                [{"value": "&kp", "params": [{"value": "Q"}]}, {"value": "&kp", "params": [{"value": "W"}]}, {"value": "&kp", "params": [{"value": "E"}]}],
                [{"value": "&kp", "params": [{"value": "1"}]}, {"value": "&kp", "params": [{"value": "2"}]}, {"value": "&kp", "params": [{"value": "3"}]}]
            ],
            "variables": {
                "tapMs": 150,
                "holdMs": 200,
                "flavor": "tap-preferred",
                "quickTap": 100
            },
            "hold_taps": [
                {
                    "name": "&ht_tap",
                    "tapping_term_ms": "${tapMs}",
                    "quick_tap_ms": "${quickTap}",
                    "flavor": "${flavor}"
                },
                {
                    "name": "&ht_hold",
                    "tapping_term_ms": "${holdMs}",
                    "quick_tap_ms": "${quickTap}",
                    "flavor": "${flavor}"
                }
            ],
            "behaviors": {
                "custom_tap": {
                    "type": "hold_tap",
                    "tapping_term_ms": "${tapMs}",
                    "flavor": "${flavor}",
                    "bindings": ["&kp", "&mo"]
                }
            },
            "combos": [
                {
                    "name": "esc_combo",
                    "timeout_ms": "${quickTap}",
                    "keyPositions": [0, 1],
                    "binding": {"value": "&kp", "params": [{"value": "ESC"}]}
                }
            ],
            "macros": [
                {
                    "name": "test_macro",
                    "wait_ms": "${quickTap}",
                    "tap_ms": "${tapMs}",
                    "bindings": [{"value": "&kp", "params": [{"value": "A"}]}, {"value": "&kp", "params": [{"value": "B"}]}]
                }
            ]
        }

    @pytest.fixture
    def layout_file_with_variables(self, sample_layout_with_variables) -> Path:
        """Create a temporary layout file with variables."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_layout_with_variables, f, indent=2)
            return Path(f.name)

    def test_to_flattened_dict_removes_variables_section(self, sample_layout_with_variables):
        """Test that to_flattened_dict() removes the variables section."""
        # Load the layout with variables preserved (skip resolution)
        from glovebox.layout.utils.json_operations import _skip_variable_resolution
        old_skip = _skip_variable_resolution
        from glovebox.layout.utils import json_operations
        json_operations._skip_variable_resolution = True

        try:
            layout_data = LayoutData.model_validate(sample_layout_with_variables)
        finally:
            json_operations._skip_variable_resolution = old_skip

        # Get flattened version (for compilation)
        flattened = layout_data.to_flattened_dict()

        # Variables section should be completely removed
        assert "variables" not in flattened, "Variables section should be removed in flattened output"

        # All variable references should be resolved to their values
        assert flattened["hold_taps"][0]["tapping_term_ms"] == 150  # ${tapMs} → 150
        assert flattened["hold_taps"][0]["quick_tap_ms"] == 100     # ${quickTap} → 100
        assert flattened["hold_taps"][0]["flavor"] == "tap-preferred"  # ${flavor} → "tap-preferred"

        assert flattened["hold_taps"][1]["tapping_term_ms"] == 200  # ${holdMs} → 200
        assert flattened["hold_taps"][1]["quick_tap_ms"] == 100
        assert flattened["hold_taps"][1]["flavor"] == "tap-preferred"

        assert flattened["behaviors"]["custom_tap"]["tapping_term_ms"] == 150
        assert flattened["behaviors"]["custom_tap"]["flavor"] == "tap-preferred"

        assert flattened["combos"][0]["timeout_ms"] == 100
        assert flattened["macros"][0]["wait_ms"] == 100
        assert flattened["macros"][0]["tap_ms"] == 150

    def test_compilation_uses_flattened_dict(self, sample_layout_with_variables):
        """Test that layout compilation should use flattened dict for JSON output.

        This test demonstrates the intended behavior - to_flattened_dict() should
        be used by compilation processes to ensure variables are resolved.
        """
        # Load the layout with variables preserved
        from glovebox.layout.utils.json_operations import _skip_variable_resolution
        old_skip = _skip_variable_resolution
        from glovebox.layout.utils import json_operations
        json_operations._skip_variable_resolution = True

        try:
            layout_data = LayoutData.model_validate(sample_layout_with_variables)
        finally:
            json_operations._skip_variable_resolution = old_skip

        # Simulate what compilation should do - use to_flattened_dict()
        flattened_for_compilation = layout_data.to_flattened_dict()

        # Verify that flattened version has no variables section
        assert "variables" not in flattened_for_compilation

        # Verify that all variable references are resolved
        assert flattened_for_compilation["hold_taps"][0]["tapping_term_ms"] == 150
        assert flattened_for_compilation["hold_taps"][0]["flavor"] == "tap-preferred"
        assert flattened_for_compilation["behaviors"]["custom_tap"]["tapping_term_ms"] == 150

        # Verify JSON serialization works properly
        json_output = json.dumps(flattened_for_compilation, indent=2)
        assert "${" not in json_output  # No variable references in JSON

    def test_json_output_has_no_variable_references(self, sample_layout_with_variables):
        """Test that JSON output from compilation contains no variable references."""
        # Load the layout with variables preserved
        from glovebox.layout.utils.json_operations import _skip_variable_resolution
        old_skip = _skip_variable_resolution
        from glovebox.layout.utils import json_operations
        json_operations._skip_variable_resolution = True

        try:
            layout_data = LayoutData.model_validate(sample_layout_with_variables)
        finally:
            json_operations._skip_variable_resolution = old_skip

        # Get flattened version (simulating compilation output)
        flattened = layout_data.to_flattened_dict()

        # Convert to JSON string and parse back to verify no variable references remain
        json_str = json.dumps(flattened, indent=2)

        # Verify no variable reference syntax remains in the JSON
        assert "${" not in json_str, "Flattened JSON should not contain variable references"

        # Parse back and verify all values are resolved
        parsed = json.loads(json_str)

        # All timing values should be numbers, not variable references
        for hold_tap in parsed["hold_taps"]:
            assert isinstance(hold_tap["tapping_term_ms"], int)
            assert isinstance(hold_tap["quick_tap_ms"], int)
            assert isinstance(hold_tap["flavor"], str)
            assert not hold_tap["flavor"].startswith("${")

    def test_flattening_preserves_non_variable_fields(self, sample_layout_with_variables):
        """Test that flattening preserves all non-variable fields correctly."""
        # Load the layout with variables preserved
        from glovebox.layout.utils.json_operations import _skip_variable_resolution
        old_skip = _skip_variable_resolution
        from glovebox.layout.utils import json_operations
        json_operations._skip_variable_resolution = True

        try:
            layout_data = LayoutData.model_validate(sample_layout_with_variables)
        finally:
            json_operations._skip_variable_resolution = old_skip

        # Get flattened version
        flattened = layout_data.to_flattened_dict()

        # Core layout fields should be preserved
        assert flattened["keyboard"] == "test_keyboard"
        assert flattened["title"] == "Compilation Test Layout"
        assert flattened["layer_names"] == ["base", "sym"]
        assert flattened["layers"] == [
            [{"value": "&kp", "params": [{"value": "Q"}]}, {"value": "&kp", "params": [{"value": "W"}]}, {"value": "&kp", "params": [{"value": "E"}]}],
            [{"value": "&kp", "params": [{"value": "1"}]}, {"value": "&kp", "params": [{"value": "2"}]}, {"value": "&kp", "params": [{"value": "3"}]}]
        ]

        # Behavior structures should be preserved (only variable values resolved)
        assert len(flattened["hold_taps"]) == 2
        assert flattened["hold_taps"][0]["name"] == "&ht_tap"
        assert flattened["hold_taps"][1]["name"] == "&ht_hold"

        assert "custom_tap" in flattened["behaviors"]
        assert flattened["behaviors"]["custom_tap"]["type"] == "hold_tap"
        assert flattened["behaviors"]["custom_tap"]["bindings"] == ["&kp", "&mo"]

        assert len(flattened["combos"]) == 1
        assert flattened["combos"][0]["name"] == "esc_combo"
        assert flattened["combos"][0]["keyPositions"] == [0, 1]

        assert len(flattened["macros"]) == 1
        assert flattened["macros"][0]["name"] == "test_macro"
        assert len(flattened["macros"][0]["bindings"]) == 2

    def test_complex_variable_resolution_in_compilation(self):
        """Test compilation with complex variable scenarios."""
        complex_layout = {
            "keyboard": "test_keyboard",
            "title": "Complex Variables Test",
            "layer_names": ["base"],
            "layers": [[{"value": "&kp", "params": [{"value": "Q"}]}]],
            "variables": {
                "base_timing": 200,
                "fast_timing": "${base_timing}",  # Variable references another variable
                "display_text": "Timing: ${fast_timing}ms",  # String interpolation
                "positions": [0, 1, 2],  # Array value
                "config": {"timeout": "${base_timing}"}  # Object value
            },
            "combos": [
                {
                    "name": "test_combo",
                    "timeout_ms": "${fast_timing}",
                    "keyPositions": [0, 1, 2],  # Direct values to avoid validation issues
                    "binding": {"value": "&kp", "params": [{"value": "ESC"}]}
                }
            ],
            "behaviors": {
                "test_behavior": {
                    "type": "hold_tap",
                    "tapping_term_ms": "${config.timeout}",  # Nested property access
                    "flavor": "tap-preferred"
                }
            }
        }

        # Load with variables preserved
        from glovebox.layout.utils.json_operations import _skip_variable_resolution
        old_skip = _skip_variable_resolution
        from glovebox.layout.utils import json_operations
        json_operations._skip_variable_resolution = True

        try:
            layout_data = LayoutData.model_validate(complex_layout)
        finally:
            json_operations._skip_variable_resolution = old_skip

        # Get flattened version for compilation
        flattened = layout_data.to_flattened_dict()

        # Variables section should be removed
        assert "variables" not in flattened

        # Complex variable resolution should work correctly
        assert flattened["combos"][0]["timeout_ms"] == 200  # ${fast_timing} → ${base_timing} → 200
        assert flattened["combos"][0]["keyPositions"] == [0, 1, 2]  # Direct values preserved
        assert flattened["behaviors"]["test_behavior"]["tapping_term_ms"] == 200  # Nested access

        # Verify no variable syntax remains
        json_str = json.dumps(flattened)
        assert "${" not in json_str
        assert "base_timing" not in json_str
        assert "fast_timing" not in json_str

    def test_compilation_vs_editing_behavior_difference(self, layout_file_with_variables):
        """Test that compilation flattens variables while editing preserves them."""
        file_adapter = create_file_adapter()

        # 1. Load for editing (should preserve variables)
        from glovebox.layout.utils.json_operations import load_layout_file
        edit_layout = load_layout_file(layout_file_with_variables, file_adapter, skip_variable_resolution=True)
        edit_dict = edit_layout.model_dump(mode="json", by_alias=True, exclude_unset=True)

        # 2. Load for compilation (should allow variable resolution)
        compile_layout = load_layout_file(layout_file_with_variables, file_adapter, skip_variable_resolution=False)
        compile_dict = compile_layout.to_flattened_dict()

        # Edit version should preserve variable references
        assert "variables" in edit_dict
        assert edit_dict["hold_taps"][0]["tapping_term_ms"] == "${tapMs}"
        assert edit_dict["hold_taps"][0]["flavor"] == "${flavor}"

        # Compilation version should resolve variables and remove variables section
        assert "variables" not in compile_dict
        assert compile_dict["hold_taps"][0]["tapping_term_ms"] == 150  # Resolved
        assert compile_dict["hold_taps"][0]["flavor"] == "tap-preferred"  # Resolved

        # Both should have same core structure otherwise
        assert edit_dict["keyboard"] == compile_dict["keyboard"]
        assert edit_dict["title"] == compile_dict["title"]
        assert edit_dict["layer_names"] == compile_dict["layer_names"]
        assert edit_dict["layers"] == compile_dict["layers"]
