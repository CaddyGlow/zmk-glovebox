"""Tests for the variable resolution system."""

import json
from pathlib import Path

import pytest

from glovebox.layout.utils.variable_resolver import (
    CircularReferenceError,
    InvalidVariableExpressionError,
    UndefinedVariableError,
    VariableError,
    VariableResolver,
)


class TestVariableResolver:
    """Test suite for the VariableResolver class."""

    def test_basic_substitution(self):
        """Test basic ${var} → value substitution."""
        variables = {"timing": 190, "flavor": "tap-preferred"}
        resolver = VariableResolver(variables)

        # Test string with single variable
        result = resolver._substitute_string("${timing}")
        assert result == 190

        # Test string with variable in text
        result = resolver._substitute_string("The timing is ${timing}ms")
        assert result == "The timing is 190ms"

        # Test string variable
        result = resolver._substitute_string("${flavor}")
        assert result == "tap-preferred"

    def test_default_value_fallback(self):
        """Test ${var:default} syntax."""
        variables = {"timing": 190}
        resolver = VariableResolver(variables)

        # Test variable with default when variable exists
        result = resolver._substitute_string("${timing:150}")
        assert result == 190

        # Test variable with default when variable doesn't exist
        result = resolver._substitute_string("${missing:150}")
        assert result == 150

        # Test string default
        result = resolver._substitute_string("${missing_flavor:balanced}")
        assert result == "balanced"

    def test_nested_object_resolution(self):
        """Test variables in nested objects."""
        variables = {"timing": 190, "flavor": "tap-preferred"}
        resolver = VariableResolver(variables)

        data = {
            "holdTaps": [
                {
                    "name": "&test_ht",
                    "tappingTermMs": "${timing}",
                    "flavor": "${flavor}",
                    "bindings": ["&kp", "&mo"],
                }
            ]
        }

        result = resolver.resolve_object(data)

        assert result["holdTaps"][0]["tappingTermMs"] == 190
        assert result["holdTaps"][0]["flavor"] == "tap-preferred"
        assert result["holdTaps"][0]["bindings"] == ["&kp", "&mo"]  # Unchanged

    def test_list_resolution(self):
        """Test variable resolution in lists."""
        variables = {"key1": "A", "key2": "B"}
        resolver = VariableResolver(variables)

        data = ["${key1}", "${key2}", "C"]
        result = resolver.resolve_value(data)

        assert result == ["A", "B", "C"]

    def test_type_coercion(self):
        """Test string → int/bool coercion."""
        resolver = VariableResolver({})

        # Test integer coercion
        assert resolver._coerce_type("123") == 123
        assert resolver._coerce_type("0") == 0

        # Test float coercion
        assert resolver._coerce_type("123.45") == 123.45

        # Test boolean coercion
        assert resolver._coerce_type("true") is True
        assert resolver._coerce_type("false") is False
        assert resolver._coerce_type("True") is True
        assert resolver._coerce_type("False") is False

        # Test string fallback
        assert resolver._coerce_type("hello") == "hello"
        assert resolver._coerce_type("not_a_number") == "not_a_number"

    def test_circular_reference_detection(self):
        """Test circular reference prevention."""
        variables = {
            "a": "${b}",
            "b": "${c}",
            "c": "${a}",  # Circular reference
        }
        resolver = VariableResolver(variables)

        with pytest.raises(CircularReferenceError, match="Circular reference detected"):
            resolver.resolve_value("${a}")

    def test_undefined_variable_error(self):
        """Test proper error for undefined variables."""
        variables = {"timing": 190}
        resolver = VariableResolver(variables)

        with pytest.raises(
            UndefinedVariableError, match="Variable 'missing' not found"
        ):
            resolver.resolve_value("${missing}")

    def test_nested_property_access(self):
        """Test ${nested.property} syntax."""
        variables = {"timing": {"fast": 130, "normal": 190, "slow": 250}}
        resolver = VariableResolver(variables)

        # Test nested access
        result = resolver._substitute_string("${timing.fast}")
        assert result == 130

        result = resolver._substitute_string("${timing.normal}")
        assert result == 190

        # Test missing nested property with default
        result = resolver._substitute_string("${timing.missing:200}")
        assert result == 200

    def test_multiple_variables_in_string(self):
        """Test multiple variable references in one string."""
        variables = {"fast": 130, "slow": 250}
        resolver = VariableResolver(variables)

        result = resolver._substitute_string("Fast: ${fast}ms, Slow: ${slow}ms")
        assert result == "Fast: 130ms, Slow: 250ms"

    def test_flatten_layout(self):
        """Test flattening removes variables section and resolves all references."""
        layout_data = {
            "keyboard": "test",
            "title": "Test Layout",
            "variables": {"timing": 190, "flavor": "tap-preferred"},
            "holdTaps": [
                {
                    "name": "&test_ht",
                    "tappingTermMs": "${timing}",
                    "flavor": "${flavor}",
                }
            ],
        }

        resolver = VariableResolver({"timing": 190, "flavor": "tap-preferred"})
        result = resolver.flatten_layout(layout_data)

        # Variables section should be removed
        assert "variables" not in result

        # Variables should be resolved
        assert result["holdTaps"][0]["tappingTermMs"] == 190
        assert result["holdTaps"][0]["flavor"] == "tap-preferred"

        # Other fields should be preserved
        assert result["keyboard"] == "test"
        assert result["title"] == "Test Layout"

    def test_flatten_layout_no_variables(self):
        """Test flattening layout with no variables."""
        layout_data = {"keyboard": "test", "title": "Test Layout", "holdTaps": []}

        resolver = VariableResolver({})
        result = resolver.flatten_layout(layout_data)

        # Should return copy of original data
        assert result == layout_data
        assert result is not layout_data  # Should be a copy

    def test_variable_usage_report(self):
        """Test getting a report of variable usage."""
        layout_data = {
            "variables": {"timing": 190, "flavor": "tap-preferred", "unused": "value"},
            "holdTaps": [
                {
                    "name": "&test_ht",
                    "tappingTermMs": "${timing}",
                    "flavor": "${flavor}",
                }
            ],
            "combos": [{"name": "test_combo", "timeoutMs": "${timing}"}],
        }

        resolver = VariableResolver(
            {"timing": 190, "flavor": "tap-preferred", "unused": "value"}
        )
        usage = resolver.get_variable_usage(layout_data)

        # timing should be used in 2 places
        assert "timing" in usage
        assert len(usage["timing"]) == 2
        assert any("holdTaps" in path for path in usage["timing"])
        assert any("combos" in path for path in usage["timing"])

        # flavor should be used in 1 place
        assert "flavor" in usage
        assert len(usage["flavor"]) == 1

        # unused should not appear in usage
        assert "unused" not in usage

    def test_validate_variables(self):
        """Test variable validation."""
        layout_data = {
            "variables": {"timing": 190, "unused": "value"},
            "holdTaps": [
                {
                    "name": "&test_ht",
                    "tappingTermMs": "${timing}",
                    "flavor": "${missing}",  # Undefined variable
                }
            ],
        }

        resolver = VariableResolver({"timing": 190, "unused": "value"})
        errors = resolver.validate_variables(layout_data)

        # Should have errors for undefined variable and unused variable
        assert len(errors) >= 1
        assert any("unused" in error for error in errors)

    def test_variable_resolution_with_recursive_values(self):
        """Test variable resolution where variable values contain other variables."""
        variables = {
            "base_timing": 200,
            "fast_timing": "${base_timing}",  # References another variable
            "display_text": "Timing: ${fast_timing}ms",
        }
        resolver = VariableResolver(variables)

        # Test recursive resolution
        result = resolver._substitute_string("${fast_timing}")
        assert result == 200

        result = resolver._substitute_string("${display_text}")
        assert result == "Timing: 200ms"

    def test_complex_data_structure_resolution(self):
        """Test resolution in complex nested data structures."""
        variables = {"timing": 190, "keys": ["A", "B", "C"], "positions": [0, 1, 2]}
        resolver = VariableResolver(variables)

        data = {
            "combos": [
                {
                    "name": "test_combo",
                    "timeoutMs": "${timing}",
                    "keyPositions": "${positions}",
                    "binding": {"value": "&kp", "params": [{"value": "${keys}"}]},
                }
            ]
        }

        result = resolver.resolve_object(data)

        assert result["combos"][0]["timeoutMs"] == 190
        assert result["combos"][0]["keyPositions"] == [0, 1, 2]
        assert result["combos"][0]["binding"]["params"][0]["value"] == ["A", "B", "C"]

    def test_edge_cases(self):
        """Test edge cases and error conditions."""
        variables = {"test": "value"}
        resolver = VariableResolver(variables)

        # Empty string
        assert resolver._substitute_string("") == ""

        # String without variables
        assert resolver._substitute_string("no variables here") == "no variables here"

        # Malformed variable syntax (missing closing brace)
        assert resolver._substitute_string("${incomplete") == "${incomplete"

        # Empty variable name
        assert resolver._substitute_string("${}") == "${}"

        # Variable name with spaces
        variables_with_spaces = {"my var": "value"}
        resolver_spaces = VariableResolver(variables_with_spaces)
        result = resolver_spaces._substitute_string("${my var}")
        assert result == "value"


