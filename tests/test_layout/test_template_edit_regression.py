"""Regression tests for template functionality during edit operations.

This module ensures that editing operations don't interfere with Jinja2 templating
and that templates continue to work correctly after various edit operations.
"""

from typing import Any

import pytest

from glovebox.layout.models import LayoutData
from glovebox.layout.utils.field_parser import set_field_value_on_model


class TestTemplateEditRegression:
    """Test template preservation and processing during edit operations."""

    @pytest.fixture
    def template_layout_data(self):
        """Create a layout with various templates for testing."""
        return {
            "keyboard": "test_keyboard",
            "version": "1.0.0",
            "variables": {
                "user_name": "TestUser",
                "timing": {
                    "fast": 150,
                    "slow": 300
                },
                "features": {
                    "combos_enabled": True
                },
                "layer_count": 2
            },
            "title": "Layout for {{ variables.user_name }}",
            "creator": "Created by {{ variables.user_name }}",
            "notes": "Fast: {{ variables.timing.fast }}ms, Slow: {{ variables.timing.slow }}ms",
            "layer_names": ["Base", "Number"],
            "holdTaps": [
                {
                    "name": "test_hold",
                    "tappingTermMs": "{{ variables.timing.fast }}",
                    "quickTapMs": "{{ variables.timing.slow }}",
                    "flavor": "balanced",
                    "bindings": ["&kp", "&mo"]
                }
            ],
            "layers": [
                [
                    {"value": "&kp", "params": [{"value": "A", "params": []}]},
                    {"value": "&kp", "params": [{"value": "B", "params": []}]}
                ],
                [
                    {"value": "&kp", "params": [{"value": "1", "params": []}]},
                    {"value": "&mo", "params": [{"value": "0", "params": []}]}
                ]
            ],
            "custom_defined_behaviors": """
// Custom behaviors for {{ variables.user_name }}
// Layer count: {{ variables.layer_count }}
{% if variables.features.combos_enabled -%}
// Combos are enabled
{%- endif %}
            """.strip()
        }

    def set_field_value(self, data: dict, field_path: str, value: Any) -> dict:
        """Helper to set field values in layout data."""
        # Create a LayoutData instance temporarily to use the field setter
        layout = LayoutData.model_validate(data)
        set_field_value_on_model(layout, field_path, value)
        return layout.model_dump(mode="json", by_alias=True)

    def test_field_edit_preserves_templates(self, template_layout_data):
        """Test that field edits preserve template syntax in unmodified fields."""
        # Load layout with templates (but don't process them yet)
        layout = LayoutData.model_validate(template_layout_data)
        
        # Edit a non-template field
        updated_data = self.set_field_value(
            layout.model_dump(mode="json", by_alias=True),
            "version",
            "2.0.0"
        )
        
        # Verify templates are preserved in source
        assert "{{ variables.user_name }}" in updated_data["title"]
        assert "{{ variables.user_name }}" in updated_data["creator"]
        assert "{{ variables.timing.fast }}" in updated_data["notes"]
        assert "{{ variables.timing.fast }}" in str(updated_data["holdTaps"][0]["tappingTermMs"])
        assert "{{ variables.user_name }}" in updated_data["custom_defined_behaviors"]
        
        # Verify the edit was applied
        assert updated_data["version"] == "2.0.0"

    def test_variable_edit_preserves_other_templates(self, template_layout_data):
        """Test that editing variables preserves templates that reference them."""
        # Load layout
        layout = LayoutData.model_validate(template_layout_data)
        
        # Edit a variable value
        updated_data = self.set_field_value(
            layout.model_dump(mode="json", by_alias=True),
            "variables.user_name",
            "EditedUser"
        )
        
        # Verify templates are preserved (not resolved)
        assert "{{ variables.user_name }}" in updated_data["title"]
        assert "{{ variables.user_name }}" in updated_data["creator"]
        assert "{{ variables.timing.fast }}" in updated_data["notes"]
        assert "{{ variables.user_name }}" in updated_data["custom_defined_behaviors"]
        
        # Verify the variable was updated
        assert updated_data["variables"]["user_name"] == "EditedUser"

    def test_adding_new_template_field(self, template_layout_data):
        """Test that new template expressions can be added via field editing."""
        # Load layout
        layout = LayoutData.model_validate(template_layout_data)
        
        # Add a new field with template syntax
        updated_data = self.set_field_value(
            layout.model_dump(mode="json", by_alias=True),
            "tags",
            ["{{ variables.user_name }}", "template-test"]
        )
        
        # Verify new template field is preserved
        assert updated_data["tags"] == ["{{ variables.user_name }}", "template-test"]
        
        # Verify other templates are still preserved
        assert "{{ variables.user_name }}" in updated_data["title"]

    def test_adding_new_variable_and_template(self, template_layout_data):
        """Test adding new variables and referencing them in templates."""
        # Load layout
        layout = LayoutData.model_validate(template_layout_data)
        data = layout.model_dump(mode="json", by_alias=True)
        
        # Add new variable
        updated_data = self.set_field_value(data, "variables.combo_timeout", 250)
        
        # Add template that uses the new variable
        updated_data = self.set_field_value(
            updated_data,
            "notes",
            "Fast: {{ variables.timing.fast }}ms, Combo: {{ variables.combo_timeout }}ms"
        )
        
        # Verify new variable was added
        assert updated_data["variables"]["combo_timeout"] == 250
        
        # Verify new template syntax is preserved
        assert "{{ variables.combo_timeout }}" in updated_data["notes"]
        assert "{{ variables.timing.fast }}" in updated_data["notes"]

    def test_template_processing_after_field_edits(self, template_layout_data):
        """Test that templates process correctly after field edits."""
        # Load layout and make edits
        layout = LayoutData.model_validate(template_layout_data)
        data = layout.model_dump(mode="json", by_alias=True)
        
        # Edit variable values
        updated_data = self.set_field_value(data, "variables.user_name", "EditedUser")
        updated_data = self.set_field_value(updated_data, "variables.timing.fast", 200)
        updated_data = self.set_field_value(updated_data, "version", "2.0.0")
        
        # Create new layout and process templates
        edited_layout = LayoutData.model_validate(updated_data)
        processed_layout = edited_layout.process_templates()
        
        # Verify templates resolved with new values
        assert processed_layout.title == "Layout for EditedUser"
        assert processed_layout.creator == "Created by EditedUser"
        assert "Fast: 200ms" in processed_layout.notes
        assert processed_layout.version == "2.0.0"
        
        # Verify behavior templates processed
        assert processed_layout.hold_taps[0].tapping_term_ms == 200
        assert processed_layout.hold_taps[0].quick_tap_ms == 300
        
        # Verify custom code templates processed
        assert "EditedUser" in processed_layout.custom_defined_behaviors
        assert "Layer count: 2" in processed_layout.custom_defined_behaviors

    def test_template_processing_with_new_variables(self, template_layout_data):
        """Test template processing works with newly added variables."""
        # Load layout and add new variable/template
        layout = LayoutData.model_validate(template_layout_data)
        data = layout.model_dump(mode="json", by_alias=True)
        
        # Add new variable and template
        updated_data = self.set_field_value(data, "variables.build_id", "test-123")
        updated_data = self.set_field_value(
            updated_data,
            "notes",
            "User: {{ variables.user_name }}, Build: {{ variables.build_id }}"
        )
        
        # Process templates
        edited_layout = LayoutData.model_validate(updated_data)
        processed_layout = edited_layout.process_templates()
        
        # Verify new template processed correctly
        assert processed_layout.notes == "User: TestUser, Build: test-123"

    def test_complex_template_expressions_preserved(self, template_layout_data):
        """Test that complex Jinja2 expressions are preserved during edits."""
        # Load layout
        layout = LayoutData.model_validate(template_layout_data)
        data = layout.model_dump(mode="json", by_alias=True)
        
        # Add complex template expression
        complex_template = """
{% if variables.features.combos_enabled -%}
Combos: enabled ({{ variables.timing.slow }}ms)
{%- else -%}
Combos: disabled
{%- endif %}
User: {{ variables.user_name|upper }}
        """.strip()
        
        updated_data = self.set_field_value(data, "creator", complex_template)
        
        # Make unrelated edit
        updated_data = self.set_field_value(updated_data, "version", "3.0.0")
        
        # Verify complex template syntax preserved
        assert "{% if variables.features.combos_enabled %}" in updated_data["creator"]
        assert "{{ variables.user_name|upper }}" in updated_data["creator"]
        
        # Process templates to verify they work
        edited_layout = LayoutData.model_validate(updated_data)
        processed_layout = edited_layout.process_templates()
        
        # Verify complex template processed correctly
        assert "Combos: enabled (300ms)" in processed_layout.creator
        assert "User: TESTUSER" in processed_layout.creator

    def test_load_with_templates_after_edits(self, template_layout_data):
        """Test that load_with_templates works correctly after edits."""
        # Make edits to the raw data
        data = template_layout_data.copy()
        updated_data = self.set_field_value(data, "variables.user_name", "LoadTestUser")
        updated_data = self.set_field_value(updated_data, "variables.timing.fast", 175)
        
        # Use load_with_templates (the main entry point)
        layout = LayoutData.load_with_templates(updated_data)
        
        # Verify templates were processed with edited values
        assert layout.title == "Layout for LoadTestUser"
        assert layout.creator == "Created by LoadTestUser"
        assert "Fast: 175ms" in layout.notes
        assert layout.hold_taps[0].tapping_term_ms == 175
        assert "LoadTestUser" in layout.custom_defined_behaviors

    def test_to_flattened_dict_after_edits(self, template_layout_data):
        """Test that to_flattened_dict works correctly after edits."""
        # Load and edit layout
        layout = LayoutData.model_validate(template_layout_data)
        data = layout.model_dump(mode="json", by_alias=True)
        
        # Edit variables
        updated_data = self.set_field_value(data, "variables.user_name", "FlattenUser")
        updated_data = self.set_field_value(updated_data, "variables.timing.slow", 350)
        
        # Create layout and flatten
        edited_layout = LayoutData.model_validate(updated_data)
        flattened = edited_layout.to_flattened_dict()
        
        # Verify templates resolved and variables section removed
        assert "variables" not in flattened
        assert flattened["title"] == "Layout for FlattenUser"
        assert flattened["creator"] == "Created by FlattenUser"
        assert "Slow: 350ms" in flattened["notes"]
        assert flattened["holdTaps"][0]["quickTapMs"] == 350


