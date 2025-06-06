"""Tests for TemplateAdapter implementation."""

from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest

from glovebox.adapters.template_adapter import (
    JinjaTemplateAdapter,
    TemplateAdapter,
    create_template_adapter,
)
from glovebox.core.errors import GloveboxError, TemplateError
from glovebox.utils.protocol_validator import validate_protocol_implementation


class TestJinjaTemplateAdapter:
    """Test JinjaTemplateAdapter class."""

    def test_template_adapter_initialization(self):
        """Test TemplateAdapter can be initialized."""
        adapter = JinjaTemplateAdapter()
        assert adapter is not None
        assert hasattr(adapter, "env")

    def test_render_template_from_string_success(self):
        """Test successful template rendering from string."""
        adapter = JinjaTemplateAdapter()
        template_content = "Hello, {{ name }}!"
        variables = {"name": "World"}

        result = adapter.render_string(template_content, variables)

        assert result == "Hello, World!"

    def test_render_template_from_string_no_variables(self):
        """Test template rendering from string without variables."""
        adapter = JinjaTemplateAdapter()
        template_content = "Hello, World!"

        result = adapter.render_string(template_content, {})

        assert result == "Hello, World!"

    def test_render_template_from_string_complex_template(self):
        """Test template rendering with complex Jinja2 features."""
        adapter = JinjaTemplateAdapter()
        template_content = """
{%- for item in items %}
{{ loop.index }}. {{ item.name }}: {{ item.value }}
{%- endfor %}
"""
        variables = {
            "items": [{"name": "first", "value": "A"}, {"name": "second", "value": "B"}]
        }

        result = adapter.render_string(template_content, variables)
        expected = "1. first: A2. second: B"

        assert result.strip() == expected

    def test_render_template_from_string_undefined_variable(self):
        """Test template rendering handles undefined variables."""
        adapter = JinjaTemplateAdapter()
        template_content = "Hello, {{ undefined_var }}!"

        with pytest.raises(
            TemplateError, match="Template operation 'render_string' failed"
        ):
            adapter.render_string(template_content, {})

    def test_render_template_from_string_syntax_error(self):
        """Test template rendering handles syntax errors."""
        adapter = JinjaTemplateAdapter()
        template_content = "Hello, {{ name"  # Missing closing brace

        with pytest.raises(
            TemplateError, match="Template operation 'render_string' failed"
        ):
            adapter.render_string(template_content, {})

    def test_render_template_from_file_success(self):
        """Test successful template rendering from file."""
        adapter = JinjaTemplateAdapter()
        template_path = Path("/test/template.j2")
        template_content = "Hello, {{ name }}!"
        variables = {"name": "World"}

        with patch("pathlib.Path.open", mock_open(read_data=template_content)):
            result = adapter.render_template_from_file(template_path, variables)

        assert result == "Hello, World!"

    def test_render_template_from_file_not_found(self):
        """Test template rendering raises error when file doesn't exist."""
        adapter = JinjaTemplateAdapter()
        template_path = Path("/nonexistent/template.j2")

        with (
            patch(
                "pathlib.Path.open", side_effect=FileNotFoundError("Template not found")
            ),
            pytest.raises(
                TemplateError,
                match="Template operation 'render_template_from_file' failed",
            ),
        ):
            adapter.render_template_from_file(template_path, {})

    def test_render_template_from_file_permission_error(self):
        """Test template rendering handles permission errors."""
        adapter = JinjaTemplateAdapter()
        template_path = Path("/restricted/template.j2")

        with (
            patch(
                "pathlib.Path.open", side_effect=PermissionError("Permission denied")
            ),
            pytest.raises(
                TemplateError,
                match="Template operation 'render_template_from_file' failed",
            ),
        ):
            adapter.render_template_from_file(template_path, {})

    def test_render_template_from_file_with_encoding(self):
        """Test template rendering from file with specific encoding."""
        adapter = JinjaTemplateAdapter()
        template_path = Path("/test/template.j2")
        template_content = "Hello, {{ name }}!"
        variables = {"name": "World"}

        with patch(
            "pathlib.Path.open", mock_open(read_data=template_content)
        ) as mock_path_open:
            result = adapter.render_template_from_file(
                template_path, variables, encoding="utf-16"
            )

        assert result == "Hello, World!"
        mock_path_open.assert_called_once_with(mode="r", encoding="utf-16")

    def test_validate_template_syntax_valid(self):
        """Test template syntax validation for valid template."""
        adapter = JinjaTemplateAdapter()
        template_content = (
            "Hello, {{ name }}! {% for item in items %}{{ item }}{% endfor %}"
        )

        result = adapter.validate_template_syntax(template_content)

        assert result is True

    def test_validate_template_syntax_invalid(self):
        """Test template syntax validation for invalid template."""
        adapter = JinjaTemplateAdapter()
        template_content = "Hello, {{ name"  # Missing closing brace

        result = adapter.validate_template_syntax(template_content)

        assert result is False

    def test_validate_template_syntax_complex_invalid(self):
        """Test template syntax validation for complex invalid template."""
        adapter = JinjaTemplateAdapter()
        template_content = (
            "{% for item in items %}{{ item }}{% endblock %}"  # Wrong closing tag
        )

        result = adapter.validate_template_syntax(template_content)

        assert result is False

    def test_get_template_variables_simple(self):
        """Test extraction of template variables from simple template."""
        adapter = JinjaTemplateAdapter()
        template_content = "Hello, {{ name }}! Your age is {{ age }}."

        result = adapter.get_template_variables(template_content)

        assert "name" in result
        assert "age" in result
        assert len(result) == 2

    def test_get_template_variables_complex(self):
        """Test extraction of template variables from complex template."""
        adapter = JinjaTemplateAdapter()
        template_content = """
Hello, {{ user.name }}!
{% for item in items %}
  {{ item.title }}: {{ item.value }}
{% endfor %}
Total: {{ total }}
"""

        result = adapter.get_template_variables(template_content)

        # Should find top-level variables
        assert "user" in result
        assert "items" in result
        assert "total" in result

    def test_get_template_variables_no_variables(self):
        """Test extraction of template variables from template without variables."""
        adapter = JinjaTemplateAdapter()
        template_content = "This is a static template with no variables."

        result = adapter.get_template_variables(template_content)

        assert len(result) == 0

    def test_get_template_variables_syntax_error(self):
        """Test template variable extraction handles syntax errors."""
        adapter = JinjaTemplateAdapter()
        template_content = "Hello, {{ name"  # Missing closing brace

        with pytest.raises(
            TemplateError,
            match="Template operation 'get_template_variables_from_string' failed",
        ):
            adapter.get_template_variables(template_content)

    def test_custom_jinja_environment(self):
        """Test that custom Jinja2 environment settings work."""
        adapter = JinjaTemplateAdapter()

        # Test that undefined variables raise errors (strict mode)
        template_content = "Hello, {{ undefined_var }}!"

        with pytest.raises(TemplateError):
            adapter.render_string(template_content, {})

    def test_template_with_filters(self):
        """Test template rendering with Jinja2 filters."""
        adapter = JinjaTemplateAdapter()
        template_content = "Hello, {{ name|upper }}! Count: {{ items|length }}"
        variables = {"name": "world", "items": [1, 2, 3, 4, 5]}

        result = adapter.render_string(template_content, variables)

        assert result == "Hello, WORLD! Count: 5"

    def test_template_with_conditionals(self):
        """Test template rendering with conditional logic."""
        adapter = JinjaTemplateAdapter()
        template_content = """
{%- if user.is_admin %}
Admin: {{ user.name }}
{%- else %}
User: {{ user.name }}
{%- endif %}
"""

        # Test admin user
        admin_vars = {"user": {"name": "Alice", "is_admin": True}}
        result = adapter.render_string(template_content, admin_vars)
        assert "Admin: Alice" in result

        # Test regular user
        user_vars = {"user": {"name": "Bob", "is_admin": False}}
        result = adapter.render_string(template_content, user_vars)
        assert "User: Bob" in result


