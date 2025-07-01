# Error Handling Reference

This document provides comprehensive reference for Glovebox's structured error handling system, including exception hierarchy, error codes, debugging guidelines, and best practices.

## Overview

Glovebox implements a comprehensive error handling system with:
- **Structured exception hierarchy** with domain-specific error types
- **Debug-aware logging** with stack traces only in debug mode
- **Contextual error information** with file paths, line numbers, and operation details
- **User-friendly messages** with actionable error guidance
- **Proper error propagation** while maintaining clean production logs

## Exception Hierarchy

### Base Exception Classes

```python
from glovebox.core.errors import GloveboxError

class GloveboxError(Exception):
    """Base exception for all Glovebox errors."""
    
    def __init__(
        self,
        message: str,
        *,
        cause: Exception | None = None,
        context: dict[str, Any] | None = None,
        error_code: str | None = None,
    ):
        """Initialize Glovebox error.
        
        Args:
            message: Human-readable error message
            cause: Underlying exception that caused this error
            context: Additional context information
            error_code: Structured error code for programmatic handling
        """
        super().__init__(message)
        self.message = message
        self.cause = cause
        self.context = context or {}
        self.error_code = error_code
    
    def __str__(self) -> str:
        """Return user-friendly error message."""
        return self.message
    
    def get_context(self) -> dict[str, Any]:
        """Get error context information."""
        context = self.context.copy()
        if self.cause:
            context["cause"] = str(self.cause)
        if self.error_code:
            context["error_code"] = self.error_code
        return context
```

### Domain-Specific Exception Classes

#### Layout Domain Errors

```python
class LayoutError(GloveboxError):
    """Base exception for layout-related errors."""
    pass

class KeymapError(LayoutError):
    """Errors related to keymap processing."""
    pass

class ValidationError(LayoutError):
    """Layout validation errors."""
    
    def __init__(
        self,
        message: str,
        *,
        field_path: str | None = None,
        validation_errors: list[dict[str, Any]] | None = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.field_path = field_path
        self.validation_errors = validation_errors or []
```

#### Compilation Domain Errors

```python
class CompilationError(GloveboxError):
    """Base exception for compilation-related errors."""
    pass

class BuildError(CompilationError):
    """Errors during firmware build process."""
    
    def __init__(
        self,
        message: str,
        *,
        build_log: str | None = None,
        exit_code: int | None = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.build_log = build_log
        self.exit_code = exit_code
```

#### Firmware Domain Errors

```python
class FlashError(GloveboxError):
    """Base exception for firmware flashing errors."""
    pass

class USBError(FlashError):
    """USB device communication errors."""
    
    def __init__(
        self,
        message: str,
        *,
        device_info: dict[str, Any] | None = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.device_info = device_info or {}
```

#### Configuration Domain Errors

```python
class ConfigError(GloveboxError):
    """Base exception for configuration-related errors."""
    pass

class ConfigurationError(ConfigError):
    """Configuration parsing and validation errors."""
    pass

class ProfileNotFoundError(ConfigError):
    """Keyboard or firmware profile not found."""
    
    def __init__(
        self,
        message: str,
        *,
        profile_name: str | None = None,
        available_profiles: list[str] | None = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.profile_name = profile_name
        self.available_profiles = available_profiles or []

class InvalidProfileError(ConfigError):
    """Invalid profile configuration."""
    pass
```

#### Adapter Domain Errors

```python
class AdapterError(GloveboxError):
    """Base exception for adapter-related errors."""
    pass

class DockerError(AdapterError):
    """Docker adapter errors."""
    
    def __init__(
        self,
        message: str,
        *,
        command: list[str] | None = None,
        exit_code: int | None = None,
        stdout: str | None = None,
        stderr: str | None = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.command = command
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr

class FileSystemError(AdapterError):
    """File system operation errors."""
    
    def __init__(
        self,
        message: str,
        *,
        file_path: Path | None = None,
        operation: str | None = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.file_path = file_path
        self.operation = operation

class TemplateError(AdapterError):
    """Template processing errors."""
    
    def __init__(
        self,
        message: str,
        *,
        template_content: str | None = None,
        line_number: int | None = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.template_content = template_content
        self.line_number = line_number
```

## Error Codes

### Structured Error Code System

Error codes follow the pattern: `DOMAIN_CATEGORY_SPECIFIC_CODE`

