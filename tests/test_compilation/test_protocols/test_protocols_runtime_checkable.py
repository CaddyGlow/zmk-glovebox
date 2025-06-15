"""Test that protocols are runtime checkable."""


def test_compilation_protocols_runtime_checkable():
    """Test that compilation protocols are runtime checkable."""
    from glovebox.compilation.protocols.compilation_protocols import (
        CompilationServiceProtocol,
    )

    # Test that protocol is runtime checkable
    assert hasattr(CompilationServiceProtocol, "__instancecheck__")

    # Test basic protocol methods exist
    assert hasattr(CompilationServiceProtocol, "compile")
    assert hasattr(CompilationServiceProtocol, "validate_config")
    assert hasattr(CompilationServiceProtocol, "check_available")
