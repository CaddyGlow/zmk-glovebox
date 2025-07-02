"""Unit tests for layer reference validation in LayoutData."""

import pytest

from glovebox.layout.models import LayoutData


class TestValidateLayerReferences:
    """Test the validate_layer_references method in LayoutData."""

    def test_all_valid_references(self):
        """Test with all layer references being valid."""
        layout = LayoutData(
            keyboard="test",
            title="Valid References",
            layer_names=["Base", "Nav", "Num"],
            layers=[
                ["&mo 1", "&lt 2 SPACE", "&trans"],
                ["&to 0", "&tog 2", "&trans"],
                ["&to 0", "&mo 1", "&trans"],
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
                ["&mo 1", "&lt 2 SPACE", "&tog 3"],  # 2 and 3 are out of range
                ["&to 0", "&mo 5", "&trans"],  # 5 is out of range
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
                ["&mo -1", "&trans"],  # Negative index
                ["&to 0", "&trans"],
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
                ["&mo 0", "&to 0", "&trans"],  # Self-references are valid
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
                ["&kp Q", "&mt LCTRL A", "&mo 1", "&trans", "&none"],
                ["&kp LEFT", "&to 0", "&hrm_l LALT Q", "&trans"],
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
                ["&lt 1 SPACE", "&lt 3 ENTER", "&trans"],  # Valid layer-tap
                ["&trans"] * 3,
                ["&trans"] * 3,
                ["&lt 4 TAB", "&trans", "&trans"],  # Invalid - layer 4 doesn't exist
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
                    "&mo 3",
                    "&lt 3 A",
                    "&to 3",
                    "&tog 3",
                ],  # All reference invalid layer 3
                ["&mo 0", "&lt 1 B", "&to 2", "&tog 0"],  # All valid
                ["&trans"] * 4,
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
                ["&mo 1", "&trans"],
                ["&to 0", "&trans"],
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
                ["&mo 0", "&mo 4", "&trans"],  # Min and max valid indices
                ["&mo 5", "&trans", "&trans"],  # Just over max
                ["&trans"] * 3,
                ["&trans"] * 3,
                ["&to 0", "&trans", "&trans"],
            ],
        )

        errors = layout.validate_layer_references()
        assert len(errors) == 1
        assert "Invalid layer reference in L1[0]: &mo 5 (valid range: 0-4)" in errors
