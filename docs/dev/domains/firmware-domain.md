# Firmware Domain Documentation

The Firmware domain handles firmware building and device flashing operations. It provides Docker-based compilation services and cross-platform USB device management for flashing firmware to keyboards.

## Overview

The Firmware domain is responsible for:
- **Firmware Compilation**: Build ZMK firmware using Docker containers
- **Device Detection**: Cross-platform USB device discovery and monitoring
- **Firmware Flashing**: Flash firmware binaries to keyboard devices
- **Build Management**: Handle build artifacts, caching, and cleanup
- **Docker Integration**: Manage Docker containers and volume permissions

## Domain Structure

```
glovebox/firmware/
├── __init__.py              # Domain exports and registry
├── build_service.py         # Main firmware build service
├── models.py               # Firmware data models
├── options.py              # Build service options
├── method_registry.py      # Compiler/flasher registry
├── method_selector.py      # Method selection logic
├── registry_init.py        # Method registration
├── compile/                # Compilation methods
│   ├── __init__.py
│   ├── methods.py          # Compilation method implementations
│   └── generic_docker_compiler.py  # Generic Docker compiler
└── flash/                  # Flash subdomain
    ├── __init__.py         # Flash domain exports
    ├── service.py          # Main flash service
    ├── models.py           # Flash data models
    ├── device_detector.py  # USB device detection
    ├── device_wait_service.py  # Device wait/monitoring
    ├── flash_operations.py # Low-level flash operations
    ├── flasher_methods.py  # Flash method implementations
    ├── os_adapters.py      # Platform-specific operations
    ├── usb.py             # USB device utilities
    ├── usb_monitor.py     # Cross-platform USB monitoring
    └── wait_state.py      # Device wait state management
```

## Core Models

### BuildResult
Result of firmware compilation:

```python
from glovebox.firmware.models import BuildResult

class BuildResult(BaseModel):
    """Result of firmware build operation."""
    success: bool
    output_files: FirmwareOutputFiles
    build_log: str
    error_message: Optional[str] = None
    build_time: float
    artifacts_path: Path
```

### FirmwareOutputFiles
Represents built firmware artifacts:

```python
class FirmwareOutputFiles(BaseModel):
    """Firmware build output files."""
    uf2_files: list[Path]           # Firmware binaries
    elf_files: list[Path]           # Debug symbols
    hex_files: list[Path]           # Hex format
    build_info: Optional[Path]      # Build metadata
    build_log: Optional[Path]       # Build log file
```

### BlockDevice (Flash Subdomain)
Represents a USB storage device:

```python
from glovebox.firmware.flash.models import BlockDevice

class BlockDevice(BaseModel):
    """USB block device for flashing."""
    name: str                       # Device name
    path: str                       # Device path
    vendor: Optional[str] = None    # Vendor ID
    serial: Optional[str] = None    # Serial number
    size: Optional[int] = None      # Device size
    removable: bool = True          # Is removable
    mounted: bool = False           # Mount status
    mount_points: list[str] = []    # Mount points
```

### FlashResult (Flash Subdomain)
Result of flash operation:

```python
class FlashResult(BaseModel):
    """Result of firmware flash operation."""
    success: bool
    device: BlockDevice
    firmware_file: Path
    flash_time: float
    error_message: Optional[str] = None
    mount_points: list[str] = []
```

## Build Services

### BuildService
Main service for firmware compilation:

```python
from glovebox.firmware import create_build_service

# Create build service
build_service = create_build_service()

# Compile firmware
result = build_service.compile(
    profile=keyboard_profile,
    keymap_file=Path("layout.keymap"),
    kconfig_file=Path("config.conf"),
    options=BuildServiceCompileOpts(
        output_dir=Path("build/"),
        jobs=4,
        verbose=True
    )
)

if result.success:
    print(f"Build completed: {result.output_files.uf2_files}")
else:
    print(f"Build failed: {result.error_message}")
```

### BuildServiceCompileOpts
Options for firmware compilation:

