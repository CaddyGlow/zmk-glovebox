# Firmware Wait Mode Implementation Plan

## Overview

This document outlines the step-by-step implementation of event-driven device waiting functionality for the firmware flash command, with comprehensive user configuration support.

## Implementation Goals

1. **Event-Driven Device Waiting**: Use USB monitoring callbacks for real-time device detection
2. **User Configuration Integration**: Support settings via config files, environment variables, and CLI flags
3. **Real-Time Progress Display**: Show device count and connection status updates
4. **Backward Compatibility**: Preserve existing flash behavior when wait mode is disabled
5. **Code Quality**: Follow CLAUDE.md conventions with mandatory linting at each step

## Prerequisites

- Current branch: `feature/multi_method`
- All existing tests passing
- Linting tools available: `ruff`, `mypy`, `pre-commit`

## Implementation Steps

### Step 1: Extend User Config Models for Wait Settings

**Goal**: Add wait-related configuration fields to user config models

**Files to Modify**:
- `glovebox/config/models/firmware.py`
- `glovebox/config/user_config.py`

**Changes**:

1. **Update `FirmwareFlashConfig` model**:
   ```python
   class FirmwareFlashConfig(BaseModel):
       # ... existing fields ...
       
       # Device waiting behavior
       wait: bool = Field(
           default=False, description="Wait for devices to connect before flashing"
       )
       poll_interval: float = Field(
           default=0.5, ge=0.1, le=5.0, description="Polling interval in seconds when waiting"
       )
       show_progress: bool = Field(
           default=True, description="Show real-time device detection progress"
       )
   ```

2. **Update `DEFAULT_CONFIG` in user_config.py**:
   ```python
   DEFAULT_CONFIG = {
       # ... existing config ...
       "firmware": {
           "flash": {
               "timeout": 60,
               "count": 2,
               "track_flashed": True,
               "skip_existing": False,
               # NEW wait settings
               "wait": False,
               "poll_interval": 0.5,
               "show_progress": True,
           }
       },
   }
   ```

3. **Add debug logging for new config fields**:
   ```python
   # In _load_config method, add after existing debug logs:
   logger.debug(
       "firmware.flash.wait: %s (source: %s)",
       self._config.firmware.flash.wait,
       self.get_source("firmware.flash.wait"),
   )
   logger.debug(
       "firmware.flash.poll_interval: %s (source: %s)",
       self._config.firmware.flash.poll_interval,
       self.get_source("firmware.flash.poll_interval"),
   )
   logger.debug(
       "firmware.flash.show_progress: %s (source: %s)",
       self._config.firmware.flash.show_progress,
       self.get_source("firmware.flash.show_progress"),
   )
   ```

**Validation Commands**:
```bash
# Format and lint
ruff format .
ruff check . --fix
mypy glovebox/

# Run config-related tests
pytest tests/test_config/ -v

# Test environment variable parsing
pytest tests/test_config/test_user_config.py::test_environment_integration -v
```

**Commit Message**:
```
feat: add wait mode configuration fields to user config

- Add wait, poll_interval, and show_progress fields to FirmwareFlashConfig
- Update DEFAULT_CONFIG with new wait settings
- Add debug logging for wait-related configuration
- Support environment variables: GLOVEBOX_FIRMWARE__FLASH__WAIT, etc.
- Maintain backward compatibility with existing flash settings

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

### Step 2: Add CLI Parameters for Wait Mode

**Goal**: Extend firmware flash CLI command with wait-related parameters

**Files to Modify**:
- `glovebox/cli/commands/firmware.py`

**Changes**:

1. **Add CLI parameters** (after existing parameters):
   ```python
   @firmware_app.command()
   @handle_errors
   @with_profile()
   def flash(
       # ... existing parameters ...
       wait: Annotated[
           bool | None,
           typer.Option(
               "--wait/--no-wait",
               help="Wait for devices to connect before flashing (uses config default if not specified)"
           )
       ] = None,
       poll_interval: Annotated[
           float | None,
           typer.Option(
               "--poll-interval",
               help="Polling interval in seconds when waiting for devices (uses config default if not specified)",
               min=0.1,
               max=5.0
           )
       ] = None,
       show_progress: Annotated[
           bool | None,
           typer.Option(
               "--show-progress/--no-show-progress",
               help="Show real-time device detection progress (uses config default if not specified)"
           )
       ] = None,
   ) -> None:
   ```

2. **Extend config precedence logic** (after existing precedence section):
   ```python
   # Apply user config defaults for wait parameters
   # CLI values override config values when explicitly provided
   if user_config:
       # ... existing precedence logic ...
       
       # NEW: Wait-related settings with precedence
       effective_wait = (
           wait if wait is not None else user_config._config.firmware.flash.wait
       )
       effective_poll_interval = (
           poll_interval if poll_interval is not None 
           else user_config._config.firmware.flash.poll_interval
       )
       effective_show_progress = (
           show_progress if show_progress is not None
           else user_config._config.firmware.flash.show_progress
       )
   else:
       # Fallback to CLI values if user config not available
       effective_wait = wait if wait is not None else False
       effective_poll_interval = poll_interval if poll_interval is not None else 0.5
       effective_show_progress = show_progress if show_progress is not None else True
   ```

3. **Update docstring examples**:
   ```python
   """Flash firmware file to connected keyboard devices.

   Automatically detects USB keyboards in bootloader mode and flashes
   the firmware file. Supports flashing multiple devices simultaneously.
   
   When --wait is enabled, the command will monitor for device connections
   in real-time and show progress updates.

   Examples:
       glovebox firmware flash firmware.uf2 --profile glove80/v25.05
       glovebox firmware flash firmware.uf2 --wait --timeout 120
       glovebox firmware flash firmware.uf2 --wait --count 2 --poll-interval 1.0
       glovebox firmware flash firmware.uf2 --query "vendor=Adafruit and serial~=GLV80-.*"
   """
   ```

**Validation Commands**:
```bash
# Format and lint
ruff format .
ruff check . --fix
mypy glovebox/

