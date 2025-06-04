# Glovebox Utility Modules

This directory contains utility modules that provide shared functionality used across the Glovebox application. These utilities are designed to be simple, focused, and maintainable by a small team.

## Module Overview

### 1. Protocol Validation (`protocol_validator.py`)

Provides tools for validating Protocol implementations at runtime:

- `validate_protocol_implementation()`: Checks if a class correctly implements a Protocol
- `assert_implements_protocol()`: Asserts that an instance implements a Protocol

**When to use**:
- When you need to verify adapter implementations against their protocols
- For runtime validation of dependency implementations
- In test code to ensure implementations satisfy their interfaces

**Example**:
```python
from glovebox.utils import validate_protocol_implementation
from my_protocol import MyProtocol

is_valid, errors = validate_protocol_implementation(MyProtocol, MyImplementation)
if not is_valid:
    print(f"Implementation errors: {errors}")
```

### 2. Process Streaming (`stream_process.py`)

Provides utilities for executing and handling output from subprocess operations:

- `OutputMiddleware`: Base class for processing command output
- `run_command()`: Executes a command and processes its output

**When to use**:
- When you need to run shell commands and process their output
- For Docker operations that produce streaming output
- To provide user feedback during long-running operations

**Example**:
```python
from glovebox.utils.stream_process import run_command, DefaultOutputMiddleware

middleware = DefaultOutputMiddleware(stdout_prefix="INFO: ")
return_code, stdout, stderr = run_command("ls -la", middleware)
```

### 3. Error Utilities (`error_utils.py`)

Provides standardized error creation functions for consistent error handling:

- `create_error()`: Generic error creation for any GloveboxError subclass
- `create_file_error()`: Creates FileSystemError with context
- `create_usb_error()`: Creates USBError with context
- `create_template_error()`: Creates TemplateError with context
- `create_docker_error()`: Creates DockerError with context

**When to use**:
- When catching and re-raising exceptions in adapters
- To provide consistent error context across the application
- When wrapping external errors in application-specific errors

**Example**:
```python
from glovebox.utils import create_file_error

try:
    with open(file_path, 'r') as f:
        content = f.read()
except FileNotFoundError as e:
    error = create_file_error(file_path, "read", e, {"encoding": "utf-8"})
    raise error from e
```

### 4. File Utilities (`file_utils.py`)

Provides common file system operations and path handling functions:

- `prepare_output_paths()`: Generates standardized output paths from a prefix
- `sanitize_filename()`: Makes strings safe for use as filenames
- `create_timestamped_backup()`: Creates date-stamped backup files
- `ensure_directory_exists()`: Creates directories safely
- `find_files_by_extension()`: Finds files matching a specific extension

**When to use**:
- For consistent file path handling across services
- To create backups of important files
- When working with user-provided filenames
- For file search operations

**Example**:
```python
from glovebox.utils import prepare_output_paths, ensure_directory_exists

output_paths = prepare_output_paths("/tmp/my_keymap")
ensure_directory_exists(output_paths["keymap"].parent)
```

### 5. Serialization (`serialization.py`)

Provides utilities for data serialization and conversion:

- `make_json_serializable()`: Converts data to JSON-serializable format
- `normalize_dict()`: Standardizes dictionaries for consistent processing
- `parse_iso_datetime()`: Parses ISO format datetime strings

**When to use**:
- Before serializing complex data structures to JSON
- When handling datetime objects in serializable data
- To standardize input dictionaries for processing

**Example**:
```python
from glovebox.utils import make_json_serializable
from datetime import datetime

data = {"date": datetime.now(), "values": [1, 2, 3]}
serializable = make_json_serializable(data)
# Now safe to use with json.dumps()
```

### 6. Adapter Validation (`validate_adapters.py`)

Command-line utility script for validating all adapter implementations:

- `validate_all_adapters()`: Validates all adapter implementations against their protocols

**When to use**:
- During development to verify adapter implementations
- In CI/CD pipelines to ensure interface consistency
- After making changes to protocol definitions

**Usage**:
```bash
python -m glovebox.utils.validate_adapters
```

## Design Principles

These utilities follow the Team Size Reality Check principle from our conventions:

1. **Simplicity First**: Each utility has a clear, focused purpose
2. **Minimal Abstractions**: Simple functions or classes with clear interfaces
3. **Self-Contained**: Minimal dependencies on other parts of the system
4. **Well-Documented**: Clear examples and usage guidelines

## Adding New Utilities

When adding new utility functions:

1. Group related functions in a single module
2. Add proper type annotations
3. Write clear docstrings with examples
4. Update this README.md with a description of the new utility
5. Re-export commonly used functions in `__init__.py` if appropriate