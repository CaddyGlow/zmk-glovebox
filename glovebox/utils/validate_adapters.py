#!/usr/bin/env python
"""Utility script to validate adapter implementations against their protocols.

This script performs runtime validation of all adapter implementations to ensure
they correctly implement their protocol interfaces. It's designed to be run both
as part of the test suite and manually during development.

Usage:
    python -m glovebox.utils.validate_adapters

Exit codes:
    0: All adapters pass validation
    1: One or more adapters fail validation

Example:
    $ python -m glovebox.utils.validate_adapters
    INFO: Validating adapter implementations against protocols...

    INFO: Validating Docker adapter...
    INFO: Docker adapter implements protocol correctly.

    INFO: Validating File adapter...
    INFO: File adapter implements protocol correctly.
"""

import logging
import sys
from typing import Any

from glovebox.adapters.docker_adapter import DockerAdapter, DockerAdapterImpl
from glovebox.adapters.file_adapter import FileAdapter, FileSystemAdapter
from glovebox.adapters.template_adapter import JinjaTemplateAdapter, TemplateAdapter
from glovebox.adapters.usb_adapter import USBAdapter, USBAdapterImpl
from glovebox.utils.protocol_validator import validate_protocol_implementation


def setup_logging() -> logging.Logger:
    """Set up logging configuration for the validator.

    Creates a logger with a simple formatter that outputs to stdout.

    Returns:
        Configured Logger instance
    """
    logger = logging.getLogger("protocol_validator")

    # Remove existing handlers to avoid duplicates
    if logger.handlers:
        for handler in logger.handlers:
            logger.removeHandler(handler)

    # Create and configure handler
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


def validate_all_adapters() -> bool:
    """Validate all adapter implementations against their protocols.

    This function validates that each adapter implementation correctly
    implements its protocol interface. It checks method signatures,
    return types, and parameter types.

    Returns:
        True if all adapters pass validation, False otherwise

    Example:
        ```python
        if not validate_all_adapters():
            print("Some adapters failed validation!")
        ```
    """
    logger = setup_logging()
    logger.info("Validating adapter implementations against protocols...")

    all_valid = True

    # List of (protocol, implementation, friendly name) tuples to validate
    adapters_to_validate: list[tuple[type, type, str]] = [
        (DockerAdapter, DockerAdapterImpl, "Docker adapter"),
        (FileAdapter, FileSystemAdapter, "File adapter"),
        (TemplateAdapter, JinjaTemplateAdapter, "Template adapter"),
        (USBAdapter, USBAdapterImpl, "USB adapter"),
    ]

    # Validate each adapter implementation
    for protocol_cls, impl_cls, name in adapters_to_validate:
        logger.info(f"\nValidating {name}...")
        is_valid, errors = validate_protocol_implementation(protocol_cls, impl_cls)

        if not is_valid:
            all_valid = False
            logger.error(f"{name} validation failed with the following errors:")
            for i, error in enumerate(errors, 1):
                logger.error(f"  {i}. {error}")
        else:
            logger.info(f"{name} implements protocol correctly.")

    return all_valid


if __name__ == "__main__":
    valid = validate_all_adapters()
    sys.exit(0 if valid else 1)