# Test CLI help and parameter parsing
glovebox firmware flash --help
pytest tests/test_cli/test_firmware_commands.py -v

# Test parameter validation
pytest tests/test_cli/test_cli_args.py -v
```

**Commit Message**:
```
feat: add wait mode CLI parameters to firmware flash command

- Add --wait/--no-wait flag with config integration
- Add --poll-interval parameter with validation (0.1-5.0 seconds)  
- Add --show-progress/--no-show-progress flag
- Implement CLI > config > default precedence for all wait settings
- Update command docstring with wait mode examples
- Maintain backward compatibility when wait parameters not specified

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

### Step 3: Implement Device Waiting State Management

**Goal**: Create state management classes for tracking device waiting progress

**Files to Create**:
- `glovebox/firmware/flash/wait_state.py`

**Changes**:

1. **Create wait state management class**:
   ```python
   """Device waiting state management for flash operations."""
   
   import time
   from dataclasses import dataclass, field
   from typing import Callable
   
   from glovebox.firmware.flash.models import BlockDevice
   
   
   @dataclass
   class DeviceWaitState:
       """State management for device waiting operations."""
       
       target_count: int
       query: str
       timeout: float
       poll_interval: float = 0.5
       show_progress: bool = True
       
       # Runtime state
       found_devices: list[BlockDevice] = field(default_factory=list)
       waiting: bool = True
       start_time: float = field(default_factory=time.time)
       
       @property
       def elapsed_time(self) -> float:
           """Get elapsed time since waiting started."""
           return time.time() - self.start_time
       
       @property
       def is_timeout(self) -> bool:
           """Check if timeout has been reached."""
           return self.elapsed_time >= self.timeout
       
       @property
       def is_target_reached(self) -> bool:
           """Check if target device count has been reached."""
           return len(self.found_devices) >= self.target_count
       
       @property
       def should_stop_waiting(self) -> bool:
           """Check if waiting should stop (target reached or timeout)."""
           return not self.waiting or self.is_target_reached or self.is_timeout
       
       def add_device(self, device: BlockDevice) -> None:
           """Add a device to the found devices list."""
           if device not in self.found_devices:
               self.found_devices.append(device)
       
       def remove_device(self, device: BlockDevice) -> None:
           """Remove a device from the found devices list."""
           self.found_devices = [d for d in self.found_devices if d.path != device.path]
       
       def stop_waiting(self) -> None:
           """Stop the waiting process."""
           self.waiting = False
   
   
   DeviceCallback = Callable[[str, BlockDevice], None]
   ProgressCallback = Callable[[DeviceWaitState], None]
   ```

**Validation Commands**:
```bash
# Format and lint
ruff format .
ruff check . --fix
mypy glovebox/

# Test the new module
python -c "from glovebox.firmware.flash.wait_state import DeviceWaitState; print('Import successful')"
```

