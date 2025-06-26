import json
from pathlib import Path
from typing import Any

import pytest

from glovebox.layout.diffing import LayoutDiffSystem, LayoutPatchSystem
from glovebox.layout.models import (
    ComboBehavior,
    HoldTapBehavior,
    InputListener,
    LayoutBinding,
    LayoutData,
    LayoutParam,
    MacroBehavior,
)

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
    def diff_system(self) -> LayoutDiffSystem:
        """Create a diff system instance."""
        return LayoutDiffSystem()

    @pytest.fixture
    def patch_system(self) -> LayoutPatchSystem:
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
        for ht_model in enhanced_model.hold_taps:
            # HoldTapBehavior.bindings are already strings in the test data
            hold_tap = HoldTapBehavior(
                name=ht_model.name,
                description=ht_model.description or "",
                tappingTermMs=ht_model.tapping_term_ms,
                quickTapMs=ht_model.quick_tap_ms,
                flavor=ht_model.flavor,
                bindings=ht_model.bindings,  # Already list[str]
            )
            hold_taps.append(hold_tap)

        combos = []
        for combo_model in enhanced_model.combos:
            # Convert binding object to proper LayoutBinding if needed
            binding = combo_model.binding
            if not hasattr(binding, "params"):
                # Convert from dict-like
                params = []
                for p in binding.params:
                    if hasattr(p, "value"):
                        # Already a LayoutParam
                        params.append(p)
                    else:
                        # Convert from dict
                        params.append(LayoutParam(value=p["value"]))  # type: ignore
                binding = LayoutBinding(value=binding.value, params=params)

            combo = ComboBehavior(
                name=combo_model.name,
                description=combo_model.description or "",
                timeoutMs=combo_model.timeout_ms,
                keyPositions=combo_model.key_positions,
                binding=binding,
            )
            combos.append(combo)

        macros = []
        for macro_model in enhanced_model.macros:
            # Convert binding objects to proper LayoutBinding objects if needed
            macro_bindings: list[LayoutBinding] = []
            for binding in macro_model.bindings:
                if hasattr(binding, "params"):
                    # Already a LayoutBinding
                    macro_bindings.append(binding)
                else:
                    # Convert from dict-like
                    params = []
                    for p in binding.params:
                        if hasattr(p, "value"):
                            # Already a LayoutParam
                            params.append(p)
                        else:
                            # Convert from dict
                            params.append(LayoutParam(value=p["value"]))  # type: ignore  # type: ignore
                    macro_bindings.append(
                        LayoutBinding(value=binding.value, params=params)
                    )

            macro = MacroBehavior(
                name=macro_model.name,
                description=macro_model.description or "",
                waitMs=macro_model.wait_ms,
                tapMs=macro_model.tap_ms,
                bindings=macro_bindings,
            )
            macros.append(macro)

        input_listeners = []
        for listener_model in enhanced_model.input_listeners:
            # Convert to InputListener if needed
            listener = InputListener(
                code=listener_model.code,
                inputProcessors=listener_model.input_processors,
                nodes=listener_model.nodes,
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

    def test_behavior_parameter_modifications(
        self, diff_system: LayoutDiffSystem
    ) -> None:
        """Test detecting modifications to behavior parameters."""
        base = self.create_enhanced_layout_data(BASE_WITH_BEHAVIORS)
        modified = self.create_enhanced_layout_data(MODIFIED_BEHAVIORS)

        diff = diff_system.create_layout_diff(base, modified)

        # Access behavior changes directly from the diff object
        hold_tap_changes = diff.hold_taps

        # Check hold-tap changes
        assert "ht_new" in getattr(diff.hold_taps, "added", [])
        assert "ht_a" in getattr(diff.hold_taps, "modified", [])

        # Check combo changes
        assert "combo_new" in getattr(diff.combos, "added", [])
        assert "combo_space" in getattr(diff.combos, "modified", [])

        # Check macro changes
        assert "macro_hello" in getattr(diff.macros, "modified", [])

        # Verify no removals in this test case
        assert len(getattr(diff.hold_taps, "removed", [])) == 0
        assert len(getattr(diff.combos, "removed", [])) == 0
        assert len(getattr(diff.macros, "removed", [])) == 0

    def test_behavior_replacement(self, diff_system: LayoutDiffSystem) -> None:
        """Test detecting complete behavior replacement."""
        base = self.create_enhanced_layout_data(BASE_WITH_BEHAVIORS)
        modified = self.create_enhanced_layout_data(BEHAVIOR_CHANGES)

        diff = diff_system.create_layout_diff(base, modified)

        # Access behavior changes directly from the diff object
        hold_tap_changes = diff.hold_taps

        # Check hold-tap changes
        assert "ht_a" in getattr(diff.hold_taps, "removed", [])
        assert "ht_new_only" in getattr(diff.hold_taps, "added", [])

        # Check combo changes
        assert "combo_space" in getattr(diff.combos, "removed", [])
        assert "combo_new_only" in getattr(diff.combos, "added", [])

        # Check macro changes
        assert "macro_hello" in getattr(diff.macros, "removed", [])
        assert "macro_new_only" in getattr(diff.macros, "added", [])

        # Should have no modifications since behaviors were completely replaced
        assert len(getattr(diff.hold_taps, "modified", [])) == 0
        assert len(getattr(diff.combos, "modified", [])) == 0
        assert len(getattr(diff.macros, "modified", [])) == 0

    def test_behavior_diff_statistics(self, diff_system: LayoutDiffSystem) -> None:
        """Test that behavior changes are reflected in diff statistics."""
        base = self.create_enhanced_layout_data(BASE_WITH_BEHAVIORS)
        modified = self.create_enhanced_layout_data(MODIFIED_BEHAVIORS)

        diff = diff_system.create_layout_diff(base, modified)

        # Should have many operations due to behavior changes
        # Count operations based on LayoutDiff structure
        operation_count = (
            len(getattr(diff.hold_taps, "added", []))
            + len(getattr(diff.hold_taps, "modified", []))
            + len(getattr(diff.hold_taps, "removed", []))
        )
        operation_count += (
            len(getattr(diff.combos, "added", []))
            + len(getattr(diff.combos, "modified", []))
            + len(getattr(diff.combos, "removed", []))
        )
        operation_count += (
            len(getattr(diff.macros, "added", []))
            + len(getattr(diff.macros, "modified", []))
            + len(getattr(diff.macros, "removed", []))
        )
        assert operation_count > 5  # At least several changes

        # Check behavior-related fields are present in diff
        has_behavior_changes = any([diff.hold_taps, diff.combos, diff.macros])
        assert has_behavior_changes, "Should have behavior-related changes"

    def test_behavior_name_tracking(self, diff_system: LayoutDiffSystem) -> None:
        """Test that behavior changes are tracked by name correctly."""
        base = self.create_enhanced_layout_data(BASE_WITH_BEHAVIORS)
        modified = self.create_enhanced_layout_data(MODIFIED_BEHAVIORS)

        diff = diff_system.create_layout_diff(base, modified)

        # Access behavior changes directly from the diff object
        hold_tap_changes = diff.hold_taps

        # Verify specific behavior names are tracked
        assert "ht_a" in getattr(diff.hold_taps, "modified", [])
        assert "combo_space" in getattr(diff.combos, "modified", [])
        assert "macro_hello" in getattr(diff.macros, "modified", [])

        # New behaviors should be tracked by name
        assert "ht_new" in getattr(diff.hold_taps, "added", [])
        assert "combo_new" in getattr(diff.combos, "added", [])

    def test_behavior_patch_application(
        self, diff_system: LayoutDiffSystem, patch_system: LayoutPatchSystem
    ) -> None:
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

    def test_behavior_round_trip(
        self, diff_system: LayoutDiffSystem, patch_system: LayoutPatchSystem
    ) -> None:
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

    def test_scenario_execution(self, diff_system: LayoutDiffSystem) -> None:
        """Execute behavior test scenarios and verify expected changes."""
        for scenario in BEHAVIOR_SCENARIOS:
            base_name: str = scenario["from"]  # type: ignore
            modified_name: str = scenario["to"]  # type: ignore

            base = self.create_enhanced_layout_data(BEHAVIOR_TEST_CASES[base_name])
            modified = self.create_enhanced_layout_data(
                BEHAVIOR_TEST_CASES[modified_name]
            )

            diff = diff_system.create_layout_diff(base, modified)

            # Basic validation that diff was created and check for changes
            has_changes = any(
                [
                    getattr(diff.hold_taps, "added", [])
                    or getattr(diff.hold_taps, "removed", [])
                    or getattr(diff.hold_taps, "modified", []),
                    getattr(diff.combos, "added", [])
                    or getattr(diff.combos, "removed", [])
                    or getattr(diff.combos, "modified", []),
                    getattr(diff.macros, "added", [])
                    or getattr(diff.macros, "removed", [])
                    or getattr(diff.macros, "modified", []),
                ]
            )

            assert has_changes, (
                f"Scenario '{scenario['name']}' should detect behavior changes"
            )
