# Code Style Guide

This document outlines the mandatory code style and conventions for the Glovebox project. All code MUST follow these conventions without exception.

## CRITICAL Requirements

### Mandatory Linting
**ALL code MUST pass linting before being considered complete:**

```bash
# Required before any commit
ruff check . --fix
ruff format .
mypy glovebox/

# Pre-commit hooks (automatically runs above)
pre-commit run --all-files
```

### File Size Limits
- **Maximum 500 lines per file** (ENFORCED)
- **Maximum 50 lines per method** (ENFORCED)
- Break large files into smaller, focused modules
- Extract complex methods into smaller functions

### Zero Tolerance Linting Violations
These violations MUST be fixed immediately:

- **SIM117**: Use single `with` statement with multiple contexts
- **UP035**: Use modern typing (`dict` not `typing.Dict`)
- **PTH123**: Use `Path.open()` not built-in `open()`
- **B904**: Use `raise ... from err` in except clauses
- **N815**: No mixedCase variable names in class scope
- **SIM102**: Use single if statement instead of nested if statements

## Import Standards

### Modern Typing
```python
# ✅ CORRECT - Modern typing
from typing import Optional, Union
from collections.abc import Sequence, Mapping

def process_data(items: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    return mapping

# ❌ INCORRECT - Legacy typing
from typing import List, Dict, Sequence, Mapping

def process_data(items: List[str]) -> Dict[str, int]:
    mapping: Dict[str, int] = {}
    return mapping
```

### Import Organization
```python
# ✅ CORRECT - Import order
# 1. Standard library
import json
import logging
from pathlib import Path
from typing import Optional

# 2. Third-party packages
import typer
from pydantic import BaseModel

# 3. Local imports (absolute)
from glovebox.core.errors import GloveboxError
from glovebox.models.config import KeyboardConfig
from glovebox.layout import create_layout_service

# ❌ INCORRECT - Mixed import order, relative imports
from glovebox.core.errors import GloveboxError
import json
from pydantic import BaseModel
from ..models.config import KeyboardConfig  # No relative imports
import typer
```

## File Operations

### Path Handling
```python
# ✅ CORRECT - Use pathlib
from pathlib import Path

def read_config_file(config_path: Path) -> str:
    with config_path.open() as f:
        return f.read()

def write_output(output_dir: Path, content: str) -> None:
    output_file = output_dir / "output.txt"
    with output_file.open("w") as f:
        f.write(content)

# ❌ INCORRECT - Built-in open() or os.path
import os

def read_config_file(config_path: str) -> str:
    with open(config_path) as f:  # Use Path.open()
        return f.read()

def write_output(output_dir: str, content: str) -> None:
    output_file = os.path.join(output_dir, "output.txt")  # Use Path
    with open(output_file, "w") as f:
        f.write(content)
```

### Multiple Context Managers
```python
# ✅ CORRECT - Single with statement
def copy_file_contents(src: Path, dst: Path) -> None:
    with src.open() as src_file, dst.open("w") as dst_file:
        dst_file.write(src_file.read())

# ❌ INCORRECT - Nested with statements
def copy_file_contents(src: Path, dst: Path) -> None:
    with src.open() as src_file:
        with dst.open("w") as dst_file:  # SIM117 violation
            dst_file.write(src_file.read())
```

## Error Handling

### Exception Chaining
```python
# ✅ CORRECT - Exception chaining
def load_config(config_path: Path) -> dict:
    try:
        with config_path.open() as f:
            return json.load(f)
    except FileNotFoundError as e:
        raise ConfigurationError(f"Config file not found: {config_path}") from e
    except json.JSONDecodeError as e:
        raise ConfigurationError(f"Invalid JSON in config: {config_path}") from e

# ❌ INCORRECT - No exception chaining
def load_config(config_path: Path) -> dict:
    try:
        with config_path.open() as f:
            return json.load(f)
    except FileNotFoundError as e:
        raise ConfigurationError(f"Config file not found: {config_path}")  # B904
    except json.JSONDecodeError as e:
        raise ConfigurationError(f"Invalid JSON in config: {config_path}")  # B904
```

### Conditional Logic
```python
# ✅ CORRECT - Single if statement
def validate_config(config: dict) -> bool:
    if "keyboard" not in config or not config["keyboard"]:
        return False
    return True

# ❌ INCORRECT - Nested if statements  
def validate_config(config: dict) -> bool:
    if "keyboard" in config:
        if config["keyboard"]:  # SIM102 violation
            return True
    return False
```

