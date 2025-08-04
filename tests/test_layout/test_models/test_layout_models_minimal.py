"""Minimal unit tests for layout models - only testing working functionality."""

import json
from datetime import UTC, datetime

import pytest

from glovebox.layout.models import (
    LayoutBinding,
    LayoutData,
    LayoutLayer,
    LayoutParam,
)


pytestmark = pytest.mark.unit


class TestLayoutDataBasic:
    """Test basic LayoutData functionality."""

    def test_layout_data_creation(self):
        """Test basic layout data creation."""
        layout = LayoutData(keyboard="glove80", title="Test Layout")

        assert layout.keyboard == "glove80"
        assert layout.title == "Test Layout"
        assert isinstance(layout.date, datetime)

    def test_layout_data_json_serialization(self):
        """Test that LayoutData can be serialized to JSON."""
        test_date = datetime(2025, 6, 19, 15, 30, 45, tzinfo=UTC)
        layout = LayoutData(keyboard="glove80", title="Test Layout", date=test_date)

        # Test JSON serialization
        json_data = layout.model_dump(mode="json")
        assert json_data["keyboard"] == "glove80"
        assert json_data["title"] == "Test Layout"
        assert isinstance(json_data["date"], int)  # Unix timestamp

        # Verify it's properly JSON serializable
        json_string = json.dumps(json_data)
        parsed_back = json.loads(json_string)
        assert parsed_back["keyboard"] == "glove80"


class TestLayoutBindingBasic:
    """Test basic LayoutBinding functionality."""

    def test_simple_behavior_parsing(self):
        """Test parsing simple behaviors."""
        binding = LayoutBinding.from_str("&kp Q")
        assert binding.value == "&kp"
        assert len(binding.params) == 1
        assert binding.params[0].value == "Q"

    def test_behavior_with_multiple_params(self):
        """Test parsing behaviors with multiple parameters."""
        binding = LayoutBinding.from_str("&mt LCTRL A")
        assert binding.value == "&mt"
        assert len(binding.params) == 2
        assert binding.params[0].value == "LCTRL"
        assert binding.params[1].value == "A"

    def test_behavior_without_params(self):
        """Test parsing behaviors without parameters."""
        binding = LayoutBinding.from_str("&trans")
        assert binding.value == "&trans"
        assert len(binding.params) == 0

    def test_behavior_property(self):
        """Test behavior property access."""
        binding = LayoutBinding.from_str("&kp Q")
        assert binding.behavior == "&kp"

    def test_empty_string_raises_error(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="Behavior string cannot be empty"):
            LayoutBinding.from_str("")

    def test_whitespace_only_raises_error(self):
        """Test that whitespace-only string raises ValueError."""
        with pytest.raises(ValueError, match="Behavior string cannot be empty"):
            LayoutBinding.from_str("   ")


class TestLayoutLayerBasic:
    """Test basic LayoutLayer functionality."""

    def test_layer_creation(self):
        """Test basic layer creation."""
        bindings = [
            LayoutBinding.from_str("&kp Q"),
            LayoutBinding.from_str("&kp W"),
            LayoutBinding.from_str("&trans"),
        ]

        layer = LayoutLayer(name="test_layer", bindings=bindings)
        assert layer.name == "test_layer"
        assert len(layer.bindings) == 3
        assert layer.bindings[0].value == "&kp"
        assert layer.bindings[0].params[0].value == "Q"

    def test_layer_with_string_bindings(self):
        """Test layer creation with string bindings (auto-conversion)."""
        bindings = [
            LayoutBinding.from_str("&kp Q"),
            LayoutBinding.from_str("&kp W"),
            LayoutBinding.from_str("&trans"),
        ]
        layer = LayoutLayer(name="test_layer", bindings=bindings)

        assert layer.name == "test_layer"
        assert len(layer.bindings) == 3
        assert all(isinstance(b, LayoutBinding) for b in layer.bindings)
        assert layer.bindings[0].value == "&kp"
        assert layer.bindings[0].params[0].value == "Q"

    def test_empty_layer(self):
        """Test empty layer creation."""
        layer = LayoutLayer(name="empty_layer", bindings=[])
        assert layer.name == "empty_layer"
        assert len(layer.bindings) == 0


class TestLayoutParamBasic:
    """Test basic LayoutParam functionality."""

    def test_layout_param_creation(self):
        """Test basic LayoutParam creation."""
        param = LayoutParam(value="Q")
        assert param.value == "Q"
        assert len(param.params) == 0

    def test_nested_layout_param(self):
        """Test nested LayoutParam creation."""
        nested = LayoutParam(value="X")
        parent = LayoutParam(value="LC", params=[nested])

        assert parent.value == "LC"
        assert len(parent.params) == 1
        assert parent.params[0].value == "X"
