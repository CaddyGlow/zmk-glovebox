# Protocol Definitions

This document provides comprehensive documentation for all protocol interfaces and behavioral contracts used throughout Glovebox. All protocols are runtime-checkable and define clear behavioral expectations for implementations.

## Overview

Glovebox uses Python's `typing.Protocol` to define interfaces that provide:
- **Type safety** with runtime checking
- **Clear behavioral contracts** for implementations
- **Testable interfaces** with protocol compliance verification
- **Adapter patterns** for external system integration

All protocols are decorated with `@runtime_checkable` to enable `isinstance()` checks at runtime.

## Base Service Protocols

### BaseServiceProtocol

Foundation protocol for all domain services.

```python
from typing import Protocol, runtime_checkable
from glovebox.protocols import BaseServiceProtocol

@runtime_checkable
class BaseServiceProtocol(Protocol):
    """Base protocol for all services."""
    
    def validate_config(self, config: Any) -> bool:
        """Validate service configuration.
        
        Args:
            config: Configuration object to validate
            
        Returns:
            bool: True if configuration is valid
            
        Raises:
            ConfigError: If configuration is invalid
        """
        ...
    
    def check_available(self) -> bool:
        """Check if service is available.
        
        Returns:
            bool: True if service can be used
        """
        ...
```

**Implementation Requirements:**
- Must validate all configuration before use
- Must provide availability checking
- Should handle graceful degradation when unavailable

**Example Implementation:**
```python
class MyService:
    def validate_config(self, config: MyConfig) -> bool:
        if not config.required_field:
            raise ConfigError("required_field is missing")
        return True
    
    def check_available(self) -> bool:
        # Check external dependencies
        return shutil.which("required_tool") is not None

# Runtime validation
assert isinstance(MyService(), BaseServiceProtocol)
```

## Compilation Domain Protocols

### CompilationServiceProtocol

Primary protocol for firmware compilation strategies.

```python
from glovebox.compilation.protocols import CompilationServiceProtocol

@runtime_checkable
class CompilationServiceProtocol(Protocol):
    """Protocol for compilation strategy services."""
    
    def compile(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: CompilationConfigUnion,
        keyboard_profile: KeyboardProfile,
        progress_callback: CompilationProgressCallback | None = None,
        json_file: Path | None = None,
    ) -> BuildResult:
        """Execute compilation using this strategy.
        
        Args:
            keymap_file: Path to keymap file
            config_file: Path to config file
            output_dir: Output directory for build artifacts
            config: Compilation configuration
            keyboard_profile: Keyboard profile for dynamic generation
            progress_callback: Optional callback for compilation progress updates
            json_file: Optional path to original JSON layout file for metadata
            
        Returns:
            BuildResult: Results of compilation
            
        Raises:
            CompilationError: If compilation fails
            ConfigError: If configuration is invalid
            FileSystemError: If file operations fail
        """
        ...
    
    def compile_from_json(
        self,
        json_file: Path,
        output_dir: Path,
        config: CompilationConfigUnion,
        keyboard_profile: KeyboardProfile,
        progress_callback: CompilationProgressCallback | None = None,
    ) -> BuildResult:
        """Execute compilation from JSON layout file.
        
        Args:
            json_file: Path to JSON layout file
            output_dir: Output directory for build artifacts
            config: Compilation configuration
            keyboard_profile: Keyboard profile for dynamic generation
            progress_callback: Optional callback for compilation progress updates
            
        Returns:
            BuildResult: Results of compilation
        """
        ...
    
    def validate_config(self, config: CompilationConfigUnion) -> bool:
        """Validate configuration for this compilation strategy.
        
        Args:
            config: Compilation configuration to validate
            
        Returns:
            bool: True if configuration is valid
        """
        ...
    
    def check_available(self) -> bool:
        """Check if this compilation strategy is available.
        
        Returns:
            bool: True if strategy is available
        """
        ...
```

**Behavioral Contract:**
- Must validate all inputs before processing
- Must provide meaningful progress updates through callbacks
- Must create reproducible builds with identical inputs
- Must handle workspace setup and cleanup
- Must provide detailed error information on failure