## Logging Standards

### Lazy Formatting
```python
# ✅ CORRECT - Lazy logging with % formatting
import logging

logger = logging.getLogger(__name__)

def process_layout(layout_name: str, layer_count: int) -> None:
    logger.info("Processing layout %s with %d layers", layout_name, layer_count)
    logger.debug("Layout details: name=%s, layers=%d", layout_name, layer_count)

# ❌ INCORRECT - f-string or .format() in logging
def process_layout(layout_name: str, layer_count: int) -> None:
    logger.info(f"Processing layout {layout_name} with {layer_count} layers")  # No f-strings
    logger.debug("Layout details: name={}, layers={}".format(layout_name, layer_count))  # No .format()
```

### Log Levels
```python
# ✅ CORRECT - Appropriate log levels
logger.debug("Internal state: %s", internal_data)           # Development info
logger.info("Processing started for %s", item_name)         # User-facing events
logger.warning("Deprecated option used: %s", option_name)   # Recoverable issues
logger.error("Failed to process %s: %s", item_name, error)  # Operation failures
logger.critical("System failure: %s", system_error)        # System failures
```

## Type Annotations

### Comprehensive Typing
```python
# ✅ CORRECT - Complete type annotations
from typing import Optional, Union
from pathlib import Path

def process_files(
    input_files: list[Path],
    output_dir: Path,
    options: Optional[dict[str, str]] = None
) -> dict[str, bool]:
    """Process files with type safety."""
    results: dict[str, bool] = {}
    
    for file_path in input_files:
        success = process_single_file(file_path, output_dir, options)
        results[file_path.name] = success
    
    return results

def process_single_file(
    file_path: Path,
    output_dir: Path,
    options: Optional[dict[str, str]]
) -> bool:
    """Process a single file."""
    # Implementation...
    return True

# ❌ INCORRECT - Missing or incomplete type annotations
def process_files(input_files, output_dir, options=None):  # No types
    results = {}  # No type annotation
    
    for file_path in input_files:
        success = process_single_file(file_path, output_dir, options)
        results[file_path.name] = success
    
    return results
```

### Union vs Optional
```python
# ✅ CORRECT - Use Optional for None unions
from typing import Optional

def get_config_value(key: str) -> Optional[str]:
    """Get config value, return None if not found."""
    return config.get(key)

# Modern Python 3.10+ alternative (if targeting 3.10+)
def get_config_value(key: str) -> str | None:
    """Get config value, return None if not found."""
    return config.get(key)

# ❌ INCORRECT - Verbose Union syntax
from typing import Union

def get_config_value(key: str) -> Union[str, None]:  # Use Optional[str]
    return config.get(key)
```

## Class Design

### Dataclasses and Pydantic
```python
# ✅ CORRECT - Use Pydantic for data models
from pydantic import BaseModel, Field
from typing import Optional

class KeyboardConfig(BaseModel):
    """Keyboard configuration model."""
    keyboard: str = Field(..., description="Keyboard identifier")
    description: str = Field(..., description="Human-readable description")
    vendor: str = Field(..., description="Keyboard vendor")
    key_count: int = Field(..., gt=0, description="Number of keys")
    version: Optional[str] = Field(None, description="Configuration version")

# ✅ CORRECT - Use dataclasses for simple data containers
from dataclasses import dataclass
from typing import Optional

@dataclass
class BuildOptions:
    """Build configuration options."""
    output_dir: Path
    jobs: int = 1
    verbose: bool = False
    clean_build: bool = False

# ❌ INCORRECT - Manual __init__ for simple data
class BuildOptions:
    def __init__(
        self,
        output_dir: Path,
        jobs: int = 1,
        verbose: bool = False,
        clean_build: bool = False
    ):
        self.output_dir = output_dir
        self.jobs = jobs
        self.verbose = verbose
        self.clean_build = clean_build
```

### Class Variable Naming
```python
# ✅ CORRECT - snake_case class variables
class LayoutService:
    """Layout processing service."""
    default_timeout: int = 30
    max_retries: int = 3
    supported_formats: list[str] = ["json", "yaml"]
    
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        self.is_initialized = False

# ❌ INCORRECT - mixedCase class variables
class LayoutService:
    defaultTimeout: int = 30        # N815 violation
    maxRetries: int = 3             # N815 violation
    supportedFormats: list[str] = ["json", "yaml"]  # N815 violation
```

## Function Design