**Commit Message**:
```
feat: add device waiting state management for flash operations

- Create DeviceWaitState dataclass for tracking wait progress
- Add timeout, target count, and progress tracking properties
- Implement device add/remove methods with deduplication
- Add type aliases for callback functions
- Follow dataclass pattern for clean state management

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

### Step 4: Implement Device Wait Service with USB Monitoring

**Goal**: Create service for event-driven device waiting using USB monitoring callbacks

**Files to Create**:
- `glovebox/firmware/flash/device_wait_service.py`

**Changes**:

1. **Create device wait service**:
   ```python
   """Device waiting service with USB monitoring for flash operations."""
   
   import logging
   import time
   from typing import TYPE_CHECKING
   
   if TYPE_CHECKING:
       from glovebox.config.flash_methods import USBFlashConfig
   
   from glovebox.cli.helpers.output import print_info_message, print_warning_message
   from glovebox.firmware.flash.models import BlockDevice
   from glovebox.firmware.flash.usb_monitor import create_usb_monitor
   from glovebox.firmware.flash.wait_state import DeviceWaitState
   from glovebox.adapters.usb_adapter import create_usb_adapter
   
   
   logger = logging.getLogger(__name__)
   
   
   class DeviceWaitService:
       """Service for waiting for USB devices with real-time monitoring."""
   
       def __init__(self):
           """Initialize device wait service."""
           self.usb_monitor = create_usb_monitor()
           self.usb_adapter = create_usb_adapter()
   
       def wait_for_devices(
           self,
           target_count: int,
           timeout: float,
           query: str,
           flash_config: "USBFlashConfig",
           poll_interval: float = 0.5,
           show_progress: bool = True,
       ) -> list[BlockDevice]:
           """Wait for devices using event-driven monitoring.
           
           Args:
               target_count: Number of devices to wait for
               timeout: Maximum time to wait in seconds
               query: Device query string for filtering
               flash_config: USB flash configuration
               poll_interval: Polling interval for progress updates
               show_progress: Whether to show progress messages
               
           Returns:
               List of found devices (may be fewer than target if timeout)
           """
           logger.info(
               "Starting device wait: target=%d, timeout=%.1fs, query='%s'",
               target_count, timeout, query
           )
   
           # Get initial device count
           initial_devices = self.usb_adapter.list_matching_devices(query)
           initial_count = len(initial_devices)
   
           if show_progress:
               if initial_count >= target_count:
                   print_info_message(
                       f"Found {initial_count} device(s), target reached immediately"
                   )
                   return initial_devices[:target_count]
               elif initial_count > 0:
                   print_info_message(
                       f"Found {initial_count} device(s), waiting for {target_count - initial_count} more... (timeout: {timeout:.0f}s)"
                   )
               else:
                   print_info_message(
                       f"Waiting for {target_count} device(s)... (timeout: {timeout:.0f}s)"
                   )
   
           # Create wait state
           state = DeviceWaitState(
               target_count=target_count,
               query=query,
               timeout=timeout,
               poll_interval=poll_interval,
               show_progress=show_progress,
               found_devices=initial_devices.copy(),
           )
   
           # If already have enough devices, return immediately
           if state.is_target_reached:
               return state.found_devices[:target_count]
   
           # Create callback for device events
           def device_callback(action: str, device: BlockDevice) -> None:
               if action == "add" and self._matches_query(device, query):
                   state.add_device(device)
                   if show_progress:
                       print_info_message(
                           f"Found device: {device.serial or device.name} [{len(state.found_devices)}/{target_count}]"
                       )
                   
                   if state.is_target_reached:
                       state.stop_waiting()
               
               elif action == "remove":
                   old_count = len(state.found_devices)
                   state.remove_device(device)
                   if show_progress and len(state.found_devices) < old_count:
                       print_warning_message(
                           f"Device removed. Remaining: [{len(state.found_devices)}/{target_count}]"
                       )
   
           try:
               # Start monitoring and register callback
               self.usb_monitor.register_callback(device_callback)
               self.usb_monitor.start_monitoring()
   
               # Wait for devices or timeout
               while not state.should_stop_waiting:
                   time.sleep(poll_interval)
   
               if state.is_timeout and show_progress:
                   print_warning_message(
                       f"Timeout reached. Found {len(state.found_devices)} of {target_count} devices."
                   )
   
               return state.found_devices[:target_count] if state.found_devices else []
   
           finally:
               # Clean up monitoring
               self.usb_monitor.unregister_callback(device_callback)
               self.usb_monitor.stop_monitoring()
   
       def _matches_query(self, device: BlockDevice, query: str) -> bool:
           """Check if device matches the query string."""
           # Use USB adapter's existing query matching logic
           matching_devices = self.usb_adapter.list_matching_devices(query)
           return any(d.path == device.path for d in matching_devices)
   
   
   def create_device_wait_service() -> DeviceWaitService:
       """Factory function to create DeviceWaitService."""
       return DeviceWaitService()
   ```

**Validation Commands**:
```bash
# Format and lint
ruff format .
ruff check . --fix
mypy glovebox/

# Test the new service
python -c "from glovebox.firmware.flash.device_wait_service import create_device_wait_service; print('Import successful')"

# Run USB-related tests
pytest tests/test_firmware/test_flash_service.py -v
```

**Commit Message**:
```
feat: implement event-driven device wait service with USB monitoring

- Create DeviceWaitService with real-time USB device monitoring
- Use callback-based approach for immediate device detection
- Add progress display with device count updates  
- Implement query matching integration with existing USB adapter
- Add proper cleanup of monitoring resources
- Support timeout and target count configuration
- Follow service factory pattern for dependency injection

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

### Step 5: Integrate Wait Service into Flash Service

**Goal**: Integrate device waiting functionality into the main flash service

**Files to Modify**:
- `glovebox/firmware/flash/service.py`

**Changes**:

1. **Add wait service dependency**:
   ```python
   # Add to imports
   from glovebox.firmware.flash.device_wait_service import create_device_wait_service
   
   class FlashService:
       def __init__(
           self,
           file_adapter: FileAdapterProtocol | None = None,
           loglevel: str = "INFO",
       ):
           # ... existing initialization ...
           self.device_wait_service = create_device_wait_service()
   ```