**Example Implementation:**
```python
class ZmkWestService:
    def compile(self, keymap_file: Path, config_file: Path, output_dir: Path, 
                config: ZmkCompilationConfig, keyboard_profile: KeyboardProfile,
                progress_callback: CompilationProgressCallback | None = None,
                json_file: Path | None = None) -> BuildResult:
        
        # Validate inputs
        if not self.validate_config(config):
            raise CompilationError("Invalid configuration")
        
        if not keymap_file.exists():
            raise FileSystemError(f"Keymap file not found: {keymap_file}")
        
        # Report progress
        if progress_callback:
            progress_callback(CompilationProgress(
                phase="workspace_setup",
                percentage=10,
                message="Setting up workspace"
            ))
        
        # Execute compilation
        try:
            # ... compilation logic
            return BuildResult(
                success=True,
                output_files=output_files,
                build_log=build_log,
                duration=duration
            )
        except Exception as e:
            return BuildResult(
                success=False,
                message=str(e),
                build_log=build_log
            )
```

## Firmware Domain Protocols

### FlasherProtocol

Protocol for firmware flashing implementations.

```python
from glovebox.protocols.flash_protocols import FlasherProtocol

@runtime_checkable
class FlasherProtocol(Protocol):
    """Protocol for firmware flashing operations."""
    
    def flash(
        self,
        firmware_file: Path,
        device: BlockDevice,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> FlashResult:
        """Flash firmware to device.
        
        Args:
            firmware_file: Path to firmware file
            device: Target block device
            progress_callback: Optional progress callback (bytes_written, total_bytes)
            
        Returns:
            FlashResult: Flash operation result
            
        Raises:
            FlashError: If flashing fails
            USBError: If device communication fails
        """
        ...
    
    def verify_device(self, device: BlockDevice) -> bool:
        """Verify device is suitable for flashing.
        
        Args:
            device: Device to verify
            
        Returns:
            bool: True if device is suitable
        """
        ...
    
    def get_supported_file_types(self) -> list[str]:
        """Get supported firmware file extensions.
        
        Returns:
            list[str]: Supported file extensions (e.g., ['.uf2', '.bin'])
        """
        ...
```

### DeviceDetectorProtocol

Protocol for USB device detection and monitoring.

```python
from glovebox.protocols.device_detector_protocol import DeviceDetectorProtocol

@runtime_checkable
class DeviceDetectorProtocol(Protocol):
    """Protocol for device detection operations."""
    
    def detect_devices(
        self,
        filter_removable: bool = True,
        vendor_filter: str | None = None,
    ) -> list[BlockDevice]:
        """Detect available block devices.
        
        Args:
            filter_removable: Only return removable devices
            vendor_filter: Filter by vendor name
            
        Returns:
            list[BlockDevice]: List of detected devices
        """
        ...
    
    def wait_for_device(
        self,
        timeout: int = 60,
        device_filter: dict[str, str] | None = None,
    ) -> BlockDevice | None:
        """Wait for specific device to appear.
        
        Args:
            timeout: Wait timeout in seconds
            device_filter: Device filter criteria
            
        Returns:
            BlockDevice | None: Detected device or None if timeout
        """
        ...
    
    def monitor_devices(
        self,
        callback: Callable[[BlockDevice, str], None],
        stop_event: threading.Event,
    ) -> None:
        """Monitor device events.
        
        Args:
            callback: Callback for device events (device, event_type)
            stop_event: Event to stop monitoring
        """
        ...
```

### FlashOSProtocol

Protocol for OS-specific flash operations.

```python
from glovebox.protocols.flash_os_protocol import FlashOSProtocol

@runtime_checkable
class FlashOSProtocol(Protocol):
    """Protocol for OS-specific flash operations."""
    
    def get_block_devices(self) -> list[BlockDevice]:
        """Get list of available block devices.
        
        Returns:
            list[BlockDevice]: Available block devices
        """
        ...
    
    def mount_device(self, device: BlockDevice) -> list[str]:
        """Mount device and return mount points.
        
        Args:
            device: Device to mount
            
        Returns:
            list[str]: List of mount points
            
        Raises:
            USBError: If mounting fails
        """
        ...
    
    def unmount_device(self, device: BlockDevice) -> bool:
        """Unmount device.
        
        Args:
            device: Device to unmount
            
        Returns:
            bool: True if successfully unmounted
        """
        ...
    
    def copy_firmware(
        self,
        firmware_file: Path,
        mount_point: str,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> int:
        """Copy firmware to mounted device.
        
        Args:
            firmware_file: Source firmware file
            mount_point: Target mount point
            progress_callback: Optional progress callback
            
        Returns:
            int: Number of bytes copied
        """
        ...
```

