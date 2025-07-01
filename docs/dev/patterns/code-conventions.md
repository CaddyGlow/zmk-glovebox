# Code Conventions and Standards

This document defines the mandatory code conventions and standards for Glovebox development. These conventions ensure consistency, maintainability, and quality across the entire codebase.

## 🚨 MANDATORY Requirements

These requirements are **ENFORCED** and **NON-NEGOTIABLE**:

### File and Method Limits

- ✅ **Maximum 500 lines per file** (ENFORCED)
- ✅ **Maximum 50 lines per method** (ENFORCED)
- ✅ **Split large files** into domain-specific modules
- ✅ **Break down complex methods** into smaller, focused functions

### Code Quality Gates

- ✅ **ALL code MUST pass linting**: `ruff check . && ruff format .`
- ✅ **ALL code MUST pass type checking**: `mypy glovebox/`
- ✅ **Minimum 90% test coverage** for new code
- ✅ **NO CODE can be merged without tests**

### Pre-Commit Requirements

```bash
# MANDATORY before every commit
make lint          # Fix all linting issues
make test          # All tests must pass
pre-commit run --all-files  # Pre-commit hooks must pass
```

## Naming Conventions

### Class Naming Standards

Follow these **MANDATORY** naming patterns:

```python
# ✅ CORRECT - Adapter classes use *Adapter suffix
class DockerAdapter:
    pass

class FileAdapter:
    pass

class USBAdapter:
    pass

# ✅ CORRECT - Service classes use *Service suffix
class LayoutService(BaseService):
    pass

class FlashService:
    pass

class CompilationService:
    pass

# ✅ CORRECT - Protocol classes use *Protocol suffix
class FileAdapterProtocol(Protocol):
    pass

class BaseServiceProtocol(Protocol):
    pass

# ❌ INCORRECT - Never use Impl suffix
class LayoutServiceImpl:  # WRONG
    pass

class FileAdapterImpl:  # WRONG
    pass
```

### Function Naming Standards

Use **descriptive verbs** that clearly indicate purpose:

```python
# ✅ CORRECT - Descriptive function names
def check_exists(path: Path) -> bool:
    """Check if file or directory exists."""
    return path.exists()

def create_directory(path: Path) -> None:
    """Create directory with parent directories if needed."""
    path.mkdir(parents=True, exist_ok=True)

def mount_device(device: BlockDevice) -> list[str]:
    """Mount USB device and return mount points."""
    # Implementation

# ❌ INCORRECT - Terse/unclear function names
def exists(path: Path) -> bool:  # Too generic
    pass

def mkdir(path: Path) -> None:  # Unix-style abbreviation
    pass

def mount(device):  # Unclear what it returns
    pass
```

### Layout Domain Specific Standards

```python
# ✅ CORRECT - Component operations
def decompose_components(layout: LayoutData) -> ComponentResult:
    """Split layout into separate component files."""
    pass

def compose_components(components: list[Path]) -> LayoutData:
    """Combine component files into complete layout."""
    pass

# ✅ CORRECT - Display operations
def show_layout(layout: LayoutData, mode: ViewMode) -> None:
    """Display layout in terminal with specified view mode."""
    pass

def format_layout_grid(layout: LayoutData) -> str:
    """Format layout as grid representation."""
    pass
```

### Factory Function Pattern

All factory functions follow the `create_*` pattern:

```python
# ✅ CORRECT - Factory function naming
def create_layout_service() -> LayoutService:
    """Create layout service with default dependencies."""
    pass

def create_keyboard_profile(keyboard: str, firmware: str = None) -> KeyboardProfile:
    """Create keyboard profile from configuration."""
    pass

def create_docker_adapter() -> DockerAdapterProtocol:
    """Create Docker adapter with default configuration."""
    pass

# ❌ INCORRECT - Inconsistent factory naming
def get_layout_service():  # Should be 'create_'
    pass

def new_keyboard_profile():  # Should be 'create_'
    pass

def make_docker_adapter():  # Should be 'create_'
    pass
```

## Type Annotations

### Comprehensive Typing Requirements

**ALL** function parameters and return types MUST be typed:

