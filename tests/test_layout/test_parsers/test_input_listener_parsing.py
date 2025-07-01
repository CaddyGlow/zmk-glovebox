"""Tests for input listener parsing functionality."""

import pytest

from glovebox.layout.parsers.keymap_processors import TemplateAwareProcessor


class TestInputListenerParsing:
    """Test input listener parsing and conversion."""

    def test_input_listener_conversion(self):
        """Test that input listeners are correctly converted from AST to models."""
        from glovebox.layout.parsers.ast_behavior_converter import ASTBehaviorConverter
        from glovebox.layout.parsers.ast_nodes import (
            DTNode,
            DTProperty,
            DTValue,
            DTValueType,
        )

        converter = ASTBehaviorConverter()

        # Create a mock DTNode for input listener
        input_listener_node = DTNode(name="mmv_input_listener")

        # Create child nodes
        child_node1 = DTNode(name="LAYER_MouseSlow")

        # Add properties to child node
        layers_prop = DTProperty(name="layers")
        layers_prop.value = DTValue(type=DTValueType.ARRAY, value=[16])
        child_node1.properties["layers"] = layers_prop

        processors_prop = DTProperty(name="input-processors")
        processors_prop.value = DTValue(
            type=DTValueType.ARRAY, value=["&zip_xy_scaler", "1", "9"]
        )
        child_node1.properties["input-processors"] = processors_prop

        # Add child to parent
        input_listener_node.children["LAYER_MouseSlow"] = child_node1

        # Convert the node
        result = converter.convert_input_listener_node(input_listener_node)

        # Verify the result
        assert result is not None
        assert result.code == "&mmv_input_listener"
        assert len(result.nodes) == 1

        node = result.nodes[0]
        assert node.code == "LAYER_MouseSlow"
        assert node.description == "LAYER_MouseSlow"  # Default when no comments
        assert node.layers == [16]
        assert len(node.input_processors) == 1

        processor = node.input_processors[0]
        assert processor.code == "&zip_xy_scaler"
        assert processor.params == [1, 9]

    def test_input_processor_extraction_separate_elements(self):
        """Test extraction of input processors from separate array elements."""
        from glovebox.layout.parsers.ast_behavior_converter import ASTBehaviorConverter
        from glovebox.layout.parsers.ast_nodes import DTProperty, DTValue, DTValueType

        converter = ASTBehaviorConverter()

        # Test single processor with multiple parameters (separate elements)
        prop = DTProperty(name="input-processors")
        prop.value = DTValue(type=DTValueType.ARRAY, value=["&zip_xy_scaler", "3", "1"])

        processors = converter._extract_input_processors_from_property(prop)

        assert len(processors) == 1
        assert processors[0].code == "&zip_xy_scaler"
        assert processors[0].params == [3, 1]

    def test_input_processor_extraction_space_separated(self):
        """Test extraction of input processors from space-separated string."""
        from glovebox.layout.parsers.ast_behavior_converter import ASTBehaviorConverter
        from glovebox.layout.parsers.ast_nodes import DTProperty, DTValue, DTValueType

        converter = ASTBehaviorConverter()

        # Test single processor with space-separated parameters
        prop = DTProperty(name="input-processors")
        prop.value = DTValue(type=DTValueType.ARRAY, value=["&zip_xy_scaler 3 1"])

        processors = converter._extract_input_processors_from_property(prop)

        assert len(processors) == 1
        assert processors[0].code == "&zip_xy_scaler"
        assert processors[0].params == [3, 1]

    def test_multiple_input_processors(self):
        """Test extraction of multiple input processors."""
        from glovebox.layout.parsers.ast_behavior_converter import ASTBehaviorConverter
        from glovebox.layout.parsers.ast_nodes import DTProperty, DTValue, DTValueType

        converter = ASTBehaviorConverter()

        # Test multiple processors (separate elements)
        prop = DTProperty(name="input-processors")
        prop.value = DTValue(
            type=DTValueType.ARRAY,
            value=["&zip_xy_scaler", "12", "1", "&another_processor", "5"],
        )

        processors = converter._extract_input_processors_from_property(prop)

        assert len(processors) == 2
        assert processors[0].code == "&zip_xy_scaler"
        assert processors[0].params == [12, 1]
        assert processors[1].code == "&another_processor"
        assert processors[1].params == [5]

    def test_template_aware_processor_input_listener_conversion(self):
        """Test that TemplateAwareProcessor properly converts input listeners from DTSI to JSON models."""
        from glovebox.layout.models import LayoutData
        from glovebox.layout.parsers.keymap_processors import TemplateAwareProcessor

        processor = TemplateAwareProcessor()
        layout_data = LayoutData(keyboard="test", title="Test Layout")

        # Sample input listener DTSI content (complete device tree structure)
        input_listeners_dtsi = """
        / {
            mmv_input_listener: mmv_input_listener {
                compatible = "zmk,input-listener";
                device = <&glidepoint>;

                LAYER_MouseSlow {
                    layers = <16>;
                    input-processors = <&zip_xy_scaler>, <1>, <9>;
                };
            };
        };
        """

        # Test the conversion method
        processor._convert_input_listeners_from_dtsi(layout_data, input_listeners_dtsi)

        # Verify that input listeners were properly converted to JSON models
        assert hasattr(layout_data, "input_listeners")
        assert layout_data.input_listeners is not None
        assert len(layout_data.input_listeners) > 0

        # Verify the structure of the converted input listener
        input_listener = layout_data.input_listeners[0]
        assert input_listener.code == "&mmv_input_listener"

    def test_transform_behavior_references_to_definitions(self):
        """Test that behavior references are properly transformed to definitions."""
        processor = TemplateAwareProcessor()

        # Test input listener transformation
        dtsi_content_input_listener = """
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
"""

        result = processor._transform_behavior_references_to_definitions(dtsi_content_input_listener)

        # Should transform &mmv_input_listener to mmv_input_listener with compatible property
        assert "&mmv_input_listener" not in result
        assert "mmv_input_listener {" in result
        assert 'compatible = "zmk,input-listener";' in result
        assert "LAYER_MouseSlow" in result
        assert "layers = <16>;" in result

    def test_template_aware_processor_input_listener_data_handling(self):
        """Test that TemplateAwareProcessor handles both string and list input listener data."""
        from glovebox.layout.models import LayoutData
        from glovebox.layout.models.behaviors import InputListener
        from glovebox.layout.parsers.keymap_processors import TemplateAwareProcessor

        processor = TemplateAwareProcessor()

        # Test case 1: String data (raw DTSI) - should be converted
        layout_data = LayoutData(keyboard="test", title="Test Layout")
        processed_data = {"input_listeners": "raw DTSI content"}

        processor._populate_layout_from_processed_data(layout_data, processed_data)

        # Should attempt conversion but may fail with invalid DTSI - that's expected
        # The important thing is that it doesn't crash

        # Test case 2: List data (already converted models) - should be assigned directly
        layout_data2 = LayoutData(keyboard="test", title="Test Layout")
        input_listener = InputListener(code="&test_listener")
        processed_data2 = {"input_listeners": [input_listener]}

        processor._populate_layout_from_processed_data(layout_data2, processed_data2)

        # Should be assigned directly to input_listeners
        assert layout_data2.input_listeners == [input_listener]

    def test_template_aware_processor_bare_input_listener_definitions(self):
        """Test that TemplateAwareProcessor can handle bare input listener definitions (section extractor format)."""
        from glovebox.layout.models import LayoutData
        from glovebox.layout.parsers.keymap_processors import TemplateAwareProcessor

        processor = TemplateAwareProcessor()
        layout_data = LayoutData(keyboard="test", title="Test Layout")

        # Bare input listener definitions as provided by section extractor
        # This matches the actual format that causes parsing issues
        input_listeners_dtsi = """&mmv_input_listener {
    // LAYER_MouseSlow
    LAYER_MouseSlow {
        layers = <16>;
        input-processors = <&zip_xy_scaler 1 9>;
    };
    // LAYER_MouseFast
    LAYER_MouseFast {
        layers = <17>;
        input-processors = <&zip_xy_scaler 3 1>;
    };
    // LAYER_MouseWarp
    LAYER_MouseWarp {
        layers = <18>;
        input-processors = <&zip_xy_scaler 12 1>;
    };
};

&msc_input_listener {
    // LAYER_MouseSlow
    LAYER_MouseSlow {
        layers = <16>;
        input-processors = <&zip_scroll_scaler 1 9>;
    };
    // LAYER_MouseFast
    LAYER_MouseFast {
        layers = <17>;
        input-processors = <&zip_scroll_scaler 3 1>;
    };
    // LAYER_MouseWarp
    LAYER_MouseWarp {
        layers = <18>;
        input-processors = <&zip_scroll_scaler 12 1>;
    };
};"""

        # Test the conversion method
        processor._convert_input_listeners_from_dtsi(layout_data, input_listeners_dtsi)

        # Verify that input listeners were properly converted to JSON models
        assert hasattr(layout_data, "input_listeners")
        assert layout_data.input_listeners is not None
        assert len(layout_data.input_listeners) == 2

        # Verify the first input listener (mmv_input_listener)
        mmv_listener = layout_data.input_listeners[0]
        assert mmv_listener.code == "&mmv_input_listener"
        assert len(mmv_listener.nodes) == 3

        # Check first node (LAYER_MouseSlow)
        slow_node = mmv_listener.nodes[0]
        assert slow_node.code == "LAYER_MouseSlow"
        assert slow_node.layers == [16]
        assert len(slow_node.input_processors) == 1
        assert slow_node.input_processors[0].code == "&zip_xy_scaler"
        assert slow_node.input_processors[0].params == [1, 9]

        # Check second node (LAYER_MouseFast)
        fast_node = mmv_listener.nodes[1]
        assert fast_node.code == "LAYER_MouseFast"
        assert fast_node.layers == [17]
        assert len(fast_node.input_processors) == 1
        assert fast_node.input_processors[0].code == "&zip_xy_scaler"
        assert fast_node.input_processors[0].params == [3, 1]

        # Check third node (LAYER_MouseWarp)
        warp_node = mmv_listener.nodes[2]
        assert warp_node.code == "LAYER_MouseWarp"
        assert warp_node.layers == [18]
        assert len(warp_node.input_processors) == 1
        assert warp_node.input_processors[0].code == "&zip_xy_scaler"
        assert warp_node.input_processors[0].params == [12, 1]

        # Verify the second input listener (msc_input_listener)
        msc_listener = layout_data.input_listeners[1]
        assert msc_listener.code == "&msc_input_listener"
        assert len(msc_listener.nodes) == 3

        # Check first msc node (LAYER_MouseSlow)
        msc_slow_node = msc_listener.nodes[0]
        assert msc_slow_node.code == "LAYER_MouseSlow"
        assert msc_slow_node.layers == [16]
        assert len(msc_slow_node.input_processors) == 1
        assert msc_slow_node.input_processors[0].code == "&zip_scroll_scaler"
        assert msc_slow_node.input_processors[0].params == [1, 9]

        # Check second msc node (LAYER_MouseFast)
        msc_fast_node = msc_listener.nodes[1]
        assert msc_fast_node.code == "LAYER_MouseFast"
        assert msc_fast_node.layers == [17]
        assert len(msc_fast_node.input_processors) == 1
        assert msc_fast_node.input_processors[0].code == "&zip_scroll_scaler"
        assert msc_fast_node.input_processors[0].params == [3, 1]

        # Check third msc node (LAYER_MouseWarp)
        msc_warp_node = msc_listener.nodes[2]
        assert msc_warp_node.code == "LAYER_MouseWarp"
        assert msc_warp_node.layers == [18]
        assert len(msc_warp_node.input_processors) == 1
        assert msc_warp_node.input_processors[0].code == "&zip_scroll_scaler"
        assert msc_warp_node.input_processors[0].params == [12, 1]
