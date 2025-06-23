"""Integration tests for variable resolution with LayoutData model."""

import json
from pathlib import Path

import pytest

from glovebox.layout.models import LayoutData
from glovebox.layout.utils.variable_resolver import UndefinedVariableError


class TestVariableLayoutDataIntegration:
    """Test variable resolution integration with LayoutData model."""

    def test_layout_data_variable_resolution(self):
        """Test that LayoutData resolves variables during model validation."""
        data = {
            "keyboard": "test",
            "title": "Test Layout",
            "variables": {"timing": 190, "flavor": "tap-preferred"},
            "holdTaps": [
                {
                    "name": "&test_ht",
                    "tappingTermMs": "${timing}",
                    "flavor": "${flavor}",
                    "bindings": ["&kp", "&mo"],
                }
            ],
        }

        # Create LayoutData - should resolve variables automatically
        layout = LayoutData.model_validate(data)

        # Variables should be resolved in the model
        assert layout.hold_taps[0].tapping_term_ms == 190
        assert layout.hold_taps[0].flavor == "tap-preferred"

        # Variables section should still be present
        assert layout.variables == {"timing": 190, "flavor": "tap-preferred"}

    def test_layout_data_flattening(self):
        """Test LayoutData.to_flattened_dict() method."""
        data = {
            "keyboard": "test",
            "title": "Test Layout",
            "variables": {"timing": 190, "flavor": "tap-preferred"},
            "holdTaps": [
                {
                    "name": "&test_ht",
                    "tappingTermMs": "${timing}",
                    "flavor": "${flavor}",
                    "bindings": ["&kp", "&mo"],
                }
            ],
        }

        layout = LayoutData.model_validate(data)
        flattened = layout.to_flattened_dict()

        # Variables section should be removed
        assert "variables" not in flattened

        # Variables should be resolved
        assert flattened["holdTaps"][0]["tappingTermMs"] == 190
        assert flattened["holdTaps"][0]["flavor"] == "tap-preferred"

        # Other fields should be preserved
        assert flattened["keyboard"] == "test"
        assert flattened["title"] == "Test Layout"

    def test_layout_data_no_variables(self):
        """Test LayoutData with no variables section."""
        data = {
            "keyboard": "test",
            "title": "Test Layout",
            "holdTaps": [
                {
                    "name": "&test_ht",
                    "tappingTermMs": 190,
                    "flavor": "tap-preferred",
                    "bindings": ["&kp", "&mo"],
                }
            ],
        }

        layout = LayoutData.model_validate(data)
        flattened = layout.to_flattened_dict()

        # Should work fine without variables
        assert flattened["holdTaps"][0]["tappingTermMs"] == 190
        assert flattened["holdTaps"][0]["flavor"] == "tap-preferred"
        assert "variables" not in flattened

    def test_layout_data_empty_variables(self):
        """Test LayoutData with empty variables section."""
        data = {
            "keyboard": "test",
            "title": "Test Layout",
            "variables": {},
            "holdTaps": [
                {
                    "name": "&test_ht",
                    "tappingTermMs": 190,
                    "flavor": "tap-preferred",
                    "bindings": ["&kp", "&mo"],
                }
            ],
        }

        layout = LayoutData.model_validate(data)
        flattened = layout.to_flattened_dict()

        # Should remove empty variables section
        assert "variables" not in flattened
        assert flattened["holdTaps"][0]["tappingTermMs"] == 190

    def test_layout_data_complex_variables(self):
        """Test LayoutData with complex variable structures."""
        data = {
            "keyboard": "test",
            "title": "Test Layout",
            "variables": {
                "timings": {"fast": 130, "normal": 190, "slow": 250},
                "common_bindings": ["&kp", "&mo"],
                "positions": [0, 1, 2, 3],
            },
            "holdTaps": [
                {
                    "name": "&fast_ht",
                    "tappingTermMs": "${timings.fast}",
                    "flavor": "tap-preferred",
                    "bindings": "${common_bindings}",
                }
            ],
            "combos": [
                {
                    "name": "test_combo",
                    "timeoutMs": "${timings.normal}",
                    "keyPositions": "${positions}",
                    "binding": {"value": "&kp", "params": [{"value": "ESC"}]},
                }
            ],
        }

        layout = LayoutData.model_validate(data)

        # Check that complex variables are resolved
        assert layout.hold_taps[0].tapping_term_ms == 130
        assert layout.hold_taps[0].bindings == ["&kp", "&mo"]
        assert layout.combos[0].timeout_ms == 190
        assert layout.combos[0].key_positions == [0, 1, 2, 3]

    def test_layout_data_variable_error_handling(self):
        """Test LayoutData handles variable resolution errors properly."""
        data = {
            "keyboard": "test",
            "title": "Test Layout",
            "variables": {"timing": 190},
            "holdTaps": [
                {
                    "name": "&test_ht",
                    "tappingTermMs": "${missing_variable}",  # Undefined
                    "flavor": "tap-preferred",
                    "bindings": ["&kp", "&mo"],
                }
            ],
        }

        # Should raise ValidationError because unresolved variable can't be parsed as int
        with pytest.raises(
            Exception
        ):  # Could be ValidationError or UndefinedVariableError
            LayoutData.model_validate(data)

    def test_layout_data_serialization_order(self):
        """Test that variables appear in correct order in serialized output."""
        data = {
            "keyboard": "test",
            "title": "Test Layout",
            "variables": {"timing": 190},
            "holdTaps": [],
        }

        layout = LayoutData.model_validate(data)
        serialized = layout.model_dump(mode="json", by_alias=True, exclude_unset=True)

        # Variables should appear in the correct position
        keys = list(serialized.keys())
        assert "variables" in keys
        # Variables should come after basic metadata but before behaviors
        variables_index = keys.index("variables")
        title_index = keys.index("title")
        holdtaps_index = keys.index("holdTaps") if "holdTaps" in keys else len(keys)

        assert title_index < variables_index < holdtaps_index

    def test_layout_data_recursive_variables(self):
        """Test LayoutData with variables that reference other variables."""
        data = {
            "keyboard": "test",
            "title": "Test Layout",
            "variables": {
                "base_timing": 200,
                "fast_timing": "${base_timing}",  # References base_timing
                "modifier": 10,
                "adjusted_timing": "${fast_timing}",  # References fast_timing which references base_timing
            },
            "holdTaps": [
                {
                    "name": "&test_ht",
                    "tappingTermMs": "${adjusted_timing}",
                    "flavor": "tap-preferred",
                    "bindings": ["&kp", "&mo"],
                }
            ],
        }

        layout = LayoutData.model_validate(data)

        # Should resolve the chain: adjusted_timing -> fast_timing -> base_timing -> 200
        assert layout.hold_taps[0].tapping_term_ms == 200

    def test_layout_data_default_values(self):
        """Test LayoutData with variable default values."""
        data = {
            "keyboard": "test",
            "title": "Test Layout",
            "variables": {"timing": 190},
            "holdTaps": [
                {
                    "name": "&test_ht",
                    "tappingTermMs": "${timing}",
                    "flavor": "${missing_flavor:tap-preferred}",  # Default value
                    "bindings": ["&kp", "&mo"],
                }
            ],
        }

        layout = LayoutData.model_validate(data)

        # Should use default value for missing variable
        assert layout.hold_taps[0].tapping_term_ms == 190
        assert layout.hold_taps[0].flavor == "tap-preferred"

    def test_layout_data_all_behavior_types(self):
        """Test variable resolution works with all behavior types."""
        data = {
            "keyboard": "test",
            "title": "Test Layout",
            "variables": {
                "timing": 190,
                "timeout": 40,
                "wait": 10,
                "tap": 5,
                "positions": [0, 1],
                "bindings": ["&kp", "&mo"],
            },
            "holdTaps": [
                {
                    "name": "&test_ht",
                    "tappingTermMs": "${timing}",
                    "flavor": "tap-preferred",
                    "bindings": "${bindings}",
                }
            ],
            "combos": [
                {
                    "name": "test_combo",
                    "timeoutMs": "${timeout}",
                    "keyPositions": "${positions}",
                    "binding": {"value": "&kp", "params": [{"value": "ESC"}]},
                }
            ],
            "macros": [
                {
                    "name": "test_macro",
                    "waitMs": "${wait}",
                    "tapMs": "${tap}",
                    "bindings": [{"value": "&kp", "params": [{"value": "A"}]}],
                }
            ],
            "inputListeners": [
                {
                    "code": "test_listener",
                    "inputProcessors": [
                        {"code": "test_processor", "params": ["${timing}"]}
                    ],
                }
            ],
        }

        layout = LayoutData.model_validate(data)

        # Test hold taps
        assert layout.hold_taps[0].tapping_term_ms == 190
        assert layout.hold_taps[0].bindings == ["&kp", "&mo"]

        # Test combos
        assert layout.combos[0].timeout_ms == 40
        assert layout.combos[0].key_positions == [0, 1]

        # Test macros
        assert layout.macros[0].wait_ms == 10
        assert layout.macros[0].tap_ms == 5

        # Test input listeners
        assert layout.input_listeners[0].input_processors[0].params == [190]