```python
class ErrorCodes:
    """Structured error codes for programmatic handling."""
    
    # Layout Domain (LAY)
    LAY_PARSE_INVALID_JSON = "LAY_PARSE_001"
    LAY_PARSE_MISSING_FIELD = "LAY_PARSE_002"
    LAY_PARSE_INVALID_BINDING = "LAY_PARSE_003"
    LAY_VALIDATE_LAYER_MISMATCH = "LAY_VALIDATE_001"
    LAY_VALIDATE_BEHAVIOR_UNDEFINED = "LAY_VALIDATE_002"
    LAY_TEMPLATE_SYNTAX_ERROR = "LAY_TEMPLATE_001"
    LAY_TEMPLATE_VARIABLE_UNDEFINED = "LAY_TEMPLATE_002"
    
    # Compilation Domain (COMP)
    COMP_BUILD_DOCKER_FAILED = "COMP_BUILD_001"
    COMP_BUILD_WORKSPACE_MISSING = "COMP_BUILD_002"
    COMP_BUILD_CONFIG_INVALID = "COMP_BUILD_003"
    COMP_CACHE_CORRUPTION = "COMP_CACHE_001"
    COMP_CACHE_SIZE_EXCEEDED = "COMP_CACHE_002"
    
    # Firmware Domain (FW)
    FW_FLASH_DEVICE_NOT_FOUND = "FW_FLASH_001"
    FW_FLASH_PERMISSION_DENIED = "FW_FLASH_002"
    FW_FLASH_VERIFICATION_FAILED = "FW_FLASH_003"
    FW_USB_DEVICE_DISCONNECTED = "FW_USB_001"
    FW_USB_MOUNT_FAILED = "FW_USB_002"
    
    # Configuration Domain (CFG)
    CFG_PROFILE_NOT_FOUND = "CFG_PROFILE_001"
    CFG_PROFILE_INVALID = "CFG_PROFILE_002"
    CFG_KEYBOARD_NOT_FOUND = "CFG_KEYBOARD_001"
    CFG_FIRMWARE_NOT_FOUND = "CFG_FIRMWARE_001"
    CFG_USER_CONFIG_INVALID = "CFG_USER_001"
    
    # Adapter Domain (ADP)
    ADP_DOCKER_NOT_AVAILABLE = "ADP_DOCKER_001"
    ADP_DOCKER_IMAGE_MISSING = "ADP_DOCKER_002"
    ADP_FILE_NOT_FOUND = "ADP_FILE_001"
    ADP_FILE_PERMISSION_DENIED = "ADP_FILE_002"
    ADP_TEMPLATE_SYNTAX_ERROR = "ADP_TEMPLATE_001"
```

### Error Code Usage

```python
def create_structured_error():
    """Example of creating errors with structured codes."""
    raise ProfileNotFoundError(
        "Keyboard profile 'invalid_keyboard' not found",
        error_code=ErrorCodes.CFG_PROFILE_NOT_FOUND,
        context={
            "profile_name": "invalid_keyboard",
            "available_profiles": ["glove80", "moonlander"],
            "search_paths": ["/usr/share/glovebox/keyboards"]
        }
    )

# Programmatic error handling
try:
    operation()
except GloveboxError as e:
    if e.error_code == ErrorCodes.CFG_PROFILE_NOT_FOUND:
        # Handle profile not found specifically
        suggest_alternatives(e.context.get("available_profiles", []))
    else:
        # Generic error handling
        log_error(e)
```

## Debug-Aware Logging Pattern

### Mandatory Exception Logging Pattern

**CRITICAL: This pattern is MANDATORY for ALL exception handlers that log errors/warnings.**

```python
import logging

class MyService:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def risky_operation(self) -> str:
        """Example operation with proper error handling."""
        try:
            # Perform operation that might fail
            result = self._perform_operation()
            return result
            
        except Exception as e:
            # MANDATORY PATTERN: Debug-aware exception logging
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Operation failed: %s", e, exc_info=exc_info)
            
            # Re-raise or handle as appropriate
            raise GloveboxError(
                "Failed to perform operation",
                cause=e,
                error_code=ErrorCodes.OPERATION_FAILED
            ) from e
```

**Why this pattern is mandatory:**
- **Clean production logs**: Stack traces only appear when debug logging is enabled
- **Developer debugging**: Full stack traces available when needed (debug mode)
- **Consistent behavior**: All exception handlers follow the same pattern
- **One-liner option**: Can be shortened to `exc_info=self.logger.isEnabledFor(logging.DEBUG)`