```python
# ✅ CORRECT - Comprehensive typing
def process_layout_file(
    file_path: Path,
    profile: KeyboardProfile,
    output_dir: Path | None = None,
    validate_only: bool = False
) -> LayoutResult:
    """Process layout file with complete type annotations."""
    pass

# ✅ CORRECT - Modern typing syntax
from typing import Union  # Import if needed for older Python

def handle_multiple_inputs(
    inputs: list[str],
    options: dict[str, Any],
    callback: Callable[[str], bool] | None = None
) -> tuple[bool, str]:
    """Use modern typing syntax."""
    pass

# ❌ INCORRECT - Missing type annotations
def process_file(file_path, profile, output_dir=None):  # NO TYPES
    pass

# ❌ INCORRECT - Old typing syntax
def handle_inputs(inputs: List[str], options: Dict[str, Any]) -> Tuple[bool, str]:
    pass  # Use list, dict, tuple instead of List, Dict, Tuple
```

### Protocol Usage

Define and use protocols for type safety:

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class FileAdapterProtocol(Protocol):
    """Protocol defining file adapter interface."""
    
    def read_file(self, path: Path) -> str:
        """Read text content from file."""
        ...
    
    def write_file(self, path: Path, content: str) -> None:
        """Write text content to file."""
        ...

# Use protocols in service constructors
class LayoutService:
    def __init__(self, file_adapter: FileAdapterProtocol):
        # Runtime checking (optional but recommended)
        assert isinstance(file_adapter, FileAdapterProtocol)
        self.file_adapter = file_adapter
```

## File Operations

### Pathlib Requirements

**MANDATORY**: Use `pathlib` for ALL file operations:

```python
from pathlib import Path

# ✅ CORRECT - Use pathlib.Path
def read_layout_file(file_path: Path) -> LayoutData:
    """Read layout from file using pathlib."""
    content = file_path.read_text(encoding="utf-8")
    return LayoutData.model_validate_json(content)