2. **Add wait-enabled flash method**:
   ```python
   def flash_with_wait(
       self,
       firmware_file: str | Path,
       profile: Optional["KeyboardProfile"] = None,
       query: str = "",
       timeout: int = 60,
       count: int = 1,
       track_flashed: bool = True,
       skip_existing: bool = False,
       wait: bool = False,
       poll_interval: float = 0.5,
       show_progress: bool = True,
   ) -> FlashResult:
       """Flash firmware with optional device waiting.
       
       Args:
           firmware_file: Path to the firmware file to flash
           profile: KeyboardProfile with flash configuration
           query: Device query string (overrides profile-specific query)
           timeout: Timeout in seconds for waiting for devices
           count: Number of devices to flash (0 for unlimited)
           track_flashed: Whether to track which devices have been flashed
           skip_existing: Whether to skip devices already present at startup
           wait: Whether to wait for devices to connect
           poll_interval: Polling interval when waiting for devices
           show_progress: Whether to show progress updates
           
       Returns:
           FlashResult with details of the flash operation
       """
       logger.info("Starting firmware flash operation with wait=%s", wait)
       result = FlashResult(success=True)

       try:
           # Convert firmware_file to Path if it's a string
           if isinstance(firmware_file, str):
               firmware_file = Path(firmware_file)

           # Get flash method configs from profile or use defaults
           flash_configs = self._get_flash_method_configs(profile, query)

           # Select the best available flasher with fallbacks
           flasher = select_flasher_with_fallback(flash_configs)
           logger.info("Selected flasher method: %s", type(flasher).__name__)

           # Get devices - either wait for them or list immediately
           if wait:
               devices = self.device_wait_service.wait_for_devices(
                   target_count=count if count > 0 else 1,
                   timeout=timeout,
                   query=flash_configs[0].device_query,
                   flash_config=flash_configs[0],
                   poll_interval=poll_interval,
                   show_progress=show_progress,
               )
           else:
               devices = flasher.list_devices(flash_configs[0])

           if not devices:
               result.success = False
               result.add_error("No compatible devices found")
               return result

           # Flash to available devices (existing logic)
           devices_flashed = 0
           devices_failed = 0

           for device in devices[: count if count > 0 else len(devices)]:
               logger.info("Flashing device: %s", device.description or device.name)

               device_result = flasher.flash_device(
                   device=device,
                   firmware_file=firmware_file,
                   config=flash_configs[0],
               )

               # Store detailed device info (existing logic)
               device_details = {
                   "name": device.description or device.path,
                   "serial": device.serial,
                   "status": "success" if device_result.success else "failed",
               }

               if not device_result.success:
                   device_details["error"] = (
                       device_result.errors[0]
                       if device_result.errors
                       else "Unknown error"
                   )
                   devices_failed += 1
               else:
                   devices_flashed += 1

               result.device_details.append(device_details)

           # Update result with device counts (existing logic)
           result.devices_flashed = devices_flashed
           result.devices_failed = devices_failed

           # Overall success logic (existing)
           if devices_flashed == 0 and devices_failed == 0:
               result.success = False
               result.add_error("No devices were flashed")
           elif devices_failed > 0:
               result.success = False
               if devices_flashed > 0:
                   result.add_error(
                       f"{devices_failed} device(s) failed to flash, {devices_flashed} succeeded"
                   )
               else:
                   result.add_error(f"{devices_failed} device(s) failed to flash")
           else:
               result.add_message(f"Successfully flashed {devices_flashed} device(s)")

       except Exception as e:
           logger.error("Error in flash operation: %s", e)
           result.success = False
           result.add_error(f"Flash operation failed: {str(e)}")

       return result
   ```

3. **Update flash_from_file method**:
   ```python
   def flash_from_file(
       self,
       firmware_file_path: Path,
       profile: Optional["KeyboardProfile"] = None,
       query: str = "",
       timeout: int = 60,
       count: int = 1,
       track_flashed: bool = True,
       skip_existing: bool = False,
       wait: bool = False,
       poll_interval: float = 0.5,
       show_progress: bool = True,
   ) -> FlashResult:
       """Flash firmware from a file with optional device waiting."""
       logger.info(
           "Starting firmware flash operation from file: %s", firmware_file_path
       )

       # Validate firmware file existence
       if not self.file_adapter.check_exists(firmware_file_path):
           result = FlashResult(success=False)
           result.add_error(f"Firmware file not found: {firmware_file_path}")
           return result

       try:
           # Use the wait-enabled flash method
           return self.flash_with_wait(
               firmware_file=firmware_file_path,
               profile=profile,
               query=query,
               timeout=timeout,
               count=count,
               track_flashed=track_flashed,
               skip_existing=skip_existing,
               wait=wait,
               poll_interval=poll_interval,
               show_progress=show_progress,
           )
       except Exception as e:
           logger.error("Error preparing flash operation: %s", e)
           result = FlashResult(success=False)
           result.add_error(f"Flash preparation failed: {str(e)}")
           return result
   ```

**Validation Commands**:
```bash
# Format and lint
ruff format .
ruff check . --fix
mypy glovebox/

# Run flash service tests
pytest tests/test_firmware/test_flash_service.py -v

# Test flash integration
pytest tests/test_firmware/ -v
```

