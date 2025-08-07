"""Unit tests for GloveboxTemplateProvider."""

from unittest.mock import Mock

import pytest

from glovebox.adapters.zmk_layout.template_provider import GloveboxTemplateProvider


class TestGloveboxTemplateProvider:
    """Test suite for GloveboxTemplateProvider."""

    @pytest.fixture
    def mock_template_service(self):
        """Mock template service."""
        service = Mock()
        service.render_string.return_value = "Rendered string"
        service.render_file.return_value = "Rendered file"
        service.contains_template_syntax.return_value = True
        service.validate_syntax.return_value = None  # No errors
        service.escape_template_content.return_value = "Escaped content"
        service.get_engine_name.return_value = "jinja2"
        service.get_engine_version.return_value = "3.1.0"
        service.get_supported_features.return_value = [
            "loops",
            "conditionals",
            "filters",
        ]
        return service

    @pytest.fixture
    def provider(self, mock_template_service):
        """Create provider instance for testing."""
        return GloveboxTemplateProvider(template_service=mock_template_service)

    def test_initialization(self, provider, mock_template_service):
        """Test provider initialization."""
        assert provider.template_service is mock_template_service

    def test_render_string_success(self, provider, mock_template_service):
        """Test successful string rendering."""
        template = "Hello {{name}}"
        context = {"name": "World"}

        result = provider.render_string(template, context)

        assert result == "Rendered string"
        mock_template_service.render_string.assert_called_once_with(template, context)

    def test_render_string_error(self, provider, mock_template_service):
        """Test error handling in string rendering."""
        mock_template_service.render_string.side_effect = Exception("Template error")

        with pytest.raises(ValueError, match="Template rendering failed"):
            provider.render_string("{{invalid}}", {})

    def test_render_file_success(self, provider, mock_template_service):
        """Test successful file rendering."""
        template_path = "/path/to/template.j2"
        context = {"key": "value"}

        result = provider.render_file(template_path, context)

        assert result == "Rendered file"
        mock_template_service.render_file.assert_called_once_with(
            template_path, context
        )

    def test_render_file_error(self, provider, mock_template_service):
        """Test error handling in file rendering."""
        mock_template_service.render_file.side_effect = Exception("File error")

        with pytest.raises(ValueError, match="Template file rendering failed"):
            provider.render_file("/invalid/path", {})

    def test_has_template_syntax_true(self, provider, mock_template_service):
        """Test template syntax detection returning True."""
        mock_template_service.contains_template_syntax.return_value = True

        result = provider.has_template_syntax("{{variable}}")

        assert result is True
        mock_template_service.contains_template_syntax.assert_called_once_with(
            "{{variable}}"
        )

    def test_has_template_syntax_false(self, provider, mock_template_service):
        """Test template syntax detection returning False."""
        mock_template_service.contains_template_syntax.return_value = False

        result = provider.has_template_syntax("plain text")

        assert result is False
        mock_template_service.contains_template_syntax.assert_called_once_with(
            "plain text"
        )

    def test_has_template_syntax_error(self, provider, mock_template_service):
        """Test error handling in template syntax detection."""
        mock_template_service.contains_template_syntax.side_effect = Exception(
            "Syntax error"
        )

        # Should return True as conservative fallback
        result = provider.has_template_syntax("some content")

        assert result is True

    def test_validate_template_success(self, provider, mock_template_service):
        """Test successful template validation."""
        mock_template_service.validate_syntax.return_value = None

        errors = provider.validate_template("{{valid_template}}")

        assert errors == []
        mock_template_service.validate_syntax.assert_called_once_with(
            "{{valid_template}}"
        )

    def test_validate_template_error(self, provider, mock_template_service):
        """Test template validation with errors."""
        mock_template_service.validate_syntax.side_effect = Exception("Invalid syntax")

        errors = provider.validate_template("{{invalid")

        assert len(errors) == 1
        assert "Invalid syntax" in errors[0]

    def test_escape_content_success(self, provider, mock_template_service):
        """Test successful content escaping."""
        mock_template_service.escape_template_content.return_value = "{{escaped}}"

        result = provider.escape_content("{raw}")

        assert result == "{{escaped}}"
        mock_template_service.escape_template_content.assert_called_once_with("{raw}")

    def test_escape_content_error(self, provider, mock_template_service):
        """Test error handling in content escaping."""
        mock_template_service.escape_template_content.side_effect = Exception(
            "Escape error"
        )

        # Should provide fallback escaping
        result = provider.escape_content("{raw}")

        assert result == "{{raw}}"  # Basic fallback escaping

    def test_get_template_engine_info_success(self, provider, mock_template_service):
        """Test successful template engine info retrieval."""
        info = provider.get_template_engine_info()

        assert info["engine"] == "jinja2"
        assert info["version"] == "3.1.0"
        assert info["features"] == ["loops", "conditionals", "filters"]

        mock_template_service.get_engine_name.assert_called_once()
        mock_template_service.get_engine_version.assert_called_once()
        mock_template_service.get_supported_features.assert_called_once()

    def test_get_template_engine_info_error(self, provider, mock_template_service):
        """Test error handling in template engine info retrieval."""
        mock_template_service.get_engine_name.side_effect = Exception("Info error")

        info = provider.get_template_engine_info()

        # Should provide fallback info
        assert info["engine"] == "unknown"
        assert info["version"] == "unknown"
        assert info["features"] == []

    def test_complex_template_rendering(self, provider, mock_template_service):
        """Test complex template rendering scenario."""
        # Setup complex template response
        complex_result = """
        / {
            keymap {
                compatible = "zmk,keymap";

                layer_0 {
                    bindings = <
                        &kp Q &kp W &kp E
                    >;
                };
            };
        };
        """
        mock_template_service.render_string.return_value = complex_result

        template = "Complex template with {{keyboard}} configuration"
        context = {
            "keyboard": "crkbd",
            "layers": ["base", "lower", "raise"],
            "behaviors": ["kp", "mt", "lt"],
        }

        result = provider.render_string(template, context)

        assert result == complex_result
        mock_template_service.render_string.assert_called_once_with(template, context)

    def test_template_validation_multiple_errors(self, provider, mock_template_service):
        """Test template validation with multiple errors."""
        # Mock service that raises exception with multiple error details
        error_msg = "Multiple syntax errors: unclosed braces, invalid variable names"
        mock_template_service.validate_syntax.side_effect = Exception(error_msg)

        errors = provider.validate_template("{{invalid template with multiple issues")

        assert len(errors) == 1
        assert error_msg in errors[0]

    def test_edge_case_empty_template(self, provider, mock_template_service):
        """Test edge case with empty template."""
        mock_template_service.render_string.return_value = ""
        mock_template_service.contains_template_syntax.return_value = False

        # Empty template
        result = provider.render_string("", {})
        assert result == ""

        # Template syntax detection on empty string
        has_syntax = provider.has_template_syntax("")
        assert has_syntax is False

    def test_edge_case_large_context(self, provider, mock_template_service):
        """Test edge case with large context dictionary."""
        large_context = {f"key_{i}": f"value_{i}" for i in range(1000)}
        mock_template_service.render_string.return_value = "Rendered with large context"

        result = provider.render_string("{{key_500}}", large_context)

        assert result == "Rendered with large context"
        mock_template_service.render_string.assert_called_once_with(
            "{{key_500}}", large_context
        )
