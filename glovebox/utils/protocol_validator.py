"""Utilities for validating protocol implementations.

This module provides tools to validate that class implementations correctly
satisfy Protocol requirements at runtime. This is particularly useful for
adapter implementations to ensure they adhere to their interface contracts.

Example:
    ```python
    from typing import Protocol

    class MyProtocol(Protocol):
        def some_method(self, param: str) -> int:
            ...

    class MyImplementation:
        def some_method(self, param: str) -> int:
            return len(param)

    # Check implementation
    is_valid, errors = validate_protocol_implementation(MyProtocol, MyImplementation)
    if not is_valid:
        print(f"Implementation errors: {errors}")
    ```
"""

import abc
import inspect
from collections.abc import Callable
from typing import Any, Protocol, TypeVar, cast, get_type_hints


# Type variables for generic usage
# Use Any for the bound since Protocol can't be used directly as a bound
P = TypeVar("P")  # Protocol type
ImplT = TypeVar("ImplT")  # Implementation type


def validate_protocol_implementation(
    protocol_class: type[P],
    implementation_class: type[ImplT],
    *,
    raise_on_error: bool = False,
) -> tuple[bool, list[str]]:
    """
    Validate that a class correctly implements a protocol.

    Args:
        protocol_class: The protocol class to validate against
        implementation_class: The implementation class to validate
        raise_on_error: Whether to raise an exception on validation errors

    Returns:
        Tuple containing:
            - Boolean indicating if the implementation is valid
            - List of error messages (if any)

    Raises:
        TypeError: If raise_on_error is True and validation errors are found
    """
    error_messages = []

    # Check if the protocol_class is a Protocol
    # Protocols don't always have __protocol_attrs__, so we use a more general check
    # We can't directly use Protocol in issubclass due to typing restrictions
    try:
        # Try to detect if it's a Protocol by checking common Protocol attributes
        is_protocol = hasattr(protocol_class, "_is_protocol") or "_is_protocol" in vars(
            protocol_class
        )

        if not is_protocol:
            # Also check for ABC which can be used as Protocol-like
            is_protocol = hasattr(protocol_class, "__abstractmethods__")

        if not is_protocol:
            msg = f"{protocol_class.__name__} is not a Protocol class"
            error_messages.append(msg)
            if raise_on_error:
                raise TypeError(msg) from None
            return False, error_messages
    except (TypeError, AttributeError):
        msg = f"Could not check if {protocol_class.__name__} is a Protocol class"
        error_messages.append(msg)
        if raise_on_error:
            raise TypeError(msg) from None
        return False, error_messages

    # Get protocol methods and attributes
    protocol_attrs = _get_protocol_attributes(protocol_class)

    # Get implementation methods and attributes
    impl_attrs = _get_class_attributes(implementation_class)

    # Validate required attributes
    for attr_name, protocol_attr in protocol_attrs.items():
        # Check if attribute exists in implementation
        if attr_name not in impl_attrs:
            msg = f"Missing attribute: {attr_name}"
            error_messages.append(msg)
            continue

        impl_attr = impl_attrs[attr_name]

        # If it's a method, check signature compatibility
        # Check if it's a function, property or abstractmethod
        is_method = inspect.isfunction(protocol_attr)
        is_property = isinstance(protocol_attr, property)
        has_abstract_attr = hasattr(protocol_attr, "__isabstractmethod__")

        if is_method or is_property or has_abstract_attr:
            # Get type hints
            try:
                protocol_types = get_type_hints(protocol_attr)
                impl_types = get_type_hints(impl_attr)

                # Check return type compatibility
                if "return" in protocol_types:
                    if "return" not in impl_types:
                        msg = f"Method {attr_name} missing return type annotation"
                        error_messages.append(msg)
                    elif not _is_compatible_type(
                        impl_types["return"], protocol_types["return"]
                    ):
                        msg = (
                            f"Method {attr_name} return type mismatch: "
                            f"implementation {impl_types['return']} vs protocol {protocol_types['return']}"
                        )
                        error_messages.append(msg)

                # Check parameter types compatibility
                proto_params = {
                    p: t for p, t in protocol_types.items() if p != "return"
                }
                impl_params = {p: t for p, t in impl_types.items() if p != "return"}

                # Check missing parameters
                for param, p_type in proto_params.items():
                    if param not in impl_params:
                        msg = f"Method {attr_name} missing parameter {param} of type {p_type}"
                        error_messages.append(msg)
                    elif not _is_compatible_type(p_type, impl_params[param]):
                        msg = (
                            f"Method {attr_name} parameter {param} type mismatch: "
                            f"protocol {p_type} vs implementation {impl_params[param]}"
                        )
                        error_messages.append(msg)

                # Check signature compatibility (parameters, defaults, etc.)
                proto_sig = inspect.signature(protocol_attr)
                impl_sig = inspect.signature(impl_attr)

                # Check if implementation has all required parameters
                proto_params_set = set(proto_sig.parameters)
                impl_params_set = set(impl_sig.parameters)

                missing_params = proto_params_set - impl_params_set
                if missing_params:
                    msg = f"Method {attr_name} missing parameters: {', '.join(missing_params)}"
                    error_messages.append(msg)

                # Check if implementation parameters maintain the same order
                proto_param_list = list(proto_sig.parameters)
                impl_param_list = list(impl_sig.parameters)

                # Check only the common parameters for order
                common_params = list(proto_params_set.intersection(impl_params_set))
                proto_common_params = [
                    p for p in proto_param_list if p in common_params
                ]
                impl_common_params = [p for p in impl_param_list if p in common_params]

                if proto_common_params != impl_common_params:
                    msg = (
                        f"Method {attr_name} has different parameter order: "
                        f"protocol {proto_common_params} vs implementation {impl_common_params}"
                    )
                    error_messages.append(msg)

            except Exception as e:
                msg = f"Error checking method {attr_name}: {e}"
                error_messages.append(msg)

    # If we have errors and raise_on_error is True, raise an exception
    if error_messages and raise_on_error:
        raise TypeError("\n".join(error_messages)) from None

    return not bool(error_messages), error_messages


