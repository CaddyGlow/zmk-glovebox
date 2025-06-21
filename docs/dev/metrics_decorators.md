# Metrics Decorators Usage Guide

## Overview

The metrics decorator system provides automatic metrics collection for functions with minimal code changes. It follows CLAUDE.md patterns with dependency injection support and comprehensive context extraction.

## Basic Usage

### CLI Commands

```python
from glovebox.metrics.context_extractors import extract_cli_context
from glovebox.metrics.decorators import track_layout_operation

@handle_errors
@with_profile()
@track_layout_operation(extract_context=extract_cli_context)
def compile_layout(ctx, json_file, output_dir, profile=None, force=False):
    # Your CLI command implementation
    pass
```

### Service Methods

```python
from glovebox.metrics.context_extractors import extract_service_context
from glovebox.metrics.decorators import track_layout_operation

class LayoutService:
    @track_layout_operation(extract_context=extract_service_context)
    def generate_from_file(self, profile, json_file_path, output_file_prefix, force=False):
        # Your service method implementation
        pass
```

## Available Decorators

### Generic Decorator

```python
from glovebox.metrics.decorators import track_operation
from glovebox.metrics.models import OperationType

@track_operation(OperationType.LAYOUT_COMPILATION)
def my_function():
    pass
```

### Convenience Decorators

```python
from glovebox.metrics.decorators import (
    track_layout_operation,
    track_firmware_operation,
    track_flash_operation
)

@track_layout_operation()
def layout_function():
    pass

@track_firmware_operation()
def firmware_function():
    pass

@track_flash_operation()
def flash_function():
    pass
```

## Context Extractors

### CLI Context Extractor

Automatically extracts:
- Profile names
- Input/output file paths
- Boolean flags (force, verbose, etc.)
- Format options

```python
from glovebox.metrics.context_extractors import extract_cli_context

@track_operation(OperationType.LAYOUT_COMPILATION, extract_context=extract_cli_context)
def cli_command(ctx, json_file, output_dir, profile=None):
    pass
```

### Service Context Extractor

Automatically extracts:
- Keyboard profile information
- File paths from method parameters
- Service-specific flags

```python
from glovebox.metrics.context_extractors import extract_service_context

@track_layout_operation(extract_context=extract_service_context)
def service_method(self, profile, json_file_path, output_file_prefix):
    pass
```

### Compilation Context Extractor

Automatically extracts:
- Compilation strategy
- Board targets
- Docker image information
- Repository and branch details

```python
from glovebox.metrics.context_extractors import extract_compilation_context

@track_firmware_operation(extract_context=extract_compilation_context)
def compile_method(self, keymap_file, config_file, output_dir, config):
    pass
```

## Dependency Injection

### With Custom Metrics Service

```python
from glovebox.metrics import create_metrics_service
from glovebox.metrics.decorators import track_operation

# Create custom metrics service
custom_service = create_metrics_service()

@track_operation(
    OperationType.LAYOUT_COMPILATION,
    metrics_service=custom_service
)
def my_function():
    pass
```

### Factory Pattern

```python
from glovebox.metrics import create_operation_tracker

# Create reusable tracker
layout_tracker = create_operation_tracker(
    OperationType.LAYOUT_COMPILATION,
    extract_context=extract_cli_context
)

@layout_tracker
def function1():
    pass

@layout_tracker
def function2():
    pass
```

## Custom Context Extractors

```python
def custom_extractor(func, args, kwargs):
    """Custom context extraction logic."""
    context = {}
    
    # Extract custom information
    if 'custom_param' in kwargs:
        context['custom_value'] = kwargs['custom_param']
    
    return context

@track_operation(
    OperationType.LAYOUT_COMPILATION,
    extract_context=custom_extractor
)
def my_function(custom_param=None):
    pass
```

## Collected Metrics

The decorators automatically collect:

### Timing Information
- Operation start/end time
- Total duration
- Sub-operation timing (when used with manual metrics)

### Context Information
- Profile names and versions
- Input/output file paths
- Operation-specific parameters
- Configuration details

### Success/Failure Tracking
- Operation status
- Error messages and categorization
- Exception details with debug-aware stack traces

### Cache Information
- Cache hit/miss status
- Cache keys used
- Multi-level cache details

## Best Practices

### 1. Use Appropriate Extractors
Choose the context extractor that matches your function type:
- `extract_cli_context` for CLI commands
- `extract_service_context` for service methods
- `extract_compilation_context` for compilation operations

### 2. Maintain Existing Manual Metrics
The decorators work alongside existing manual metrics collection:

```python
@track_firmware_operation(extract_context=extract_compilation_context)
def compile_with_detailed_metrics(self, ...):
    # Decorator handles overall operation tracking
    
    # Manual metrics for detailed sub-operations
    with firmware_metrics() as metrics:
        with metrics.time_operation("workspace_setup"):
            # Detailed timing
            pass
```

### 3. Handle Circular Imports
Avoid circular imports by using conditional imports when needed:

```python
# In service files, import decorators conditionally if needed
def my_service_method(self, ...):
    # Import here if circular dependency exists
    from glovebox.metrics.decorators import track_layout_operation
    # Or apply decorator at runtime
```

### 4. Testing with Dependency Injection
Use dependency injection for testing:

```python
def test_decorated_function():
    mock_service = Mock(spec=MetricsServiceProtocol)
    
    @track_operation(
        OperationType.LAYOUT_COMPILATION,
        metrics_service=mock_service
    )
    def test_function():
        return "success"
    
    result = test_function()
    assert result == "success"
    # Verify metrics service was called
```

## Error Handling

The decorators handle errors gracefully:
- Context extraction failures don't break function execution
- Missing metrics service falls back to default
- All exceptions are logged with debug-aware stack traces
- Original function behavior is preserved

## Performance Considerations

- Minimal overhead: ~1-2ms per operation
- Conditional metrics service creation
- Efficient context extraction
- No impact on function signatures or return values