class TestVariableResolverIntegration:
    """Integration tests for variable resolution with real layout data."""

    def test_holdtap_variable_integration(self):
        """Test variables in HoldTapBehavior integration."""
        layout_data = {
            "keyboard": "test",
            "title": "Test Layout",
            "variables": {
                "fast_timing": 130,
                "normal_timing": 190,
                "tap_flavor": "tap-preferred",
            },
            "holdTaps": [
                {
                    "name": "&fast_ht",
                    "tappingTermMs": "${fast_timing}",
                    "flavor": "${tap_flavor}",
                    "bindings": ["&kp", "&mo"],
                },
                {
                    "name": "&normal_ht",
                    "tappingTermMs": "${normal_timing}",
                    "flavor": "${tap_flavor}",
                    "bindings": ["&kp", "&sl"],
                },
            ],
        }

        resolver = VariableResolver(
            {
                "fast_timing": 130,
                "normal_timing": 190,
                "tap_flavor": "tap-preferred",
            }
        )
        result = resolver.resolve_object(layout_data)

        # Check that variables are resolved correctly
        assert result["holdTaps"][0]["tappingTermMs"] == 130
        assert result["holdTaps"][0]["flavor"] == "tap-preferred"
        assert result["holdTaps"][1]["tappingTermMs"] == 190
        assert result["holdTaps"][1]["flavor"] == "tap-preferred"

        # Check that non-variable fields are preserved
        assert result["holdTaps"][0]["bindings"] == ["&kp", "&mo"]
        assert result["holdTaps"][1]["bindings"] == ["&kp", "&sl"]

    def test_combo_variable_integration(self):
        """Test variables in ComboBehavior integration."""
        layout_data = {
            "variables": {"combo_timeout": 40, "esc_positions": [0, 1]},
            "combos": [
                {
                    "name": "esc_combo",
                    "timeoutMs": "${combo_timeout}",
                    "keyPositions": "${esc_positions}",
                    "binding": {"value": "&kp", "params": [{"value": "ESC"}]},
                }
            ],
        }

        resolver = VariableResolver({"combo_timeout": 40, "esc_positions": [0, 1]})
        result = resolver.resolve_object(layout_data)

        assert result["combos"][0]["timeoutMs"] == 40
        assert result["combos"][0]["keyPositions"] == [0, 1]
        assert result["combos"][0]["binding"]["value"] == "&kp"

    def test_macro_variable_integration(self):
        """Test variables in MacroBehavior integration."""
        layout_data = {
            "variables": {"macro_wait": 10, "macro_tap": 5},
            "macros": [
                {
                    "name": "test_macro",
                    "waitMs": "${macro_wait}",
                    "tapMs": "${macro_tap}",
                    "bindings": [
                        {"value": "&kp", "params": [{"value": "A"}]},
                        {"value": "&kp", "params": [{"value": "B"}]},
                    ],
                }
            ],
        }

        resolver = VariableResolver({"macro_wait": 10, "macro_tap": 5})
        result = resolver.resolve_object(layout_data)

        assert result["macros"][0]["waitMs"] == 10
        assert result["macros"][0]["tapMs"] == 5
        assert len(result["macros"][0]["bindings"]) == 2
