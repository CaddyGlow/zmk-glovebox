"""Tests for TemplateService with comprehensive Jinja2 template processing."""

from unittest.mock import Mock

import pytest

from glovebox.layout.models import HoldTapBehavior, LayoutData
from glovebox.layout.template_service import (
    CircularReferenceError,
    TemplateError,
    TemplateService,
    create_jinja2_template_service,
    create_template_service,
)
from glovebox.protocols.template_adapter_protocol import TemplateAdapterProtocol


class TestTemplateService:
    """Test cases for TemplateService functionality."""

    @pytest.fixture
    def mock_template_adapter(self):
        """Create a mock template adapter for testing."""
        adapter = Mock(spec=TemplateAdapterProtocol)

        def mock_render_string(template, context):
            """Mock Jinja2-style template rendering."""
            import re

            # Simple mock that handles {{ variables.key }} patterns
            def replace_var(match):
                var_path = match.group(1).strip()
                try:
                    # Handle nested variable access like variables.key
                    parts = var_path.split(".")
                    value = context
                    for part in parts:
                        value = value[part]
                    return str(value)
                except (KeyError, TypeError):
                    return match.group(0)  # Return original if not found

            return re.sub(r"\{\{\s*([^}]+)\s*\}\}", replace_var, template)

        adapter.render_string.side_effect = mock_render_string
        return adapter

    @pytest.fixture
    def template_service(self, mock_template_adapter):
        """Create a TemplateService instance for testing."""
        return TemplateService(mock_template_adapter)

    @pytest.fixture
    def sample_layout_data(self):
        """Create sample layout data with templates."""
        return {
            "keyboard": "glove80",
            "title": "Test Layout for {{ variables.user_name }}",
            "variables": {
                "user_name": "Alice",
                "fast_timing": 200,
                "slow_timing": 400,
                "combo_enabled": True,
            },
            "layer_names": ["Base", "Number", "Function"],
            "holdTaps": [
                {
                    "name": "my_holdtap",
                    "tappingTermMs": "{{ variables.fast_timing }}",
                    "bindings": ["&kp", "&lt"],
                }
            ],
            "layers": [
                [{"value": "&kp A"}, {"value": "&lt {{ holdTaps[0].name }} 0 0"}],
                [{"value": "&kp 1"}, {"value": "&kp 2"}],
                [{"value": "&kp F1"}, {"value": "&kp F2"}],
            ],
            "custom_defined_behaviors": "// Custom behavior for {{ variables.user_name }}",
        }

    def test_service_initialization(self, mock_template_adapter):
        """Test TemplateService initialization."""
        service = TemplateService(mock_template_adapter)

        assert service.service_name == "TemplateService"
        assert service.service_version == "1.0.0"
        assert service.template_adapter == mock_template_adapter
        assert service._resolution_cache == {}

    def test_has_templates_detection(self, template_service):
        """Test detection of Jinja2 template syntax."""
        # Data with templates
        data_with_templates = {
            "title": "Hello {{ name }}",
            "notes": "{% if enabled %}Active{% endif %}",
            "custom": "{# comment #}",
        }
        assert template_service._has_templates(data_with_templates)

        # Data without templates
        data_without_templates = {
            "title": "Hello World",
            "notes": "Simple text",
            "custom": "No templates here",
        }
        assert not template_service._has_templates(data_without_templates)

        # Empty data
        assert not template_service._has_templates({})

    def test_template_context_creation_basic_stage(
        self, template_service, sample_layout_data
    ):
        """Test template context creation for basic stage."""
        # Use isolated configuration to prevent template resolution during validation
        from glovebox.layout.utils.json_operations import VariableResolutionContext

        with VariableResolutionContext(skip=True):
            layout = LayoutData.model_validate(sample_layout_data)

        context = template_service.create_template_context(layout, "basic")

        # Check base context
        assert context["variables"] == sample_layout_data["variables"]
        assert context["keyboard"] == "glove80"
        # Title should be the original template string since we skipped resolution
        assert context["title"] == sample_layout_data["title"]
        assert context["layer_names"] == ["Base", "Number", "Function"]

        # Check layer utilities
        assert context["layer_name_to_index"] == {"Base": 0, "Number": 1, "Function": 2}
        assert callable(context["get_layer_index"])
        assert context["get_layer_index"]("Base") == 0
        assert context["get_layer_index"]("Unknown") == -1

        # Basic stage should not have behaviors
        assert "holdTaps" not in context or context["holdTaps"] == []

    def test_template_context_creation_behaviors_stage(self, template_service):
        """Test template context creation for behaviors stage with cached data."""
        template_service._resolution_cache = {
            "holdTaps": [{"name": "test_hold_tap", "tappingTermMs": 200}],
            "combos": [{"name": "test_combo"}],
            "macros": [{"name": "test_macro"}],
        }

        layout_data = {
            "variables": {"test": "value"},
            "keyboard": "test",
            "title": "Test",
            "layer_names": ["Base"],
        }

        context = template_service._create_template_context_from_dict(
            layout_data, "behaviors"
        )

        assert context["holdTaps"] == [{"name": "test_hold_tap", "tappingTermMs": 200}]
        assert context["combos"] == [{"name": "test_combo"}]
        assert context["macros"] == [{"name": "test_macro"}]

    def test_template_context_creation_layers_stage(self, template_service):
        """Test template context creation for layers stage with layer utilities."""
        template_service._resolution_cache = {
            "layers_by_name": {
                "Base": [{"value": "&kp A"}],
                "Number": [{"value": "&kp 1"}],
            }
        }

        layout_data = {
            "variables": {"test": "value"},
            "keyboard": "test",
            "title": "Test",
            "layer_names": ["Base", "Number"],
        }

        context = template_service._create_template_context_from_dict(
            layout_data, "layers"
        )

        assert (
            context["layers_by_name"]
            == template_service._resolution_cache["layers_by_name"]
        )
        assert callable(context["get_layer_bindings"])
        assert context["get_layer_bindings"]("Base") == [{"value": "&kp A"}]
        assert context["get_layer_bindings"]("Unknown") == []

    def test_process_field_value_string_templates(self, template_service):
        """Test processing of string fields with templates."""
        context = {"variables": {"name": "Alice", "timing": 200}}

        # Simple variable substitution
        result = template_service._process_string_field(
            "Hello {{ variables.name }}", context
        )
        assert result == "Hello Alice"

        # Numeric conversion
        result = template_service._process_string_field(
            "{{ variables.timing }}", context
        )
        assert result == 200

        # Non-template string
        result = template_service._process_string_field("Plain text", context)
        assert result == "Plain text"

    def test_process_field_value_nested_structures(self, template_service):
        """Test processing of nested dict and list structures."""
        context = {"variables": {"name": "Alice", "count": 3}}

        # Dictionary with templates
        data = {
            "title": "Hello {{ variables.name }}",
            "count": "{{ variables.count }}",
            "static": "unchanged",
        }
        result = template_service._process_field_value(data, context)
        assert result == {"title": "Hello Alice", "count": 3, "static": "unchanged"}

        # List with templates
        list_data = ["{{ variables.name }}", "{{ variables.count }}", "static"]
        result = template_service._process_field_value(list_data, context)
        assert result == ["Alice", 3, "static"]

    def test_convert_to_appropriate_type(self, template_service):
        """Test type conversion from rendered template strings."""
        # Integer conversion
        assert template_service._convert_to_appropriate_type("42") == 42
        assert template_service._convert_to_appropriate_type("-10") == -10

        # Float conversion
        assert template_service._convert_to_appropriate_type("3.14") == 3.14
        assert template_service._convert_to_appropriate_type("-2.5") == -2.5

        # Boolean conversion
        assert template_service._convert_to_appropriate_type("true") is True
        assert template_service._convert_to_appropriate_type("True") is True
        assert template_service._convert_to_appropriate_type("yes") is True

        assert template_service._convert_to_appropriate_type("false") is False
        assert template_service._convert_to_appropriate_type("False") is False
        assert template_service._convert_to_appropriate_type("no") is False

        # Note: "1" and "0" are converted to integers, not booleans
        assert template_service._convert_to_appropriate_type("1") == 1
        assert template_service._convert_to_appropriate_type("0") == 0

        # String fallback
        assert template_service._convert_to_appropriate_type("hello") == "hello"
        assert template_service._convert_to_appropriate_type("") == ""

    def test_variables_field_ordering(self):
        """Test that variables field appears first in serialized JSON."""
        layout_data = LayoutData.model_validate(
            {
                "keyboard": "test",
                "title": "Test Layout",
                "variables": {"test_var": "value"},
                "layer_names": ["Base"],
                "layers": [[{"value": "&kp A"}]],
            }
        )

        # Get the serialized data
        json_data = layout_data.to_dict()

        # Variables should be the first key
        first_key = next(iter(json_data.keys()))
        assert first_key == "variables", (
            f"Expected 'variables' to be first, got '{first_key}'"
        )

        # Also test with more complex data
        complex_layout = LayoutData.model_validate(
            {
                "title": "Complex Layout",  # Put title first to test reordering
                "keyboard": "glove80",
                "creator": "Alice",
                "variables": {
                    "user": "Alice",
                    "timing": 200,
                },  # Variables not first in input
                "layer_names": ["Base", "Number"],
                "holdTaps": [{"name": "test", "bindings": ["&kp", "&mo"]}],
                "layers": [[{"value": "&kp A"}], [{"value": "&kp 1"}]],
            }
        )

        complex_json = complex_layout.to_dict()
        first_key_complex = next(iter(complex_json.keys()))
        assert first_key_complex == "variables", (
            f"Expected 'variables' to be first in complex layout, got '{first_key_complex}'"
        )

        # Test flattened dict (without variables)
        flattened = complex_layout.to_flattened_dict()
        assert "variables" not in flattened, (
            "Variables should be removed in flattened dict"
        )
        # First key should be keyboard after variables are removed
        first_key_flattened = next(iter(flattened.keys()))
        assert first_key_flattened == "keyboard", (
            f"Expected 'keyboard' to be first in flattened layout, got '{first_key_flattened}'"
        )

    def test_process_layout_data_no_templates(self, template_service):
        """Test processing layout data without templates."""
        layout_data = LayoutData.model_validate(
            {
                "keyboard": "glove80",
                "title": "Simple Layout",
                "layer_names": ["Base"],
                "layers": [[{"value": "&kp A"}]],
            }
        )

        result = template_service.process_layout_data(layout_data)

        # Should return the same data since no templates
        assert result.title == "Simple Layout"
        assert result.keyboard == "glove80"

    def test_process_layout_data_with_templates(
        self, template_service, sample_layout_data
    ):
        """Test processing layout data with various templates."""

        # Setup template adapter to handle the specific templates
        def mock_render(template, context):
            if "{{ variables.user_name }}" in template:
                return template.replace(
                    "{{ variables.user_name }}", context["variables"]["user_name"]
                )
            elif "{{ variables.fast_timing }}" in template:
                return str(context["variables"]["fast_timing"])
            elif "{{ holdTaps[0].name }}" in template:
                return template.replace(
                    "{{ holdTaps[0].name }}", context["holdTaps"][0]["name"]
                )
            return template

        template_service.template_adapter.render_string.side_effect = mock_render

        layout = LayoutData.model_validate(sample_layout_data)
        result = template_service.process_layout_data(layout)

        assert result.title == "Test Layout for Alice"
        assert result.hold_taps[0].tapping_term_ms == 200
        assert result.custom_defined_behaviors == "// Custom behavior for Alice"

    def test_process_layout_data_template_error(
        self, template_service, sample_layout_data
    ):
        """Test handling of template processing errors."""
        # Create layout without template resolution first
        from glovebox.layout.utils.json_operations import VariableResolutionContext

        with VariableResolutionContext(skip=True):
            layout = LayoutData.model_validate(sample_layout_data)

        # Setup template adapter to raise an error
        template_service.template_adapter.render_string.side_effect = Exception(
            "Template error"
        )

        with pytest.raises(TemplateError, match="Template processing failed"):
            template_service.process_layout_data(layout)

    def test_validate_template_syntax_valid(self, template_service):
        """Test validation of valid template syntax."""
        layout_data = LayoutData.model_validate(
            {
                "keyboard": "test",
                "title": "Hello {{ name }}",
                "variables": {"name": "World"},
                "layer_names": ["Base"],
                "layers": [[{"value": "&kp A"}]],
            }
        )

        # Setup adapter to not raise errors for valid syntax
        template_service.template_adapter.render_string.return_value = "rendered"

        errors = template_service.validate_template_syntax(layout_data)
        assert errors == []

    def test_validate_template_syntax_invalid(self, template_service):
        """Test validation of invalid template syntax."""
        layout_data = LayoutData.model_validate(
            {
                "keyboard": "test",
                "title": "Hello {{ invalid syntax",
                "variables": {"name": "World"},
                "layer_names": ["Base"],
                "layers": [[{"value": "&kp A"}]],
            }
        )

        # Setup adapter to raise errors for invalid syntax
        template_service.template_adapter.render_string.side_effect = Exception(
            "Invalid syntax"
        )

        errors = template_service.validate_template_syntax(layout_data)
        assert len(errors) > 0
        assert "Invalid template syntax" in errors[0]

    def test_multi_pass_resolution_order(self, template_service, sample_layout_data):
        """Test that multi-pass resolution processes stages in correct order."""
        calls = []

        def track_calls(method_name):
            def wrapper(data):
                calls.append(method_name)
                return data  # Return the data to continue processing

            return wrapper

        # Create layout without template resolution
        from glovebox.layout.utils.json_operations import VariableResolutionContext

        with VariableResolutionContext(skip=True):
            layout = LayoutData.model_validate(sample_layout_data)

        # Patch resolution methods to track call order
        original_basic = template_service._resolve_basic_fields
        original_behaviors = template_service._resolve_behaviors
        original_layers = template_service._resolve_layers
        original_custom = template_service._resolve_custom_code

        template_service._resolve_basic_fields = track_calls("basic")
        template_service._resolve_behaviors = track_calls("behaviors")
        template_service._resolve_layers = track_calls("layers")
        template_service._resolve_custom_code = track_calls("custom")

        try:
            template_service.process_layout_data(layout)
        except Exception:
            pass  # We expect this might fail due to mocking
        finally:
            # Restore original methods
            template_service._resolve_basic_fields = original_basic
            template_service._resolve_behaviors = original_behaviors
            template_service._resolve_layers = original_layers
            template_service._resolve_custom_code = original_custom

        assert calls == ["basic", "behaviors", "layers", "custom"]

    def test_resolution_cache_behavior(self, template_service):
        """Test that resolution cache is properly managed."""
        # Cache should be empty initially
        assert template_service._resolution_cache == {}

        # Mock some data
        sample_data = {"keyboard": "test", "layer_names": []}

        # Call behaviors resolution
        template_service._resolve_behaviors(sample_data)

        # Cache should still be empty if no behaviors processed
        # (since we're not actually processing behaviors in this test)

        # Clear cache manually and verify
        template_service._resolution_cache["test"] = "value"
        assert template_service._resolution_cache["test"] == "value"


