import json
from pathlib import Path
from typing import Any

import pytest

from glovebox.layout.models import (
    ComboBehavior,
    HoldTapBehavior,
    InputListener,
    LayoutBinding,
    LayoutData,
    LayoutParam,
    MacroBehavior,
)

from . import LayoutDiffSystem, LayoutPatchSystem
from .data_test import (
    BASE_WITH_BEHAVIORS,
    BEHAVIOR_CHANGES,
    BEHAVIOR_SCENARIOS,
    BEHAVIOR_TEST_CASES,
    MODIFIED_BEHAVIORS,
    EnhancedLayerModel,
)


class TestBehaviorDiff:
    """Test suite for behavior-based layout diff functionality."""

    @pytest.fixture
    def diff_system(self):
        """Create a diff system instance."""
        return LayoutDiffSystem()

    @pytest.fixture
    def patch_system(self):
        """Create a patch system instance."""
        return LayoutPatchSystem()

    def create_enhanced_layout_data(
        self, enhanced_model: EnhancedLayerModel
    ) -> LayoutData:
        """Convert EnhancedLayerModel to LayoutData for testing."""
        # Convert string bindings to LayoutBinding objects
        layers = []
        for layer in enhanced_model.layers:
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

        # Convert behavior dictionaries to proper models
        hold_taps = []
        for ht_dict in enhanced_model.hold_taps:
            # Convert binding dictionaries to LayoutBinding objects
            bindings = []
            for binding_dict in ht_dict["bindings"]:
                params = [
                    LayoutParam(value=p["value"])
                    for p in binding_dict.get("params", [])
                ]
                bindings.append(
                    LayoutBinding(value=binding_dict["value"], params=params)
                )

            hold_tap = HoldTapBehavior(
                name=ht_dict["name"],
                description=ht_dict.get("description", ""),
                tappingTermMs=ht_dict["tapping_term_ms"],
                quickTapMs=ht_dict.get("quick_tap_ms"),
                flavor=ht_dict["flavor"],
                bindings=bindings,
            )
            hold_taps.append(hold_tap)

        combos = []
        for combo_dict in enhanced_model.combos:
            # Convert binding dictionary to LayoutBinding object
            binding_dict = combo_dict["binding"]
            params = [
                LayoutParam(value=p["value"]) for p in binding_dict.get("params", [])
            ]
            binding = LayoutBinding(value=binding_dict["value"], params=params)

            combo = ComboBehavior(
                name=combo_dict["name"],
                description=combo_dict.get("description", ""),
                timeoutMs=combo_dict.get("timeout_ms"),
                keyPositions=combo_dict["key_positions"],
                binding=binding,
            )
            combos.append(combo)

        macros = []
        for macro_dict in enhanced_model.macros:
            # Convert binding dictionaries to LayoutBinding objects
            bindings = []
            for binding_dict in macro_dict["bindings"]:
                params = [
                    LayoutParam(value=p["value"])
                    for p in binding_dict.get("params", [])
                ]
                bindings.append(
                    LayoutBinding(value=binding_dict["value"], params=params)
                )

            macro = MacroBehavior(
                name=macro_dict["name"],
                description=macro_dict.get("description", ""),
                waitMs=macro_dict.get("wait_ms"),
                tapMs=macro_dict.get("tap_ms"),
                bindings=bindings,
            )
            macros.append(macro)

        input_listeners = []
        for listener_dict in enhanced_model.input_listeners:
            # Convert to InputListener if needed
            listener = InputListener(
                code=listener_dict["code"],
                input_processors=listener_dict.get("input_processors", []),
                nodes=listener_dict.get("nodes", []),
            )
            input_listeners.append(listener)

        return LayoutData(
            keyboard="test_keyboard",
            title="Test Layout with Behaviors",
            layer_names=enhanced_model.layer_names,
            layers=layers,
            version="1.0.0",
            uuid="test-uuid-behavior",
            holdTaps=hold_taps,
            combos=combos,
            macros=macros,
            inputListeners=input_listeners,
        )

    def test_behavior_parameter_modifications(self, diff_system):
        """Test detecting modifications to behavior parameters."""
        base = self.create_enhanced_layout_data(BASE_WITH_BEHAVIORS)
        modified = self.create_enhanced_layout_data(MODIFIED_BEHAVIORS)

        diff = diff_system.create_layout_diff(base, modified)

        behavior_changes = diff["layout_changes"]["behaviors"]

        # Check hold-tap changes
        assert "ht_new" in behavior_changes["hold_taps"]["added"]
        assert "ht_a" in behavior_changes["hold_taps"]["modified"]

        # Check combo changes
        assert "combo_new" in behavior_changes["combos"]["added"]
        assert "combo_space" in behavior_changes["combos"]["modified"]

        # Check macro changes
        assert "macro_hello" in behavior_changes["macros"]["modified"]

        # Verify no removals in this test case
        assert len(behavior_changes["hold_taps"]["removed"]) == 0
        assert len(behavior_changes["combos"]["removed"]) == 0
        assert len(behavior_changes["macros"]["removed"]) == 0

    def test_behavior_replacement(self, diff_system):
        """Test detecting complete behavior replacement."""
        base = self.create_enhanced_layout_data(BASE_WITH_BEHAVIORS)
        modified = self.create_enhanced_layout_data(BEHAVIOR_CHANGES)

        diff = diff_system.create_layout_diff(base, modified)

        behavior_changes = diff["layout_changes"]["behaviors"]

        # Check hold-tap changes
        assert "ht_a" in behavior_changes["hold_taps"]["removed"]
        assert "ht_new_only" in behavior_changes["hold_taps"]["added"]

        # Check combo changes
        assert "combo_space" in behavior_changes["combos"]["removed"]
        assert "combo_new_only" in behavior_changes["combos"]["added"]

        # Check macro changes
        assert "macro_hello" in behavior_changes["macros"]["removed"]
        assert "macro_new_only" in behavior_changes["macros"]["added"]

        # Should have no modifications since behaviors were completely replaced
        assert len(behavior_changes["hold_taps"]["modified"]) == 0
        assert len(behavior_changes["combos"]["modified"]) == 0
        assert len(behavior_changes["macros"]["modified"]) == 0

    def test_behavior_diff_statistics(self, diff_system):
        """Test that behavior changes are reflected in diff statistics."""
        base = self.create_enhanced_layout_data(BASE_WITH_BEHAVIORS)
        modified = self.create_enhanced_layout_data(MODIFIED_BEHAVIORS)

        diff = diff_system.create_layout_diff(base, modified)

        # Should have many operations due to behavior changes
        stats = diff["statistics"]
        assert stats["total_operations"] > 5  # At least several changes

        # Check that the JSON patch includes behavior-related paths
        patch_paths = [op.get("path", "") for op in diff["json_patch"]]
        behavior_paths = [
            path
            for path in patch_paths
            if any(
                behavior_type in path
                for behavior_type in ["/holdTaps", "/combos", "/macros"]
            )
        ]
        assert len(behavior_paths) > 0, "Should have behavior-related patch operations"

    def test_behavior_name_tracking(self, diff_system):
        """Test that behavior changes are tracked by name correctly."""
        base = self.create_enhanced_layout_data(BASE_WITH_BEHAVIORS)
        modified = self.create_enhanced_layout_data(MODIFIED_BEHAVIORS)

        diff = diff_system.create_layout_diff(base, modified)

        behavior_changes = diff["layout_changes"]["behaviors"]

        # Verify specific behavior names are tracked
        assert "ht_a" in behavior_changes["hold_taps"]["modified"]
        assert "combo_space" in behavior_changes["combos"]["modified"]
        assert "macro_hello" in behavior_changes["macros"]["modified"]

        # New behaviors should be tracked by name
        assert "ht_new" in behavior_changes["hold_taps"]["added"]
        assert "combo_new" in behavior_changes["combos"]["added"]

    def test_behavior_patch_application(self, diff_system, patch_system):
        """Test applying behavior-related patches."""
        base = self.create_enhanced_layout_data(BASE_WITH_BEHAVIORS)
        modified = self.create_enhanced_layout_data(MODIFIED_BEHAVIORS)

        # Create diff
        diff = diff_system.create_layout_diff(base, modified)

        # Apply patch
        patched = patch_system.apply_patch(base, diff)

        # Verify behavior counts match
        assert len(patched.hold_taps) == len(modified.hold_taps)
        assert len(patched.combos) == len(modified.combos)
        assert len(patched.macros) == len(modified.macros)

        # Verify specific behavior names exist
        hold_tap_names = {ht.name for ht in patched.hold_taps}
        combo_names = {combo.name for combo in patched.combos}
        macro_names = {macro.name for macro in patched.macros}

        assert "ht_a" in hold_tap_names
        assert "ht_new" in hold_tap_names
        assert "combo_space" in combo_names
        assert "combo_new" in combo_names
        assert "macro_hello" in macro_names

    def test_behavior_round_trip(self, diff_system, patch_system):
        """Test round-trip behavior diff and patch operations."""
        for test_name, test_layout in BEHAVIOR_TEST_CASES.items():
            if test_name == "base_with_behaviors":
                continue

            base = self.create_enhanced_layout_data(BASE_WITH_BEHAVIORS)
            modified = self.create_enhanced_layout_data(test_layout)

            # Create diff
            diff = diff_system.create_layout_diff(base, modified)

            # Apply patch
            patched = patch_system.apply_patch(base, diff)

            # Verify basic structure matches
            assert len(patched.layers) == len(modified.layers)
            assert patched.layer_names == modified.layer_names
            assert len(patched.hold_taps) == len(modified.hold_taps)
            assert len(patched.combos) == len(modified.combos)
            assert len(patched.macros) == len(modified.macros)

    def test_scenario_execution(self, diff_system):
        """Execute behavior test scenarios and verify expected changes."""
        for scenario in BEHAVIOR_SCENARIOS:
            base_name = scenario["from"]
            modified_name = scenario["to"]

            base = self.create_enhanced_layout_data(BEHAVIOR_TEST_CASES[base_name])
            modified = self.create_enhanced_layout_data(
                BEHAVIOR_TEST_CASES[modified_name]
            )

            diff = diff_system.create_layout_diff(base, modified)

            # Basic validation that diff was created
            assert "layout_changes" in diff
            assert "behaviors" in diff["layout_changes"]

            behavior_changes = diff["layout_changes"]["behaviors"]

            # At least one behavior type should have changes
            has_changes = any(
                [
                    behavior_changes["hold_taps"]["added"]
                    or behavior_changes["hold_taps"]["removed"]
                    or behavior_changes["hold_taps"]["modified"],
                    behavior_changes["combos"]["added"]
                    or behavior_changes["combos"]["removed"]
                    or behavior_changes["combos"]["modified"],
                    behavior_changes["macros"]["added"]
                    or behavior_changes["macros"]["removed"]
                    or behavior_changes["macros"]["modified"],
                ]
            )

            assert has_changes, (
                f"Scenario '{scenario['name']}' should detect behavior changes"
            )