### Function Length and Complexity
```python
# ✅ CORRECT - Small, focused functions (under 50 lines)
def validate_layout_data(layout_data: dict) -> list[str]:
    """Validate layout data structure."""
    errors: list[str] = []
    
    errors.extend(_validate_required_fields(layout_data))
    errors.extend(_validate_layer_structure(layout_data))
    errors.extend(_validate_behavior_references(layout_data))
    
    return errors

def _validate_required_fields(layout_data: dict) -> list[str]:
    """Validate required fields are present."""
    errors: list[str] = []
    required_fields = ["metadata", "layers"]
    
    for field in required_fields:
        if field not in layout_data:
            errors.append(f"Missing required field: {field}")
    
    return errors

def _validate_layer_structure(layout_data: dict) -> list[str]:
    """Validate layer structure."""
    errors: list[str] = []
    
    if "layers" not in layout_data:
        return errors
    
    layers = layout_data["layers"]
    if not isinstance(layers, list):
        errors.append("Layers must be a list")
    
    return errors

# ❌ INCORRECT - Large, complex function (would exceed 50 lines)
def validate_layout_data(layout_data: dict) -> list[str]:
    """Validate layout data structure."""
    errors: list[str] = []
    
    # Required fields validation (10+ lines)
    required_fields = ["metadata", "layers"]
    for field in required_fields:
        if field not in layout_data:
            errors.append(f"Missing required field: {field}")
    
    # Layer structure validation (15+ lines)
    if "layers" in layout_data:
        layers = layout_data["layers"]
        if not isinstance(layers, list):
            errors.append("Layers must be a list")
        else:
            for i, layer in enumerate(layers):
                if not isinstance(layer, dict):
                    errors.append(f"Layer {i} must be an object")
                # ... more validation logic
    
    # Behavior validation (20+ lines)
    if "behaviors" in layout_data:
        behaviors = layout_data["behaviors"]
        # ... extensive behavior validation
    
    return errors
```

### Parameter Handling
```python
# ✅ CORRECT - Clear parameter types and defaults
def generate_keymap(
    layout_data: LayoutData,
    profile: KeyboardProfile,
    output_prefix: str,
    *,  # Force keyword-only arguments
    force_overwrite: bool = False,
    validate: bool = True,
    include_debug: bool = False
) -> LayoutResult:
    """Generate keymap files from layout data."""
    # Implementation...

# ❌ INCORRECT - Unclear parameters, positional arguments
def generate_keymap(
    layout_data,        # No type annotation
    profile,           # No type annotation
    output_prefix,     # No type annotation
    force_overwrite=False,  # Allow positional
    validate=True,     # Allow positional
    include_debug=False # Allow positional
):
    # Implementation...
```

## Documentation Standards

### Docstring Format
```python
# ✅ CORRECT - Complete docstrings
def compile_firmware(
    keymap_file: Path,
    kconfig_file: Path,
    profile: KeyboardProfile,
    options: BuildServiceCompileOpts
) -> BuildResult:
    """Compile ZMK firmware from keymap and configuration files.
    
    Args:
        keymap_file: Path to ZMK keymap (.keymap) file
        kconfig_file: Path to ZMK configuration (.conf) file
        profile: Keyboard profile with build configuration
        options: Compilation options and settings
        
    Returns:
        BuildResult with compilation status and output files
        
    Raises:
        BuildError: If compilation fails due to invalid configuration
        DockerNotFoundError: If Docker is not available
        
    Example:
        >>> profile = create_keyboard_profile("glove80", "v25.05")
        >>> options = BuildServiceCompileOpts(output_dir=Path("build/"))
        >>> result = compile_firmware(
        ...     keymap_file=Path("layout.keymap"),
        ...     kconfig_file=Path("config.conf"),
        ...     profile=profile,
        ...     options=options
        ... )
        >>> print(f"Success: {result.success}")
    """
    # Implementation...

# ❌ INCORRECT - Missing or incomplete docstring
def compile_firmware(keymap_file, kconfig_file, profile, options):
    """Compile firmware."""  # Too brief, no parameter docs
    # Implementation...
```

