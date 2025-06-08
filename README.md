# Glovebox

A comprehensive tool for ZMK keyboard firmware management, supporting multiple keyboards with different build chains. Glovebox provides keymap building, firmware compilation, device flashing, and configuration management for ZMK-based keyboards.

## Features

- **Multi-Keyboard Support**: Extensible architecture supporting different keyboard types
- **Keymap Building**: Convert JSON layouts to ZMK keymap and configuration files
- **Firmware Building**: Multiple build chains (Docker-based ZMK, QMK, custom toolchains)
- **Device Flashing**: USB device detection and firmware flashing with retry logic
- **Configuration Management**: Profile-based configuration system with inheritance
- **Layout Visualization**: Display keyboard layouts in terminal
- **Behavior Management**: Keyboard-specific behavior registration and validation

## How It Works

Glovebox transforms keyboard layouts through a multi-stage pipeline:

```
Layout Editor → JSON File → ZMK Files → Firmware → Flash
  (Design)    →  (.json)  → (.keymap + .conf) → (.uf2) → (Keyboard)
```

1. **Design**: Create layouts using the [Glove80 Layout Editor](https://my.glove80.com/#/edit)
2. **Generate**: Convert JSON to ZMK Device Tree Source (`.keymap`) and config (`.conf`) files
3. **Build**: Compile ZMK files into firmware binary (`.uf2`)
4. **Flash**: Transfer firmware to your keyboard via USB

The `.keymap` files use ZMK's Device Tree Source Interface (DTSI) format to define keyboard behavior at the firmware level.

## Supported Keyboards

- **Glove80**: Full support with MoErgo Docker build chain
- **Corne**: Standard ZMK build chain with split keyboard support
- **Planck**: QMK build chain (planned)
- **Extensible**: Architecture designed for easy addition of new keyboards

## Installation

### Requirements

- Python 3.11 or higher
- Docker (required for firmware building)
- **Cross-Platform Device Flashing**:
  - **Linux**: udisksctl (part of udisks2 package)
  - **macOS**: diskutil (built-in)
  - **Windows**: Not yet supported

### Install from PyPI

```bash
pip install glovebox
```

### Install from Source

```bash
git clone https://github.com/your-org/glovebox.git
cd glovebox
pip install -e .
```

### Development Installation

```bash
git clone https://github.com/your-org/glovebox.git
cd glovebox
pip install -e ".[dev]"
pre-commit install
```

## Quick Start

### Build a Keymap

```bash
# Build a keymap with a specific keyboard profile
glovebox keymap generate my_layout.json output/my_keymap --profile glove80/v25.05

# Read from stdin
cat my_layout.json | glovebox keymap generate - output/my_keymap --profile glove80/v25.05

# Force overwrite of existing files
glovebox keymap generate my_layout.json output/my_keymap --profile glove80/v25.05 --force
```

### Build Firmware

```bash
# Build firmware with default settings using profile
glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05

# Build with custom output directory
glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 --output-dir build/glove80

# Using keyboard and firmware separately (legacy approach)
glovebox firmware compile keymap.keymap config.conf --keyboard glove80 --firmware v25.05

# Specify custom branch and repository (overrides profile settings)
glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 --branch dev --repo custom/zmk-fork
```

### Flash Firmware

```bash
# Flash firmware to detected devices with profile
glovebox firmware flash glove80.uf2 --profile glove80/v25.05

# Auto-detect keyboard from filename (legacy approach)
glovebox firmware flash glove80.uf2

# Flash with custom device query
glovebox firmware flash firmware.uf2 --profile glove80/v25.05 --query "vendor=Adafruit and serial~=GLV80-.*"

# Flash multiple devices
glovebox firmware flash firmware.uf2 --profile glove80/v25.05 --count 2

# Flash with longer timeout
glovebox firmware flash firmware.uf2 --profile glove80/v25.05 --timeout 120
```

### System Commands

```bash
# List available profiles
glovebox config list

# Show detailed profile information
glovebox config list --verbose

# Show details of a specific profile
glovebox config show glove80/main

# Show current configuration settings
glovebox config show

# Show configuration with sources
glovebox config show --sources

# Set a configuration value
glovebox config set default_keyboard glove80

# Set a boolean configuration value
glovebox config set debug true

# Set a list configuration value
glovebox config set keyboard_paths /path/to/keyboards,/another/path

# Show system status
glovebox status

# Install shell completion
glovebox --install-completion
```

### User Configuration

Glovebox allows users to customize their experience through a configuration system:

#### Configuration Locations

Configuration is loaded from multiple sources with the following precedence:
1. Environment variables (`GLOVEBOX_LOG_LEVEL`, `GLOVEBOX_DEFAULT_KEYBOARD`, etc.)
2. User configuration file (`~/.config/glovebox/config.yaml`)
3. Local project configuration file (`./.glovebox.yaml`)
4. Default values

#### Available Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `default_keyboard` | string | `"glove80"` | Default keyboard to use when not specified |
| `default_firmware` | string | `"v25.05"` | Default firmware to use when not specified |
| `log_level` | string | `"INFO"` | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `keyboard_paths` | list | `[]` | Additional paths to search for keyboard configurations |

#### Viewing Configuration

View the current configuration settings:

```bash
# Show all configuration settings
glovebox config show

# Show configuration with their sources
glovebox config show --sources
```

#### Setting Configuration

Set configuration values that persist between runs:

```bash
# Set default keyboard
glovebox config set default_keyboard glove80

# Set default firmware version
glovebox config set default_firmware v25.05

# Set logging level
glovebox config set log_level DEBUG

# Set custom keyboard paths (comma-separated)
glovebox config set keyboard_paths ~/custom-keyboards,~/projects/keyboards
```

#### Using Environment Variables

For temporary settings or CI/CD environments, use environment variables:

```bash
# Set temporary configuration
export GLOVEBOX_DEFAULT_KEYBOARD=glove80
export GLOVEBOX_DEFAULT_FIRMWARE=v25.05
export GLOVEBOX_LOG_LEVEL=DEBUG

# Run command with environment configuration
glovebox keymap generate my_layout.json output/
```

## CLI Reference

### Keymap Commands

#### `glovebox keymap generate`

Generate ZMK keymap and config files from a JSON keymap file.

```bash
glovebox keymap generate [OPTIONS] OUTPUT_FILE_PREFIX JSON_FILE
```

**Arguments:**
- `OUTPUT_FILE_PREFIX`: Output directory and base filename (e.g., 'config/my_glove80')
- `JSON_FILE`: Path to keymap JSON file (use '-' or omit for stdin)

**Options:**
- `--profile, -p`: Profile to use (e.g., 'glove80/v25.05')
- `--force`: Overwrite existing files

**Examples:**
```bash
# Using a specific profile (keyboard/firmware)
glovebox keymap generate output/glove80 layout.json --profile glove80/v25.05

# Reading from stdin
cat layout.json | glovebox keymap generate output/glove80 - --profile glove80/v25.05
```

#### `glovebox keymap extract`

Extract layers from a keymap file into individual layer files.

```bash
glovebox keymap extract [OPTIONS] KEYMAP_FILE OUTPUT_DIR
```

**Arguments:**
- `KEYMAP_FILE`: Path to keymap JSON file
- `OUTPUT_DIR`: Directory to save extracted files

**Options:**
- `--force`: Overwrite existing files

Creates structure:
```
output_dir/
├── metadata.json       # Keymap metadata configuration
├── device.dtsi         # Custom device tree (if present)
├── keymap.dtsi         # Custom behaviors (if present)
└── layers/
    ├── DEFAULT.json
    ├── LOWER.json
    └── ...
```

#### `glovebox keymap merge`

Merge layer files into a single keymap file.

```bash
glovebox keymap merge [OPTIONS] INPUT_DIR
```

**Arguments:**
- `INPUT_DIR`: Directory with metadata.json and layers/ subdirectory

**Options:**
- `--output, -o`: Output keymap JSON file path
- `--force`: Overwrite existing files

#### `glovebox keymap show`

Display keymap layout in terminal.

```bash
glovebox keymap show [OPTIONS] JSON_FILE
```

**Arguments:**
- `JSON_FILE`: Path to keyboard layout JSON file

**Options:**
- `--key-width, -w`: Width for displaying each key (default: 10)

#### `glovebox keymap validate`

Validate keymap syntax and structure.

```bash
glovebox keymap validate JSON_FILE
```

**Arguments:**
- `JSON_FILE`: Path to keymap JSON file

### Firmware Commands

#### `glovebox firmware compile`

Compile firmware from keymap and config files.

```bash
glovebox firmware compile [OPTIONS] KEYMAP_FILE KCONFIG_FILE
```

**Arguments:**
- `KEYMAP_FILE`: Path to keymap (.keymap) file
- `KCONFIG_FILE`: Path to kconfig (.conf) file

**Options:**
- `--profile, -p`: Profile to use (e.g., 'glove80/v25.05')
- `--output-dir, -o`: Build output directory (default: build)
- `--keyboard, -k`: Target keyboard (legacy, use --profile instead)
- `--firmware, -f`: Firmware version (legacy, use --profile instead)
- `--branch`: Git branch to use (overrides profile settings)
- `--repo`: Git repository (overrides profile settings)
- `--jobs, -j`: Number of parallel jobs
- `--verbose, -v`: Enable verbose build output

#### `glovebox firmware flash`

Flash firmware to USB devices.

```bash
glovebox firmware flash [OPTIONS] FIRMWARE_FILE
```

**Arguments:**
- `FIRMWARE_FILE`: Path to firmware file (.uf2)

**Options:**
- `--profile, -p`: Profile to use (e.g., 'glove80/v25.05')
- `--query, -q`: Device query string (default: from profile)
- `--timeout`: Device detection timeout in seconds (default: 60)
- `--count, -n`: Number of devices to flash (default: 2, 0 for unlimited)
- `--no-track`: Allow flashing same device multiple times

**Device Query Format:**
```bash
# Match by vendor
--query "vendor=Adafruit"

# Match by serial pattern
--query "serial~=GLV80-.*"

# Combine conditions
--query "vendor=Adafruit and serial~=GLV80-.* and removable=true"

# Available operators: = (exact), != (not equal), ~= (regex)
```

### Config Commands

#### `glovebox config list`

List available keyboard configurations.

```bash
glovebox config list [OPTIONS]
```

**Options:**
- `--verbose, -v`: Show detailed information
- `--format`: Output format (text or json)

#### `glovebox config show`

Show details of a specific keyboard configuration.

```bash
glovebox config show KEYBOARD_NAME
```

**Arguments:**
- `KEYBOARD_NAME`: Keyboard name to show (e.g., 'glove80')

#### `glovebox config firmwares`

List available firmware variants for a keyboard.

```bash
glovebox config firmwares KEYBOARD_NAME
```

**Arguments:**
- `KEYBOARD_NAME`: Keyboard name (e.g., 'glove80')

#### `glovebox config firmware`

Show details of a specific firmware configuration.

```bash
glovebox config firmware KEYBOARD_NAME FIRMWARE_NAME
```

**Arguments:**
- `KEYBOARD_NAME`: Keyboard name (e.g., 'glove80')
- `FIRMWARE_NAME`: Firmware variant name (e.g., 'v25.05')

### Utility Commands

#### Shell Completion

Typer provides built-in shell completion installation.

```bash
# Install completion for current shell
glovebox --install-completion

# Show completion for current shell
glovebox --show-completion
```

#### `glovebox status`

Show system status and diagnostics.

## Configuration

### Typed Configuration System

Glovebox uses a comprehensive type-safe configuration system to support different keyboards, firmware versions, and user preferences:

#### Key Components:

1. **Keyboard Configurations**: YAML files that define keyboard-specific configurations
   - Each keyboard has its own configuration file
   - Configurations include build settings, templates, and firmware options

2. **Firmware Configurations**:
   - Each keyboard configuration can define multiple firmware variants
   - Firmware variants can override keyboard-level settings

3. **User Configuration**:
   - User-specific settings using Pydantic models for validation
   - Multi-source configuration with precedence (environment, global, local)
   - Direct property access with type safety

4. **Keymap Configuration**:
   - Type-safe representation of keymap JSON files
   - Validation and serialization using Pydantic models

5. **Configuration Files**:
   - Stored in a discoverable directory structure
   - Simple hierarchy: keyboard → firmware variants
   - YAML files for keyboard/firmware configurations
   - JSON files for keymaps

6. **Adapter Pattern**:
   - `ConfigFileAdapter`: Generic adapter for config file operations
   - Type-parametrized for different configuration models
   - Unified loading, saving, and validation

7. **Type Safety**:
   - All configuration objects are strongly typed with dataclasses and Pydantic models
   - Better IDE support with autocompletion
   - Early validation of configuration structure

8. **KeyboardProfile**:
   - Unified access to keyboard and firmware configuration
   - Simplifies working with combined settings

9. **Configuration Components**:
   - `get_available_keyboards()`: Lists available keyboard configurations
   - `load_keyboard_config()`: Loads typed configuration for a specific keyboard
   - `create_keyboard_profile()`: Creates a profile for a keyboard and firmware variant
   - `create_config_file_adapter()`: Creates an adapter for a specific config type

#### Usage Examples:

**Keyboard Configuration Loading**:
```python
from glovebox.config.keyboard_config import load_keyboard_config

# Load keyboard configuration as a typed object
keyboard_config = load_keyboard_config("glove80")

# Access properties directly with IDE autocompletion
print(keyboard_config.description)
print(keyboard_config.vendor)
print(keyboard_config.key_count)
```

**Keyboard Profile Usage**:
```python
from glovebox.config.keyboard_config import create_keyboard_profile

# Create a profile for a specific keyboard and firmware
profile = create_keyboard_profile("glove80", "v25.05")

# Access keyboard and firmware properties
print(profile.keyboard_name)
print(profile.firmware_version)

# Access firmware configuration
build_options = profile.firmware_config.build_options
```

**User Configuration**:
```python
from glovebox.config.user_config import create_user_config
from glovebox.models.config import UserConfigData

# Create user configuration
user_config = create_user_config()

# Direct property access with type safety
log_level = user_config.log_level
default_keyboard = user_config.default_keyboard

# Set and save configuration
user_config.set("default_keyboard", "glove80")
user_config.save()
```

**Keymap Configuration**:
```python
from glovebox.services.keymap_service import create_keymap_service
from pathlib import Path

# Create keymap service
keymap_service = create_keymap_service()

# Validate keymap
keymap_valid = keymap_service.validate_file(profile, Path("my_keymap.json"))

# Generate keymap
result = keymap_service.generate_from_file(profile, Path("my_keymap.json"), "output/my_keymap")

# Access generated files
print(f"Keymap file: {result.keymap_path}")
print(f"Config file: {result.conf_path}")
```

**Using the ConfigFileAdapter**:
```python
from glovebox.adapters.config_file_adapter import create_keymap_config_adapter
from glovebox.models.config import KeymapConfigData
from pathlib import Path

# Create typed adapter
config_adapter = create_keymap_config_adapter()

# Load configuration with validation
keymap_config = config_adapter.load_model(Path("my_keymap.json"), KeymapConfigData)

# Save with validation
config_adapter.save_model(Path("output.json"), keymap_config)
```

For detailed information about the typed configuration system, see [Typed Configuration Guide](docs/typed_configuration.md).

**Keyboard Configuration Example**:
```yaml
# keyboards/glove80.yaml
keyboard: glove80
description: MoErgo Glove80 split ergonomic keyboard
vendor: MoErgo

# Flash configuration
flash:
  method: mass_storage
  query: vendor=Adafruit and serial~=GLV80-.* and removable=true
  usb_vid: 0x1209
  usb_pid: 0x0080

# Build configuration
build:
  method: docker
  docker_image: moergo-zmk-build
  repository: moergo-sc/zmk
  branch: v25.05

# Available firmware variants
firmwares:
  v25.05:
    description: Stable MoErgo firmware v25.05
    version: v25.05
    branch: v25.05

  v25.04-beta.1:
    description: Beta MoErgo firmware v25.04-beta.1
    version: v25.04-beta.1
    branch: v25.04-beta.1
```

### Keyboard Support

Glovebox uses this configuration system for each keyboard:

- **Layout Definition**: Physical key arrangement and position mapping
- **Build Chain**: Keyboard-specific build process (Docker images, commands)
- **Behavior Definitions**: Keyboard-specific ZMK behaviors
- **Templates**: Jinja2 templates for generating keymap files

### Adding New Keyboards

To add support for a new keyboard:

1. Create a keyboard configuration YAML file:
```yaml
# keyboards/my_keyboard.yaml
keyboard: my_keyboard
description: My custom 60-key keyboard
vendor: Custom Keyboards
version: v1.0.0

# Flash configuration
flash:
  method: mass_storage
  query: vendor=Custom and removable=true
  usb_vid: 0x1234
  usb_pid: 0x5678

# Build configuration
build:
  method: docker
  docker_image: zmk-build
  repository: zmkfirmware/zmk
  branch: main

# Available firmware variants
firmwares:
  default:
    description: Default ZMK firmware
    version: main
    branch: main

  bluetooth:
    description: Bluetooth-focused firmware
    version: bluetooth
    branch: bluetooth
    kconfig:
      CONFIG_ZMK_BLE: "y"
      CONFIG_ZMK_USB: "n"

# Templates
templates:
  keymap: |
    #include <behaviors.dtsi>
    #include <dt-bindings/zmk/keys.h>
    {{ resolved_includes }}

    / {
      keymap {
        compatible = "zmk,keymap";
        {{ keymap_node }}
      };
    };
```

2. Place templates or reference external templates:
```yaml
# Template references
templates:
  keymap: /path/to/templates/my_keyboard_keymap.j2
  kconfig: /path/to/templates/my_keyboard_kconfig.j2
```

3. Test configuration discovery:
```bash
# List available keyboards
glovebox config list

# Show keyboard configuration
glovebox config show my_keyboard
```

## Development

### Project Structure

```
glovebox/
├── core/                    # Core utilities and errors
├── models/                  # Pydantic data models
├── services/                # Business logic services
├── adapters/                # External system interfaces
├── build/                   # Build system and chains
├── config/                  # Configuration and profiles
├── formatters/              # Output formatting
├── generators/              # Content generation
├── flash/                   # USB device and OS-specific operations
│   ├── os_adapters.py       # Platform-specific implementations
│   ├── flash_operations.py  # High-level flash operations
│   └── usb_monitor.py       # Cross-platform USB monitoring
├── protocols/               # Interface definitions
│   └── flash_os_protocol.py # OS abstraction interface
└── cli.py                   # Command-line interface
```

### Architecture Principles

- **Service Layer**: Business logic with single responsibility
- **Adapter Pattern**: External system interfaces (Docker, USB, File)
- **Profile System**: Keyboard-specific configuration inheritance
- **Build Chains**: Pluggable build system for different toolchains
- **OS Abstraction**: Platform-specific operations isolated and testable

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=glovebox

# Run specific test category
pytest -m unit
pytest -m integration
```

### Code Quality

```bash
# Lint and format
ruff check .
ruff format .

# Type checking (Note: mypy pre-commit hook currently disabled due to ongoing type fixes)
mypy glovebox/services/base_service.py  # Test with a file known to pass type checks

# Pre-commit hooks (recommended)
pre-commit install
pre-commit run --all-files
```

### Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/new-keyboard`
3. Make changes following code conventions
4. Add tests for new functionality
5. Run quality checks: `ruff check . && ruff format . && pytest`
6. Submit pull request

## Troubleshooting

### Common Issues

**Docker not available:**
```bash
# Check Docker installation
docker --version

# Start Docker service (Linux)
sudo systemctl start docker
```

**USB device not detected:**
```bash
# Linux: Check device permissions and groups
ls -la /dev/disk/by-id/
sudo usermod -a -G plugdev,dialout $USER

# macOS: Check device is mountable
diskutil list

# Check if device matches query
glovebox firmware flash --list-devices --profile glove80/v25.05
```

**Build failures:**
```bash
# Check build requirements
glovebox firmware build-info --keyboard glove80

# View detailed build logs
glovebox firmware build keymap.keymap config.conf --keyboard glove80 --verbose
```

**Template not found:**
```bash
# List available profiles
glovebox config list --verbose

# Check profile resolution
glovebox keyboards info glove80
```

### Debug Logging

Enable debug logging for troubleshooting:

```bash
# Enable verbose output (info level)
glovebox -v keymap compile layout.json output

# Enable debug output (very verbose)
glovebox -vv keymap compile layout.json output

# Log to file
glovebox --log-file debug.log keymap compile layout.json output
```

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please read CONTRIBUTING.md for guidelines.

## Support

- Issues: GitHub Issues
- Documentation: docs/
- Examples: examples/
