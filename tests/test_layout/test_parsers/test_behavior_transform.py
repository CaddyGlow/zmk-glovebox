"""Tests for behavior reference transformation functionality."""

import pytest

from glovebox.layout.parsers.keymap_processors import TemplateAwareProcessor


class TestBehaviorTransformation:
    """Test behavior reference transformation from &name to proper definitions."""

    def test_transform_generic_behavior_references(self):
        """Test that generic behavior references get proper compatible strings."""
        processor = TemplateAwareProcessor()

        # Test generic behavior transformation
        dtsi_content_generic = """
&custom_behavior {
    some-property = <value>;
    another-property = "test";
};

&another_input_listener {
    layers = <1>;
};
"""

        result = processor._transform_behavior_references_to_definitions(
            dtsi_content_generic
        )

        # Should transform both behaviors with appropriate compatible strings
        assert "&custom_behavior" not in result
        assert "&another_input_listener" not in result

        # custom_behavior should get generic compatible
        assert "custom_behavior {" in result
        assert 'compatible = "zmk,behavior";' in result

        # another_input_listener should get input-listener compatible
        assert "another_input_listener {" in result
        assert 'compatible = "zmk,input-listener";' in result

    def test_transform_multiple_behavior_references(self):
        """Test transformation of multiple behavior references in one content."""
        processor = TemplateAwareProcessor()

        dtsi_content_multiple = """
&mmv_input_listener {
    LAYER_Mouse {
        layers = <15>;
    };
};

&msc_input_listener {
    LAYER_Mouse {
        layers = <15>;
    };
};

&custom_macro {
    bindings = <&kp A>, <&kp B>;
};
"""

        result = processor._transform_behavior_references_to_definitions(
            dtsi_content_multiple
        )

        # All references should be transformed
        assert "&mmv_input_listener" not in result
        assert "&msc_input_listener" not in result
        assert "&custom_macro" not in result

        # Should have proper definitions with compatible strings
        assert "mmv_input_listener {" in result
        assert "msc_input_listener {" in result
        assert "custom_macro {" in result

        # Input listeners should get input-listener compatible
        input_listener_sections = result.count('compatible = "zmk,input-listener";')
        assert input_listener_sections == 2

        # Generic behavior should get generic compatible
        generic_behavior_sections = result.count('compatible = "zmk,behavior";')
        assert generic_behavior_sections == 1

    def test_transform_preserves_nested_braces(self):
        """Test that transformation preserves nested brace structures."""
        processor = TemplateAwareProcessor()

        dtsi_content_nested = """
&complex_input_listener {
    LAYER_One {
        layers = <1>;
        nested_config {
            sub_property = <value>;
        };
    };
    LAYER_Two {
        layers = <2>;
    };
};
"""

        result = processor._transform_behavior_references_to_definitions(
            dtsi_content_nested
        )

        # Should preserve nested structure
        assert "LAYER_One {" in result
        assert "nested_config {" in result
        assert "sub_property = <value>;" in result
        assert "LAYER_Two {" in result

        # Should add compatible at the beginning
        assert 'compatible = "zmk,input-listener";' in result

        # Should transform reference to definition
        assert "&complex_input_listener" not in result
        assert "complex_input_listener {" in result

    def test_transform_empty_body(self):
        """Test transformation with empty or minimal body content."""
        processor = TemplateAwareProcessor()

        dtsi_content_empty = """
&simple_behavior {
};
"""

        result = processor._transform_behavior_references_to_definitions(
            dtsi_content_empty
        )

        # Should transform and add compatible
        assert "&simple_behavior" not in result
        assert "simple_behavior {" in result
        assert 'compatible = "zmk,behavior";' in result

    def test_transform_no_references(self):
        """Test that content without behavior references remains unchanged."""
        processor = TemplateAwareProcessor()

        dtsi_content_no_refs = """
/ {
    behaviors {
        my_behavior: my_behavior {
            compatible = "zmk,behavior-hold-tap";
            tapping-term-ms = <280>;
        };
    };
};
"""

        result = processor._transform_behavior_references_to_definitions(
            dtsi_content_no_refs
        )

        # Should remain unchanged (no behavior references to transform)
        assert result == dtsi_content_no_refs

    def test_transform_input_listener_detection(self):
        """Test that input listener detection works correctly."""
        processor = TemplateAwareProcessor()

        # Test various input listener patterns
        test_cases = [
            ("mmv_input_listener", True),
            ("msc_input_listener", True),
            ("custom_input_listener", True),
            ("xyz_input_listener", True),
            ("my_behavior", False),
            ("hold_tap_behavior", False),
            ("macro_def", False),
        ]

        for behavior_name, should_be_input_listener in test_cases:
            dtsi_content = f"""
&{behavior_name} {{
    some-property = <value>;
}};
"""

            result = processor._transform_behavior_references_to_definitions(
                dtsi_content
            )

            if should_be_input_listener:
                assert 'compatible = "zmk,input-listener";' in result, (
                    f"Failed for {behavior_name}: {result}"
                )
                assert 'compatible = "zmk,behavior";' not in result
            else:
                assert 'compatible = "zmk,behavior";' in result, (
                    f"Failed for {behavior_name}: {result}"
                )
                assert 'compatible = "zmk,input-listener";' not in result

    def test_transform_edge_case_input_listener(self):
        """Test the edge case - bare 'input_listener' name."""
        processor = TemplateAwareProcessor()

        dtsi_content = """
&input_listener {
    some-property = <value>;
};
"""

        result = processor._transform_behavior_references_to_definitions(dtsi_content)

        # 'input_listener' doesn't end with '_input_listener', so it should get generic compatible
        # This is actually correct behavior - the pattern is *_input_listener, not input_listener
        assert 'compatible = "zmk,behavior";' in result
        assert 'compatible = "zmk,input-listener";' not in result
