"""Base service protocol definition for all Glovebox services."""

import logging
from typing import Protocol, runtime_checkable


logger = logging.getLogger(__name__)


@runtime_checkable
class BaseServiceProtocol(Protocol):
    """Protocol defining the base interface for all Glovebox services.

    All service classes should implement this protocol to ensure consistent
    interface and behavior across the application.

    Services are responsible for implementing business logic and coordinating
    between various adapters and models. They should not directly interact
    with external systems - this should be delegated to adapters.
    """

    def get_service_info(self) -> dict[str, str]:
        """Get basic information about this service.

        Returns:
            Dictionary containing service name, version, and other metadata.
        """
        ...


class BaseService:
    """Base implementation class for Glovebox services.

    Provides common functionality for all service implementations.
    Services should inherit from this class to gain common behavior.

    Attributes:
        _service_name: The name of this service
        _service_version: The version of this service
    """

    def __init__(self, service_name: str, service_version: str = "1.0.0"):
        """Initialize the base service.

        Args:
            service_name: The name of this service
            service_version: The version of this service
        """
        self._service_name = service_name
        self._service_version = service_version
        logger.debug(f"Initializing {service_name} service (v{service_version})")

    def get_service_info(self) -> dict[str, str]:
        """Get basic information about this service.

        Returns:
            Dictionary containing service name, version, and other metadata.
        """
        return {
            "name": self._service_name,
            "version": self._service_version,
            "type": self.__class__.__name__,
        }