```python
from glovebox.firmware.options import BuildServiceCompileOpts

options = BuildServiceCompileOpts(
    output_dir=Path("build/"),      # Build output directory
    jobs=4,                         # Parallel jobs
    verbose=True,                   # Verbose output
    clean_build=False,              # Clean before build
    docker_uid=None,                # Override Docker UID
    docker_gid=None,                # Override Docker GID
    docker_username=None,           # Override Docker username
    docker_home=None,               # Override Docker home
    docker_container_home=None,     # Override container home
    disable_user_mapping=False      # Disable user mapping
)
```

## Compilation Methods

### DockerCompiler
Docker-based firmware compilation:

```python
from glovebox.firmware.compile import create_docker_compiler

compiler = create_docker_compiler()

# Compile using Docker
result = compiler.compile(
    image="zmk-build:latest",
    source_dir=Path("source/"),
    output_dir=Path("build/"),
    build_args=["CONFIG_ZMK_BOARD=nice_nano_v2"]
)
```

### GenericDockerCompiler
Generic Docker compiler with advanced features:

```python
from glovebox.firmware.compile import create_generic_docker_compiler

compiler = create_generic_docker_compiler()

# Advanced compilation with user context
result = compiler.compile_with_user_context(
    profile=profile,
    keymap_file=keymap_file,
    kconfig_file=kconfig_file,
    options=compile_options,
    user_context=DockerUserContext(
        uid=1000,
        gid=1000,
        username="builder",
        home_dir="/home/builder"
    )
)
```

### Method Registry
Registry system for compilation and flash methods:

```python
from glovebox.firmware.method_registry import compiler_registry, flasher_registry

# Register custom compiler
@compiler_registry.register("custom_docker")
def create_custom_compiler():
    return CustomDockerCompiler()

# Get available methods
compilers = compiler_registry.get_available_methods()
flashers = flasher_registry.get_available_methods()
```

## Flash Subdomain

### FlashService
Main service for device flashing:

```python
from glovebox.firmware.flash import create_flash_service

flash_service = create_flash_service()

# Flash firmware to device
result = flash_service.flash_device(
    device=target_device,
    firmware_file=Path("firmware.uf2"),
    timeout=60
)

# Flash with device detection
results = flash_service.flash_with_detection(
    firmware_file=Path("firmware.uf2"),
    device_query="vendor=Adafruit and serial~=GLV80-.*",
    count=2,  # Flash 2 devices
    timeout=120
)
```

### DeviceDetector
Cross-platform USB device detection:

```python
from glovebox.firmware.flash import create_device_detector

detector = create_device_detector()

# List all USB storage devices
devices = detector.list_devices()

# Find devices matching query
matching_devices = detector.find_devices(
    query="vendor=Adafruit and removable=true"
)

# Monitor for device changes
for event in detector.monitor_devices():
    if event.event_type == "added":
        print(f"Device connected: {event.device.name}")
```

### Device Query Language
Flexible device query system:

```python
# Query examples
queries = [
    "vendor=Adafruit",                          # Exact vendor match
    "serial~=GLV80-.*",                         # Regex serial match
    "vendor=Adafruit and removable=true",       # Boolean AND
    "vendor=Adafruit or vendor=MoErgo",         # Boolean OR  
    "not vendor=Generic",                       # Boolean NOT
    "size>1000000",                             # Size comparison
    "(vendor=Adafruit or vendor=MoErgo) and removable=true"  # Grouping
]

# Query operators
# = (equals), != (not equals), ~= (regex match)
# > (greater), < (less), >= (gte), <= (lte)
# and, or, not, () (grouping)
```

### FlashOperations
Low-level flash operations:

```python
from glovebox.firmware.flash.flash_operations import create_flash_operations

flash_ops = create_flash_operations()

# Mount and flash device
success = flash_ops.mount_and_flash(
    device=device,
    firmware_file=Path("firmware.uf2"),
    max_retries=3
)

# Manual mount/unmount
mount_points = flash_ops.mount_device(device)
try:
    # Copy firmware file
    flash_ops.copy_firmware_file(firmware_file, mount_points[0])
finally:
    flash_ops.unmount_device(device)
```

### Cross-Platform OS Adapters
Platform-specific operations abstracted:

```python
from glovebox.firmware.flash.os_adapters import create_flash_os_adapter

os_adapter = create_flash_os_adapter()

# Works on Linux, macOS, Windows (where supported)
mount_points = os_adapter.mount_device(device)
success = os_adapter.copy_firmware_file(firmware_file, mount_points[0])
os_adapter.sync_filesystem(mount_points[0])
os_adapter.unmount_device(device)
```

