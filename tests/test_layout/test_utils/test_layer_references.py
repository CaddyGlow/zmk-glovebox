"""Tests for layer reference tracking and updating utilities."""

import pytest

from glovebox.layout.models import LayoutBinding, LayoutData, LayoutParam
from glovebox.layout.utils.layer_references import (
    LAYER_REFERENCING_BEHAVIORS,
    LayerReference,
    create_layer_mapping_for_add,
    create_layer_mapping_for_move,
    create_layer_mapping_for_remove,
    find_layer_references,
    update_layer_references,
)


class TestLayerReferenceDetection:
    """Test finding layer references in bindings."""

    def test_find_mo_references(self):
        """Test finding &mo (momentary layer) references."""
        layout_data = LayoutData(
            keyboard="test",
            title="Test Layout",
            layer_names=["Base", "Layer1", "Layer2"],
            layers=[
                [
                    LayoutBinding.from_str("&kp Q"),
                    LayoutBinding.from_str("&mo 1"),
                    LayoutBinding.from_str("&mo 2"),
                ],
                [
                    LayoutBinding.from_str("&trans"),
                    LayoutBinding.from_str("&mo 0"),
                ],
                [],
            ],
        )

        references = find_layer_references(layout_data)

        assert len(references) == 3
        # First layer references
        assert references[0].layer_index == 0
        assert references[0].binding_index == 1
        assert references[0].layer_id == 1
        assert references[0].behavior == "&mo"

        assert references[1].layer_index == 0
        assert references[1].binding_index == 2
        assert references[1].layer_id == 2

        # Second layer reference
        assert references[2].layer_index == 1
        assert references[2].binding_index == 1
        assert references[2].layer_id == 0

    def test_find_lt_references(self):
        """Test finding &lt (layer-tap) references."""
        layout_data = LayoutData(
            keyboard="test",
            title="Test Layout",
            layer_names=["Base", "Layer1"],
            layers=[
                [
                    LayoutBinding.from_str("&lt 1 SPACE"),
                    LayoutBinding.from_str("&kp Q"),
                ],
                [],
            ],
        )

        references = find_layer_references(layout_data)

        assert len(references) == 1
        assert references[0].layer_index == 0
        assert references[0].binding_index == 0
        assert references[0].layer_id == 1
        assert references[0].behavior == "&lt"

    def test_find_to_tog_references(self):
        """Test finding &to and &tog references."""
        layout_data = LayoutData(
            keyboard="test",
            title="Test Layout",
            layer_names=["Base", "Layer1", "Layer2"],
            layers=[
                [
                    LayoutBinding.from_str("&to 1"),
                    LayoutBinding.from_str("&tog 2"),
                ],
                [],
                [],
            ],
        )

        references = find_layer_references(layout_data)

        assert len(references) == 2
        assert references[0].behavior == "&to"
        assert references[0].layer_id == 1
        assert references[1].behavior == "&tog"
        assert references[1].layer_id == 2

    def test_ignore_non_layer_behaviors(self):
        """Test that non-layer behaviors are ignored."""
        layout_data = LayoutData(
            keyboard="test",
            title="Test Layout",
            layer_names=["Base"],
            layers=[
                [
                    LayoutBinding.from_str("&kp Q"),
                    LayoutBinding.from_str("&trans"),
                    LayoutBinding.from_str("&none"),
                    LayoutBinding.from_str("&mt LCTRL A"),
                ],
            ],
        )

        references = find_layer_references(layout_data)
        assert len(references) == 0


class TestLayerMappingCreation:
    """Test layer mapping creation for different operations."""

    def test_create_mapping_for_add_at_end(self):
        """Test mapping when adding layer at end."""
        mapping = create_layer_mapping_for_add(3, 3)

        assert mapping == {0: 0, 1: 1, 2: 2}  # No changes

    def test_create_mapping_for_add_at_beginning(self):
        """Test mapping when adding layer at beginning."""
        mapping = create_layer_mapping_for_add(3, 0)

        assert mapping == {0: 1, 1: 2, 2: 3}  # All shift up

    def test_create_mapping_for_add_in_middle(self):
        """Test mapping when adding layer in middle."""
        mapping = create_layer_mapping_for_add(3, 1)

        assert mapping == {0: 0, 1: 2, 2: 3}  # Layers after insertion shift up

    def test_create_mapping_for_remove_single(self):
        """Test mapping when removing single layer."""
        mapping = create_layer_mapping_for_remove(4, [1])

        assert mapping == {0: 0, 1: None, 2: 1, 3: 2}

    def test_create_mapping_for_remove_multiple(self):
        """Test mapping when removing multiple layers."""
        mapping = create_layer_mapping_for_remove(5, [1, 3])

        assert mapping == {0: 0, 1: None, 2: 1, 3: None, 4: 2}

    def test_create_mapping_for_move_down(self):
        """Test mapping when moving layer down."""
        mapping = create_layer_mapping_for_move(4, 1, 3)

        assert mapping == {0: 0, 1: 3, 2: 1, 3: 2}

    def test_create_mapping_for_move_up(self):
        """Test mapping when moving layer up."""
        mapping = create_layer_mapping_for_move(4, 3, 1)

        assert mapping == {0: 0, 1: 2, 2: 3, 3: 1}