**Commit Message**:
```
feat: integrate device wait service into flash service

- Add device_wait_service dependency to FlashService
- Implement flash_with_wait method with conditional waiting logic
- Update flash_from_file to support wait parameters
- Preserve existing flash behavior when wait=False
- Add comprehensive logging for wait operations
- Maintain backward compatibility with existing flash methods

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

### Step 6: Connect CLI Command to Wait-Enabled Flash Service

**Goal**: Update CLI command to use wait-enabled flash service methods

**Files to Modify**:
- `glovebox/cli/commands/firmware.py`

**Changes**:

1. **Update flash service call**:
   ```python
   # Update the flash_service.flash_from_file call to include wait parameters
   result = flash_service.flash_from_file(
       firmware_file_path=firmware_file,
       profile=keyboard_profile,
       query=query,
       timeout=effective_timeout,
       count=effective_count,
       track_flashed=effective_track_flashed,
       skip_existing=effective_skip_existing,
       # NEW: Add wait parameters
       wait=effective_wait,
       poll_interval=effective_poll_interval,
       show_progress=effective_show_progress,
   )
   ```

2. **Update help text to mention config options**:
   ```python
   """Flash firmware file to connected keyboard devices.

   Automatically detects USB keyboards in bootloader mode and flashes
   the firmware file. Supports flashing multiple devices simultaneously.
   
   Wait mode uses real-time USB device monitoring for immediate detection
   when devices are connected. Configure defaults in user config file.

   Examples:
       # Basic flash (uses config defaults)
       glovebox firmware flash firmware.uf2 --profile glove80/v25.05
       
       # Enable wait mode with CLI flags
       glovebox firmware flash firmware.uf2 --wait --timeout 120
       
       # Configure multiple devices with custom polling
       glovebox firmware flash firmware.uf2 --wait --count 2 --poll-interval 1.0
       
       # Use specific device query
       glovebox firmware flash firmware.uf2 --query "vendor=Adafruit and serial~=GLV80-.*"

   Configuration:
       Set defaults in ~/.config/glovebox/config.yaml:
           firmware:
             flash:
               wait: true
               timeout: 120
               poll_interval: 0.5
               show_progress: true
   """
   ```

**Validation Commands**:
```bash
# Format and lint
ruff format .
ruff check . --fix
mypy glovebox/

# Test CLI command
glovebox firmware flash --help

# Test CLI integration
pytest tests/test_cli/test_firmware_commands.py -v

# Integration test with mock devices
pytest tests/test_cli/test_command_execution.py -v
```

**Commit Message**:
```
feat: connect CLI firmware flash command to wait-enabled service

- Update flash_from_file call to include wait parameters
- Pass effective_wait, effective_poll_interval, effective_show_progress to service
- Update command docstring with wait mode usage examples
- Add configuration documentation in help text
- Maintain full backward compatibility for existing usage patterns

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

### Step 7: Add Comprehensive Tests for Wait Functionality

**Goal**: Create comprehensive test coverage for wait mode functionality

**Files to Create**:
- `tests/test_firmware/test_device_wait_service.py`
- `tests/test_config/test_wait_config.py`

**Files to Modify**:
- `tests/test_cli/test_firmware_commands.py`

**Changes**:

1. **Create device wait service tests**:
   ```python
   """Tests for device wait service functionality."""
   
   import pytest
   from unittest.mock import Mock, patch
   import time
   
   from glovebox.firmware.flash.device_wait_service import DeviceWaitService
   from glovebox.firmware.flash.models import BlockDevice
   from glovebox.firmware.flash.wait_state import DeviceWaitState
   
   
   @pytest.fixture
   def mock_device():
       return BlockDevice(
           name="test_device",
           device_node="/dev/test",
           model="Test Device",
           vendor="Test Vendor",
           serial="TEST123",
           vendor_id="1234",
           product_id="5678",
       )
   
   
   @pytest.fixture
   def wait_service():
       return DeviceWaitService()
   
   
   class TestDeviceWaitState:
       def test_initial_state(self):
           state = DeviceWaitState(
               target_count=2,
               query="test",
               timeout=60.0,
           )
           
           assert state.target_count == 2
           assert state.query == "test"
           assert state.timeout == 60.0
           assert state.waiting is True
           assert len(state.found_devices) == 0
           assert not state.is_target_reached
           assert not state.is_timeout
   
       def test_add_remove_devices(self, mock_device):
           state = DeviceWaitState(target_count=2, query="test", timeout=60.0)
           
           # Add device
           state.add_device(mock_device)
           assert len(state.found_devices) == 1
           assert mock_device in state.found_devices
           
           # Add same device again (should not duplicate)
           state.add_device(mock_device)
           assert len(state.found_devices) == 1
           
           # Remove device
           state.remove_device(mock_device)
           assert len(state.found_devices) == 0
   
       def test_target_reached(self, mock_device):
           state = DeviceWaitState(target_count=1, query="test", timeout=60.0)
           
           assert not state.is_target_reached
           state.add_device(mock_device)
           assert state.is_target_reached
   
   
   class TestDeviceWaitService:
       @patch('glovebox.firmware.flash.device_wait_service.create_usb_monitor')
       @patch('glovebox.firmware.flash.device_wait_service.create_usb_adapter')
       def test_immediate_target_reached(self, mock_adapter_factory, mock_monitor_factory, mock_device):
           """Test when target devices are already available."""
           mock_adapter = Mock()
           mock_adapter.list_matching_devices.return_value = [mock_device]
           mock_adapter_factory.return_value = mock_adapter
           
           service = DeviceWaitService()
           
           result = service.wait_for_devices(
               target_count=1,
               timeout=60.0,
               query="test",
               flash_config=Mock(),
               show_progress=False,
           )
           
           assert len(result) == 1
           assert result[0] == mock_device
   
       @patch('glovebox.firmware.flash.device_wait_service.create_usb_monitor')
       @patch('glovebox.firmware.flash.device_wait_service.create_usb_adapter')
       @patch('time.sleep')
       def test_wait_with_callback(self, mock_sleep, mock_adapter_factory, mock_monitor_factory, mock_device):
           """Test waiting with device callback."""
           mock_adapter = Mock()
           mock_adapter.list_matching_devices.return_value = []
           mock_adapter_factory.return_value = mock_adapter
           
           mock_monitor = Mock()
           mock_monitor_factory.return_value = mock_monitor
           
           service = DeviceWaitService()
           
           # Mock the query matching to return True
           service._matches_query = Mock(return_value=True)
           
           # Simulate device callback after a short wait
           callback_called = []
           def capture_callback(callback):
               callback_called.append(callback)
           
           mock_monitor.register_callback.side_effect = capture_callback
           
           # Start the wait in a separate thread to simulate async behavior
           import threading
           result_container = []
           
           def run_wait():
               result = service.wait_for_devices(
                   target_count=1,
                   timeout=60.0,
                   query="test",
                   flash_config=Mock(),
                   poll_interval=0.1,
                   show_progress=False,
               )
               result_container.append(result)
           
           thread = threading.Thread(target=run_wait)
           thread.start()
           
           # Wait a bit then trigger callback
           time.sleep(0.05)
           if callback_called:
               callback_called[0]("add", mock_device)
           
           thread.join(timeout=1.0)
           
           # Verify monitoring was set up and cleaned up
           mock_monitor.register_callback.assert_called_once()
           mock_monitor.start_monitoring.assert_called_once()
           mock_monitor.unregister_callback.assert_called_once()
           mock_monitor.stop_monitoring.assert_called_once()
   ```