## Layout Domain Protocols

### TemplateServiceProtocol

Protocol for template processing operations.

```python
from glovebox.protocols.layout_protocols import TemplateServiceProtocol

@runtime_checkable
class TemplateServiceProtocol(Protocol):
    """Protocol for template processing services."""
    
    def process_layout_data(self, layout: LayoutData) -> LayoutData:
        """Process templates in layout data.
        
        Args:
            layout: Layout data with potential templates
            
        Returns:
            LayoutData: Layout with resolved templates
            
        Raises:
            TemplateError: If template processing fails
        """
        ...
    
    def render_template(
        self,
        template: str,
        context: dict[str, Any],
    ) -> str:
        """Render template with context.
        
        Args:
            template: Template string
            context: Template context variables
            
        Returns:
            str: Rendered template
        """
        ...
    
    def validate_template(self, template: str) -> bool:
        """Validate template syntax.
        
        Args:
            template: Template string to validate
            
        Returns:
            bool: True if template is valid
        """
        ...
```

### BehaviorRegistryProtocol

Protocol for behavior registry implementations.

```python
from glovebox.protocols.behavior_protocols import BehaviorRegistryProtocol

@runtime_checkable
class BehaviorRegistryProtocol(Protocol):
    """Protocol for behavior registry operations."""
    
    def register_behavior(
        self,
        behavior_code: str,
        behavior_class: type,
        formatter: Callable[[Any], str] | None = None,
    ) -> None:
        """Register behavior type with formatter.
        
        Args:
            behavior_code: Behavior code (e.g., "&kp", "&mt")
            behavior_class: Behavior model class
            formatter: Optional custom formatter
        """
        ...
    
    def get_behavior_formatter(self, behavior_code: str) -> Callable[[Any], str] | None:
        """Get formatter for behavior code.
        
        Args:
            behavior_code: Behavior code
            
        Returns:
            Formatter function or None if not found
        """
        ...
    
    def format_binding(self, binding: LayoutBinding) -> str:
        """Format binding using registered formatters.
        
        Args:
            binding: Binding to format
            
        Returns:
            str: Formatted binding string
        """
        ...
```

## Adapter Protocols

### DockerAdapterProtocol

Protocol for Docker container operations.

```python
from glovebox.protocols.docker_adapter_protocol import DockerAdapterProtocol

@runtime_checkable
class DockerAdapterProtocol(Protocol):
    """Protocol for Docker adapter operations."""
    
    def run(
        self,
        image: str,
        command: list[str],
        volumes: list[DockerVolume] | None = None,
        environment: dict[str, str] | None = None,
        working_dir: str | None = None,
        user: str | None = None,
        remove: bool = True,
        stdout_middleware: OutputMiddleware | None = None,
        stderr_middleware: OutputMiddleware | None = None,
    ) -> DockerResult:
        """Run command in Docker container.
        
        Args:
            image: Docker image name
            command: Command to execute
            volumes: Volume mounts
            environment: Environment variables
            working_dir: Working directory
            user: User specification
            remove: Remove container after execution
            stdout_middleware: Stdout processing middleware
            stderr_middleware: Stderr processing middleware
            
        Returns:
            DockerResult: Execution result
            
        Raises:
            DockerError: If Docker operation fails
        """
        ...
    
    def pull_image(self, image: str) -> bool:
        """Pull Docker image.
        
        Args:
            image: Image name to pull
            
        Returns:
            bool: True if pull was successful
        """
        ...
    
    def image_exists(self, image: str) -> bool:
        """Check if Docker image exists locally.
        
        Args:
            image: Image name to check
            
        Returns:
            bool: True if image exists
        """
        ...
    
    def get_version(self) -> str | None:
        """Get Docker version.
        
        Returns:
            str | None: Docker version or None if unavailable
        """
        ...
```

### FileAdapterProtocol

Protocol for file system operations.

