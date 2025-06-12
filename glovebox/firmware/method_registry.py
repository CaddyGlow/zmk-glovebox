"""Generic registry system for method implementations."""

import logging
from typing import Any, Generic, TypeVar

from glovebox.config.flash_methods import USBFlashConfig
from glovebox.protocols.flash_protocols import FlasherProtocol


logger = logging.getLogger(__name__)


# Use Any for config type since we don't need strict typing here
ConfigType = TypeVar("ConfigType")
ProtocolType = TypeVar("ProtocolType")


class MethodRegistry(Generic[ConfigType, ProtocolType]):
    """Generic registry for method implementations."""

    def __init__(self) -> None:
        self._methods: dict[str, type[ProtocolType]] = {}
        self._config_types: dict[str, type[ConfigType]] = {}

    def register_method(
        self,
        method_name: str,
        implementation: type[ProtocolType],
        config_type: type[ConfigType],
    ) -> None:
        """Register a method implementation with its config type."""
        self._methods[method_name] = implementation
        self._config_types[method_name] = config_type
        logger.debug(
            "Registered method: %s with config type: %s",
            method_name,
            config_type.__name__,
        )

    def create_method(
        self,
        method_name: str,
        config: ConfigType,
        **dependencies: Any,
    ) -> ProtocolType:
        """Create method implementation with config validation."""
        if method_name not in self._methods:
            available = list(self._methods.keys())
            raise ValueError(f"Unknown method: {method_name}. Available: {available}")

        # Validate config type matches expected type
        expected_config_type = self._config_types[method_name]
        if not isinstance(config, expected_config_type):
            raise TypeError(
                f"Expected {expected_config_type.__name__}, got {type(config).__name__}"
            )

        implementation_class = self._methods[method_name]
        return implementation_class(**dependencies)

    def get_available_methods(self) -> list[str]:
        """Get list of available method names."""
        available = []
        for method_name, impl_class in self._methods.items():
            try:
                # Try to create instance to check availability
                temp_impl = impl_class()
                if (
                    hasattr(temp_impl, "check_available")
                    and temp_impl.check_available()
                ):
                    available.append(method_name)
            except Exception:
                pass  # Method not available
        return available

    def get_registered_methods(self) -> list[str]:
        """Get list of all registered method names."""
        return list(self._methods.keys())


# Global registry instance for flash methods
# Note: Compilation methods are now handled by the compilation domain services
flasher_registry: MethodRegistry[USBFlashConfig, FlasherProtocol] = MethodRegistry()