2. **Create wait config tests**:
   ```python
   """Tests for wait configuration functionality."""
   
   import pytest
   import os
   from pathlib import Path
   
   from glovebox.config.models.user import UserConfigData
   from glovebox.config.user_config import create_user_config
   
   
   class TestWaitConfiguration:
       def test_default_wait_config(self):
           """Test default wait configuration values."""
           config = UserConfigData()
           
           assert config.firmware.flash.wait is False
           assert config.firmware.flash.poll_interval == 0.5
           assert config.firmware.flash.show_progress is True
           assert config.firmware.flash.timeout == 60
           assert config.firmware.flash.count == 2
   
       def test_environment_variable_override(self):
           """Test wait config from environment variables."""
           env_vars = {
               "GLOVEBOX_FIRMWARE__FLASH__WAIT": "true",
               "GLOVEBOX_FIRMWARE__FLASH__POLL_INTERVAL": "1.0",
               "GLOVEBOX_FIRMWARE__FLASH__SHOW_PROGRESS": "false",
           }
           
           # Set environment variables
           for key, value in env_vars.items():
               os.environ[key] = value
           
           try:
               config = UserConfigData()
               
               assert config.firmware.flash.wait is True
               assert config.firmware.flash.poll_interval == 1.0
               assert config.firmware.flash.show_progress is False
           finally:
               # Clean up environment variables
               for key in env_vars:
                   os.environ.pop(key, None)
   
       def test_config_file_wait_settings(self, tmp_path):
           """Test wait config from YAML file."""
           config_file = tmp_path / "test_config.yaml"
           config_file.write_text("""
   firmware:
     flash:
       wait: true
       timeout: 120
       poll_interval: 2.0
       show_progress: false
   """)
           
           user_config = create_user_config(cli_config_path=config_file)
           
           assert user_config._config.firmware.flash.wait is True
           assert user_config._config.firmware.flash.timeout == 120
           assert user_config._config.firmware.flash.poll_interval == 2.0
           assert user_config._config.firmware.flash.show_progress is False
   
       def test_poll_interval_validation(self):
           """Test poll_interval field validation."""
           # Valid values
           config = UserConfigData(firmware={"flash": {"poll_interval": 0.5}})
           assert config.firmware.flash.poll_interval == 0.5
           
           config = UserConfigData(firmware={"flash": {"poll_interval": 5.0}})
           assert config.firmware.flash.poll_interval == 5.0
           
           # Invalid values should raise validation error
           with pytest.raises(ValueError):
               UserConfigData(firmware={"flash": {"poll_interval": 0.05}})  # Too small
           
           with pytest.raises(ValueError):
               UserConfigData(firmware={"flash": {"poll_interval": 10.0}})  # Too large
   ```

3. **Update CLI tests**:
   ```python
   # Add to tests/test_cli/test_firmware_commands.py
   
   def test_flash_command_wait_parameters(runner):
       """Test flash command with wait parameters."""
       result = runner.invoke(app, [
           "firmware", "flash", 
           "test.uf2", 
           "--wait",
           "--poll-interval", "1.0",
           "--show-progress",
           "--profile", "glove80/v25.05"
       ])
       
       # Should not crash with parameter parsing
       assert "--wait" in result.stdout or result.exit_code != 2  # Not a parameter error
   
   def test_flash_command_help_includes_wait_options(runner):
       """Test that help includes wait-related options."""
       result = runner.invoke(app, ["firmware", "flash", "--help"])
       
       assert "--wait" in result.stdout
       assert "--poll-interval" in result.stdout
       assert "--show-progress" in result.stdout
       assert "config" in result.stdout.lower()  # Mentions configuration
   ```

