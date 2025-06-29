"""Test model converters, specifically macro parameter field extraction."""

import pytest

from glovebox.layout.models import MacroBehavior
from glovebox.layout.parsers import ast_nodes
from glovebox.layout.parsers.model_converters import MacroConverter


class TestMacroConverter:
    """Test MacroConverter functionality, especially params field extraction."""

    def test_macro_params_extraction_single_param(self):
        """Test params field extraction from #binding-cells = <1>."""
        # Create a mock DTNode with #binding-cells = <1>
        node = ast_nodes.DTNode(
            name="test_macro",
            line=1,
        )

        # Add #binding-cells property with value 1
        binding_cells_prop = ast_nodes.DTProperty(
            name="#binding-cells",
            value=ast_nodes.DTValue.integer(1, "1"),
            line=2,
        )
        node.add_property(binding_cells_prop)

        # Add label property for description
        label_prop = ast_nodes.DTProperty(
            name="label",
            value=ast_nodes.DTValue.string("TEST_MACRO", '"TEST_MACRO"'),
            line=3,
        )
        node.add_property(label_prop)

        # Convert to macro behavior
        converter = MacroConverter()
        macro = converter.convert(node)

        # Verify params field is correctly set
        assert isinstance(macro, MacroBehavior)
        assert macro.params == ["code"]
        assert macro.name == "&test_macro"
        assert macro.description == "TEST_MACRO"

    def test_macro_params_extraction_two_params(self):
        """Test params field extraction from #binding-cells = <2>."""
        # Create a mock DTNode with #binding-cells = <2>
        node = ast_nodes.DTNode(
            name="test_macro_two",
            line=1,
        )

        # Add #binding-cells property with value 2
        binding_cells_prop = ast_nodes.DTProperty(
            name="#binding-cells",
            value=ast_nodes.DTValue.integer(2, "2"),
            line=2,
        )
        node.add_property(binding_cells_prop)

        # Convert to macro behavior
        converter = MacroConverter()
        macro = converter.convert(node)

        # Verify params field is correctly set for 2 parameters
        assert isinstance(macro, MacroBehavior)
        assert macro.params == ["param1", "param2"]
        assert macro.name == "&test_macro_two"

    def test_macro_params_extraction_zero_params(self):
        """Test params field extraction from #binding-cells = <0>."""
        # Create a mock DTNode with #binding-cells = <0>
        node = ast_nodes.DTNode(
            name="test_macro_zero",
            line=1,
        )

        # Add #binding-cells property with value 0
        binding_cells_prop = ast_nodes.DTProperty(
            name="#binding-cells",
            value=ast_nodes.DTValue.integer(0, "0"),
            line=2,
        )
        node.add_property(binding_cells_prop)

        # Convert to macro behavior
        converter = MacroConverter()
        macro = converter.convert(node)

        # Verify params field is None for 0 parameters
        assert isinstance(macro, MacroBehavior)
        assert macro.params is None
        assert macro.name == "&test_macro_zero"

    def test_macro_params_extraction_no_binding_cells(self):
        """Test params field when #binding-cells property is missing."""
        # Create a mock DTNode without #binding-cells
        node = ast_nodes.DTNode(
            name="test_macro_no_cells",
            line=1,
        )

        # Convert to macro behavior
        converter = MacroConverter()
        macro = converter.convert(node)

        # Verify params field is None when #binding-cells is missing
        assert isinstance(macro, MacroBehavior)
        assert macro.params is None
        assert macro.name == "&test_macro_no_cells"

    def test_macro_params_extraction_higher_values(self):
        """Test params field extraction from #binding-cells with higher values."""
        # Create a mock DTNode with #binding-cells = <3>
        node = ast_nodes.DTNode(
            name="test_macro_three",
            line=1,
        )

        # Add #binding-cells property with value 3
        binding_cells_prop = ast_nodes.DTProperty(
            name="#binding-cells",
            value=ast_nodes.DTValue.integer(3, "3"),
            line=2,
        )
        node.add_property(binding_cells_prop)

        # Convert to macro behavior
        converter = MacroConverter()
        macro = converter.convert(node)

        # Current implementation treats higher values as unexpected and sets params to None
        # This tests the current behavior rather than ideal behavior
        assert isinstance(macro, MacroBehavior)
        assert macro.params is None  # Current behavior for unexpected values
        assert macro.name == "&test_macro_three"

    def test_macro_description_cleanup(self):
        """Test description cleanup removes ampersand prefix."""
        # Create a mock DTNode with label containing ampersand
        node = ast_nodes.DTNode(
            name="test_macro_desc",
            line=1,
        )

        # Add label property with ampersand prefix
        label_prop = ast_nodes.DTProperty(
            name="label",
            value=ast_nodes.DTValue.string("&TEST_MACRO_DESC", '"&TEST_MACRO_DESC"'),
            line=2,
        )
        node.add_property(label_prop)

        # Convert to macro behavior
        converter = MacroConverter()
        macro = converter.convert(node)

        # Verify description has ampersand removed
        assert isinstance(macro, MacroBehavior)
        assert macro.description == "TEST_MACRO_DESC"
        assert not macro.description.startswith("&")

    def test_macro_params_with_bindings(self):
        """Test params field extraction with actual macro bindings."""
        # Create a mock DTNode with both #binding-cells and bindings
        node = ast_nodes.DTNode(
            name="mod_tab_v1_TKZ",
            line=1,
        )

        # Add #binding-cells property with value 1
        binding_cells_prop = ast_nodes.DTProperty(
            name="#binding-cells",
            value=ast_nodes.DTValue.integer(1, "1"),
            line=2,
        )
        node.add_property(binding_cells_prop)

        # Add label property
        label_prop = ast_nodes.DTProperty(
            name="label",
            value=ast_nodes.DTValue.string("MOD_TAB_V1_TKZ", '"MOD_TAB_V1_TKZ"'),
            line=3,
        )
        node.add_property(label_prop)

        # Add bindings property with macro content
        bindings_prop = ast_nodes.DTProperty(
            name="bindings",
            value=ast_nodes.DTValue.array(
                ["&macro_press", "&kp", "LALT", "&macro_tap", "&kp", "TAB", "&macro_release", "&kp", "LALT"],
                "<&macro_press &kp LALT &macro_tap &kp TAB &macro_release &kp LALT>"
            ),
            line=4,
        )
        node.add_property(bindings_prop)

        # Convert to macro behavior
        converter = MacroConverter()
        macro = converter.convert(node)

        # Verify all fields are correctly set
        assert isinstance(macro, MacroBehavior)
        assert macro.params == ["code"]
        assert macro.name == "&mod_tab_v1_TKZ"
        assert macro.description == "MOD_TAB_V1_TKZ"
        assert len(macro.bindings) > 0  # Should have parsed bindings

    def test_macro_params_regression_test(self):
        """Regression test for the specific issue where params was missing."""
        # This test specifically recreates the bug scenario where
        # params: ["code"] was missing from macro output
        node = ast_nodes.DTNode(
            name="test_regression_macro",
            line=1,
        )

        # Add the exact properties that should produce params: ["code"]
        binding_cells_prop = ast_nodes.DTProperty(
            name="#binding-cells",
            value=ast_nodes.DTValue.integer(1, "1"),
            line=2,
        )
        node.add_property(binding_cells_prop)

        converter = MacroConverter()
        macro = converter.convert(node)

        # This is the critical assertion that was failing before the fix
        assert macro is not None, "macro should not be None"
        assert macro.params is not None, "params field should not be None"
        assert macro.params == ["code"], f"Expected ['code'], got {macro.params}"

        # Ensure it's a list of strings
        assert isinstance(macro.params, list)
        assert all(isinstance(param, str) for param in macro.params)

    def test_macro_params_edge_cases(self):
        """Test edge cases for params field extraction."""
        converter = MacroConverter()

        # Test with string value instead of number (should handle gracefully)
        node_str = ast_nodes.DTNode(
            name="test_string_cells",
            line=1,
        )

        binding_cells_str = ast_nodes.DTProperty(
            name="#binding-cells",
            value=ast_nodes.DTValue.string("1", '"1"'),
            line=2,
        )
        node_str.add_property(binding_cells_str)

        macro_str = converter.convert(node_str)
        # Should handle string "1" and convert to int 1
        assert macro_str is not None
        assert macro_str.params == ["code"]

        # Test with negative value (edge case)
        node_neg = ast_nodes.DTNode(
            name="test_negative_cells",
            line=1,
        )

        binding_cells_neg = ast_nodes.DTProperty(
            name="#binding-cells",
            value=ast_nodes.DTValue.integer(-1, "-1"),
            line=2,
        )
        node_neg.add_property(binding_cells_neg)

        macro_neg = converter.convert(node_neg)
        # Should handle negative gracefully (fallback to None)
        assert macro_neg is not None
        assert macro_neg.params is None
