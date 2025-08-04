"""Unit tests for layer reference validation in LayoutData."""

from glovebox.layout.models import LayoutBinding, LayoutData


def create_binding(value: str) -> LayoutBinding:
    """Helper to create LayoutBinding from string value."""
    return LayoutBinding(value=value)


class TestValidateLayerReferences:
    """Test the validate_layer_references method in LayoutData."""

    def test_all_valid_references(self):
        """Test with all layer references being valid."""
        layout = LayoutData(
            keyboard="test",
            title="Valid References",
            layer_names=["Base", "Nav", "Num"],
            layers=[
                [
                    create_binding("&mo 1"),
                    create_binding("&lt 2 SPACE"),
                    create_binding("&trans"),
                ],
                [
                    create_binding("&to 0"),
                    create_binding("&tog 2"),
                    create_binding("&trans"),
                ],
                [
                    create_binding("&to 0"),
                    create_binding("&mo 1"),
                    create_binding("&trans"),
                ],
            ],
        )

        errors = layout.validate_layer_references()
        assert errors == []

    def test_out_of_range_references(self):
        """Test with layer references that are out of range."""
        layout = LayoutData(
            keyboard="test",
            title="Invalid References",
            layer_names=["Base", "Nav"],
            layers=[
                [
                    create_binding("&mo 1"),
                    create_binding("&lt 2 SPACE"),
                    create_binding("&tog 3"),
                ],  # 2 and 3 are out of range
                [
                    create_binding("&to 0"),
                    create_binding("&mo 5"),
                    create_binding("&trans"),
                ],  # 5 is out of range
            ],
        )

        errors = layout.validate_layer_references()
        assert len(errors) == 3
        assert "Invalid layer reference in Base[1]: &lt 2 (valid range: 0-1)" in errors
        assert "Invalid layer reference in Base[2]: &tog 3 (valid range: 0-1)" in errors
        assert "Invalid layer reference in Nav[1]: &mo 5 (valid range: 0-1)" in errors

    def test_negative_layer_references(self):
        """Test with negative layer indices."""
        layout = LayoutData(
            keyboard="test",
            title="Negative References",
            layer_names=["Base", "Nav"],
            layers=[
                [create_binding("&mo -1"), create_binding("&trans")],  # Negative index
                [create_binding("&to 0"), create_binding("&trans")],
            ],
        )

        errors = layout.validate_layer_references()
        assert len(errors) == 1
        assert "Invalid layer reference in Base[0]: &mo -1 (valid range: 0-1)" in errors

    def test_empty_layout(self):
        """Test with an empty layout (no layers)."""
        layout = LayoutData(
            keyboard="test",
            title="Empty",
            layer_names=[],
            layers=[],
        )

        errors = layout.validate_layer_references()
        assert errors == []

    def test_single_layer_self_reference(self):
        """Test with a single layer that references itself."""
        layout = LayoutData(
            keyboard="test",
            title="Single Layer",
            layer_names=["Base"],
            layers=[
                [
                    create_binding("&mo 0"),
                    create_binding("&to 0"),
                    create_binding("&trans"),
                ],  # Self-references are valid
            ],
        )

        errors = layout.validate_layer_references()
        assert errors == []

    def test_ignores_non_layer_behaviors(self):
        """Test that non-layer-referencing behaviors are ignored."""
        layout = LayoutData(
            keyboard="test",
            title="Mixed Behaviors",
            layer_names=["Base", "Nav"],
            layers=[
                [
                    create_binding("&kp Q"),
                    create_binding("&mt LCTRL A"),
                    create_binding("&mo 1"),
                    create_binding("&trans"),
                    create_binding("&none"),
                ],
                [
                    create_binding("&kp LEFT"),
                    create_binding("&to 0"),
                    create_binding("&hrm_l LALT Q"),
                    create_binding("&trans"),
                ],
            ],
        )

        errors = layout.validate_layer_references()
        assert errors == []  # All layer references (mo 1, to 0) are valid

    def test_layer_tap_references(self):
        """Test validation of layer-tap (&lt) references."""
        layout = LayoutData(
            keyboard="test",
            title="Layer Tap",
            layer_names=["Base", "Nav", "Num", "Sym"],
            layers=[
                [
                    create_binding("&lt 1 SPACE"),
                    create_binding("&lt 3 ENTER"),
                    create_binding("&trans"),
                ],  # Valid layer-tap
                [create_binding("&trans")] * 3,
                [create_binding("&trans")] * 3,
                [
                    create_binding("&lt 4 TAB"),
                    create_binding("&trans"),
                    create_binding("&trans"),
                ],  # Invalid - layer 4 doesn't exist
            ],
        )

        errors = layout.validate_layer_references()
        assert len(errors) == 1
        assert "Invalid layer reference in Sym[0]: &lt 4 (valid range: 0-3)" in errors

    def test_all_layer_behaviors(self):
        """Test all four layer-referencing behaviors."""
        layout = LayoutData(
            keyboard="test",
            title="All Behaviors",
            layer_names=["Base", "One", "Two"],
            layers=[
                [
                    create_binding("&mo 3"),
                    create_binding("&lt 3 A"),
                    create_binding("&to 3"),
                    create_binding("&tog 3"),
                ],  # All reference invalid layer 3
                [
                    create_binding("&mo 0"),
                    create_binding("&lt 1 B"),
                    create_binding("&to 2"),
                    create_binding("&tog 0"),
                ],  # All valid
                [create_binding("&trans")] * 4,
            ],
        )

        errors = layout.validate_layer_references()
        assert len(errors) == 4
        # Check all four behavior types are detected
        assert any("&mo 3" in error for error in errors)
        assert any("&lt 3" in error for error in errors)
        assert any("&to 3" in error for error in errors)
        assert any("&tog 3" in error for error in errors)

    def test_layer_names_longer_than_layers(self):
        """Test when layer_names has more entries than layers."""
        layout = LayoutData(
            keyboard="test",
            title="Mismatched",
            layer_names=["Base", "Nav", "Num"],  # 3 names
            layers=[
                [create_binding("&mo 1"), create_binding("&trans")],
                [create_binding("&to 0"), create_binding("&trans")],
                # Missing third layer
            ],
        )

        # Should still validate references in existing layers
        errors = layout.validate_layer_references()
        assert errors == []  # References to layers 0 and 1 are valid

    def test_boundary_layer_references(self):
        """Test boundary cases for layer references."""
        layout = LayoutData(
            keyboard="test",
            title="Boundaries",
            layer_names=["L0", "L1", "L2", "L3", "L4"],  # 5 layers (0-4)
            layers=[
                [
                    create_binding("&mo 0"),
                    create_binding("&mo 4"),
                    create_binding("&trans"),
                ],  # Min and max valid indices
                [
                    create_binding("&mo 5"),
                    create_binding("&trans"),
                    create_binding("&trans"),
                ],  # Just over max
                [create_binding("&trans")] * 3,
                [create_binding("&trans")] * 3,
                [
                    create_binding("&to 0"),
                    create_binding("&trans"),
                    create_binding("&trans"),
                ],
            ],
        )

        errors = layout.validate_layer_references()
        assert len(errors) == 1
        assert "Invalid layer reference in L1[0]: &mo 5 (valid range: 0-4)" in errors
