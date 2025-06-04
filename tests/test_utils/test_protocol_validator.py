"""Tests for protocol validator."""

from typing import Protocol, runtime_checkable

import pytest

from glovebox.adapters.docker_adapter import DockerAdapter, DockerAdapterImpl
from glovebox.adapters.file_adapter import FileAdapter, FileSystemAdapter
from glovebox.adapters.template_adapter import JinjaTemplateAdapter, TemplateAdapter
from glovebox.adapters.usb_adapter import USBAdapter, USBAdapterImpl
from glovebox.utils.protocol_validator import (
    assert_implements_protocol,
    validate_protocol_implementation,
)


class TestProtocolValidator:
    """Test protocol validator utility functions."""

    def test_all_adapters_implement_protocols(self):
        """Test that all adapter implementations fully implement their protocols."""
        adapters_to_validate = [
            (DockerAdapter, DockerAdapterImpl, "Docker adapter"),
            (FileAdapter, FileSystemAdapter, "File adapter"),
            (TemplateAdapter, JinjaTemplateAdapter, "Template adapter"),
            (USBAdapter, USBAdapterImpl, "USB adapter"),
        ]

        for protocol_cls, impl_cls, name in adapters_to_validate:
            is_valid, errors = validate_protocol_implementation(protocol_cls, impl_cls)
            assert is_valid, f"{name} validation failed with: {errors}"

    def test_validator_with_mock_protocol(self):
        """Test validator with controlled mock protocol and implementation."""

        @runtime_checkable
        class MockProtocol(Protocol):
            def method_a(self, param1: str, param2: int) -> bool: ...

            def method_b(self) -> list[str]: ...

        class ValidImpl:
            def method_a(self, param1: str, param2: int) -> bool:
                return True

            def method_b(self) -> list[str]:
                return ["test"]

        class InvalidImpl:
            def method_a(self, param1: str, param2: str) -> bool:  # wrong param type
                return True

            # missing method_b

        # Valid implementation should pass
        is_valid, errors = validate_protocol_implementation(MockProtocol, ValidImpl)
        assert is_valid
        assert not errors

        # Invalid implementation should fail
        is_valid, errors = validate_protocol_implementation(MockProtocol, InvalidImpl)
        assert not is_valid
        assert len(errors) >= 1  # Should have at least one error

    def test_assert_implements_protocol(self):
        """Test the assert_implements_protocol function."""

        @runtime_checkable
        class SimpleProtocol(Protocol):
            def simple_method(self) -> str: ...

        class ValidImpl:
            def simple_method(self) -> str:
                return "test"

        class InvalidImpl:
            def wrong_method(self) -> str:
                return "test"

        # Valid implementation should not raise
        valid_instance = ValidImpl()
        assert_implements_protocol(valid_instance, SimpleProtocol)

        # Invalid implementation should raise
        invalid_instance = InvalidImpl()
        with pytest.raises(TypeError):
            assert_implements_protocol(invalid_instance, SimpleProtocol)