```python
from glovebox.protocols.file_adapter_protocol import FileAdapterProtocol

@runtime_checkable
class FileAdapterProtocol(Protocol):
    """Protocol for file system operations."""
    
    def read_text(self, file_path: Path) -> str:
        """Read text file content.
        
        Args:
            file_path: Path to file
            
        Returns:
            str: File content
            
        Raises:
            FileSystemError: If file cannot be read
        """
        ...
    
    def write_text(self, file_path: Path, content: str) -> None:
        """Write text content to file.
        
        Args:
            file_path: Path to file
            content: Content to write
            
        Raises:
            FileSystemError: If file cannot be written
        """
        ...
    
    def copy_file(
        self,
        source: Path,
        destination: Path,
        preserve_metadata: bool = True,
    ) -> None:
        """Copy file with optional metadata preservation.
        
        Args:
            source: Source file path
            destination: Destination file path
            preserve_metadata: Preserve file metadata
            
        Raises:
            FileSystemError: If copy fails
        """
        ...
    
    def ensure_directory(
        self,
        directory: Path,
        mode: int = 0o755,
    ) -> None:
        """Ensure directory exists with specified permissions.
        
        Args:
            directory: Directory path
            mode: Directory permissions
            
        Raises:
            FileSystemError: If directory cannot be created
        """
        ...
```

### USBAdapterProtocol

Protocol for USB device operations.

```python
from glovebox.protocols.usb_adapter_protocol import USBAdapterProtocol

@runtime_checkable
class USBAdapterProtocol(Protocol):
    """Protocol for USB adapter operations."""
    
    def list_devices(
        self,
        vendor_filter: str | None = None,
        product_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """List USB devices with optional filtering.
        
        Args:
            vendor_filter: Filter by vendor name/ID
            product_filter: Filter by product name/ID
            
        Returns:
            list[dict[str, Any]]: List of USB device information
        """
        ...
    
    def get_device_info(self, device_id: str) -> dict[str, Any] | None:
        """Get detailed information for specific device.
        
        Args:
            device_id: Device identifier
            
        Returns:
            dict[str, Any] | None: Device information or None if not found
        """
        ...
    
    def wait_for_device(
        self,
        vendor_id: str,
        product_id: str,
        timeout: int = 60,
    ) -> dict[str, Any] | None:
        """Wait for specific USB device to appear.
        
        Args:
            vendor_id: USB vendor ID
            product_id: USB product ID
            timeout: Wait timeout in seconds
            
        Returns:
            dict[str, Any] | None: Device info or None if timeout
        """
        ...
```

### TemplateAdapterProtocol

Protocol for template engine operations.

```python
from glovebox.protocols.template_adapter_protocol import TemplateAdapterProtocol

@runtime_checkable
class TemplateAdapterProtocol(Protocol):
    """Protocol for template adapter operations."""
    
    def render_string(
        self,
        template: str,
        context: dict[str, Any],
    ) -> str:
        """Render template string with context.
        
        Args:
            template: Template string
            context: Template context variables
            
        Returns:
            str: Rendered template
            
        Raises:
            TemplateError: If rendering fails
        """
        ...
    
    def render_file(
        self,
        template_path: Path,
        context: dict[str, Any],
        output_path: Path | None = None,
    ) -> str:
        """Render template file with context.
        
        Args:
            template_path: Path to template file
            context: Template context variables
            output_path: Optional output file path
            
        Returns:
            str: Rendered template
        """
        ...
    
    def validate_template(self, template: str) -> bool:
        """Validate template syntax.
        
        Args:
            template: Template string to validate
            
        Returns:
            bool: True if template is valid
        """
        ...
```

## Configuration Protocols

### ConfigFileAdapterProtocol

Generic protocol for configuration file operations.

```python
from glovebox.protocols.config_file_adapter_protocol import ConfigFileAdapterProtocol

@runtime_checkable
class ConfigFileAdapterProtocol(Protocol[T]):
    """Protocol for configuration file operations."""
    
    def load(self, file_path: Path) -> T:
        """Load configuration from file.
        
        Args:
            file_path: Path to configuration file
            
        Returns:
            T: Parsed configuration object
            
        Raises:
            ConfigError: If loading fails
        """
        ...
    
    def save(self, config: T, file_path: Path) -> None:
        """Save configuration to file.
        
        Args:
            config: Configuration object to save
            file_path: Path to save configuration
            
        Raises:
            ConfigError: If saving fails
        """
        ...
    
    def validate(self, config: T) -> bool:
        """Validate configuration object.
        
        Args:
            config: Configuration to validate
            
        Returns:
            bool: True if configuration is valid
        """
        ...
    
    def get_schema(self) -> dict[str, Any]:
        """Get JSON schema for configuration.
        
        Returns:
            dict[str, Any]: JSON schema
        """
        ...
```

