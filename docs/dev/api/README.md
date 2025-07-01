# API Reference

This section provides comprehensive API documentation for all Glovebox domains, services, models, and interfaces. The API reference is organized by domain to match the codebase architecture.

## Overview

Glovebox provides both **programmatic APIs** for integration and **CLI APIs** for command-line usage. This reference covers:

- **🏗️ Domain Services**: Primary business logic interfaces
- **📊 Data Models**: Pydantic models for data structures
- **🔌 Protocols**: Interface definitions for type safety
- **🏭 Factory Functions**: Service creation and dependency injection
- **💻 CLI Commands**: Command-line interface reference
- **🔧 Adapters**: Infrastructure and external system interfaces

## Quick Navigation

### Domain APIs

- **[Layout Domain](layout-domain.md)** - Keyboard layout processing and management
- **[Firmware Domain](firmware-domain.md)** - Firmware building and device flashing
- **[Compilation Domain](compilation-domain.md)** - Build strategies and workspace management
- **[Configuration Domain](config-domain.md)** - Keyboard profiles and user settings

### Core APIs

- **[Core Services](core-services.md)** - Logging, caching, and startup services
- **[Adapters](adapters.md)** - External system interfaces
- **[Models](models.md)** - Shared data models and base classes
- **[Protocols](protocols.md)** - Interface definitions and contracts

### CLI Reference

- **[CLI Commands](cli-commands.md)** - Complete command reference with examples
- **[CLI Helpers](cli-helpers.md)** - Parameter handling and utilities
- **[CLI Decorators](cli-decorators.md)** - Command decoration patterns

## API Design Principles

### Consistent Patterns

All Glovebox APIs follow consistent design patterns:

```python
# 1. Factory Function Pattern
from glovebox.layout import create_layout_service

service = create_layout_service()  # All dependencies resolved automatically

# 2. Protocol-Based Interfaces
from glovebox.protocols import FileAdapterProtocol

def my_function(file_adapter: FileAdapterProtocol) -> None:
    # Type-safe interface usage
    content = file_adapter.read_file(Path("file.txt"))

# 3. Pydantic Models with Proper Serialization
from glovebox.layout.models import LayoutData

layout = LayoutData.model_validate(data)
json_data = layout.model_dump(by_alias=True, exclude_unset=True, mode="json")

# 4. Result Objects for Operations
from glovebox.layout.models import LayoutResult

result = service.generate_layout(layout_data)
if result.success:
    print(f"Generated files: {result.files}")
else:
    print(f"Error: {result.error}")
```

### Error Handling

All APIs use consistent error handling with domain-specific exceptions:

```python
from glovebox.core.errors import LayoutError, CompilationError, FlashError

try:
    result = service.perform_operation()
except LayoutError as e:
    # Handle layout-specific errors
    logger.error("Layout operation failed: %s", e)
except Exception as e:
    # Handle unexpected errors with debug-aware stack traces
    exc_info = logger.isEnabledFor(logging.DEBUG)
    logger.error("Unexpected error: %s", e, exc_info=exc_info)
    raise
```

### Asynchronous Operations

For long-running operations, APIs provide progress callbacks:

```python
from typing import Callable

def progress_callback(current: int, total: int, message: str) -> None:
    print(f"Progress: {current}/{total} - {message}")

result = service.compile_firmware(
    keymap_content=keymap,
    config_content=config,
    progress_callback=progress_callback
)
```

## Usage Examples

### Basic Service Usage

```python
# Create services with dependencies
from glovebox.layout import create_layout_service
from glovebox.config import create_keyboard_profile

# Create keyboard profile
profile = create_keyboard_profile("glove80", "v25.05")

# Create layout service
layout_service = create_layout_service()

# Load layout data
from glovebox.layout.utils import load_layout_file
layout_data = load_layout_file(Path("my_layout.json"))

# Generate ZMK files
result = layout_service.generate(profile, layout_data, Path("output/"))

if result.success:
    print(f"Generated keymap: {result.files['keymap']}")
    print(f"Generated config: {result.files['config']}")
else:
    print(f"Generation failed: {result.error}")
```

### Advanced Integration

```python
# Custom service configuration
from glovebox.adapters import create_file_adapter, create_template_adapter
from glovebox.layout import create_layout_service

# Create custom file adapter with specific settings
file_adapter = create_file_adapter()

# Create template adapter with custom paths
template_adapter = create_template_adapter(
    template_paths=[Path("custom/templates")]
)

# Create layout service with custom dependencies
layout_service = create_layout_service(
    file_adapter=file_adapter,
    template_adapter=template_adapter
)

# Use service with custom configuration
result = layout_service.generate(profile, layout_data, output_path)
```

### Error Handling and Logging

```python
import logging
from glovebox.core.logging import setup_logging

# Configure logging
setup_logging(level="DEBUG", format="json")
logger = logging.getLogger(__name__)

try:
    # Service operation
    result = service.perform_complex_operation()
    
    if result.success:
        logger.info("Operation completed successfully")
    else:
        logger.warning("Operation completed with warnings: %s", result.warnings)
        
except Exception as e:
    # Debug-aware exception logging
    exc_info = logger.isEnabledFor(logging.DEBUG)
    logger.error("Operation failed: %s", e, exc_info=exc_info)
    raise
```

