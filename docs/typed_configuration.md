# Typed Configuration System

Glovebox has been upgraded with a fully typed configuration system that provides better IDE support, validation, and a more robust programming model.

## Key Features

- **Type Safety**: All configuration objects are now strongly typed with Python dataclasses
- **IDE Autocompletion**: Get property suggestions as you type
- **Validation**: Configuration errors are caught earlier
- **Profiles**: New KeyboardProfile class for accessing configurations
- **API Simplification**: More intuitive access to nested properties

## Using the Typed API

### Loading Configuration

```python
from glovebox.config.keyboard_config import (
    load_keyboard_config_typed,
    create_keyboard_profile,
)

# Load keyboard configuration as a typed object
keyboard_config = load_keyboard_config_typed("glove80")

# Access typed properties
print(keyboard_config.description)
print(keyboard_config.vendor)
print(keyboard_config.key_count)

# Access nested objects with proper typing
flash_config = keyboard_config.flash
print(flash_config.method)
print(flash_config.query)

# Access firmwares
for name, firmware in keyboard_config.firmwares.items():
    print(f"{name}: {firmware.version} - {firmware.description}")
```

### Using Keyboard Profiles

The new `KeyboardProfile` class provides a high-level API for accessing combined keyboard and firmware configuration:

```python
# Create a profile for a specific keyboard and firmware
profile = create_keyboard_profile("glove80", "v25.05")

# Access keyboard and firmware properties
print(profile.keyboard_name)
print(profile.firmware_version)

# Access nested configuration
print(profile.keyboard_config.description)
print(profile.firmware_config.version)

# Access templates
template = profile.get_template("keymap")

# Access combined kconfig options
kconfig_options = profile.kconfig_options

# Resolve behavior includes
includes = profile.resolve_includes(["&kp", "&bt"])
```

## CLI Integration

The CLI has been updated to use the new typed configuration system with the KeyboardProfile pattern. All major commands now support profile-based operation:

```bash
# List keyboards
glovebox config list

# Show keyboard details
glovebox config show glove80

# List firmware variants
glovebox config firmwares glove80

# Show firmware details
glovebox config firmware glove80 v25.05

# Compile keymap using profile
glovebox keymap compile my_layout.json output/my_keymap --profile glove80/v25.05

# Show keymap with profile-based layout
glovebox keymap show my_layout.json --profile glove80/v25.05 --view-mode normal

# Build firmware with explicit profile
glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05

# Build firmware with keyboard and firmware specified separately
glovebox firmware compile keymap.keymap config.conf --keyboard glove80 --firmware v25.05

# Flash firmware using profile-specific device detection
glovebox firmware flash firmware.uf2 --profile glove80/v25.05
```

### CLI Integration Pattern

All CLI commands that use keyboard configurations now follow a consistent pattern:

1. **Profile Parameter**: A `--profile` option that accepts formats like:
   - `keyboard_name` (uses default firmware)
   - `keyboard_name/firmware_version` (uses specific firmware)

2. **Creation of KeyboardProfile**:
   - CLI parses the profile parameter
   - Creates a KeyboardProfile using the keyboard and firmware names
   - Passes the KeyboardProfile to the appropriate service

3. **Error Handling**:
   - Shows available keyboards if keyboard name is invalid
   - Shows available firmware versions if firmware version is invalid
   - Provides helpful error messages with alternatives

4. **Backward Compatibility**:
   - Commands still work with legacy parameters like `--keyboard`
   - For some commands, explicit keyboard + firmware version parameters work too
   - The profile parameter takes precedence over separate parameters

## Service Integration

All services in Glovebox should follow a consistent pattern for using the KeyboardProfile:

```python
# Service constructor with dependency injection
def __init__(
    self,
    adapter1: Optional[SomeAdapter] = None,
    adapter2: Optional[AnotherAdapter] = None,
):
    self.adapter1 = adapter1 or create_some_adapter()
    self.adapter2 = adapter2 or create_another_adapter()

# Method with profile parameter
def some_operation(
    self,
    input_data: dict[str, Any],
    profile: Optional[KeyboardProfile] = None,
    keyboard_name: Optional[str] = None,
    firmware_version: Optional[str] = None,
) -> Result:
    """Perform some operation using a keyboard profile.

    Args:
        input_data: Input data for the operation
        profile: Keyboard profile to use (preferred)
        keyboard_name: Name of keyboard (used to create profile if not provided)
        firmware_version: Firmware version (used with keyboard_name if profile not provided)
    """
    # Create profile if not provided
    if not profile and keyboard_name:
        try:
            profile = create_keyboard_profile(
                keyboard_name,
                firmware_version or get_default_firmware(keyboard_name)
            )
        except Exception as e:
            return Result(success=False, errors=[f"Failed to create profile: {e}"])

    # Ensure we have a profile
    if not profile:
        return Result(success=False, errors=["Profile or keyboard name required"])

    # Use profile for the operation
    # ...
```