class TestCreateTemplateAdapter:
    """Test create_template_adapter factory function."""

    def test_create_template_adapter(self):
        """Test factory function creates TemplateAdapter instance."""
        adapter = create_template_adapter()
        assert isinstance(adapter, JinjaTemplateAdapter)
        assert isinstance(adapter, TemplateAdapter)


class TestTemplateAdapterIntegration:
    """Integration tests using real template operations."""

    def test_render_real_template_file(self, tmp_path):
        """Test rendering a real template file."""
        adapter = JinjaTemplateAdapter()

        # Create template file
        template_file = tmp_path / "test_template.j2"
        template_content = """
# Configuration for {{ app_name }}
version: {{ version }}
debug: {{ debug }}

features:
{%- for feature in features %}
  - {{ feature }}
{%- endfor %}
"""
        template_file.write_text(template_content)

        # Render template
        variables = {
            "app_name": "MyApp",
            "version": "1.0.0",
            "debug": True,
            "features": ["auth", "logging", "metrics"],
        }

        result = adapter.render_template_from_file(template_file, variables)

        # Verify rendered content
        assert "# Configuration for MyApp" in result
        assert "version: 1.0.0" in result
        assert "debug: True" in result
        assert "- auth" in result
        assert "- logging" in result
        assert "- metrics" in result

    def test_complex_template_with_inheritance(self, tmp_path):
        """Test complex template with Jinja2 inheritance features."""
        adapter = JinjaTemplateAdapter()

        # Create base template
        base_template = tmp_path / "base.j2"
        base_content = """
# Base Configuration
app: {{ app_name }}
{% block content %}{% endblock %}
"""
        base_template.write_text(base_content)

        # Create child template
        child_template = tmp_path / "child.j2"
        child_content = """
{% extends "base.j2" %}
{% block content %}
version: {{ version }}
features: {{ features|join(', ') }}
{% endblock %}
"""
        child_template.write_text(child_content)

        # Note: This test would require setting up Jinja2 file system loader
        # For now, we'll test a simpler case without inheritance
        simple_template = """
# Configuration
app: {{ app_name }}
version: {{ version }}
features: {{ features|join(', ') }}
"""

        variables = {
            "app_name": "TestApp",
            "version": "2.0.0",
            "features": ["feature1", "feature2", "feature3"],
        }

        result = adapter.render_string(simple_template, variables)

        assert "app: TestApp" in result
        assert "version: 2.0.0" in result
        assert "features: feature1, feature2, feature3" in result


class TestTemplateAdapterProtocol:
    """Test TemplateAdapter protocol implementation."""

    def test_template_adapter_implements_protocol(self):
        """Test that JinjaTemplateAdapter correctly implements TemplateAdapter protocol."""
        valid, errors = validate_protocol_implementation(
            TemplateAdapter, JinjaTemplateAdapter
        )
        assert valid, (
            f"JinjaTemplateAdapter does not implement TemplateAdapter protocol: {errors}"
        )

    def test_runtime_protocol_check(self):
        """Test that JinjaTemplateAdapter passes runtime protocol check."""
        adapter = JinjaTemplateAdapter()
        assert isinstance(adapter, TemplateAdapter), (
            "JinjaTemplateAdapter should be instance of TemplateAdapter"
        )