### Logging Levels and Usage

```python
# ERROR: For errors that prevent operation completion
self.logger.error("Compilation failed: %s", error_message, exc_info=exc_info)

# WARNING: For issues that don't prevent completion but may cause problems
self.logger.warning("Cache cleanup failed: %s", e, exc_info=exc_info)

# INFO: For important operational information
self.logger.info("Layout compiled successfully: %s", output_file)

# DEBUG: For detailed debugging information
self.logger.debug("Processing binding: %s", binding)
```

## Error Creation Utilities

### Structured Error Creation

```python
from glovebox.utils.error_utils import (
    create_error,
    create_file_error,
    create_usb_error,
    create_template_error,
    create_docker_error
)

def create_error(
    error_type: type[E],
    message: str,
    *,
    cause: Exception | None = None,
    context: dict[str, Any] | None = None,
    error_code: str | None = None,
) -> E:
    """Create structured error with context information.
    
    Args:
        error_type: Error class to create
        message: Human-readable error message
        cause: Underlying cause exception
        context: Additional context information
        error_code: Structured error code
        
    Returns:
        Configured error instance
    """
    return error_type(
        message,
        cause=cause,
        context=context,
        error_code=error_code
    )

def create_file_error(
    message: str,
    file_path: Path,
    operation: str,
    *,
    cause: Exception | None = None,
) -> FileSystemError:
    """Create file system error with context."""
    return create_error(
        FileSystemError,
        message,
        cause=cause,
        context={
            "file_path": str(file_path),
            "operation": operation,
            "exists": file_path.exists() if file_path else False,
            "is_dir": file_path.is_dir() if file_path and file_path.exists() else False,
        },
        error_code=ErrorCodes.ADP_FILE_NOT_FOUND if not file_path.exists() else ErrorCodes.ADP_FILE_PERMISSION_DENIED
    )

def create_usb_error(
    message: str,
    device_info: dict[str, Any] | None = None,
    *,
    cause: Exception | None = None,
) -> USBError:
    """Create USB error with device context."""
    return create_error(
        USBError,
        message,
        cause=cause,
        context={"device_info": device_info or {}},
        error_code=ErrorCodes.FW_USB_DEVICE_DISCONNECTED
    )
```

## Error Handling Patterns

### Service Layer Error Handling

```python
class LayoutService:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def compile(self, input_file: Path, output_path: Path, profile: KeyboardProfile) -> LayoutResult:
        """Compile layout with comprehensive error handling."""
        try:
            # Validate inputs
            if not input_file.exists():
                raise create_file_error(
                    f"Layout file not found: {input_file}",
                    file_path=input_file,
                    operation="read"
                )
            
            # Parse layout
            try:
                layout_data = self._parse_layout(input_file)
            except json.JSONDecodeError as e:
                exc_info = self.logger.isEnabledFor(logging.DEBUG)
                self.logger.error("Invalid JSON in layout file: %s", e, exc_info=exc_info)
                raise LayoutError(
                    f"Invalid JSON in layout file: {input_file}",
                    cause=e,
                    context={"file_path": str(input_file), "line": e.lineno, "column": e.colno},
                    error_code=ErrorCodes.LAY_PARSE_INVALID_JSON
                ) from e
            
            # Validate layout
            try:
                self._validate_layout(layout_data, profile)
            except ValidationError as e:
                # Re-raise validation errors with additional context
                e.context.update({
                    "input_file": str(input_file),
                    "profile": str(profile)
                })
                raise
            
            # Generate output
            result = self._generate_output(layout_data, output_path, profile)
            
            self.logger.info("Layout compiled successfully: %s", output_path)
            return result
            
        except GloveboxError:
            # Re-raise Glovebox errors without modification
            raise
        except Exception as e:
            # Wrap unexpected errors
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Unexpected error during compilation: %s", e, exc_info=exc_info)
            raise LayoutError(
                "Unexpected error during layout compilation",
                cause=e,
                context={
                    "input_file": str(input_file),
                    "output_path": str(output_path),
                    "profile": str(profile)
                }
            ) from e
```

### Adapter Error Handling