def _get_protocol_attributes(protocol_class: type[Any]) -> dict[str, Any]:
    """
    Get all attributes and methods defined in a Protocol class.

    Args:
        protocol_class: Protocol class to inspect

    Returns:
        Dictionary of attribute names to their values
    """
    attrs = {}

    # Get all attributes of the protocol
    for attr_name in dir(protocol_class):
        # Skip magic methods and private attributes
        if attr_name.startswith("_") and attr_name != "__call__":
            continue

        try:
            attr = getattr(protocol_class, attr_name)
            attrs[attr_name] = attr
        except (AttributeError, TypeError):
            # Some attributes might not be accessible
            pass

    return attrs


def _get_class_attributes(cls: type[Any]) -> dict[str, Any]:
    """
    Get all attributes and methods of a class.

    Args:
        cls: Class to inspect

    Returns:
        Dictionary of attribute names to their values
    """
    attrs = {}

    # Get all attributes of the class including inherited ones
    for attr_name in dir(cls):
        # Skip magic methods and private attributes
        if attr_name.startswith("_") and attr_name != "__call__":
            continue

        try:
            attr = getattr(cls, attr_name)
            attrs[attr_name] = attr
        except (AttributeError, TypeError):
            # Some attributes might not be accessible
            pass

    return attrs


def _is_compatible_type(protocol_type: Any, impl_type: Any) -> bool:
    """
    Check if the implementation type is compatible with the protocol type.

    Args:
        protocol_type: Type from the protocol
        impl_type: Type from the implementation

    Returns:
        True if types are compatible, False otherwise
    """
    # For now, simple string comparison
    # This could be extended with more sophisticated type compatibility rules
    return str(protocol_type) == str(impl_type)


def assert_implements_protocol(impl_instance: Any, protocol_class: type[Any]) -> None:
    """
    Assert that an instance implements a protocol.

    Args:
        impl_instance: Instance to check
        protocol_class: Protocol class to validate against

    Raises:
        TypeError: If the instance doesn't implement the protocol
    """
    if not isinstance(impl_instance, protocol_class):
        valid, errors = validate_protocol_implementation(
            protocol_class, type(impl_instance), raise_on_error=True
        )
        if not valid:
            raise TypeError(
                f"{type(impl_instance).__name__} does not implement {protocol_class.__name__}"
            ) from None