**Validation Commands**:
```bash
# Format and lint
ruff format .
ruff check . --fix
mypy glovebox/

# Run all new tests
pytest tests/test_firmware/test_device_wait_service.py -v
pytest tests/test_config/test_wait_config.py -v
pytest tests/test_cli/test_firmware_commands.py::test_flash_command_wait_parameters -v

# Run full test suite to ensure no regressions
pytest tests/ -x
```

**Commit Message**:
```
test: add comprehensive test coverage for wait mode functionality

- Add DeviceWaitService tests with mock USB monitoring
- Test DeviceWaitState behavior and device management
- Add user config tests for wait settings and validation
- Test environment variable override for wait configuration
- Add CLI parameter tests for wait mode flags
- Test poll_interval validation bounds (0.1-5.0 seconds)
- Ensure backward compatibility with existing test suite

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

### Step 8: Update Documentation and Examples

**Goal**: Update documentation to reflect new wait mode functionality

**Files to Modify**:
- `CLAUDE.md`
- `README.md` (if exists)
- `docs/example-config.yml`

**Files to Create**:
- `docs/firmware_wait_mode_usage.md`

**Changes**:

1. **Update CLAUDE.md with wait mode commands**:
   ```markdown
   # In the essential commands section, add:

   ### Firmware Flash with Wait Mode

   ```bash
   # Enable wait mode with default settings
   glovebox firmware flash firmware.uf2 --wait --profile glove80/v25.05

   # Custom wait configuration
   glovebox firmware flash firmware.uf2 --wait --timeout 120 --poll-interval 1.0 --count 3

   # Configure via user config for persistent settings
   # ~/.config/glovebox/config.yaml:
   firmware:
     flash:
       wait: true
       timeout: 120
       poll_interval: 0.5
       show_progress: true
   ```
   ```

2. **Update example config**:
   ```yaml
   # docs/example-config.yml - Add wait settings section
   
   # Firmware flash configuration
   firmware:
     flash:
       # Device detection and flashing behavior
       timeout: 60                 # Timeout in seconds for flash operations
       count: 2                    # Number of devices to flash (0 for infinite)
       track_flashed: true         # Enable device tracking during flash
       skip_existing: false        # Skip devices already present at startup
       
       # Wait mode settings (NEW)
       wait: false                 # Wait for devices to connect before flashing
       poll_interval: 0.5          # Polling interval in seconds when waiting (0.1-5.0)
       show_progress: true         # Show real-time device detection progress

   # Environment variable examples:
   # GLOVEBOX_FIRMWARE__FLASH__WAIT=true
   # GLOVEBOX_FIRMWARE__FLASH__POLL_INTERVAL=1.0
   # GLOVEBOX_FIRMWARE__FLASH__SHOW_PROGRESS=false
   ```

3. **Create usage documentation**:
   ```markdown
   # docs/firmware_wait_mode_usage.md
   
   # Firmware Wait Mode Usage Guide

   Wait mode enables real-time device detection for firmware flashing operations. Instead of failing immediately when no devices are found, wait mode monitors for device connections and provides live feedback.

   ## Basic Usage

   ### Enable Wait Mode via CLI
   ```bash
   # Wait for devices with default settings
   glovebox firmware flash firmware.uf2 --wait

   # Custom timeout and polling
   glovebox firmware flash firmware.uf2 --wait --timeout 120 --poll-interval 1.0

   # Wait for multiple devices
   glovebox firmware flash firmware.uf2 --wait --count 3 --timeout 180
   ```

   ### Configure via User Config
   ```yaml
   # ~/.config/glovebox/config.yaml
   firmware:
     flash:
       wait: true
       timeout: 120
       poll_interval: 0.5
       show_progress: true
       count: 2
   ```

   ## Configuration Options

   | Setting | CLI Flag | Environment Variable | Default | Description |
   |---------|----------|---------------------|---------|-------------|
   | wait | `--wait/--no-wait` | `GLOVEBOX_FIRMWARE__FLASH__WAIT` | false | Enable device waiting |
   | poll_interval | `--poll-interval` | `GLOVEBOX_FIRMWARE__FLASH__POLL_INTERVAL` | 0.5 | Polling interval (0.1-5.0s) |
   | show_progress | `--show-progress/--no-show-progress` | `GLOVEBOX_FIRMWARE__FLASH__SHOW_PROGRESS` | true | Show progress updates |

   ## User Experience

   ### Without Wait Mode (Default)
   ```
   $ glovebox firmware flash firmware.uf2
   Found 0 compatible device(s)
   ❌ Flash operation failed: No compatible devices found
   ```

   ### With Wait Mode
   ```
   $ glovebox firmware flash firmware.uf2 --wait --count 2
   Waiting for 2 device(s)... (timeout: 60s)
   Found device: GLV80-1234 [1/2]
   Found device: GLV80-5678 [2/2]
   ✓ Starting flash operation...
   ✓ Successfully flashed 2 device(s)
   ```

   ## Precedence Rules

   Configuration values are applied in this order (highest to lowest precedence):

   1. **CLI flags** - `--wait`, `--poll-interval`, etc.
   2. **Environment variables** - `GLOVEBOX_FIRMWARE__FLASH__WAIT=true`
   3. **Config files** - `~/.config/glovebox/config.yaml`
   4. **Defaults** - Built-in default values

   ## Tips

   - Use wait mode when flashing multiple keyboards sequentially
   - Set `poll_interval` higher (1.0-2.0) for slower systems
   - Disable `show_progress` for automated scripts
   - Configure persistent settings in user config for regular use
   ```

**Validation Commands**:
```bash
# Check documentation formatting
ruff format docs/ || true  # Docs may not be Python