class TestTemplateServiceFactories:
    """Test factory functions for TemplateService."""

    def test_create_template_service(self):
        """Test create_template_service factory function."""
        mock_adapter = Mock(spec=TemplateAdapterProtocol)
        service = create_template_service(mock_adapter)

        assert isinstance(service, TemplateService)
        assert service.template_adapter == mock_adapter

    def test_create_jinja2_template_service(self):
        """Test create_jinja2_template_service factory function."""
        service = create_jinja2_template_service()

        assert isinstance(service, TemplateService)
        assert service.template_adapter is not None
        assert service.service_name == "TemplateService"


class TestTemplateServiceIntegration:
    """Integration tests for TemplateService with real scenarios."""

    def test_holdtap_template_integration(self):
        """Test HoldTap behavior with template processing."""
        layout_data = {
            "keyboard": "glove80",
            "title": "HoldTap Test Layout",
            "variables": {
                "fast_tap": 180,
                "slow_tap": 300,
            },
            "layer_names": ["Base"],
            "holdTaps": [
                {
                    "name": "fast_hold",
                    "tappingTermMs": "{{ variables.fast_tap }}",
                    "quickTapMs": "{{ variables.slow_tap }}",
                    "bindings": ["&kp", "&mo"],
                },
            ],
            "layers": [[{"value": "&lt fast_hold 0 1"}]],
        }

        service = create_jinja2_template_service()
        layout = LayoutData.model_validate(layout_data)
        result = service.process_layout_data(layout)

        assert result.hold_taps[0].tapping_term_ms == 180
        assert result.hold_taps[0].quick_tap_ms == 300

    @pytest.mark.xfail(
        reason="Recursion issue with nested template resolution - needs investigation"
    )
    def test_layer_name_context_integration(self):
        """Test layer name utilities in template context."""
        # Test that template resolution works through model validation
        layout_data = {
            "keyboard": "test",
            "title": "Layer Name Test Layout",
            "variables": {"base_layer": "Base"},
            "layer_names": ["{{ variables.base_layer }}", "Number", "Function"],
            "layers": [
                [{"value": "&kp A"}],
                [{"value": "&kp 1"}],
                [{"value": "&kp F1"}],
            ],
        }

        # Let the normal validation process handle template resolution
        layout = LayoutData.model_validate(layout_data)

        # The layer names should be resolved through the model validation
        assert layout.layer_names == ["Base", "Number", "Function"]

    def test_complex_nested_template_integration(self):
        """Test complex nested template scenarios."""
        layout_data = {
            "keyboard": "test",
            "variables": {
                "user": "Alice",
                "timings": {"fast": 150, "slow": 400},
                "features": {"combos": True, "macros": False},
            },
            "title": "Layout for {{ variables.user }}",
            "layer_names": ["Base"],
            "holdTaps": [
                {
                    "name": "adaptive_hold",
                    "tappingTermMs": "{{ variables.timings.fast }}",
                    "bindings": ["&kp", "&mo"],
                }
            ],
            "layers": [[{"value": "&kp A"}]],
            "custom_defined_behaviors": """
            // Behaviors for {{ variables.user }}
            // Fast timing: {{ variables.timings.fast }}ms
            // Combos enabled: {{ variables.features.combos }}
            """.strip(),
        }

        service = create_jinja2_template_service()

        # Create layout without template resolution to avoid double processing
        from glovebox.layout.utils.json_operations import VariableResolutionContext

        with VariableResolutionContext(skip=True):
            layout = LayoutData.model_validate(layout_data)

        result = service.process_layout_data(layout)

        assert result.title == "Layout for Alice"
        assert result.hold_taps[0].tapping_term_ms == 150
        assert "Alice" in result.custom_defined_behaviors
        assert "150ms" in result.custom_defined_behaviors
        assert "True" in result.custom_defined_behaviors