class TestLayerOperationTemplateRegression:
    """Test template preservation during layer operations."""

    @pytest.fixture
    def template_layout_with_layers(self):
        """Create layout with templates in layer-related fields."""
        return {
            "keyboard": "test_keyboard",
            "version": "1.0.0",
            "variables": {
                "user_name": "LayerTestUser",
                "base_layer": "QWERTY",
                "num_layers": 3
            },
            "title": "{{ variables.num_layers }}-layer layout for {{ variables.user_name }}",
            "layer_names": ["{{ variables.base_layer }}", "Numbers", "Symbols"],
            "layers": [
                [{"value": "&kp", "params": [{"value": "A", "params": []}]}],
                [{"value": "&kp", "params": [{"value": "1", "params": []}]}],
                [{"value": "&kp", "params": [{"value": "EXCL", "params": []}]}]
            ],
            "custom_defined_behaviors": "// Layers for {{ variables.user_name }}: {{ variables.num_layers }}"
        }

    def test_add_layer_preserves_templates(self, template_layout_with_layers):
        """Test that adding layers preserves existing templates."""
        # Load layout
        layout = LayoutData.model_validate(template_layout_with_layers)
        data = layout.model_dump(mode="json", by_alias=True)
        
        # Simulate adding a layer (what the CLI does)
        # Add to layer_names
        layer_names = data["layer_names"].copy()
        layer_names.append("NewLayer")
        updated_data = self.set_field_value(data, "layer_names", layer_names)
        
        # Add empty layer
        layers = data["layers"].copy()
        layers.append([])
        updated_data = self.set_field_value(updated_data, "layers", layers)
        
        # Verify templates preserved
        assert "{{ variables.user_name }}" in updated_data["title"]
        assert "{{ variables.num_layers }}" in updated_data["title"]
        assert "{{ variables.base_layer }}" in updated_data["layer_names"][0]
        assert "{{ variables.user_name }}" in updated_data["custom_defined_behaviors"]
        
        # Verify layer was added
        assert len(updated_data["layer_names"]) == 4
        assert updated_data["layer_names"][3] == "NewLayer"
        assert len(updated_data["layers"]) == 4

    def test_copy_layer_preserves_templates(self, template_layout_with_layers):
        """Test that copying layers preserves templates."""
        # Load layout
        layout = LayoutData.model_validate(template_layout_with_layers)
        data = layout.model_dump(mode="json", by_alias=True)
        
        # Simulate copying a layer
        layer_names = data["layer_names"].copy()
        layer_names.append("CopiedLayer")
        updated_data = self.set_field_value(data, "layer_names", layer_names)
        
        # Copy first layer content
        layers = data["layers"].copy()
        layers.append(layers[0].copy())  # Copy first layer
        updated_data = self.set_field_value(updated_data, "layers", layers)
        
        # Verify templates preserved
        assert "{{ variables.base_layer }}" in updated_data["layer_names"][0]
        assert "{{ variables.user_name }}" in updated_data["title"]
        
        # Verify layer was copied
        assert len(updated_data["layers"]) == 4
        assert updated_data["layers"][3] == updated_data["layers"][0]

    def test_remove_layer_preserves_templates(self, template_layout_with_layers):
        """Test that removing layers preserves templates."""
        # Load layout
        layout = LayoutData.model_validate(template_layout_with_layers)
        data = layout.model_dump(mode="json", by_alias=True)
        
        # Simulate removing last layer
        layer_names = data["layer_names"][:-1]  # Remove last
        updated_data = self.set_field_value(data, "layer_names", layer_names)
        
        layers = data["layers"][:-1]  # Remove last layer
        updated_data = self.set_field_value(updated_data, "layers", layers)
        
        # Verify templates preserved
        assert "{{ variables.base_layer }}" in updated_data["layer_names"][0]
        assert "{{ variables.user_name }}" in updated_data["title"]
        assert "{{ variables.num_layers }}" in updated_data["custom_defined_behaviors"]
        
        # Verify layer was removed
        assert len(updated_data["layer_names"]) == 2
        assert len(updated_data["layers"]) == 2

    def test_layer_operations_with_template_processing(self, template_layout_with_layers):
        """Test that templates work correctly after layer operations."""
        # Load layout and perform layer operations
        layout = LayoutData.model_validate(template_layout_with_layers)
        data = layout.model_dump(mode="json", by_alias=True)
        
        # Add layer and update layer count
        layer_names = data["layer_names"].copy()
        layer_names.append("FunctionKeys")
        updated_data = self.set_field_value(data, "layer_names", layer_names)
        
        layers = data["layers"].copy()
        layers.append([{"value": "&kp", "params": [{"value": "F1", "params": []}]}])
        updated_data = self.set_field_value(updated_data, "layers", layers)
        
        # Update variable to reflect new layer count
        updated_data = self.set_field_value(updated_data, "variables.num_layers", 4)
        
        # Process templates
        edited_layout = LayoutData.model_validate(updated_data)
        processed_layout = edited_layout.process_templates()
        
        # Verify templates processed with updated values
        assert processed_layout.title == "4-layer layout for LayerTestUser"
        assert processed_layout.layer_names[0] == "QWERTY"  # Template resolved
        assert processed_layout.layer_names[3] == "FunctionKeys"  # New layer
        assert "LayerTestUser" in processed_layout.custom_defined_behaviors
        assert "4" in processed_layout.custom_defined_behaviors