### Cache Integration

```python
from glovebox.core.cache import create_default_cache

# Create domain-specific cache
cache = create_default_cache(tag="my_domain")

# Use cache in service operations
def cached_operation(key: str, data: Any) -> Any:
    # Check cache first
    cached_result = cache.get(key)
    if cached_result is not None:
        logger.info("Cache hit for key: %s", key)
        return cached_result
    
    # Perform operation
    result = expensive_operation(data)
    
    # Cache result with TTL
    cache.set(key, result, expire=3600)  # 1 hour
    
    return result
```

## Testing with APIs

### Unit Testing Services

```python
import pytest
from unittest.mock import Mock

from glovebox.layout import create_layout_service
from glovebox.protocols import FileAdapterProtocol

class TestLayoutService:
    @pytest.fixture
    def mock_file_adapter(self):
        return Mock(spec=FileAdapterProtocol)
    
    @pytest.fixture
    def service(self, mock_file_adapter):
        return create_layout_service(file_adapter=mock_file_adapter)
    
    def test_generate_layout_success(self, service, mock_file_adapter):
        # Setup mocks
        mock_file_adapter.read_file.return_value = "template content"
        
        # Test service
        result = service.generate(profile, layout_data, output_path)
        
        # Verify behavior
        assert result.success is True
        mock_file_adapter.write_file.assert_called()
```

### Integration Testing

```python
class TestLayoutIntegration:
    def test_real_layout_generation(self, tmp_path):
        # Use real services for integration testing
        profile = create_keyboard_profile("glove80", "v25.05")
        service = create_layout_service()
        
        # Load real test data
        layout_data = load_layout_file(Path("tests/fixtures/test_layout.json"))
        
        # Perform real operation
        result = service.generate(profile, layout_data, tmp_path)
        
        # Verify real results
        assert result.success is True
        assert (tmp_path / "keymap.keymap").exists()
        assert (tmp_path / "config.conf").exists()
```

## API Versioning and Compatibility

### Semantic Versioning

Glovebox APIs follow semantic versioning:

- **Major version** changes indicate breaking API changes
- **Minor version** changes add new features while maintaining compatibility
- **Patch version** changes fix bugs without changing interfaces

### Compatibility Guidelines

```python
# Deprecated APIs are marked with warnings
@deprecated("Use create_new_service() instead", version="0.3.0")
def create_old_service() -> OldService:
    warnings.warn(
        "create_old_service() is deprecated, use create_new_service()",
        DeprecationWarning,
        stacklevel=2
    )
    return OldService()

# New APIs maintain backward compatibility
def create_new_service(
    # New parameters with defaults for compatibility
    new_feature: bool = False,
    # Existing parameters unchanged
    file_adapter: FileAdapterProtocol | None = None,
) -> NewService:
    return NewService(new_feature=new_feature, file_adapter=file_adapter)
```

## Performance Considerations

### Efficient API Usage

```python
# Reuse services instead of recreating
service = create_layout_service()  # Create once

for layout_file in layout_files:
    # Reuse same service instance
    result = service.generate(profile, layout_data, output_path)

# Use caching for expensive operations
cache = create_default_cache(tag="layout_generation")

def cached_generation(layout_hash: str, layout_data: LayoutData) -> LayoutResult:
    cached_result = cache.get(layout_hash)
    if cached_result:
        return cached_result
    
    result = service.generate(profile, layout_data, output_path)
    cache.set(layout_hash, result, expire=3600)
    return result
```

### Memory Management

```python
# Close resources properly
cache_manager = create_default_cache()
try:
    # Use cache
    cache_manager.set("key", "value")
finally:
    cache_manager.close()

# Use context managers when available
from glovebox.core.metrics import create_session_metrics

with create_session_metrics() as metrics:
    # Use metrics
    metrics.counter("operation_count").inc()
    # Automatically cleaned up
```

## Contributing to the API

### Adding New APIs

When adding new APIs, follow these guidelines:

1. **🏗️ Follow Domain Architecture** - Place APIs in appropriate domains
2. **📋 Use Protocols** - Define interfaces with protocols for type safety
3. **🏭 Create Factory Functions** - Provide consistent creation patterns
4. **📊 Use Pydantic Models** - Inherit from GloveboxBaseModel
5. **🧪 Write Comprehensive Tests** - Include unit and integration tests
6. **📚 Document Thoroughly** - Provide docstrings and examples

### API Design Checklist

- [ ] **Protocol interface defined** for type safety
- [ ] **Factory function created** following create_* pattern
- [ ] **Pydantic models inherit from GloveboxBaseModel**
- [ ] **Error handling uses domain-specific exceptions**
- [ ] **Logging uses debug-aware patterns**
- [ ] **Comprehensive tests written** with >90% coverage
- [ ] **Docstrings include examples** and parameter descriptions
- [ ] **API exported from domain __init__.py**

---

**Next Steps**:
- Explore specific [Domain APIs](layout-domain.md) for detailed interface documentation
- Review [CLI Commands](cli-commands.md) for command-line usage
- Check [Examples](../examples/) for practical usage patterns