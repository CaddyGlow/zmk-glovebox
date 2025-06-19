import json
from pathlib import Path
from typing import Any

import pytest

from glovebox.layout.diffing import LayoutDiffSystem, LayoutPatchSystem
from glovebox.layout.models import LayoutBinding, LayoutData, LayoutParam

from .data_test import (
    BASE_LAYOUT,
    COMPLEX_CHANGE,
    LAYER_ADDITION,
    LAYER_CONTENT_CHANGE,
    LAYER_MOVE_WITH_KEY_CHANGE,
    LAYER_REMOVAL,
    LAYER_REORDER,
    MULTIPLE_KEY_CHANGES,
    PARTIAL_LAYER_CHANGE,
    SINGLE_KEY_CHANGE,
    TEST_CASES,
    TEST_SCENARIOS,
    LayerModel,
)


class TestLayoutDiff:
    """Test suite for layout diff functionality."""

    @pytest.fixture
    def diff_system(self) -> LayoutDiffSystem:
        """Create a diff system instance."""
        return LayoutDiffSystem()

    @pytest.fixture
    def patch_system(self) -> LayoutPatchSystem:
        """Create a patch system instance."""
        return LayoutPatchSystem()

    def create_layout_data(self, layer_model: LayerModel) -> LayoutData:
        """Convert LayerModel to LayoutData for testing."""
        # Convert string bindings to LayoutBinding objects
        layers = []
        for layer in layer_model.layers:
            layer_bindings = []
            for binding_str in layer:
                # Parse the binding string (e.g., "&kp Q")
                parts = binding_str.split()
                if len(parts) >= 2:
                    behavior = parts[0]
                    param = parts[1] if len(parts) > 1 else ""
                    binding = LayoutBinding(
                        value=behavior,
                        params=[LayoutParam(value=param)] if param else [],
                    )
                else:
                    binding = LayoutBinding(value=binding_str, params=[])
                layer_bindings.append(binding)
            layers.append(layer_bindings)

        return LayoutData(
            keyboard="test_keyboard",
            title="Test Layout",
            layer_names=layer_model.layer_names,
            layers=layers,
            version="1.0.0",
            uuid="test-uuid-base",
        )

    def test_single_key_change(self, diff_system: LayoutDiffSystem) -> None:
        """Test diffing a single key change."""
        base = self.create_layout_data(BASE_LAYOUT)
        modified = self.create_layout_data(SINGLE_KEY_CHANGE)

        diff = diff_system.create_layout_diff(base, modified)

        # Verify the diff captured the change
        assert diff["statistics"]["total_operations"] > 0
        assert diff["statistics"]["replacements"] >= 1

        # Check that the specific binding change was detected
        behavior_changes = diff["movements"]["behavior_changes"]
        assert len(behavior_changes) == 1
        assert behavior_changes[0]["layer"] == 0
        assert behavior_changes[0]["position"] == 0

        # Verify the change details
        change = behavior_changes[0]
        assert change["from"]["value"] == "&kp"
        assert change["from"]["params"][0]["value"] == "Q"
        assert change["to"]["value"] == "&kp"
        assert change["to"]["params"][0]["value"] == "A"

    def test_multiple_key_changes(self, diff_system: LayoutDiffSystem) -> None:
        """Test diffing multiple key changes in the same layer."""
        base = self.create_layout_data(BASE_LAYOUT)
        modified = self.create_layout_data(MULTIPLE_KEY_CHANGES)

        diff = diff_system.create_layout_diff(base, modified)

        # Should have multiple behavior changes
        behavior_changes = diff["movements"]["behavior_changes"]
        assert len(behavior_changes) == 2

        # Verify both changes
        positions_changed = {change["position"] for change in behavior_changes}
        assert positions_changed == {0, 2}  # Q->A at 0, E->D at 2

    def test_layer_reorder(self, diff_system: LayoutDiffSystem) -> None:
        """Test detecting layer reordering."""
        base = self.create_layout_data(BASE_LAYOUT)
        modified = self.create_layout_data(LAYER_REORDER)

        diff = diff_system.create_layout_diff(base, modified)

        # Check that layer reordering was detected
        layer_changes = diff["layout_changes"]
        assert layer_changes["layers"]["reordered"] is True
        assert layer_changes["layer_names"]["order_changed"] is True

        # Verify the name changes
        name_changes = layer_changes["layer_names"]["renamed"]
        assert len(name_changes) == 2

    def test_layer_addition(self, diff_system: LayoutDiffSystem) -> None:
        """Test detecting layer addition."""
        base = self.create_layout_data(BASE_LAYOUT)
        modified = self.create_layout_data(LAYER_ADDITION)

        diff = diff_system.create_layout_diff(base, modified)

        # Check that layer addition was detected
        layer_changes = diff["layout_changes"]
        assert len(layer_changes["layers"]["added"]) == 1
        assert 4 in layer_changes["layers"]["added"]  # 5th layer (index 4)

        # Verify statistics
        assert diff["statistics"]["additions"] > 0

    def test_layer_removal(self, diff_system: LayoutDiffSystem) -> None:
        """Test detecting layer removal."""
        base = self.create_layout_data(BASE_LAYOUT)
        modified = self.create_layout_data(LAYER_REMOVAL)

        diff = diff_system.create_layout_diff(base, modified)

        # Check that layer removal was detected
        layer_changes = diff["layout_changes"]
        assert len(layer_changes["layers"]["removed"]) == 1
        assert 3 in layer_changes["layers"]["removed"]  # adjust layer removed

        # Verify statistics
        assert diff["statistics"]["removals"] > 0

    def test_layer_content_change(self, diff_system: LayoutDiffSystem) -> None:
        """Test detecting complete layer content change."""
        base = self.create_layout_data(BASE_LAYOUT)
        modified = self.create_layout_data(LAYER_CONTENT_CHANGE)

        diff = diff_system.create_layout_diff(base, modified)

        # Check that layer modification was detected
        layer_changes = diff["layout_changes"]
        assert 1 in layer_changes["layers"]["modified"]  # lower layer modified

        # Should have many binding changes in layer 1
        behavior_changes = [
            c for c in diff["movements"]["behavior_changes"] if c["layer"] == 1
        ]
        assert len(behavior_changes) == 10  # All 10 keys changed

    def test_complex_change(self, diff_system: LayoutDiffSystem) -> None:
        """Test complex changes with multiple operations."""
        base = self.create_layout_data(BASE_LAYOUT)
        modified = self.create_layout_data(COMPLEX_CHANGE)

        diff = diff_system.create_layout_diff(base, modified)

        layer_changes = diff["layout_changes"]

        # Check multiple types of changes
        assert len(layer_changes["layers"]["added"]) > 0  # nav layer added
        assert len(layer_changes["layer_names"]["renamed"]) > 0  # layers renamed
        assert len(layer_changes["layers"]["modified"]) > 0  # content changes

        # Verify high operation count
        assert diff["statistics"]["total_operations"] > 10

    def test_partial_layer_change(self, diff_system: LayoutDiffSystem) -> None:
        """Test selective position changes in a layer."""
        base = self.create_layout_data(BASE_LAYOUT)
        modified = self.create_layout_data(PARTIAL_LAYER_CHANGE)

        diff = diff_system.create_layout_diff(base, modified)

        # Get changes in layer 1 (lower)
        layer_1_changes = [
            c for c in diff["movements"]["behavior_changes"] if c["layer"] == 1
        ]

        # Should have exactly 3 changes at positions 2, 3, 7
        assert len(layer_1_changes) == 3
        changed_positions = {c["position"] for c in layer_1_changes}
        assert changed_positions == {2, 3, 7}

    def test_patch_application(
        self, diff_system: LayoutDiffSystem, patch_system: LayoutPatchSystem
    ) -> None:
        """Test applying a patch to recreate the modified layout."""
        base = self.create_layout_data(BASE_LAYOUT)
        modified = self.create_layout_data(SINGLE_KEY_CHANGE)

        # Create diff
        diff = diff_system.create_layout_diff(base, modified)

        # Apply patch
        patched = patch_system.apply_patch(base, diff)

        # Verify the patched layout matches the expected modified layout
        assert patched.layer_names == modified.layer_names
        assert len(patched.layers) == len(modified.layers)

        # Check specific binding change
        assert patched.layers[0][0].value == modified.layers[0][0].value
        assert patched.layers[0][0].params[0].value == "A"

    def test_layer_move_with_key_change(self, diff_system: LayoutDiffSystem) -> None:
        """Test layer movement combined with key changes."""
        base = self.create_layout_data(BASE_LAYOUT)
        modified = self.create_layout_data(LAYER_MOVE_WITH_KEY_CHANGE)

        diff = diff_system.create_layout_diff(base, modified)

        layer_changes = diff["layout_changes"]

        # Should detect layer reordering
        assert layer_changes["layers"]["reordered"] is True
        assert layer_changes["layer_names"]["order_changed"] is True

        # Should detect layer name changes at multiple positions
        name_changes = layer_changes["layer_names"]["renamed"]
        assert len(name_changes) >= 3  # At least 3 positions changed

        # Should detect key change in base layer
        behavior_changes = [
            c for c in diff["movements"]["behavior_changes"] if c["layer"] == 0
        ]
        assert len(behavior_changes) == 1  # Q -> A change
        assert behavior_changes[0]["position"] == 0

        # Verify the specific change
        change = behavior_changes[0]
        assert change["from"]["value"] == "&kp"
        assert change["from"]["params"][0]["value"] == "Q"
        assert change["to"]["value"] == "&kp"
        assert change["to"]["params"][0]["value"] == "A"

    def test_round_trip_diff_patch(
        self, diff_system: LayoutDiffSystem, patch_system: LayoutPatchSystem
    ) -> None:
        """Test that diff and patch operations are reversible."""
        for test_name, test_layout in TEST_CASES.items():
            if test_name == "base":
                continue

            base = self.create_layout_data(BASE_LAYOUT)
            modified = self.create_layout_data(test_layout)

            # Create diff
            diff = diff_system.create_layout_diff(base, modified)

            # Apply patch
            patched = patch_system.apply_patch(base, diff)

            # The patched layout should match the modified layout
            patched_dict = patched.model_dump(
                by_alias=True, exclude_unset=True, mode="json"
            )
            modified_dict = modified.model_dump(
                by_alias=True, exclude_unset=True, mode="json"
            )

            # Compare layers
            assert len(patched_dict["layers"]) == len(modified_dict["layers"])
            assert patched_dict["layer_names"] == modified_dict["layer_names"]
