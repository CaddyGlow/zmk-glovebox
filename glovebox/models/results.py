"""Base result model for cross-domain operations."""

import logging
from datetime import datetime
from typing import Any

from pydantic import Field, field_validator, model_validator

from glovebox.core.structlog_logger import get_struct_logger
from glovebox.models.base import GloveboxBaseModel


logger = get_struct_logger(__name__)


class BaseResult(GloveboxBaseModel):
    """Base class for all operation results."""

    success: bool
    timestamp: datetime = Field(default_factory=datetime.now)
    messages: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_success_consistency(self) -> "BaseResult":
        """Ensure success flag is consistent with errors."""
        if self.errors and self.success:
            logger.warning("result_success_mismatch", has_errors=len(self.errors) > 0)
            self.success = False
        return self

    @field_validator("messages", "errors")
    @classmethod
    def validate_message_lists(cls, v: list[str]) -> list[str]:
        """Validate that message lists contain only strings."""
        if not isinstance(v, list):
            raise ValueError("Messages and errors must be lists")
        for item in v:
            if not isinstance(item, str):
                raise ValueError("All messages and errors must be strings")
        return v

    def add_message(self, message: str) -> None:
        """Add an informational message."""
        if not isinstance(message, str):
            raise ValueError("Message must be a string") from None
        self.messages.append(message)
        logger.info("result_message_added", message=message)

    def add_error(self, error: str) -> None:
        """Add an error message."""
        if not isinstance(error, str):
            raise ValueError("Error must be a string") from None
        self.errors.append(error)
        logger.error(error)
        self.success = False

    def is_success(self) -> bool:
        """Check if the operation was successful."""
        return self.success and not self.errors

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the result."""
        return {
            "success": self.success,
            "timestamp": self.timestamp.isoformat(),
            "message_count": len(self.messages),
            "error_count": len(self.errors),
            "errors": self.errors if self.errors else None,
        }


__all__ = ["BaseResult"]