# Test example config loading
python -c "
import yaml
with open('docs/example-config.yml') as f:
    config = yaml.safe_load(f)
    print('Config loaded successfully')
    print(f'Wait setting: {config[\"firmware\"][\"flash\"][\"wait\"]}')
"

# Test help output includes config info
glovebox firmware flash --help | grep -i config
```

**Commit Message**:
```
docs: add comprehensive documentation for firmware wait mode

- Update CLAUDE.md with wait mode command examples
- Add wait settings to example-config.yml with environment variable examples
- Create detailed usage guide in docs/firmware_wait_mode_usage.md
- Document configuration precedence rules and all available options
- Add user experience examples showing before/after behavior
- Include tips for optimal wait mode usage

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

### Step 9: Final Integration Testing and Performance Validation

**Goal**: Comprehensive testing of complete wait mode functionality

**Changes**:

1. **Integration test scenarios**:
   ```bash
   # Test basic wait functionality
   glovebox firmware flash tests_data/28e97485-dab5-4afb-afbc-5de5f1c52c45_v25.05_Glorious\ Engrammer\ v42\ preview\ with\ v41\ QWERTY\ layout.uf2 --wait --timeout 10 --show-progress

   # Test config integration
   echo "firmware:
     flash:
       wait: true
       timeout: 30
       poll_interval: 1.0" > test_config.yaml
   
   glovebox firmware flash tests_data/28e97485-dab5-4afb-afbc-5de5f1c52c45_v25.05_Glorious\ Engrammer\ v42\ preview\ with\ v41\ QWERTY\ layout.uf2 --config test_config.yaml

   # Test environment variables
   GLOVEBOX_FIRMWARE__FLASH__WAIT=true GLOVEBOX_FIRMWARE__FLASH__TIMEOUT=15 glovebox firmware flash tests_data/28e97485-dab5-4afb-afbc-5de5f1c52c45_v25.05_Glorious\ Engrammer\ v42\ preview\ with\ v41\ QWERTY\ layout.uf2
   ```

2. **Performance validation**:
   ```bash
   # Test with debug logging to verify callback performance
   glovebox --debug firmware flash tests_data/28e97485-dab5-4afb-afbc-5de5f1c52c45_v25.05_Glorious\ Engrammer\ v42\ preview\ with\ v41\ QWERTY\ layout.uf2 --wait --timeout 5
   ```

**Validation Commands**:
```bash
# Final comprehensive validation
ruff format .
ruff check . --fix
mypy glovebox/
pre-commit run --all-files

# Full test suite
pytest tests/ -v

# Integration tests
pytest tests/test_cli/test_command_execution.py -v
pytest tests/test_firmware/ -v
pytest tests/test_config/ -v

# Manual integration test (should show wait behavior)
echo "Testing wait mode with non-existent devices (should timeout gracefully):"
timeout 10 glovebox firmware flash tests_data/28e97485-dab5-4afb-afbc-5de5f1c52c45_v25.05_Glorious\ Engrammer\ v42\ preview\ with\ v41\ QWERTY\ layout.uf2 --wait --timeout 5 --poll-interval 0.5 || echo "Test completed (expected timeout)"
```

**Commit Message**:
```
feat: complete firmware wait mode implementation with full integration

- All wait mode functionality implemented and tested
- Event-driven USB device monitoring with callback system
- Comprehensive user configuration support (CLI, env vars, config files)
- Real-time progress display with device count tracking
- Full backward compatibility maintained
- Performance validated with debug logging
- Documentation complete with usage examples

Features implemented:
- --wait flag for event-driven device detection
- --poll-interval for customizable monitoring frequency  
- --show-progress for real-time feedback control
- User config integration with precedence rules
- Timeout handling with graceful degradation
- Device add/remove event handling
- Query-based device filtering
- Comprehensive test coverage

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

## Code Quality Requirements

Each step MUST include:

1. **Mandatory Linting**: 
   ```bash
   ruff format .
   ruff check . --fix
   mypy glovebox/
   ```

2. **Test Validation**:
   ```bash
   pytest [relevant_test_files] -v
   ```

3. **Pre-commit Checks**:
   ```bash
   pre-commit run --all-files
   ```

4. **Integration Verification**: Manual testing of affected functionality

## Success Criteria

- [ ] All linting passes without warnings
- [ ] All tests pass including new test coverage
- [ ] Backward compatibility maintained
- [ ] User config integration working
- [ ] Real-time device detection functional
- [ ] Documentation complete and accurate
- [ ] Performance acceptable (< 100ms callback response)
- [ ] Clean commit history with descriptive messages

## Risk Mitigation

- **Backup Strategy**: Each step is a separate commit for easy rollback
- **Testing Strategy**: Comprehensive test coverage prevents regressions
- **Monitoring Strategy**: Debug logging validates performance and behavior
- **Rollback Plan**: Individual commits can be reverted without affecting other functionality

This plan ensures systematic implementation with quality gates at each step, following CLAUDE.md conventions strictly.