## Cache Protocols

### CacheManager

Protocol for cache management operations.

```python
from glovebox.core.cache.cache_manager import CacheManager

@runtime_checkable
class CacheManager(Protocol):
    """Generic cache manager interface."""
    
    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve value from cache.
        
        Args:
            key: Cache key to retrieve
            default: Default value if key not found
            
        Returns:
            Cached value or default
        """
        ...
    
    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Store value in cache.
        
        Args:
            key: Cache key to store under
            value: Value to cache
            ttl: Time-to-live in seconds (None for no expiration)
        """
        ...
    
    def delete(self, key: str) -> bool:
        """Remove value from cache.
        
        Args:
            key: Cache key to remove
            
        Returns:
            True if key was removed, False if not found
        """
        ...
    
    def clear(self) -> None:
        """Clear all entries from cache."""
        ...
    
    def get_stats(self) -> CacheStats:
        """Get cache performance statistics.
        
        Returns:
            Current cache statistics
        """
        ...
    
    def close(self) -> None:
        """Close the cache and release resources."""
        ...
```

### MountCacheProtocol

Protocol for mount point caching operations.

```python
from glovebox.protocols.mount_cache_protocol import MountCacheProtocol

@runtime_checkable
class MountCacheProtocol(Protocol):
    """Protocol for mount point cache operations."""
    
    def get_mount_points(self, device_name: str) -> list[str]:
        """Get cached mount points for device.
        
        Args:
            device_name: Device name
            
        Returns:
            list[str]: List of mount points
        """
        ...
    
    def cache_mount_points(
        self,
        device_name: str,
        mount_points: list[str],
    ) -> None:
        """Cache mount points for device.
        
        Args:
            device_name: Device name
            mount_points: List of mount points
        """
        ...
    
    def invalidate_device(self, device_name: str) -> None:
        """Invalidate cache for specific device.
        
        Args:
            device_name: Device name to invalidate
        """
        ...
    
    def clear_cache(self) -> None:
        """Clear all cached mount points."""
        ...
```

## Progress and Metrics Protocols

### ProgressCoordinatorProtocol

Protocol for progress coordination operations.

```python
from glovebox.protocols.progress_coordinator_protocol import ProgressCoordinatorProtocol

@runtime_checkable
class ProgressCoordinatorProtocol(Protocol):
    """Protocol for progress coordination."""
    
    def start_operation(
        self,
        operation_id: str,
        total_steps: int,
        description: str,
    ) -> None:
        """Start tracking operation progress.
        
        Args:
            operation_id: Unique operation identifier
            total_steps: Total number of steps
            description: Operation description
        """
        ...
    
    def update_progress(
        self,
        operation_id: str,
        current_step: int,
        step_description: str | None = None,
    ) -> None:
        """Update operation progress.
        
        Args:
            operation_id: Operation identifier
            current_step: Current step number
            step_description: Optional step description
        """
        ...
    
    def complete_operation(self, operation_id: str) -> None:
        """Mark operation as complete.
        
        Args:
            operation_id: Operation identifier
        """
        ...
    
    def fail_operation(
        self,
        operation_id: str,
        error_message: str,
    ) -> None:
        """Mark operation as failed.
        
        Args:
            operation_id: Operation identifier
            error_message: Error description
        """
        ...
```

### MetricsProtocol

Protocol for metrics collection operations.