### Inline Comments
```python
# ✅ CORRECT - Explain WHY, not WHAT
def calculate_build_matrix(profile: KeyboardProfile) -> dict[str, list[str]]:
    """Calculate build matrix for GitHub Actions."""
    # Use shield name for split keyboards to ensure proper target naming
    # This follows ZMK's convention where split keyboards need separate builds
    if profile.is_split_keyboard():
        shield_name = profile.get_shield_name()
        return {
            "shield": [f"{shield_name}_left", f"{shield_name}_right"],
            "board": [profile.board_name]
        }
    
    # Single board keyboards use direct board targeting
    return {
        "board": [profile.board_name]
    }

# ❌ INCORRECT - Comments explain obvious code
def calculate_build_matrix(profile: KeyboardProfile) -> dict[str, list[str]]:
    """Calculate build matrix for GitHub Actions."""
    # Check if profile is split keyboard
    if profile.is_split_keyboard():
        # Get shield name
        shield_name = profile.get_shield_name()
        # Return matrix with left and right shields
        return {
            "shield": [f"{shield_name}_left", f"{shield_name}_right"],
            "board": [profile.board_name]
        }
    
    # Return matrix with board name
    return {
        "board": [profile.board_name]
    }
```

## Testing Standards

### Test Function Names
```python
# ✅ CORRECT - Descriptive test names
def test_layout_service_generates_valid_keymap_with_macros():
    """Test that LayoutService generates valid keymap with macro behaviors."""
    
def test_flash_service_handles_device_not_found_error():
    """Test that FlashService raises appropriate error when device not found."""
    
def test_keyboard_profile_loads_optional_firmware_section():
    """Test KeyboardProfile handles keyboards with optional firmware config."""

# ❌ INCORRECT - Vague test names
def test_layout_service():
    """Test layout service."""
    
def test_flash_error():
    """Test flash error."""
    
def test_profile_loading():
    """Test profile loading."""
```

### Test Structure
```python
# ✅ CORRECT - Clear test structure with AAA pattern
def test_device_detector_finds_matching_devices():
    """Test DeviceDetector finds devices matching query criteria."""
    # Arrange
    detector = create_device_detector()
    mock_devices = [
        create_mock_device(vendor="Adafruit", serial="GLV80-001"),
        create_mock_device(vendor="Generic", serial="USB-001"),
        create_mock_device(vendor="Adafruit", serial="GLV80-002"),
    ]
    detector._devices = mock_devices
    
    # Act
    found_devices = detector.find_devices("vendor=Adafruit")
    
    # Assert
    assert len(found_devices) == 2
    assert all(device.vendor == "Adafruit" for device in found_devices)
    assert found_devices[0].serial == "GLV80-001"
    assert found_devices[1].serial == "GLV80-002"
```

## Performance Guidelines

### Lazy Evaluation
```python
# ✅ CORRECT - Lazy evaluation for expensive operations
class KeyboardProfileCache:
    """Cache for keyboard profiles."""
    
    def __init__(self) -> None:
        self._profiles: dict[str, KeyboardProfile] = {}
    
    def get_profile(self, keyboard: str, firmware: str) -> KeyboardProfile:
        """Get profile, loading if not cached."""
        cache_key = f"{keyboard}/{firmware}"
        
        if cache_key not in self._profiles:
            # Only load when needed
            self._profiles[cache_key] = self._load_profile(keyboard, firmware)
        
        return self._profiles[cache_key]

# ❌ INCORRECT - Eager loading
class KeyboardProfileCache:
    """Cache for keyboard profiles."""
    
    def __init__(self) -> None:
        # Don't load everything upfront
        self._profiles = {
            profile_name: self._load_profile(keyboard, firmware)
            for keyboard in get_all_keyboards()
            for firmware in get_all_firmwares(keyboard)
            for profile_name in [f"{keyboard}/{firmware}"]
        }
```

### Resource Management
```python
# ✅ CORRECT - Proper resource cleanup
class DockerBuildService:
    """Service for Docker-based builds."""
    
    def compile_firmware(self, options: BuildOptions) -> BuildResult:
        """Compile firmware using Docker."""
        container_id: Optional[str] = None
        
        try:
            container_id = self._start_build_container(options)
            result = self._run_build(container_id, options)
            return result
        finally:
            # Always cleanup, even on exceptions
            if container_id:
                self._cleanup_container(container_id)

# ❌ INCORRECT - No cleanup on exceptions
class DockerBuildService:
    """Service for Docker-based builds."""
    
    def compile_firmware(self, options: BuildOptions) -> BuildResult:
        """Compile firmware using Docker."""
        container_id = self._start_build_container(options)
        result = self._run_build(container_id, options)
        
        # Cleanup only on success - container leaks on exceptions
        self._cleanup_container(container_id)
        return result
```

This style guide ensures consistent, maintainable, and high-quality code across the Glovebox project. All contributions must follow these conventions.