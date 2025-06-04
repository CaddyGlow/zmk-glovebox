"""Utility modules and functions for the Glovebox application.

This package provides shared utility functions organized into logical groups:

1. Protocol Validation: Tools for validating Protocol implementations
2. Process Streaming: Utilities for subprocess execution and output handling
3. Error Utilities: Standardized error creation and handling functions
4. File Utilities: Common file system operations and path handling
5. Serialization: JSON serialization and data conversion utilities
6. Adapter Validation: Command-line tools for validating adapter implementations

See the README.md file in this directory for detailed documentation.
"""

# Group 1: Protocol Validation
# Group 3: Error Utilities
from glovebox.utils.error_utils import (
    create_docker_error,
    create_error,
    create_file_error,
    create_template_error,
    create_usb_error,
)

# Group 4: File Utilities
from glovebox.utils.file_utils import (
    create_timestamped_backup,
    ensure_directory_exists,
    find_files_by_extension,
    get_parent_directory,
    prepare_output_paths,
    sanitize_filename,
)
from glovebox.utils.protocol_validator import (
    assert_implements_protocol,
    validate_protocol_implementation,
)

# Group 5: Serialization
from glovebox.utils.serialization import (
    make_json_serializable,
    normalize_dict,
    parse_iso_datetime,
)

# Group 2: Process Streaming
from glovebox.utils.stream_process import (
    DefaultOutputMiddleware,
    OutputMiddleware,
    run_command,
)
