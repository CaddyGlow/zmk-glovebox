"""Utility modules and functions for the Glovebox application.

This package provides shared utility functions organized into logical groups:

1. Process Streaming: Utilities for subprocess execution and output handling
2. Error Utilities: Standardized error creation and handling functions
3. Diagnostics: Comprehensive system diagnostic data collection
4. File Utilities: Common file system operations and path handling
5. Serialization: JSON serialization and data conversion utilities

See the README.md file in this directory for detailed documentation.
"""

# Group 3: Diagnostics
from glovebox.utils.diagnostics import (
    collect_all_diagnostics,
    collect_config_diagnostics,
    collect_docker_diagnostics,
    collect_layout_diagnostics,
    collect_system_diagnostics,
    collect_usb_flash_diagnostics,
)

# Group 2: Error Utilities
from glovebox.utils.error_utils import (
    create_docker_error,
    create_error,
    create_file_error,
    create_template_error,
    create_usb_error,
)

# Group 1: Process Streaming
from glovebox.utils.stream_process import (
    DefaultOutputMiddleware,
    OutputMiddleware,
    run_command,
)