```python
from glovebox.protocols.metrics_protocol import MetricsProtocol

@runtime_checkable
class MetricsProtocol(Protocol):
    """Protocol for metrics collection."""
    
    def counter(self, name: str, labels: dict[str, str] | None = None) -> Any:
        """Get or create counter metric.
        
        Args:
            name: Metric name
            labels: Optional labels
            
        Returns:
            Counter metric instance
        """
        ...
    
    def gauge(self, name: str, labels: dict[str, str] | None = None) -> Any:
        """Get or create gauge metric.
        
        Args:
            name: Metric name
            labels: Optional labels
            
        Returns:
            Gauge metric instance
        """
        ...
    
    def histogram(self, name: str, labels: dict[str, str] | None = None) -> Any:
        """Get or create histogram metric.
        
        Args:
            name: Metric name
            labels: Optional labels
            
        Returns:
            Histogram metric instance
        """
        ...
    
    def time_operation(self, name: str) -> Any:
        """Context manager for timing operations.
        
        Args:
            name: Operation name
            
        Returns:
            Context manager for timing
        """
        ...
```

## Protocol Testing

### Compliance Testing

All protocols should include compliance tests to verify implementations.

```python
import pytest
from typing import Protocol

def test_protocol_compliance():
    """Test that implementation satisfies protocol."""
    service = MyService()
    
    # Runtime protocol checking
    assert isinstance(service, BaseServiceProtocol)
    assert isinstance(service, CompilationServiceProtocol)
    
    # Method signature verification
    assert hasattr(service, 'compile')
    assert hasattr(service, 'validate_config')
    assert hasattr(service, 'check_available')

def test_protocol_methods():
    """Test protocol method behavior."""
    service = MyService()
    
    # Test configuration validation
    valid_config = create_valid_config()
    assert service.validate_config(valid_config) is True
    
    invalid_config = create_invalid_config()
    with pytest.raises(ConfigError):
        service.validate_config(invalid_config)
    
    # Test availability checking
    availability = service.check_available()
    assert isinstance(availability, bool)
```

### Mock Implementations

Protocols enable easy mock implementations for testing.

```python
class MockCompilationService:
    """Mock implementation for testing."""
    
    def compile(self, keymap_file: Path, config_file: Path, output_dir: Path,
                config: CompilationConfigUnion, keyboard_profile: KeyboardProfile,
                progress_callback: CompilationProgressCallback | None = None,
                json_file: Path | None = None) -> BuildResult:
        return BuildResult(success=True, message="Mock compilation")
    
    def compile_from_json(self, json_file: Path, output_dir: Path,
                          config: CompilationConfigUnion, keyboard_profile: KeyboardProfile,
                          progress_callback: CompilationProgressCallback | None = None) -> BuildResult:
        return BuildResult(success=True, message="Mock JSON compilation")
    
    def validate_config(self, config: CompilationConfigUnion) -> bool:
        return True
    
    def check_available(self) -> bool:
        return True

# Verify mock satisfies protocol
mock_service = MockCompilationService()
assert isinstance(mock_service, CompilationServiceProtocol)
```

## Implementation Guidelines

### Protocol Implementation Best Practices

1. **Always validate inputs** before processing
2. **Provide meaningful error messages** with context
3. **Handle edge cases gracefully** with appropriate exceptions
4. **Use proper logging** with debug-aware stack traces
5. **Follow consistent return patterns** across implementations
6. **Implement proper resource cleanup** in finally blocks or context managers

### Error Handling Patterns

```python
def my_protocol_method(self, param: str) -> str:
    """Implementation with proper error handling."""
    try:
        # Validate inputs
        if not param:
            raise ValueError("Parameter cannot be empty")
        
        # Process operation
        result = self._process_operation(param)
        
        return result
        
    except Exception as e:
        # Log with debug-aware stack trace
        exc_info = self.logger.isEnabledFor(logging.DEBUG)
        self.logger.error("Operation failed: %s", e, exc_info=exc_info)
        raise
```

### Protocol Extension

Protocols can be extended through inheritance.

```python
@runtime_checkable
class EnhancedCompilationServiceProtocol(CompilationServiceProtocol, Protocol):
    """Extended compilation service with additional capabilities."""
    
    def compile_parallel(
        self,
        jobs: list[CompilationJob],
        max_workers: int = 4,
    ) -> list[BuildResult]:
        """Compile multiple jobs in parallel."""
        ...
    
    def get_build_cache_stats(self) -> CacheStats:
        """Get build cache performance statistics."""
        ...
```

This comprehensive protocol system ensures type safety, clear behavioral contracts, and maintainable code throughout the Glovebox codebase.