class TestLayerReferenceUpdates:
    """Test updating layer references based on mappings."""

    def test_update_references_after_add(self):
        """Test updating references after adding a layer."""
        layout_data = LayoutData(
            keyboard="test",
            title="Test Layout",
            layer_names=["Base", "Layer1"],
            layers=[
                [
                    LayoutBinding.from_str("&mo 1"),
                ],
                [],
            ],
        )

        # Simulate adding layer at position 1
        mapping = create_layer_mapping_for_add(2, 1)
        updated_layout, warnings = update_layer_references(layout_data, mapping)

        # Check that &mo 1 is now &mo 2
        binding = updated_layout.layers[0][0]
        assert binding.params[0].value == 2

    def test_update_references_after_remove(self):
        """Test updating references after removing a layer."""
        layout_data = LayoutData(
            keyboard="test",
            title="Test Layout",
            layer_names=["Base", "Layer1", "Layer2"],
            layers=[
                [
                    LayoutBinding.from_str("&mo 1"),
                    LayoutBinding.from_str("&mo 2"),
                ],
                [],
                [],
            ],
        )

        # Simulate removing layer 1
        mapping = create_layer_mapping_for_remove(3, [1])
        updated_layout, warnings = update_layer_references(layout_data, mapping)

        # Check that &mo 1 generates warning (removed layer)
        assert len(warnings) == 1
        assert "removed layer 1" in warnings[0]
        assert "key 0" in warnings[0]  # Check key position is included

        # Check that &mo 2 is now &mo 1
        binding = updated_layout.layers[0][1]
        assert binding.params[0].value == 1

    def test_update_lt_references(self):
        """Test updating layer-tap references."""
        layout_data = LayoutData(
            keyboard="test",
            title="Test Layout",
            layer_names=["Base", "Layer1", "Layer2"],
            layers=[
                [
                    LayoutBinding.from_str("&lt 2 SPACE"),
                ],
                [],
                [],
            ],
        )

        # Simulate removing layer 1
        mapping = create_layer_mapping_for_remove(3, [1])
        updated_layout, warnings = update_layer_references(layout_data, mapping)

        # Check that &lt 2 SPACE is now &lt 1 SPACE
        binding = updated_layout.layers[0][0]
        assert binding.params[0].value == 1
        assert binding.params[1].value == "SPACE"  # Second param unchanged

    def test_no_update_when_mapping_unchanged(self):
        """Test that references are not updated when mapping doesn't change them."""
        layout_data = LayoutData(
            keyboard="test",
            title="Test Layout",
            layer_names=["Base", "Layer1"],
            layers=[
                [
                    LayoutBinding.from_str("&mo 0"),
                ],
                [],
            ],
        )

        # Simulate adding layer at end (doesn't affect existing refs)
        mapping = create_layer_mapping_for_add(2, 2)
        updated_layout, warnings = update_layer_references(layout_data, mapping)

        # Check that &mo 0 remains &mo 0
        binding = updated_layout.layers[0][0]
        assert binding.params[0].value == 0
        assert len(warnings) == 0


class TestIntegrationScenarios:
    """Test complete scenarios with multiple operations."""

    def test_complex_layer_operations(self):
        """Test a complex scenario with multiple layer operations."""
        # Start with a layout that has cross-layer references
        layout_data = LayoutData(
            keyboard="test",
            title="Test Layout",
            layer_names=["Base", "Nav", "Num", "Sym"],
            layers=[
                [
                    LayoutBinding.from_str("&mo 1"),  # To Nav
                    LayoutBinding.from_str("&lt 2 SPACE"),  # To Num
                ],
                [
                    LayoutBinding.from_str("&to 0"),  # Back to Base
                    LayoutBinding.from_str("&tog 3"),  # Toggle Sym
                ],
                [
                    LayoutBinding.from_str("&mo 3"),  # To Sym
                ],
                [
                    LayoutBinding.from_str("&to 0"),  # Back to Base
                ],
            ],
        )

        # Remove Nav layer (index 1)
        mapping = create_layer_mapping_for_remove(4, [1])
        layout_data, warnings = update_layer_references(layout_data, mapping)

        # Verify warnings about removed layer
        assert any("removed layer 1" in w for w in warnings)
        # Check that key position is included in warning
        assert any("key 0" in w for w in warnings)  # &mo 1 at position 0

        # After removing Nav (index 1), the layers are NOT actually removed from layout_data
        # because update_layer_references only updates references, it doesn't remove layers
        # So we still have all 4 layers in layout_data.layers

        # Verify updated references
        # Base layer (index 0): &mo 1 warned (removed), &lt 2 -> &lt 1
        assert layout_data.layers[0][1].params[0].value == 1

        # Nav layer (index 1) is still there but references to it are warned
        # It has &to 0 (unchanged) and &tog 3 -> &tog 2
        assert layout_data.layers[1][0].params[0].value == 0  # &to 0
        assert layout_data.layers[1][1].params[0].value == 2  # &tog 3 -> &tog 2

        # Num layer (index 2): &mo 3 -> &mo 2
        assert layout_data.layers[2][0].params[0].value == 2

        # Sym layer (index 3): &to 0 stays &to 0
        assert layout_data.layers[3][0].params[0].value == 0


@pytest.mark.parametrize(
    "behavior,expected",
    [
        ("&lt", True),
        ("&mo", True),
        ("&to", True),
        ("&tog", True),
        ("&kp", False),
        ("&mt", False),
        ("&trans", False),
    ],
)
def test_layer_referencing_behaviors_constant(behavior, expected):
    """Test that LAYER_REFERENCING_BEHAVIORS contains expected behaviors."""
    assert (behavior in LAYER_REFERENCING_BEHAVIORS) == expected