```python
class DockerAdapter:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def run(
        self,
        image: str,
        command: list[str],
        **kwargs
    ) -> DockerResult:
        """Run Docker command with proper error handling."""
        try:
            # Check Docker availability
            if not self._is_docker_available():
                raise DockerError(
                    "Docker is not available or not running",
                    error_code=ErrorCodes.ADP_DOCKER_NOT_AVAILABLE,
                    context={"image": image, "command": command}
                )
            
            # Check image availability
            if not self._image_exists(image):
                self.logger.info("Pulling Docker image: %s", image)
                try:
                    self._pull_image(image)
                except Exception as e:
                    exc_info = self.logger.isEnabledFor(logging.DEBUG)
                    self.logger.error("Failed to pull Docker image: %s", e, exc_info=exc_info)
                    raise DockerError(
                        f"Failed to pull Docker image: {image}",
                        cause=e,
                        error_code=ErrorCodes.ADP_DOCKER_IMAGE_MISSING,
                        context={"image": image}
                    ) from e
            
            # Execute command
            result = self._execute_command(image, command, **kwargs)
            
            if result.exit_code != 0:
                raise DockerError(
                    f"Docker command failed with exit code {result.exit_code}",
                    command=command,
                    exit_code=result.exit_code,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    error_code=ErrorCodes.COMP_BUILD_DOCKER_FAILED,
                    context={"image": image}
                )
            
            return result
            
        except DockerError:
            # Re-raise Docker errors
            raise
        except Exception as e:
            # Wrap unexpected errors
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Unexpected Docker error: %s", e, exc_info=exc_info)
            raise DockerError(
                "Unexpected Docker operation error",
                cause=e,
                command=command,
                context={"image": image}
            ) from e
```

### CLI Error Handling

```python
from glovebox.cli.decorators.error_handling import handle_errors

@handle_errors
def compile_command(
    input_file: Path,
    output_path: Path,
    profile: str | None = None,
) -> None:
    """CLI command with error handling decorator."""
    try:
        # Create services
        layout_service = create_layout_service()
        keyboard_profile = create_keyboard_profile_from_name(profile) if profile else None
        
        # Execute compilation
        result = layout_service.compile(input_file, output_path, keyboard_profile)
        
        if result.success:
            console.print_success(f"Layout compiled successfully: {result.output_files}")
        else:
            console.print_error(f"Compilation failed: {result.message}")
            raise typer.Exit(1)
            
    except ProfileNotFoundError as e:
        console.print_error(f"Profile not found: {e.message}")
        if e.available_profiles:
            console.print_info("Available profiles:")
            for available_profile in e.available_profiles:
                console.print_list_item(available_profile)
        raise typer.Exit(1)
        
    except ValidationError as e:
        console.print_error(f"Layout validation failed: {e.message}")
        if e.validation_errors:
            for error in e.validation_errors:
                console.print_error(f"  {error['loc']}: {error['msg']}")
        raise typer.Exit(1)
        
    except GloveboxError as e:
        console.print_error(f"Operation failed: {e.message}")
        if e.error_code:
            console.print_info(f"Error code: {e.error_code}")
        raise typer.Exit(1)

def handle_errors(func: Callable) -> Callable:
    """Decorator for CLI error handling."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyboardInterrupt:
            console.print_warning("Operation cancelled by user")
            raise typer.Exit(130)
        except GloveboxError as e:
            # Glovebox errors are handled by the command itself
            raise
        except Exception as e:
            # Unexpected errors
            console.print_error(f"Unexpected error: {e}")
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                console.print_exception()
            raise typer.Exit(1)
    
    return wrapper
```

## Error Recovery Strategies

### Graceful Degradation

```python
class CompilationService:
    def compile_with_fallback(self, config: CompilationConfig) -> BuildResult:
        """Compile with fallback strategies."""
        strategies = ["primary", "fallback", "local"]
        
        for strategy in strategies:
            try:
                self.logger.info("Attempting compilation with %s strategy", strategy)
                return self._compile_with_strategy(config, strategy)
                
            except CompilationError as e:
                self.logger.warning(
                    "Compilation failed with %s strategy: %s", 
                    strategy, e,
                    exc_info=self.logger.isEnabledFor(logging.DEBUG)
                )
                if strategy == strategies[-1]:
                    # Last strategy failed, re-raise
                    raise
                continue
        
        # Should never reach here
        raise CompilationError("All compilation strategies failed")
```

### Retry with Backoff

```python
import time
import random

class USBFlasher:
    def flash_with_retry(
        self,
        firmware_file: Path,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> FlashResult:
        """Flash firmware with exponential backoff retry."""
        for attempt in range(max_retries):
            try:
                return self._flash_firmware(firmware_file)
                
            except USBError as e:
                if attempt == max_retries - 1:
                    # Last attempt failed
                    raise
                
                # Calculate backoff delay
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                
                self.logger.warning(
                    "Flash attempt %d failed, retrying in %.1fs: %s",
                    attempt + 1, delay, e,
                    exc_info=self.logger.isEnabledFor(logging.DEBUG)
                )
                
                time.sleep(delay)
```