### DeviceWaitService
Event-driven device detection:

```python
from glovebox.firmware.flash.device_wait_service import create_device_wait_service

wait_service = create_device_wait_service()

# Wait for specific devices
devices = wait_service.wait_for_devices(
    query="vendor=Adafruit",
    count=2,
    timeout=120,
    poll_interval=1.0
)

# Monitor with callbacks
def on_device_found(device: BlockDevice):
    print(f"Found device: {device.name}")

wait_service.monitor_devices(
    query="vendor=Adafruit",
    on_device_found=on_device_found,
    timeout=60
)
```

## Docker Integration

### User Context Management
Automatic Docker user context handling:

```python
from glovebox.adapters.docker_adapter import DockerUserContext

# Auto-detected user context
user_context = DockerUserContext.auto_detect()

# Manual user context
user_context = DockerUserContext(
    uid=1001,
    gid=1001,
    username="custom_user",
    home_dir="/custom/home",
    container_home="/home/custom_user"
)

# Apply to Docker commands
docker_cmd = ["docker", "run", "--user", f"{user_context.uid}:{user_context.gid}"]
```

### Volume Permission Handling
Automatic volume permission management:

```python
# Permissions automatically handled for build operations
result = build_service.compile(
    profile=profile,
    keymap_file=keymap_file,
    kconfig_file=kconfig_file,
    options=options  # User context auto-detected
)

# Manual override options
options = BuildServiceCompileOpts(
    docker_uid=1001,                    # Override UID
    docker_gid=1001,                    # Override GID
    docker_username="builder",          # Override username
    docker_home="/custom/home",         # Override host home
    docker_container_home="/home/builder",  # Override container home
    disable_user_mapping=False          # Enable/disable mapping
)
```

## Usage Patterns

### Basic Firmware Build

```python
from glovebox.firmware import create_build_service
from glovebox.config import create_keyboard_profile
from glovebox.firmware.options import BuildServiceCompileOpts

# Create services and profile
build_service = create_build_service()
profile = create_keyboard_profile("glove80", "v25.05")

# Configure build options
options = BuildServiceCompileOpts(
    output_dir=Path("build/glove80/"),
    jobs=4,
    verbose=True
)

# Build firmware
result = build_service.compile(
    profile=profile,
    keymap_file=Path("my_layout.keymap"),
    kconfig_file=Path("my_config.conf"),
    options=options
)

if result.success:
    firmware_files = result.output_files.uf2_files
    print(f"Built firmware: {firmware_files}")
else:
    print(f"Build failed: {result.error_message}")
```

### Device Detection and Flashing

```python
from glovebox.firmware.flash import create_flash_service

flash_service = create_flash_service()

# Flash firmware with automatic device detection
results = flash_service.flash_with_detection(
    firmware_file=Path("build/glove80.uf2"),
    device_query="vendor=Adafruit and serial~=GLV80-.*",
    count=2,        # Flash left and right halves
    timeout=120,    # Wait up to 2 minutes
    track_devices=True  # Prevent double-flashing
)

for result in results:
    if result.success:
        print(f"Flashed {result.device.name} successfully")
    else:
        print(f"Failed to flash {result.device.name}: {result.error_message}")
```

### Advanced Docker Configuration

```python
from glovebox.firmware.options import BuildServiceCompileOpts

# Custom Docker user configuration
options = BuildServiceCompileOpts(
    output_dir=Path("build/"),
    docker_uid=1001,                        # Custom UID
    docker_gid=1001,                        # Custom GID  
    docker_username="zmk_builder",          # Custom username
    docker_home="/home/user",               # Host home directory
    docker_container_home="/home/zmk_builder",  # Container home
    verbose=True
)

result = build_service.compile(
    profile=profile,
    keymap_file=keymap_file,
    kconfig_file=kconfig_file,
    options=options
)
```

### Event-Driven Device Monitoring

