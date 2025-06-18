import json
from pathlib import Path

import pytest

from glovebox.layout.models import LayoutBinding, LayoutData, LayoutParam

from . import LayoutDiffSystem, LayoutPatchSystem
from .data_test import (
    BASE_LAYOUT,
    COMPLEX_CHANGE,
    TEST_CASES,
    TEST_SCENARIOS,
    LayerModel,
)


class TestLayoutDiffIntegration:
    """Integration tests for the complete diff/patch workflow."""

    @pytest.fixture
    def diff_system(self):
        """Create a diff system instance."""
        return LayoutDiffSystem()

    @pytest.fixture
    def patch_system(self):
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

    def test_scenario_execution(self, diff_system, patch_system):
        """Execute all test scenarios and verify results."""
        results = []

        for scenario in TEST_SCENARIOS:
            base_name = scenario["from"]
            modified_name = scenario["to"]

            base = self.create_layout_data(TEST_CASES[base_name])
            modified = self.create_layout_data(TEST_CASES[modified_name])

            # Create diff
            diff = diff_system.create_layout_diff(base, modified)

            # Apply patch
            patched = patch_system.apply_patch(base, diff)

            # Verify
            success = self._verify_layout_equality(patched, modified)

            results.append(
                {
                    "scenario": scenario["name"],
                    "success": success,
                    "operations": diff["statistics"]["total_operations"],
                    "description": scenario["description"],
                }
            )

        # All scenarios should pass
        assert all(r["success"] for r in results)

        # Print summary
        for result in results:
            print(f"\n{result['scenario']}: {'✓' if result['success'] else '✗'}")
            print(f"  Operations: {result['operations']}")
            print(f"  {result['description']}")

    def _verify_layout_equality(self, layout1: LayoutData, layout2: LayoutData) -> bool:
        """Verify two layouts are functionally equivalent."""
        # Compare layer names
        if layout1.layer_names != layout2.layer_names:
            return False

        # Compare number of layers
        if len(layout1.layers) != len(layout2.layers):
            return False

        # Compare each layer
        for _i, (layer1, layer2) in enumerate(
            zip(layout1.layers, layout2.layers, strict=False)
        ):
            if len(layer1) != len(layer2):
                return False

            for _j, (binding1, binding2) in enumerate(
                zip(layer1, layer2, strict=False)
            ):
                if binding1.value != binding2.value:
                    return False
                if len(binding1.params) != len(binding2.params):
                    return False
                for p1, p2 in zip(binding1.params, binding2.params, strict=False):
                    if p1.value != p2.value:
                        return False

        return True

    def test_save_and_load_diff(self, diff_system, tmp_path):
        """Test saving and loading diffs from files."""
        base = self.create_layout_data(BASE_LAYOUT)
        modified = self.create_layout_data(COMPLEX_CHANGE)

        # Create diff
        diff = diff_system.create_layout_diff(base, modified)

        # Save to file
        diff_file = tmp_path / "test.diff.json"
        with diff_file.open("w") as f:
            json.dump(diff, f, indent=2)

        # Load from file
        with diff_file.open() as f:
            loaded_diff = json.load(f)

        # Verify loaded diff has same structure
        assert loaded_diff["metadata"]["diff_type"] == "layout_diff_v1"
        assert len(loaded_diff["json_patch"]) == len(diff["json_patch"])
        assert loaded_diff["statistics"] == diff["statistics"]