class TestTemplateCompilationRegression:
    """Integration tests for template processing during compilation workflow."""

    @pytest.fixture
    def compilation_test_layout(self):
        """Create layout optimized for compilation testing."""
        return {
            "keyboard": "planck",  # Use real keyboard for compilation
            "version": "1.0.0",
            "variables": {
                "user_name": "CompileUser",
                "hold_timing": 200,
                "tap_timing": 150
            },
            "title": "Compilation test for {{ variables.user_name }}",
            "creator": "{{ variables.user_name }}",
            "notes": "Hold: {{ variables.hold_timing }}ms, Tap: {{ variables.tap_timing }}ms",
            "layer_names": ["QWERTY"],
            "holdTaps": [
                {
                    "name": "compile_test_hold",
                    "tappingTermMs": "{{ variables.hold_timing }}",
                    "quickTapMs": "{{ variables.tap_timing }}",
                    "flavor": "balanced",
                    "bindings": ["&kp", "&mo"]
                }
            ],
            "layers": [
                [
                    {"value": "&kp", "params": [{"value": "Q", "params": []}]},
                    {"value": "&kp", "params": [{"value": "W", "params": []}]},
                    {"value": "&kp", "params": [{"value": "E", "params": []}]}
                ]
            ],
            "custom_defined_behaviors": "// Compiled for {{ variables.user_name }}"
        }

    def test_load_with_templates_preserves_edit_compatibility(self, compilation_test_layout):
        """Test that load_with_templates preserves ability to edit templates."""
        # Load with templates processed
        processed_layout = LayoutData.load_with_templates(compilation_test_layout)
        
        # Convert back to dict for editing
        data = processed_layout.model_dump(mode="json", by_alias=True)
        
        # Edit a variable in the processed data
        updated_data = self.set_field_value(data, "variables.user_name", "PostProcessUser")
        
        # Load again with templates
        reprocessed_layout = LayoutData.load_with_templates(updated_data)
        
        # Verify templates processed with new value
        assert reprocessed_layout.title == "Compilation test for PostProcessUser"
        assert reprocessed_layout.creator == "PostProcessUser"
        assert "PostProcessUser" in reprocessed_layout.custom_defined_behaviors

    def test_edit_then_compile_workflow(self, compilation_test_layout):
        """Test the complete edit → compile workflow with templates."""
        # Step 1: Edit the layout
        data = compilation_test_layout.copy()
        updated_data = self.set_field_value(data, "variables.user_name", "WorkflowUser")
        updated_data = self.set_field_value(updated_data, "variables.hold_timing", 250)
        
        # Step 2: Simulate compilation loading (what the CLI does)
        layout = LayoutData.load_with_templates(updated_data)
        
        # Step 3: Verify templates processed correctly for compilation
        assert layout.title == "Compilation test for WorkflowUser"
        assert layout.creator == "WorkflowUser"
        assert "Hold: 250ms" in layout.notes
        assert layout.hold_taps[0].tapping_term_ms == 250
        assert layout.hold_taps[0].quick_tap_ms == 150
        assert "WorkflowUser" in layout.custom_defined_behaviors
        
        # Step 4: Verify can be serialized for compilation (removes variables)
        flattened = layout.to_flattened_dict()
        assert "variables" not in flattened
        assert flattened["title"] == "Compilation test for WorkflowUser"
        assert flattened["holdTaps"][0]["tappingTermMs"] == 250

    def test_multiple_edit_cycles_preserve_templates(self, compilation_test_layout):
        """Test that multiple edit cycles don't degrade template functionality."""
        data = compilation_test_layout.copy()
        
        # Perform multiple edit cycles
        for i in range(3):
            # Edit variables
            updated_data = self.set_field_value(data, "variables.user_name", f"User{i}")
            updated_data = self.set_field_value(updated_data, "variables.hold_timing", 200 + i * 10)
            
            # Add new template field
            updated_data = self.set_field_value(
                updated_data,
                "notes",
                f"Cycle {i}: Hold {{ variables.hold_timing }}ms for {{ variables.user_name }}"
            )
            
            # Process templates
            layout = LayoutData.load_with_templates(updated_data)
            
            # Verify templates work
            assert layout.title == f"Compilation test for User{i}"
            assert layout.creator == f"User{i}"
            assert f"Cycle {i}: Hold {200 + i * 10}ms for User{i}" == layout.notes
            assert layout.hold_taps[0].tapping_term_ms == 200 + i * 10
            
            # Update data for next cycle
            data = updated_data

    def test_template_error_handling_after_edits(self, compilation_test_layout):
        """Test that template error handling works after edits."""
        # Create invalid template through editing
        data = compilation_test_layout.copy()
        
        # Add invalid template syntax
        updated_data = self.set_field_value(
            data,
            "title",
            "Invalid template: {{ variables.nonexistent.field }}"
        )
        
        # Should not raise exception, should fallback gracefully
        layout = LayoutData.load_with_templates(updated_data)
        
        # Verify graceful fallback (returns original if template fails)
        # The exact behavior depends on implementation, but should not crash
        assert layout is not None
        assert hasattr(layout, 'title')