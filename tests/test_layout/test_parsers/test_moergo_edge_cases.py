"""Tests for MoErgo-specific edge case handling in parsers."""

from glovebox.layout.parsers.ast_behavior_converter import ASTBehaviorConverter
from glovebox.layout.parsers.keymap_parser import ZmkKeymapParser


class TestMoErgoEdgeCases:
    """Test MoErgo-specific edge case transformations in parsers."""

    def test_keymap_parser_sys_reset_transformation(self):
        """Test that &sys_reset gets transformed to &reset in keymap parser."""
        parser = ZmkKeymapParser()

        result = parser._preprocess_moergo_binding_edge_cases("&sys_reset")
        assert result == "&reset"

    def test_keymap_parser_sys_reset_no_transform_other_behaviors(self):
        """Test that other behaviors starting with &sys are not transformed."""
        parser = ZmkKeymapParser()

        # Should not transform other &sys behaviors
        result = parser._preprocess_moergo_binding_edge_cases("&sys_power_off")
        assert result == "&sys_power_off"

    def test_keymap_parser_magic_parameter_cleanup(self):
        """Test that &magic parameters get cleaned up correctly in keymap parser."""
        parser = ZmkKeymapParser()

        # Should clean up &magic with LAYER_ prefix and 0 parameter
        result = parser._preprocess_moergo_binding_edge_cases("&magic LAYER_Magic 0")
        assert result == "&magic"

    def test_keymap_parser_magic_different_parameters_no_cleanup(self):
        """Test that &magic with different parameters is not cleaned up."""
        parser = ZmkKeymapParser()

        # Should not clean up if not LAYER_ prefix
        result = parser._preprocess_moergo_binding_edge_cases("&magic OTHER_Magic 0")
        assert result == "&magic OTHER_Magic 0"

        # Should not clean up if not 0 parameter
        result = parser._preprocess_moergo_binding_edge_cases("&magic LAYER_Magic 1")
        assert result == "&magic LAYER_Magic 1"

        # Should not clean up if insufficient parameters
        result = parser._preprocess_moergo_binding_edge_cases("&magic LAYER_Magic")
        assert result == "&magic LAYER_Magic"

    def test_keymap_parser_normal_behaviors_unchanged(self):
        """Test that normal behaviors are not affected by preprocessing."""
        parser = ZmkKeymapParser()

        # Normal behaviors should pass through unchanged
        assert parser._preprocess_moergo_binding_edge_cases("&kp Q") == "&kp Q"
        assert (
            parser._preprocess_moergo_binding_edge_cases("&mt LCTRL A") == "&mt LCTRL A"
        )
        assert parser._preprocess_moergo_binding_edge_cases("&reset") == "&reset"

    def test_ast_behavior_converter_sys_reset_transformation(self):
        """Test that &sys_reset gets transformed to &reset in AST behavior converter."""
        converter = ASTBehaviorConverter()

        result = converter._preprocess_moergo_binding_edge_cases("&sys_reset")
        assert result == "&reset"

    def test_ast_behavior_converter_magic_parameter_cleanup(self):
        """Test that &magic parameters get cleaned up correctly in AST behavior converter."""
        converter = ASTBehaviorConverter()

        result = converter._preprocess_moergo_binding_edge_cases("&magic LAYER_Magic 0")
        assert result == "&magic"

    def test_ast_behavior_converter_normal_behaviors_unchanged(self):
        """Test that normal behaviors are not affected by preprocessing in AST converter."""
        converter = ASTBehaviorConverter()

        # Normal behaviors should pass through unchanged
        assert converter._preprocess_moergo_binding_edge_cases("&kp Q") == "&kp Q"
        assert (
            converter._preprocess_moergo_binding_edge_cases("&mt LCTRL A")
            == "&mt LCTRL A"
        )
        assert converter._preprocess_moergo_binding_edge_cases("&reset") == "&reset"

    def test_edge_case_transformations_logged(self):
        """Test that edge case transformations are properly logged."""
        from unittest.mock import Mock

        parser = ZmkKeymapParser()
        parser.logger = Mock()

        # Test &sys_reset transformation logging
        result = parser._preprocess_moergo_binding_edge_cases("&sys_reset")
        assert result == "&reset"
        parser.logger.debug.assert_called_with(
            "Transforming &sys_reset to &reset for MoErgo compatibility"
        )

        # Reset mock
        parser.logger.reset_mock()

        # Test &magic cleanup logging
        result = parser._preprocess_moergo_binding_edge_cases("&magic LAYER_Magic 0")
        assert result == "&magic"
        parser.logger.debug.assert_called_with(
            "Cleaning up &magic parameters for MoErgo compatibility: %s -> &magic",
            "&magic LAYER_Magic 0",
        )

    def test_multiple_edge_cases_in_sequence(self):
        """Test processing multiple edge cases in sequence."""
        parser = ZmkKeymapParser()

        # Test that each edge case is handled independently
        test_cases = [
            ("&sys_reset", "&reset"),
            ("&magic LAYER_Magic 0", "&magic"),
            ("&kp Q", "&kp Q"),  # Normal case
            ("&sys_reset", "&reset"),  # Repeat to ensure consistency
        ]

        for input_binding, expected_output in test_cases:
            result = parser._preprocess_moergo_binding_edge_cases(input_binding)
            assert result == expected_output, (
                f"Failed for input '{input_binding}': expected '{expected_output}', got '{result}'"
            )

    def test_empty_and_whitespace_input(self):
        """Test handling of empty and whitespace-only input."""
        parser = ZmkKeymapParser()

        # Empty string should remain empty
        assert parser._preprocess_moergo_binding_edge_cases("") == ""

        # Whitespace should be preserved
        assert parser._preprocess_moergo_binding_edge_cases("   ") == "   "

        # Leading/trailing whitespace with valid behavior
        assert (
            parser._preprocess_moergo_binding_edge_cases("  &sys_reset  ")
            == "  &sys_reset  "
        )