def write_keymap_file(output_path: Path, content: str) -> None:
    """Write keymap content using pathlib."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")

# ✅ CORRECT - Use Path.open() instead of built-in open()
def process_large_file(file_path: Path) -> Iterator[str]:
    """Process large file line by line."""
    with file_path.open(encoding="utf-8") as f:
        for line in f:
            yield line.strip()

# ❌ INCORRECT - Never use os.path
import os.path  # FORBIDDEN

def bad_read_file(file_path: str) -> str:
    if os.path.exists(file_path):  # WRONG
        with open(file_path) as f:  # WRONG - use Path.open()
            return f.read()

# ❌ INCORRECT - String path manipulation
def bad_path_handling(base_path: str, filename: str) -> str:
    return base_path + "/" + filename  # WRONG - use Path / operator
```

### File Operation Patterns

```python
# ✅ CORRECT - Comprehensive file handling
def save_layout_safely(layout: LayoutData, output_path: Path) -> None:
    """Save layout with proper error handling."""
    try:
        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write with explicit encoding
        content = layout.model_dump_json(indent=2)
        output_path.write_text(content, encoding="utf-8")
        
    except PermissionError as e:
        raise FileSystemError(f"Permission denied writing to {output_path}") from e
    except OSError as e:
        raise FileSystemError(f"Failed to write file {output_path}: {e}") from e

# ✅ CORRECT - Safe file reading
def load_layout_safely(file_path: Path) -> LayoutData:
    """Load layout with comprehensive error handling."""
    try:
        if not file_path.exists():
            raise FileNotFoundError(f"Layout file not found: {file_path}")
        
        content = file_path.read_text(encoding="utf-8")
        return LayoutData.model_validate_json(content)
        
    except json.JSONDecodeError as e:
        raise LayoutError(f"Invalid JSON in {file_path}: {e}") from e
    except ValidationError as e:
        raise LayoutError(f"Invalid layout data in {file_path}: {e}") from e
```

## Pydantic Model Standards

### MANDATORY Model Requirements

**ALL** Pydantic models MUST inherit from `GloveboxBaseModel`:

```python
from glovebox.models.base import GloveboxBaseModel

# ✅ CORRECT - Always inherit from GloveboxBaseModel
class LayoutData(GloveboxBaseModel):
    """Layout data model."""
    title: str
    keyboard: str
    layers: list[LayoutLayer]

class KeyboardConfig(GloveboxBaseModel):
    """Keyboard configuration model."""
    name: str
    description: str
    boards: list[str]
```

### Model Serialization Standards

**NEVER** use `.to_dict()` - **ALWAYS** use `.model_dump()`:

```python
# ✅ CORRECT - Use model_dump with proper parameters
def serialize_layout(layout: LayoutData) -> dict[str, Any]:
    """Serialize layout with proper parameters."""
    return layout.model_dump(by_alias=True, exclude_unset=True, mode="json")

# ✅ CORRECT - Use inherited to_dict() method (calls model_dump correctly)
def serialize_layout_alternative(layout: LayoutData) -> dict[str, Any]:
    """Use the inherited to_dict method."""
    return layout.to_dict()

# ✅ CORRECT - JSON serialization
def save_layout_json(layout: LayoutData, path: Path) -> None:
    """Save layout as JSON file."""
    json_data = layout.model_dump_json(indent=2, by_alias=True)
    path.write_text(json_data, encoding="utf-8")

# ❌ INCORRECT - Never call model_dump without parameters
def bad_serialize(layout: LayoutData) -> dict:
    return layout.model_dump()  # Missing required parameters

# ❌ INCORRECT - Never use deprecated methods
def bad_serialize_old(layout: LayoutData) -> dict:
    return layout.dict()  # Deprecated in Pydantic v2
```

### Model Validation Standards

```python
# ✅ CORRECT - Use model_validate with proper mode
def load_layout_from_dict(data: dict[str, Any]) -> LayoutData:
    """Load layout from dictionary data."""
    return LayoutData.model_validate(data, mode="json")

# ✅ CORRECT - Use model_validate_json for JSON strings
def load_layout_from_json(json_string: str) -> LayoutData:
    """Load layout from JSON string."""
    return LayoutData.model_validate_json(json_string)

# ❌ INCORRECT - Never use deprecated methods
def bad_load_layout(data: dict) -> LayoutData:
    return LayoutData.parse_obj(data)  # Deprecated in Pydantic v2
```

### Special Model Configuration

For formatting classes that need whitespace preservation:

```python
from pydantic import ConfigDict

class FormattingConfig(GloveboxBaseModel):
    """Configuration for ZMK file formatting."""
    
    model_config = ConfigDict(
        extra="allow",
        str_strip_whitespace=False,  # Preserve whitespace for formatting
        use_enum_values=True,
        validate_assignment=True,
    )
    
    indent_size: int = 2
    line_ending: str = "\n"
    preserve_comments: bool = True
```

## Logging Conventions

### MANDATORY Exception Logging Pattern

**ALL** exception handlers that log errors MUST use debug-aware stack traces:

```python
import logging

# ✅ REQUIRED - Exception logging with debug-aware stack traces
class LayoutService:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def generate_layout(self, layout_data: LayoutData) -> LayoutResult:
        try:
            # Operation implementation
            return self._perform_generation(layout_data)
        except Exception as e:
            # MANDATORY pattern for all exception handlers
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Layout generation failed: %s", e, exc_info=exc_info)
            raise LayoutError(f"Generation failed: {e}") from e

# ✅ CORRECT - One-line version for brevity
def another_operation(self):
    try:
        # Operation
        pass
    except Exception as e:
        self.logger.error("Operation failed: %s", e, 
                         exc_info=self.logger.isEnabledFor(logging.DEBUG))
        raise

# ❌ INCORRECT - Missing debug-aware stack trace
def bad_error_handling(self):
    try:
        # Operation
        pass
    except Exception as e:
        self.logger.error("Operation failed: %s", e)  # Missing exc_info
        raise
```

### Lazy Logging Formatting

Use `%` style formatting, not f-strings, for performance:

```python
# ✅ CORRECT - Lazy logging with % formatting
self.logger.info("Processing layout %s for keyboard %s", layout.title, layout.keyboard)
self.logger.debug("Generated %d files in %s", file_count, output_dir)

# ✅ CORRECT - Multiple parameters
self.logger.info(
    "Compilation completed: strategy=%s, duration=%.2fs, files=%d",
    strategy_name, duration, len(output_files)
)

# ❌ INCORRECT - f-string formatting (not lazy)
self.logger.info(f"Processing layout {layout.title} for keyboard {layout.keyboard}")

# ❌ INCORRECT - String concatenation
self.logger.info("Processing layout " + layout.title + " for " + layout.keyboard)
```

## Import Organization

### Clean Import Patterns

Follow domain boundaries and avoid backward compatibility layers:

```python
# ✅ CORRECT - Domain-specific models from their domains
from glovebox.layout.models import LayoutData, LayoutBinding, LayoutLayer
from glovebox.firmware.flash.models import FlashResult, BlockDevice
from glovebox.compilation.models import CompilationConfig, BuildMatrix

# ✅ CORRECT - Core models from models package
from glovebox.models.base import GloveboxBaseModel
from glovebox.models.results import BaseResult
from glovebox.models.docker import DockerUserContext

# ✅ CORRECT - Domain services via factory functions
from glovebox.layout import create_layout_service
from glovebox.firmware.flash import create_flash_service
from glovebox.compilation import create_compilation_service

# ✅ CORRECT - Configuration from config package
from glovebox.config import create_keyboard_profile, create_user_config

# ✅ CORRECT - Adapters with factory functions
from glovebox.adapters import create_docker_adapter, create_file_adapter

# ✅ CORRECT - Shared cache coordination
from glovebox.core.cache import create_default_cache, get_shared_cache_instance

# ❌ INCORRECT - Avoid relative imports in production code
from .models import LayoutData  # Use absolute imports
from ..config import KeyboardProfile  # Use absolute imports
```

### Import Grouping

Organize imports in this order:

```python
# 1. Standard library imports
import json
import logging
from pathlib import Path
from typing import Any, Protocol

# 2. Third-party imports
import typer
from pydantic import ValidationError
from rich.console import Console

# 3. Glovebox imports (grouped by domain)
from glovebox.models.base import GloveboxBaseModel
from glovebox.config import create_keyboard_profile
from glovebox.layout import create_layout_service
from glovebox.layout.models import LayoutData
```

## Error Handling Standards

### Domain-Specific Error Hierarchy

```python
# Define clear error hierarchy
class GloveboxError(Exception):
    """Base exception for all Glovebox errors."""
    pass

class LayoutError(GloveboxError):
    """Base exception for layout-related errors."""
    pass

class LayoutValidationError(LayoutError):
    """Layout validation failed."""
    pass

class LayoutGenerationError(LayoutError):
    """Layout generation failed."""
    pass

# Use specific exceptions
def validate_layout(layout: LayoutData) -> None:
    if not layout.layers:
        raise LayoutValidationError("Layout must have at least one layer")
    
    for layer in layout.layers:
        if len(layer.bindings) != 80:
            raise LayoutValidationError(f"Layer '{layer.name}' must have 80 bindings")
```

### Error Context and Chaining

```python
# ✅ CORRECT - Error chaining with context
def load_layout_file(file_path: Path) -> LayoutData:
    try:
        content = file_path.read_text(encoding="utf-8")
        return LayoutData.model_validate_json(content)
    except FileNotFoundError as e:
        raise LayoutError(f"Layout file not found: {file_path}") from e
    except json.JSONDecodeError as e:
        raise LayoutError(f"Invalid JSON in layout file {file_path}: {e}") from e
    except ValidationError as e:
        raise LayoutValidationError(f"Invalid layout data in {file_path}: {e}") from e

# ✅ CORRECT - Multiple exception handling
def compile_layout(layout: LayoutData, profile: KeyboardProfile) -> CompilationResult:
    try:
        return self._perform_compilation(layout, profile)
    except (LayoutError, CompilationError):
        # Re-raise domain-specific errors
        raise
    except Exception as e:
        # Wrap unexpected errors
        exc_info = self.logger.isEnabledFor(logging.DEBUG)
        self.logger.error("Unexpected compilation error: %s", e, exc_info=exc_info)
        raise CompilationError(f"Compilation failed: {e}") from e
```

## Documentation Standards

### Docstring Conventions

Use comprehensive docstrings for all public functions and classes:

```python
def create_layout_service(
    file_adapter: FileAdapterProtocol | None = None,
    template_adapter: TemplateAdapterProtocol | None = None,
    behavior_registry: BehaviorRegistryProtocol | None = None,
) -> LayoutService:
    """Create a layout service with specified or default dependencies.
    
    Args:
        file_adapter: File adapter for file operations. If None, creates default adapter.
        template_adapter: Template adapter for rendering. If None, creates default adapter.
        behavior_registry: Behavior registry for analysis. If None, creates default registry.
    
    Returns:
        Configured LayoutService instance ready for use.
    
    Raises:
        ConfigurationError: If service configuration is invalid.
        
    Example:
        >>> service = create_layout_service()
        >>> result = service.generate(profile, layout_data, output_path)
    """
    # Implementation
```

### Type Documentation

Document complex types clearly:

```python
from typing import TypeAlias, Dict, List, Union

# Type aliases for complex types
LayerBindings: TypeAlias = list[str]
ConfigParamList: TypeAlias = list[dict[str, Any]]
TemplateContext: TypeAlias = dict[str, Any]

class LayoutData(GloveboxBaseModel):
    """Complete keyboard layout data.
    
    Attributes:
        title: Human-readable layout name
        keyboard: Target keyboard identifier (e.g., 'glove80')
        layers: List of layout layers with bindings
        behaviors: Custom behavior definitions
        config: Additional configuration parameters
    """
    title: str
    keyboard: str
    layers: list[LayoutLayer]
    behaviors: list[BehaviorData] = []
    config: dict[str, Any] = {}
```

## Performance Guidelines

### Efficient Patterns

```python
# ✅ CORRECT - Use generators for large data processing
def process_layout_bindings(layout: LayoutData) -> Iterator[ProcessedBinding]:
    """Process bindings efficiently using generators."""
    for layer in layout.layers:
        for binding in layer.bindings:
            yield self._process_binding(binding)

# ✅ CORRECT - Cache expensive operations
from functools import lru_cache

class BehaviorRegistry:
    @lru_cache(maxsize=128)
    def parse_behavior_definition(self, behavior_code: str) -> BehaviorData:
        """Cache parsed behavior definitions."""
        return self._parse_behavior(behavior_code)

# ✅ CORRECT - Use pathlib efficiently
def find_layout_files(search_dir: Path) -> list[Path]:
    """Find layout files efficiently."""
    return list(search_dir.glob("**/*.json"))

# ❌ INCORRECT - Inefficient list comprehension
def bad_find_files(search_dir: Path) -> list[Path]:
    return [f for f in search_dir.rglob("*") if f.suffix == ".json"]
```

## Code Organization Standards

### File Structure

Organize code files consistently:

```python
# File header pattern
"""Module for layout processing services.