```python
from glovebox.firmware.flash.device_wait_service import create_device_wait_service

wait_service = create_device_wait_service()

def flash_when_ready(device):
    """Flash device when it becomes available."""
    print(f"Device ready: {device.name}")
    
    flash_service = create_flash_service()
    result = flash_service.flash_device(
        device=device,
        firmware_file=Path("firmware.uf2")
    )
    
    if result.success:
        print(f"Successfully flashed {device.name}")
    else:
        print(f"Flash failed: {result.error_message}")

# Monitor for Glove80 devices
wait_service.monitor_devices(
    query="vendor=Adafruit and serial~=GLV80-.*",
    on_device_found=flash_when_ready,
    timeout=300  # 5 minute timeout
)
```

## Testing

### Unit Tests
Test individual components:

```python
def test_build_service_compilation():
    """Test firmware compilation service."""
    build_service = create_build_service()
    profile = create_test_profile()
    
    result = build_service.compile(
        profile=profile,
        keymap_file=Path("test.keymap"),
        kconfig_file=Path("test.conf"),
        options=BuildServiceCompileOpts()
    )
    
    assert result.success
    assert len(result.output_files.uf2_files) > 0

def test_device_detection():
    """Test USB device detection."""
    detector = create_device_detector()
    devices = detector.list_devices()
    
    # Should find at least system devices
    assert isinstance(devices, list)
```

### Integration Tests
Test cross-component functionality:

```python
def test_full_build_and_flash_flow():
    """Test complete build and flash workflow."""
    # Build firmware
    build_service = create_build_service()
    build_result = build_service.compile(...)
    
    assert build_result.success
    
    # Flash to mock device
    flash_service = create_flash_service()
    mock_device = create_mock_device()
    
    flash_result = flash_service.flash_device(
        device=mock_device,
        firmware_file=build_result.output_files.uf2_files[0]
    )
    
    assert flash_result.success
```

### CLI Tests
Test command-line interface:

```python
def test_firmware_compile_command():
    """Test firmware compile CLI command."""
    result = runner.invoke(app, [
        "firmware", "compile",
        "test.keymap", "test.conf",
        "--profile", "glove80/v25.05",
        "--output-dir", "test_build/"
    ])
    
    assert result.exit_code == 0
    assert "Build completed" in result.output

def test_firmware_flash_command():
    """Test firmware flash CLI command."""
    result = runner.invoke(app, [
        "firmware", "flash",
        "test_firmware.uf2",
        "--profile", "glove80/v25.05",
        "--count", "1"
    ])
    
    assert result.exit_code == 0
```

## Error Handling

### Build Errors
```python
from glovebox.core.errors import BuildError

try:
    result = build_service.compile(...)
    if not result.success:
        raise BuildError(
            "Firmware compilation failed",
            build_log=result.build_log,
            error_details=result.error_message
        )
except DockerNotFoundError as e:
    raise BuildError("Docker not available") from e
```

### Flash Errors
```python
from glovebox.core.errors import FlashError

try:
    result = flash_service.flash_device(device, firmware_file)
    if not result.success:
        raise FlashError(
            f"Failed to flash device {device.name}",
            device_info=device.model_dump(),
            error_details=result.error_message
        )
except DeviceNotFoundError as e:
    raise FlashError("Target device not found") from e
```

## Performance Considerations

### Build Optimization
- **Docker image caching**: Build images cached locally
- **Incremental builds**: Only rebuild changed components  
- **Parallel compilation**: Multiple jobs for faster builds
- **Artifact caching**: Build artifacts cached between runs

### Device Detection
- **Event-driven monitoring**: Efficient USB event handling
- **Query optimization**: Device queries optimized for performance
- **Polling intervals**: Configurable polling for device detection
- **Resource management**: Proper cleanup of USB handles

### Memory Management
- **Streaming operations**: Large build logs streamed, not buffered
- **Temporary file cleanup**: Build artifacts cleaned automatically
- **Docker container cleanup**: Containers removed after builds
- **Device handle management**: USB handles properly closed

## Future Enhancements

### Planned Features
- **Remote builds**: Cloud-based firmware compilation
- **Build caching**: Distributed build artifact caching
- **Wireless flashing**: Support for wireless firmware updates
- **Build pipelines**: Multi-stage build workflows

### Extension Points
- **Custom compilers**: Plugin system for alternative build methods
- **Flash methods**: Support for different flashing protocols
- **Device drivers**: Additional USB device support
- **Build strategies**: Alternative compilation strategies