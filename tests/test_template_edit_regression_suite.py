"""Template-Edit Regression Test Suite.

This module provides a comprehensive test suite to ensure that template functionality
is not regressed when edit operations are performed. Run this test suite regularly
to catch any regressions in the template → edit → template workflow.

Usage:
    pytest tests/test_template_edit_regression_suite.py -v

Or run specific test categories:
    pytest tests/test_template_edit_regression_suite.py::TestTemplateEditRegressionSuite::test_basic_template_preservation -v
"""

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from glovebox.layout.models import LayoutData
from glovebox.layout.utils.field_parser import set_field_value_on_model


class TestTemplateEditRegressionSuite:
    """Comprehensive regression test suite for template-edit interactions."""

    def set_field_value(
        self, data: dict[str, Any], field_path: str, value: Any
    ) -> dict[str, Any]:
        """Helper to set field values in layout data."""
        layout = LayoutData.model_validate(data)
        set_field_value_on_model(layout, field_path, value)
        return layout.model_dump(mode="json", by_alias=True)

    @pytest.fixture
    def sample_template_layout(self):
        """Create a sample layout with various templates for testing."""
        return {
            "keyboard": "planck",
            "version": "1.0.0",
            "variables": {
                "user_name": "RegressionTester",
                "timing": {"fast": 180, "slow": 300},
                "build_info": {"version": "1.2.3", "date": "2024-01-15"},
                "features": {"combos": True, "macros": False},
            },
            "title": "Regression Test Layout for {{ variables.user_name }}",
            "creator": "{{ variables.user_name }} <{{ variables.user_name|lower }}@test.com>",
            "notes": """
Build: {{ variables.build_info.version }} ({{ variables.build_info.date }})
Timing: {{ variables.timing.fast }}ms / {{ variables.timing.slow }}ms
{% if variables.features.combos -%}
Combos: enabled
{%- else -%}
Combos: disabled
{%- endif %}
            """.strip(),
            "layer_names": ["Base", "Numbers"],
            "holdTaps": [
                {
                    "name": "regression_hold",
                    "description": "Test hold-tap for {{ variables.user_name }}",
                    "tappingTermMs": "{{ variables.timing.fast }}",
                    "quickTapMs": "{{ variables.timing.slow }}",
                    "flavor": "balanced",
                    "bindings": ["&kp", "&mo"],
                }
            ],
            "layers": [
                [
                    {"value": "&kp", "params": [{"value": "Q", "params": []}]},
                    {"value": "&kp", "params": [{"value": "W", "params": []}]},
                ],
                [
                    {"value": "&kp", "params": [{"value": "1", "params": []}]},
                    {"value": "&kp", "params": [{"value": "2", "params": []}]},
                ],
            ],
            "custom_defined_behaviors": """
// Regression test layout for {{ variables.user_name }}
// Build: {{ variables.build_info.version }}
// Generated on {{ variables.build_info.date }}
{% if variables.features.macros -%}
// Macros enabled
{%- endif %}
            """.strip(),
        }

    def test_basic_template_preservation(self, sample_template_layout):
        """Test that basic field edits preserve template syntax."""
        # Test multiple field edits
        data = sample_template_layout.copy()

        # Edit non-template fields
        updated_data = self.set_field_value(data, "version", "2.0.0")
        updated_data = self.set_field_value(updated_data, "keyboard", "test_board")

        # Verify all templates preserved
        assert "{{ variables.user_name }}" in updated_data["title"]
        assert "{{ variables.user_name|lower }}" in updated_data["creator"]
        assert "{{ variables.timing.fast }}" in updated_data["notes"]
        assert "{{ variables.build_info.version }}" in updated_data["notes"]
        assert "{% if variables.features.combos" in updated_data["notes"]
        assert "{{ variables.user_name }}" in updated_data["custom_defined_behaviors"]

        # Verify edits applied
        assert updated_data["version"] == "2.0.0"
        assert updated_data["keyboard"] == "test_board"

    def test_variable_editing_preserves_templates(self, sample_template_layout):
        """Test that editing variables preserves template references."""
        data = sample_template_layout.copy()

        # Edit variables at different nesting levels
        updated_data = self.set_field_value(data, "variables.user_name", "EditedUser")
        updated_data = self.set_field_value(updated_data, "variables.timing.fast", 200)
        updated_data = self.set_field_value(
            updated_data, "variables.build_info.version", "2.0.0"
        )
        updated_data = self.set_field_value(
            updated_data, "variables.features.combos", False
        )

        # Verify templates preserved
        assert "{{ variables.user_name }}" in updated_data["title"]
        assert "{{ variables.timing.fast }}" in updated_data["notes"]
        assert "{{ variables.build_info.version }}" in updated_data["notes"]
        assert "{% if variables.features.combos" in updated_data["notes"]

        # Verify variable values updated
        assert updated_data["variables"]["user_name"] == "EditedUser"
        assert updated_data["variables"]["timing"]["fast"] == 200
        assert updated_data["variables"]["build_info"]["version"] == "2.0.0"
        assert updated_data["variables"]["features"]["combos"] is False

    def test_template_processing_after_edits(self, sample_template_layout):
        """Test that templates process correctly after edits."""
        data = sample_template_layout.copy()

        # Make edits
        updated_data = self.set_field_value(data, "variables.user_name", "PostEditUser")
        updated_data = self.set_field_value(updated_data, "variables.timing.fast", 250)
        updated_data = self.set_field_value(
            updated_data, "variables.features.combos", False
        )

        # Process templates
        layout = LayoutData.load_with_templates(updated_data)

        # Verify templates processed with edited values
        assert layout.title == "Regression Test Layout for PostEditUser"
        assert layout.creator == "PostEditUser <postedituser@test.com>"
        assert "Timing: 250ms / 300ms" in layout.notes
        assert "Combos: disabled" in layout.notes
        assert layout.hold_taps[0].description == "Test hold-tap for PostEditUser"
        assert layout.hold_taps[0].tapping_term_ms == 250
        assert "PostEditUser" in layout.custom_defined_behaviors

    def test_adding_new_variables_and_templates(self, sample_template_layout):
        """Test adding new variables and template expressions."""
        data = sample_template_layout.copy()

        # Add new variables
        updated_data = self.set_field_value(
            data, "variables.device.name", "CustomDevice"
        )
        updated_data = self.set_field_value(
            updated_data, "variables.device.version", "3.1.4"
        )

        # Add new template expression
        updated_data = self.set_field_value(
            updated_data,
            "notes",
            "Device: {{ variables.device.name }} v{{ variables.device.version }} for {{ variables.user_name }}",
        )

        # Process templates
        layout = LayoutData.load_with_templates(updated_data)

        # Verify new templates work
        assert layout.notes == "Device: CustomDevice v3.1.4 for RegressionTester"

    def test_complex_conditional_logic(self, sample_template_layout):
        """Test complex conditional template logic after edits."""
        data = sample_template_layout.copy()

        # Add complex conditional template
        complex_template = """
Summary for {{ variables.user_name }}:
{% if variables.features.combos and variables.features.macros -%}
✓ Full feature set enabled
{%- elif variables.features.combos -%}
⚡ Combos only
{%- elif variables.features.macros -%}
🔧 Macros only
{%- else -%}
⚠ Basic configuration
{%- endif %}
Build: {{ variables.build_info.version }}
        """.strip()

        updated_data = self.set_field_value(data, "creator", complex_template)

        # Test different feature combinations
        test_cases: list[dict[str, Any]] = [
            {"combos": True, "macros": True, "expected": "✓ Full feature set enabled"},
            {"combos": True, "macros": False, "expected": "⚡ Combos only"},
            {"combos": False, "macros": True, "expected": "🔧 Macros only"},
            {"combos": False, "macros": False, "expected": "⚠ Basic configuration"},
        ]

        for case in test_cases:
            test_data = self.set_field_value(
                updated_data, "variables.features.combos", case["combos"]
            )
            test_data = self.set_field_value(
                test_data, "variables.features.macros", case["macros"]
            )

            layout = LayoutData.load_with_templates(test_data)
            expected_text = str(case["expected"])
            assert expected_text in layout.creator
            assert "Summary for RegressionTester" in layout.creator
            assert "Build: 1.2.3" in layout.creator

    def test_layer_operations_preserve_templates(self, sample_template_layout):
        """Test that layer operations preserve templates."""
        data = sample_template_layout.copy()

        # Add layer
        layer_names = data["layer_names"].copy()
        layer_names.append("Symbols")
        updated_data = self.set_field_value(data, "layer_names", layer_names)

        # Add layer content
        layers = data["layers"].copy()
        layers.append([{"value": "&kp", "params": [{"value": "EXCL", "params": []}]}])
        updated_data = self.set_field_value(updated_data, "layers", layers)

        # Verify templates preserved
        assert "{{ variables.user_name }}" in updated_data["title"]
        assert "{{ variables.timing.fast }}" in updated_data["notes"]

        # Verify layer added
        assert len(updated_data["layer_names"]) == 3
        assert updated_data["layer_names"][2] == "Symbols"
        assert len(updated_data["layers"]) == 3

    def test_multiple_edit_cycles_stability(self, sample_template_layout):
        """Test stability through multiple edit cycles."""
        data = sample_template_layout.copy()

        # Perform 3 edit cycles
        for cycle in range(3):
            # Edit different aspects each cycle
            updated_data = self.set_field_value(
                data, "variables.user_name", f"CycleUser{cycle}"
            )
            updated_data = self.set_field_value(
                updated_data, "variables.timing.fast", 180 + cycle * 20
            )
            updated_data = self.set_field_value(
                updated_data, "variables.build_info.version", f"1.{cycle}.0"
            )

            # Process templates
            layout = LayoutData.load_with_templates(updated_data)

            # Verify templates work correctly each cycle
            assert layout.title == f"Regression Test Layout for CycleUser{cycle}"
            assert f"cycleuser{cycle}@test.com" in layout.creator
            assert f"Timing: {180 + cycle * 20}ms" in layout.notes
            assert f"Build: 1.{cycle}.0" in layout.notes
            assert layout.hold_taps[0].tapping_term_ms == 180 + cycle * 20

            # Update data for next cycle
            data = updated_data

    def test_template_error_recovery(self, sample_template_layout):
        """Test error recovery when templates have issues."""
        data = sample_template_layout.copy()

        # Add template with potential error
        updated_data = self.set_field_value(
            data,
            "title",
            "Layout for {{ variables.user_name }} v{{ variables.nonexistent_var | default('unknown') }}",
        )

        # Should handle gracefully
        layout = LayoutData.load_with_templates(updated_data)

        # Should process successfully with fallback
        assert "Layout for RegressionTester" in layout.title
        assert "unknown" in layout.title or "RegressionTester" in layout.title

    def test_flattened_dict_after_edits(self, sample_template_layout):
        """Test to_flattened_dict removes variables after template processing."""
        data = sample_template_layout.copy()

        # Edit variables
        updated_data = self.set_field_value(data, "variables.user_name", "FlattenUser")
        updated_data = self.set_field_value(updated_data, "variables.timing.fast", 275)

        # Create layout and flatten
        layout = LayoutData.model_validate(updated_data)
        flattened = layout.to_flattened_dict()

        # Verify variables removed and templates processed
        assert "variables" not in flattened
        assert flattened["title"] == "Regression Test Layout for FlattenUser"
        assert "Timing: 275ms" in flattened["notes"]
        assert flattened["holdTaps"][0]["tappingTermMs"] == 275

    def test_roundtrip_edit_template_edit(self, sample_template_layout):
        """Test roundtrip: edit → template → edit → template."""
        data = sample_template_layout.copy()

        # Step 1: Edit
        step1_data = self.set_field_value(data, "variables.user_name", "Step1User")

        # Step 2: Process templates
        step1_layout = LayoutData.load_with_templates(step1_data)
        assert step1_layout.title == "Regression Test Layout for Step1User"

        # Step 3: Edit again
        step2_data = step1_layout.model_dump(mode="json", by_alias=True)
        step2_data = self.set_field_value(
            step2_data, "variables.user_name", "Step2User"
        )
        step2_data = self.set_field_value(step2_data, "variables.timing.fast", 225)

        # Step 4: Process templates again
        step2_layout = LayoutData.load_with_templates(step2_data)

        # Verify final state
        assert step2_layout.title == "Regression Test Layout for Step2User"
        assert "step2user@test.com" in step2_layout.creator
        assert step2_layout.hold_taps[0].tapping_term_ms == 225

    def test_compilation_workflow_integration(self, sample_template_layout):
        """Test the complete edit → compile workflow with templates."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create layout file with templates
            layout_file = temp_path / "template_test.json"
            data = sample_template_layout.copy()

            # Edit variables
            updated_data = self.set_field_value(
                data, "variables.user_name", "CompileUser"
            )
            updated_data = self.set_field_value(
                updated_data, "variables.timing.fast", 190
            )

            # Save to file
            layout_file.write_text(json.dumps(updated_data, indent=2))

            # Load with templates (simulating CLI compilation)
            layout = LayoutData.load_with_templates(updated_data)

            # Verify templates processed for compilation
            assert layout.title == "Regression Test Layout for CompileUser"
            assert layout.hold_taps[0].tapping_term_ms == 190
            assert "CompileUser" in layout.custom_defined_behaviors

            # Verify can be serialized (what CLI compile does)
            compiled_data = layout.model_dump(mode="json", by_alias=True)
            assert compiled_data["title"] == "Regression Test Layout for CompileUser"
            assert compiled_data["holdTaps"][0]["tappingTermMs"] == 190


def run_regression_suite():
    """Convenience function to run the full regression suite."""
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_template_edit_regression_suite.py",
            "-v",
            "--tb=short",
        ],
        capture_output=True,
        text=True,
    )

    print("Template-Edit Regression Test Suite Results:")
    print("=" * 50)
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)

    if result.returncode == 0:
        print("✅ All regression tests passed!")
    else:
        print("❌ Some regression tests failed!")

    return result.returncode == 0


if __name__ == "__main__":
    success = run_regression_suite()
    exit(0 if success else 1)
