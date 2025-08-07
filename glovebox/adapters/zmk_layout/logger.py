"""Glovebox implementation of LayoutLogger for zmk-layout."""

import logging
from typing import Any

from glovebox.models.base import GloveboxBaseModel


class GloveboxLogger(GloveboxBaseModel):
    """Logger that bridges glovebox logging service to zmk-layout."""

    def __init__(self, logging_service: Any, component: str = "zmk_layout") -> None:
        super().__init__()
        self.logger = logging_service.get_logger(component)
        self.component = component

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message with optional context."""
        self.logger.debug(message, extra={"component": self.component, **kwargs})

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message with optional context."""
        self.logger.info(message, extra={"component": self.component, **kwargs})

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message with optional context."""
        self.logger.warning(message, extra={"component": self.component, **kwargs})

    def error(self, message: str, exc_info: bool = False, **kwargs: Any) -> None:
        """Log error message with optional exception info."""
        self.logger.error(
            message, exc_info=exc_info, extra={"component": self.component, **kwargs}
        )

    def exception(self, message: str, **kwargs: Any) -> None:
        """Log exception with traceback."""
        self.logger.exception(message, extra={"component": self.component, **kwargs})

    def log_layout_operation(
        self, operation: str, keyboard: str, **details: Any
    ) -> None:
        """Log layout-specific operation (glovebox extension)."""
        self.info(
            f"Layout operation: {operation}",
            operation=operation,
            keyboard=keyboard,
            **details,
        )

    def log_performance_metric(
        self, metric_name: str, value: float, unit: str = "ms"
    ) -> None:
        """Log performance metrics (glovebox extension)."""
        self.info(
            f"Performance metric: {metric_name}",
            metric=metric_name,
            value=value,
            unit=unit,
            category="performance",
        )