This module provides the main LayoutService class and related utilities
for processing keyboard layouts from JSON to ZMK files.
"""

# Imports (organized as specified above)
import json
from pathlib import Path
from typing import Any

from glovebox.models.base import GloveboxBaseModel
from glovebox.layout.models import LayoutData

# Constants (if any)
DEFAULT_OUTPUT_EXTENSION = ".keymap"
MAX_LAYER_COUNT = 10

# Main implementation
class LayoutService:
    """Main service for layout operations."""
    pass

# Factory functions at the end
def create_layout_service() -> LayoutService:
    """Create layout service with default configuration."""
    return LayoutService()
```

### Method Organization

Organize methods in classes consistently:

```python
class LayoutService(BaseService):
    """Service for layout operations."""
    
    # 1. Constructor
    def __init__(self, file_adapter: FileAdapterProtocol):
        super().__init__()
        self.file_adapter = file_adapter
    
    # 2. Public methods (alphabetically)
    def generate(self, layout: LayoutData) -> LayoutResult:
        """Generate ZMK files from layout."""
        pass
    
    def validate(self, layout: LayoutData) -> bool:
        """Validate layout data."""
        pass
    
    # 3. Private methods (alphabetically)
    def _generate_keymap_content(self, layout: LayoutData) -> str:
        """Generate keymap file content."""
        pass
    
    def _validate_bindings(self, layout: LayoutData) -> None:
        """Validate layer bindings."""
        pass
```

---

**Next Steps**:
- Review [Testing Strategy](../guides/testing-strategy.md) for testing conventions
- Explore [Service Layer Patterns](service-layer.md) for service implementation guidelines
- Check [Factory Functions](factory-functions.md) for dependency management patterns