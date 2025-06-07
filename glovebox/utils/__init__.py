"""Utility modules and functions for the Glovebox application.

This package provides shared utility functions organized into logical groups:

1. Process Streaming: Utilities for subprocess execution and output handling
2. Error Utilities: Standardized error creation and handling functions
3. File Utilities: Common file system operations and path handling
4. Serialization: JSON serialization and data conversion utilities

See the README.md file in this directory for detailed documentation.
"""

# Group 2: Error Utilities
from glovebox.utils.error_utils import (
    create_docker_error,
    create_error,
    create_file_error,
    create_template_error,
    create_usb_error,
)

# Group 3: File Utilities
from glovebox.utils.file_utils import (
    create_timestamped_backup,
    ensure_directory_exists,
    find_files_by_extension,
    get_parent_directory,
)

# Group 4: Serialization
from glovebox.utils.serialization import (
    make_json_serializable,
    normalize_dict,
    parse_iso_datetime,
)

# Group 1: Process Streaming
from glovebox.utils.stream_process import (
    DefaultOutputMiddleware,
    OutputMiddleware,
    run_command,
)
