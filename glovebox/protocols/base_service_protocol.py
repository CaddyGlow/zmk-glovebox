"""Protocol definitions for base service interfaces."""

from typing import Protocol, runtime_checkable


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
