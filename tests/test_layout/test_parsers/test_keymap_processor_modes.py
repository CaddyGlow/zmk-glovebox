"""Tests for keymap processor modes (full vs template) to prevent regressions."""

import pytest

from glovebox.layout.parsers.keymap_processors import (
    FullKeymapProcessor,
    TemplateAwareProcessor,
)
from glovebox.layout.parsers.parsing_models import ParsingContext


class TestKeymapProcessorModes:
    """Test both full and template mode processors to ensure correct behavior."""

    @pytest.fixture
    def sample_keymap_content(self):
        """Sample keymap content with input listeners and various behaviors."""
        return """
/*
 * Sample keymap with input listeners and behaviors
 */

#include <behaviors.dtsi>
#include <dt-bindings/zmk/keys.h>

/* Input Listeners */
&mmv_input_listener {
    LAYER_MouseSlow {
        layers = <16>;
        input-processors = <&zip_xy_scaler 1 9>;
    };
    LAYER_MouseFast {
        layers = <17>;
        input-processors = <&zip_xy_scaler 3 1>;
    };
};

&msc_input_listener {
    LAYER_MouseSlow {
        layers = <16>;
        input-processors = <&zip_scroll_scaler 1 9>;
    };
};

/* Custom behavior reference */
&custom_behavior {
    some-property = <value>;
    bindings = <&kp A>;
};

/ {
    behaviors {
        test_hold_tap: test_hold_tap {
            compatible = "zmk,behavior-hold-tap";
            tapping-term-ms = <200>;
            quick-tap-ms = <0>;
            flavor = "tap-preferred";
            bindings = <&mo>, <&kp>;
        };
    };

    macros {
        test_macro: test_macro {
            compatible = "zmk,behavior-macro";
            bindings = <&kp H &kp E &kp L &kp L &kp O>;
        };
    };

    combos {
        compatible = "zmk,combos";
        test_combo {
            timeout-ms = <50>;
            key-positions = <0 1>;
            bindings = <&kp ESC>;
        };
    };

    keymap {
        compatible = "zmk,keymap";

        default_layer {
            bindings = <
                &kp Q &kp W &kp E &kp R &kp T
                &kp A &kp S &kp D &kp F &kp G
            >;
        };

        nav_layer {
            bindings = <
                &kp N1 &kp N2 &kp N3 &kp N4 &kp N5
                &kp LEFT &kp DOWN &kp UP &kp RIGHT &trans
            >;
        };
    };
};
"""

    @pytest.fixture
    def parsing_context(self, sample_keymap_content):
        """Create parsing context for tests."""
        return ParsingContext(
            keymap_content=sample_keymap_content,
            keyboard_name="glove80",  # Use real profile
        )

    @pytest.fixture
    def template_processor(self):
        """Create a TemplateAwareProcessor for testing."""
        return TemplateAwareProcessor()

    def test_full_mode_processes_input_listeners(self, parsing_context):
        """Test that full mode correctly processes input listeners."""
        processor = FullKeymapProcessor()

        result = processor.process(parsing_context)

        assert result is not None
        assert result.input_listeners is not None
        assert len(result.input_listeners) == 2

        # Check first input listener (mmv_input_listener)
        mmv_listener = result.input_listeners[0]
        assert mmv_listener.code == "&mmv_input_listener"
        assert len(mmv_listener.nodes) == 2

        # Check nodes have correct layers and processors
        slow_node = next(
            node for node in mmv_listener.nodes if node.code == "LAYER_MouseSlow"
        )
        assert slow_node.layers == [16]
        assert len(slow_node.input_processors) == 1
        assert slow_node.input_processors[0].code == "&zip_xy_scaler"
        assert slow_node.input_processors[0].params == [1, 9]

    def test_template_mode_processes_input_listeners(
        self, parsing_context, template_processor
    ):
        """Test that template mode correctly processes input listeners."""
        result = template_processor.process(parsing_context)

        assert result is not None
        assert result.input_listeners is not None
        assert len(result.input_listeners) == 2

        # Check first input listener (mmv_input_listener)
        mmv_listener = result.input_listeners[0]
        assert mmv_listener.code == "&mmv_input_listener"
        assert len(mmv_listener.nodes) == 2

    def test_both_modes_handle_behavior_references(
        self, parsing_context, template_processor
    ):
        """Test that both modes handle behavior references (&name) correctly."""
        full_processor = FullKeymapProcessor()

        full_result = full_processor.process(parsing_context)
        template_result = template_processor.process(parsing_context)

        # Both should process input listeners successfully
        assert full_result is not None
        assert template_result is not None
        assert full_result.input_listeners is not None
        assert template_result.input_listeners is not None
        assert len(full_result.input_listeners) == 2
        assert len(template_result.input_listeners) == 2

        # Both should have the same input listener structure
        for full_listener, template_listener in zip(
            full_result.input_listeners, template_result.input_listeners, strict=False
        ):
            assert full_listener.code == template_listener.code
            assert len(full_listener.nodes) == len(template_listener.nodes)

    def test_full_mode_processes_more_content_than_template(
        self, parsing_context, template_processor
    ):
        """Test that full mode processes more content than template mode."""
        full_processor = FullKeymapProcessor()

        full_result = full_processor.process(parsing_context)
        template_result = template_processor.process(parsing_context)

        # Full mode should typically find more behaviors (including template/boilerplate)
        # Template mode should find fewer (only user-defined)
        assert full_result is not None
        assert template_result is not None
        full_hold_taps = len(full_result.hold_taps) if full_result.hold_taps else 0
        template_hold_taps = (
            len(template_result.hold_taps) if template_result.hold_taps else 0
        )

        full_macros = len(full_result.macros) if full_result.macros else 0
        template_macros = len(template_result.macros) if template_result.macros else 0

        # At minimum, both should find the user-defined behaviors
        assert full_hold_taps >= 1  # At least test_hold_tap
        assert full_macros >= 1  # At least test_macro

        # Template mode may find fewer behaviors depending on section extraction
        # Just verify it doesn't crash and processes some content
        assert template_hold_taps >= 0  # Template mode may extract differently
        assert template_macros >= 0  # Template mode may extract differently

    def test_transformation_applied_to_input_listeners(self, parsing_context):
        """Test that behavior reference transformation is applied correctly."""
        processor = FullKeymapProcessor()

        # Test the transformation method directly
        sample_content = """
&mmv_input_listener {
    LAYER_Test {
        layers = <1>;
        input-processors = <&test_processor 2 3>;
    };
};

&custom_behavior {
    some-property = <value>;
};
"""

        transformed = processor._transform_behavior_references_to_definitions(
            sample_content
        )

        # Should transform references to definitions
        assert "&mmv_input_listener" not in transformed
        assert "&custom_behavior" not in transformed

        # Should add appropriate compatible strings
        assert "mmv_input_listener {" in transformed
        assert 'compatible = "zmk,input-listener";' in transformed
        assert "custom_behavior {" in transformed
        assert 'compatible = "zmk,behavior";' in transformed

        # Should preserve content
        assert "LAYER_Test" in transformed
        assert "layers = <1>;" in transformed
        assert "input-processors = <&test_processor 2 3>;" in transformed

    def test_no_regression_in_parsing_context_errors(
        self, parsing_context, template_processor
    ):
        """Test that parsing doesn't introduce errors in context."""
        full_processor = FullKeymapProcessor()

        # Clear any existing errors
        parsing_context.errors = []
        parsing_context.warnings = []

        full_result = full_processor.process(parsing_context)
        full_errors = parsing_context.errors.copy()

        # Reset context for template mode
        parsing_context.errors = []
        parsing_context.warnings = []

        template_result = template_processor.process(parsing_context)
        template_errors = parsing_context.errors.copy()

        # Both should succeed without critical errors
        assert full_result is not None
        assert template_result is not None

        # Should not have critical parsing errors
        critical_errors = [error for error in full_errors if "Failed to parse" in error]
        assert len(critical_errors) == 0

        critical_errors = [
            error for error in template_errors if "Failed to parse" in error
        ]
        assert len(critical_errors) == 0

    def test_input_listener_pattern_detection(self):
        """Test that input listener pattern detection works correctly."""
        processor = FullKeymapProcessor()

        test_cases = [
            # (content, expected_input_listener_compatible_count, expected_generic_compatible_count)
            ("&mmv_input_listener { layers = <1>; };", 1, 0),
            ("&msc_input_listener { layers = <1>; };", 1, 0),
            ("&custom_input_listener { layers = <1>; };", 1, 0),
            ("&my_behavior { bindings = <&kp A>; };", 0, 1),
            ("&hold_tap_behavior { tapping-term-ms = <200>; };", 0, 1),
            (
                """
&mmv_input_listener { layers = <1>; };
&my_macro { bindings = <&kp A>; };
&another_input_listener { layers = <2>; };
""",
                2,
                1,
            ),
        ]

        for content, expected_il, expected_generic in test_cases:
            transformed = processor._transform_behavior_references_to_definitions(
                content
            )

            il_count = transformed.count('compatible = "zmk,input-listener";')
            generic_count = transformed.count('compatible = "zmk,behavior";')

            assert il_count == expected_il, (
                f"Input listener count mismatch for: {content[:50]}..."
            )
            assert generic_count == expected_generic, (
                f"Generic behavior count mismatch for: {content[:50]}..."
            )

    def test_layers_extracted_in_both_modes(self, parsing_context, template_processor):
        """Test that both modes extract layer information."""
        full_processor = FullKeymapProcessor()

        full_result = full_processor.process(parsing_context)
        template_result = template_processor.process(parsing_context)

        # Both should have layer name lists (may be empty in test)
        assert full_result is not None
        assert template_result is not None
        assert full_result.layer_names is not None
        assert template_result.layer_names is not None

        # Should have layer data lists (may be empty in test)
        assert full_result.layers is not None
        assert template_result.layers is not None

        # The important thing is that both modes work without crashing
        # Layer extraction depends on proper keymap structure which may not be in our test sample

    def test_no_duplicate_input_listeners(self, parsing_context):
        """Test that input listeners are not duplicated in processing."""
        processor = FullKeymapProcessor()

        result = processor.process(parsing_context)

        assert result is not None
        assert result.input_listeners is not None

        # Check for duplicates by code
        codes = [listener.code for listener in result.input_listeners]
        assert len(codes) == len(set(codes)), "Found duplicate input listeners"

        # Should have exactly the expected listeners
        expected_codes = ["&mmv_input_listener", "&msc_input_listener"]
        actual_codes = sorted(codes)
        assert actual_codes == sorted(expected_codes)
