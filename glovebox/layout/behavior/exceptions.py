"""Behavior-specific exceptions for the layout behavior system."""

from glovebox.core.errors import GloveboxError


class BehaviorError(GloveboxError):
    """Base exception for behavior-related errors."""


class BehaviorRegistrationError(BehaviorError):
    """Exception raised when behavior registration fails."""


class BehaviorNotFoundError(BehaviorError):
    """Exception raised when a referenced behavior is not found in the registry."""

    def __init__(self, behavior_code: str, context: str = "") -> None:
        """Initialize with behavior code and optional context.

        Args:
            behavior_code: The behavior code that was not found
            context: Optional context about where the behavior was referenced
        """
        self.behavior_code = behavior_code
        self.behavior_context = context
        msg = f"Behavior '{behavior_code}' not found in registry"
        if context:
            msg += f" (referenced in {context})"
        super().__init__(msg)


class BehaviorConflictError(BehaviorError):
    """Exception raised when there are conflicting behavior definitions."""

    def __init__(
        self, behavior_code: str, existing_origin: str, new_origin: str
    ) -> None:
        """Initialize with conflicting behavior information.

        Args:
            behavior_code: The behavior code with the conflict
            existing_origin: Origin of the existing behavior definition
            new_origin: Origin of the conflicting behavior definition
        """
        self.behavior_code = behavior_code
        self.existing_origin = existing_origin
        self.new_origin = new_origin
        super().__init__(
            f"Behavior '{behavior_code}' already registered from '{existing_origin}', "
            f"cannot register from '{new_origin}'"
        )


class BehaviorValidationError(BehaviorError):
    """Exception raised when behavior validation fails."""