This pattern ensures consistent behavior across all services and provides a clean migration path from the old API.

## Data Model

The configuration system uses these primary dataclasses:

- `KeyboardConfig`: Complete keyboard configuration
- `FlashConfig`: USB flashing configuration
- `BuildConfig`: Firmware build configuration
- `FirmwareConfig`: Firmware-specific settings
- `FormattingConfig`: Layout display formatting
- `VisualLayout`: Visual representation of keys with rows configuration
- `SystemBehavior`: ZMK behavior definition
- `KeymapSection`: Keymap-specific settings including formatting

And the profile class:

- `KeyboardProfile`: Combined keyboard and firmware profile

## Migrating from the Old API

If you're using the old dictionary-based API, here's how to migrate:

### Old API (Dictionary-based):

**Important Note:** The previous `load_keyboard_config` function has been renamed to `load_keyboard_config_raw` to better reflect its purpose. All existing code should be updated to use the new name.

```python
from glovebox.config.keyboard_config import load_keyboard_config_raw

# Load keyboard configuration
keyboard_config = load_keyboard_config_raw("glove80")

# Access properties via dictionary
description = keyboard_config.get("description", "")
vendor = keyboard_config.get("vendor", "")

# Access nested objects
flash_config = keyboard_config.get("flash", {})
flash_method = flash_config.get("method", "")

# Access firmwares
firmwares = keyboard_config.get("firmwares", {})
for name, firmware in firmwares.items():
    version = firmware.get("version", "")
    description = firmware.get("description", "")
```

### New API (Typed):

```python
from glovebox.config.keyboard_config import (
    load_keyboard_config_typed,
    create_keyboard_profile,
)

# Load keyboard configuration as a typed object
keyboard_config = load_keyboard_config_typed("glove80")

# Access properties directly
description = keyboard_config.description
vendor = keyboard_config.vendor

# Access nested objects with proper typing
flash_config = keyboard_config.flash
flash_method = flash_config.method

# Access firmwares
for name, firmware in keyboard_config.firmwares.items():
    version = firmware.version
    description = firmware.description

# Or use a profile for combined access
profile = create_keyboard_profile("glove80", "v25.05")
```

## Backward Compatibility

For backward compatibility, you can use `load_keyboard_config_raw` to get the raw dictionary representation:

```python
from glovebox.config.keyboard_config import load_keyboard_config_raw

# Load keyboard configuration as a raw dictionary
keyboard_config = load_keyboard_config_raw("glove80")
```

## Recent Changes

### KeyboardProfile Service Integration

All services have been updated to use the KeyboardProfile pattern:

1. **FlashService**: Accepts a KeyboardProfile for flash operations
2. **DisplayService**: Uses KeyboardProfile for keymap display
3. **BuildService**: Refactored to use KeyboardProfile for firmware building
4. **KeymapService**: Uses KeyboardProfile for keymap compilation

Benefits of this change:
- More consistent API across services
- Better separation of concerns
- Improved testability with dependency injection
- More type safety with proper models

### CLI Integration Updates

All CLI commands have been updated to use the KeyboardProfile pattern:

1. **keymap compile**: Now accepts `--profile` option for KeyboardProfile
2. **keymap show**: Enhanced with profile-based layout rendering
3. **firmware compile**: Supports both `--profile` and separate `--keyboard`/`--firmware` options
4. **firmware flash**: Uses KeyboardProfile to determine correct device query patterns

These changes ensure a consistent user experience while maintaining backward compatibility. The profile-based approach allows for firmware-specific flash configurations, including custom device query patterns based on keyboard type.

### Configuration Structure Updates

The keyboard configuration structure has been updated to better match the YAML files:

1. Removed the top-level `visual_layout` and `formatting` fields
2. Moved the `formatting` field into the `keymap` section
3. Updated the `VisualLayout` class to include the `rows` field
4. Updated schema validation to match these changes

This better aligns with the actual structure of the YAML files and improves code organization.

### Function Rename

The function `load_keyboard_config` has been renamed to `load_keyboard_config_raw` to better reflect its purpose and differentiate it from the typed version. This change affects:

- CLI commands (cli.py, cli_config.py)
- Service modules that load keyboard configurations
- Tests that mock or use the keyboard configuration loading

If you encounter import errors related to `load_keyboard_config`, update your imports and function calls to use `load_keyboard_config_raw` instead.

### Helper Functions

New helper functions have been added to support the KeyboardProfile pattern:

- `create_profile_from_keyboard_name(keyboard_name)`: Creates a profile with default firmware
- `get_default_firmware(keyboard_name)`: Gets the default firmware version for a keyboard

### Ongoing Test Updates

We are in the process of updating all tests to use the new function names and KeyboardProfile pattern. If you're working on tests, make sure to:

1. Use `@patch("glovebox.config.keyboard_config.load_keyboard_config_raw")` instead of the old name
2. Update any direct imports to use the new function name
3. Create mock KeyboardProfile objects for testing services
4. Consider migrating to typed configurations where appropriate