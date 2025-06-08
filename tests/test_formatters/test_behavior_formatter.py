"""Tests for the behavior formatter."""

from unittest.mock import Mock, patch

import pytest

from glovebox.layout.behavior_formatter import BehaviorFormatterImpl
from glovebox.layout.models import LayoutBinding, LayoutParam
from glovebox.models.behavior import RegistryBehavior, SystemBehavior
from glovebox.protocols.behavior_protocols import BehaviorRegistryProtocol


class MockBehaviorRegistry:
    """Mock implementation of BehaviorRegistryProtocol for testing."""

    def __init__(self):
        """Initialize the mock registry."""
        self.behaviors = {}

    def register_behavior(self, behavior):
        """Register a behavior in the registry."""
        self.behaviors[behavior.code] = behavior

    def get_behavior_info(self, name):
        """Get information about a registered behavior."""
        behavior = self.behaviors.get(name)
        if behavior is None:
            return None

        # Convert SystemBehavior to RegistryBehavior for protocol compliance
        return RegistryBehavior(
            expected_params=behavior.expected_params,
            origin=behavior.origin,
            description=behavior.description or "",
            params=behavior.params,
            url=behavior.url,
            commands=behavior.commands,
            includes=behavior.includes,
        )

    def list_behaviors(self):
        """List all registered behaviors."""
        return self.behaviors


@pytest.fixture
def behavior_registry():
    """Create a mock behavior registry for testing."""
    registry = MockBehaviorRegistry()

    # Register some common behaviors
    registry.register_behavior(
        SystemBehavior(
            code="&kp",
            name="Key Press",
            description="Key press behavior",
            expected_params=1,
            origin="zmk_core",
            params=[],
        )
    )

    registry.register_behavior(
        SystemBehavior(
            code="&mo",
            name="Momentary Layer",
            description="Momentary layer shift",
            expected_params=1,
            origin="zmk_core",
            params=[],
        )
    )

    registry.register_behavior(
        SystemBehavior(
            code="&lt",
            name="Layer Tap",
            description="Layer tap behavior",
            expected_params=2,
            origin="zmk_core",
            params=[],
        )
    )

    registry.register_behavior(
        SystemBehavior(
            code="&none",
            name="None",
            description="No-op behavior",
            expected_params=0,
            origin="zmk_core",
            params=[],
        )
    )

    return registry


@pytest.fixture
def behavior_formatter(behavior_registry):
    """Create a behavior formatter with the mock registry."""
    keycode_map = {
        "A": "A",
        "B": "B",
        "SPACE": "SPACE",
        "ENTER": "ENTER",
    }
    return BehaviorFormatterImpl(behavior_registry, keycode_map)


def test_formatter_instantiation(behavior_registry):
    """Test that the formatter can be instantiated with our protocol."""
    # This test verifies that BehaviorFormatterImpl accepts our BehaviorRegistryProtocol
    formatter = BehaviorFormatterImpl(behavior_registry)
    assert formatter._registry is behavior_registry
    assert isinstance(formatter._registry, BehaviorRegistryProtocol)


def test_format_simple_binding(behavior_formatter):
    """Test formatting a simple binding."""
    binding = LayoutBinding(value="&kp", params=[LayoutParam(value="A")])
    result = behavior_formatter.format_binding(binding)
    assert result == "&kp A"


def test_format_zero_param_binding(behavior_formatter):
    """Test formatting a binding with no parameters."""
    binding = LayoutBinding(value="&none", params=[])
    result = behavior_formatter.format_binding(binding)
    assert result == "&none"


def test_format_multi_param_binding(behavior_formatter):
    """Test formatting a binding with multiple parameters."""
    binding = LayoutBinding(
        value="&lt", params=[LayoutParam(value="1"), LayoutParam(value="SPACE")]
    )
    result = behavior_formatter.format_binding(binding)
    assert result == "&lt 1 SPACE"


def test_format_binding_with_nested_params(behavior_formatter):
    """Test formatting a binding with nested parameters (modifiers)."""
    # Create a binding with nested structure for testing modifiers
    binding = LayoutBinding(
        value="&kp",
        params=[LayoutParam(value="LSHFT", params=[LayoutParam(value="A")])],
    )

    result = behavior_formatter.format_binding(binding)
    assert result == "&kp LS(A)"


def test_format_custom_behavior(behavior_formatter, behavior_registry):
    """Test formatting a custom behavior."""
    # Register a custom behavior
    behavior_registry.register_behavior(
        SystemBehavior(
            code="&custom_behavior",
            name="Custom Behavior",
            description="A custom test behavior",
            expected_params=2,
            origin="user",
            params=[],
        )
    )

    binding = LayoutBinding(
        value="&custom_behavior",
        params=[LayoutParam(value="1"), LayoutParam(value="2")],
    )

    result = behavior_formatter.format_binding(binding)
    assert result == "&custom_behavior 1 2"


def test_behavior_with_missing_params(behavior_formatter, behavior_registry):
    """Test a behavior with missing parameters generates an appropriate error."""
    binding = LayoutBinding(
        value="&lt",
        params=[
            LayoutParam(value="1")
            # Missing second parameter
        ],
    )

    result = behavior_formatter.format_binding(binding)
    # The formatter should properly handle the error case for missing parameters
    assert "&error" in result
    assert "requires exactly 2 parameters" in result


def test_format_invalid_behavior(behavior_formatter):
    """Test formatting an invalid behavior."""
    binding = LayoutBinding(value="&invalid", params=[])
    result = behavior_formatter.format_binding(binding)
    # Should return an error binding or similar
    assert "&error" in result or "invalid" in result.lower()