### Cache Recovery

```python
class CacheService:
    def get_with_recovery(self, key: str, generator: Callable[[], Any]) -> Any:
        """Get cached value with automatic recovery."""
        try:
            value = self.cache.get(key)
            if value is not None:
                return value
                
        except Exception as e:
            self.logger.warning(
                "Cache retrieval failed for key %s: %s",
                key, e,
                exc_info=self.logger.isEnabledFor(logging.DEBUG)
            )
        
        # Generate fresh value
        try:
            value = generator()
            
            # Try to cache the result
            try:
                self.cache.set(key, value)
            except Exception as e:
                self.logger.warning(
                    "Failed to cache value for key %s: %s",
                    key, e,
                    exc_info=self.logger.isEnabledFor(logging.DEBUG)
                )
            
            return value
            
        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Failed to generate value for key %s: %s", key, e, exc_info=exc_info)
            raise
```

## Error Context and Debugging

### Rich Error Context

```python
def create_compilation_error_context(
    config: CompilationConfig,
    workspace_dir: Path,
    build_log: str | None = None,
) -> dict[str, Any]:
    """Create rich context for compilation errors."""
    context = {
        "strategy": config.type,
        "repository": config.repository,
        "branch": config.branch,
        "workspace_dir": str(workspace_dir),
        "workspace_exists": workspace_dir.exists() if workspace_dir else False,
    }
    
    if workspace_dir and workspace_dir.exists():
        context.update({
            "workspace_size": sum(f.stat().st_size for f in workspace_dir.rglob("*") if f.is_file()),
            "file_count": len(list(workspace_dir.rglob("*"))),
        })
    
    if build_log:
        # Extract key information from build log
        context["build_log_lines"] = len(build_log.splitlines())
        context["build_log_size"] = len(build_log)
        
        # Look for common error patterns
        error_patterns = [
            r"error:",
            r"fatal:",
            r"No such file",
            r"Permission denied",
            r"command not found"
        ]
        
        for pattern in error_patterns:
            if re.search(pattern, build_log, re.IGNORECASE):
                context["build_error_pattern"] = pattern
                break
    
    return context
```

### Error Serialization

```python
def serialize_error(error: GloveboxError) -> dict[str, Any]:
    """Serialize error for logging or API responses."""
    return {
        "type": error.__class__.__name__,
        "message": error.message,
        "error_code": error.error_code,
        "context": error.get_context(),
        "cause": {
            "type": error.cause.__class__.__name__,
            "message": str(error.cause)
        } if error.cause else None,
        "timestamp": datetime.now().isoformat(),
    }

def log_structured_error(logger: logging.Logger, error: GloveboxError) -> None:
    """Log error with structured information."""
    error_data = serialize_error(error)
    
    exc_info = logger.isEnabledFor(logging.DEBUG)
    logger.error(
        "Structured error: %s",
        json.dumps(error_data, indent=2 if exc_info else None),
        exc_info=exc_info
    )
```

## Best Practices Summary

### Error Handling Principles

1. **Use debug-aware logging** for all exception handlers
2. **Provide contextual information** in error messages and context
3. **Use structured error codes** for programmatic handling
4. **Maintain error hierarchy** with domain-specific exception types
5. **Log errors at appropriate levels** (ERROR for failures, WARNING for issues)
6. **Include actionable guidance** in error messages when possible
7. **Preserve original exception chains** using `raise ... from e`

### Do's and Don'ts

**DO:**
```python
# Proper exception handling with context
try:
    result = operation()
except SpecificError as e:
    exc_info = self.logger.isEnabledFor(logging.DEBUG)
    self.logger.error("Operation failed: %s", e, exc_info=exc_info)
    raise DomainError("Meaningful message", cause=e, context={"key": "value"}) from e
```

**DON'T:**
```python
# Bad: Generic exception handling
try:
    result = operation()
except Exception:
    pass  # Silently ignoring errors

# Bad: Losing stack trace information
try:
    result = operation()
except Exception as e:
    raise DomainError("Operation failed")  # Lost original context
```

This comprehensive error handling system ensures robust error management while providing excellent debugging capabilities for developers and clear error messages for users.