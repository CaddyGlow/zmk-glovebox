# Glovebox

A comprehensive tool for ZMK keyboard firmware management, supporting multiple keyboards with different build chains. Glovebox provides keymap building, firmware compilation, device flashing, and configuration management for ZMK-based keyboards.

## Features

- **Multi-Keyboard Support**: Extensible architecture supporting different keyboard types
- **Keymap Building**: Convert JSON layouts to ZMK keymap and configuration files
- **Firmware Building**: Docker-based ZMK build chain with extensible architecture
- **Docker Volume Permissions**: Automatic handling of Docker volume permission issues on Linux/macOS
- **Dynamic ZMK Config Generation**: Create complete ZMK config workspaces on-the-fly without external repositories
- **Device Flashing**: USB device detection and firmware flashing with retry logic
- **Configuration Management**: Profile-based configuration system with inheritance
- **Keyboard-Only Profiles**: Minimal configurations for flashing operations without keymap generation
- **Layout Visualization**: Display keyboard layouts in terminal
- **Behavior Management**: Keyboard-specific behavior registration and validation
- **Debug Tracing**: Comprehensive debug logging with stack traces and multiple verbosity levels

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

## Quick Start

### Build a Keymap

```bash
# Build a keymap with a specific keyboard profile
glovebox layout compile my_layout.json output/my_keymap --profile glove80/v25.05

# Read from stdin
cat my_layout.json | glovebox layout compile - output/my_keymap --profile glove80/v25.05

# Force overwrite of existing files
glovebox layout compile my_layout.json output/my_keymap --profile glove80/v25.05 --force
```

### Keyboard-Only Profiles (NEW)

Use minimal keyboard configurations for operations that don't require keymap generation:

```bash
# Check keyboard status using keyboard-only profile  
glovebox status --profile glove80

# Flash pre-built firmware using keyboard-only profile
glovebox firmware flash firmware.uf2 --profile glove80

# List available configurations
glovebox config list --profile glove80

# View keyboard-specific information
glovebox config show --profile glove80
```

**Use Cases:**
- **Flashing Operations**: Flash firmware without needing full keymap configuration
- **Status Checks**: Query keyboard information and USB device detection
- **Minimal Setups**: Simple configurations with only essential keyboard details (no firmware-specific behaviors)

### Build Firmware

```bash
# Build firmware with default settings using profile
glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05

# Build with custom output directory
glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 --output-dir build/glove80

# Using keyboard and firmware separately
glovebox firmware compile keymap.keymap config.conf --keyboard glove80 --firmware v25.05

# Specify custom branch and repository (overrides profile settings)
glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 --branch dev --repo custom/zmk-fork
```

### Docker Volume Permission Handling (NEW)

Glovebox automatically handles Docker volume permission issues that can occur when building firmware on Linux/macOS systems, with comprehensive manual override capabilities:

```bash
# Volume permissions are automatically managed
glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05

# The system automatically:
# - Detects current user ID (UID) and group ID (GID)  
# - Adds --user UID:GID flag to Docker commands
# - Ensures build artifacts have correct host permissions
# - Works transparently across Linux and macOS platforms
```

**Manual Override Options (NEW):**
```bash
# Override UID/GID manually
glovebox firmware compile keymap.keymap config.conf --docker-uid 1001 --docker-gid 1001

# Specify custom username
glovebox firmware compile keymap.keymap config.conf --docker-username myuser

# Custom home directory mapping (host path → container path)
glovebox firmware compile keymap.keymap config.conf \
  --docker-home /custom/host/home --docker-container-home /home/myuser

# Complete manual override
glovebox firmware compile keymap.keymap config.conf \
  --docker-uid 1001 --docker-gid 1001 --docker-username myuser \
  --docker-home /custom/home --docker-container-home /home/myuser

# Disable user mapping entirely
glovebox firmware compile keymap.keymap config.conf --no-docker-user-mapping
```

**Configuration Options:**
```yaml
# In keyboard configurations (keyboards/*.yaml)
build:
  method: generic_docker
  # Docker user mapping configuration
  enable_user_mapping: true         # Enable --user flag (default: true)
  detect_user_automatically: true   # Auto-detect UID/GID (default: true)
  
  # Manual override options (take precedence over auto-detection)
  manual_uid: 1001                  # Manual UID override
  manual_gid: 1001                  # Manual GID override  
  manual_username: myuser           # Manual username override
  host_home_dir: /custom/home       # Host home directory to map
  container_home_dir: /home/myuser  # Container home directory path
  force_manual: true                # Force manual settings, skip auto-detection
```

**User Configuration:**
```yaml
# In user config (~/.config/glovebox/config.yaml)
firmware:
  docker:
    enable_user_mapping: true
    manual_uid: 1001
    manual_gid: 1001
    manual_username: myuser
    host_home_dir: /custom/home
    container_home_dir: /home/myuser
```

**Precedence Rules:**
CLI flags → Keyboard config → User config → Auto-detection

**Key Features:**
- **Automatic Detection**: User context automatically detected on Linux/macOS
- **Manual Overrides**: Complete control over UID/GID/username/home directories
- **Home Directory Mapping**: Map custom host directories into containers
- **Cross-Platform**: Graceful fallback on unsupported platforms (Windows)
- **Precedence Resolution**: CLI takes priority over config files over auto-detection
- **Template Variables**: UID/GID available as `{uid}`, `{gid}`, `{docker_user}` in environment templates
- **Type-Safe**: Full model validation and error handling

**Benefits:**
- **No Permission Errors**: Eliminates `permission denied` errors when accessing build artifacts
- **Flexible Configuration**: Manual overrides for complex Docker setups
- **Seamless Operation**: Works transparently without user intervention in most cases
- **Maintains Security**: Uses least-privilege principle with actual user permissions
- **CI/CD Compatible**: Manual overrides enable consistent builds in automated environments

### Flash Firmware

```bash
# Flash firmware to detected devices with profile
glovebox firmware flash glove80.uf2 --profile glove80/v25.05

# Auto-detect keyboard from filename
glovebox firmware flash glove80.uf2

# Flash with custom device query
glovebox firmware flash firmware.uf2 --profile glove80/v25.05 --query "vendor=Adafruit and serial~=GLV80-.*"

# Flash multiple devices
glovebox firmware flash firmware.uf2 --profile glove80/v25.05 --count 2

# Flash with longer timeout
glovebox firmware flash firmware.uf2 --profile glove80/v25.05 --timeout 120
```

### Dynamic ZMK Config Generation (NEW)

Glovebox can automatically generate complete ZMK config workspaces on-the-fly, eliminating the need for separate ZMK config repositories:

```bash
# Enable dynamic generation by leaving config_repo_url empty in keyboard configuration
# This automatically creates a complete ZMK workspace from your glovebox layout files

# The system automatically:
# - Creates build.yaml with appropriate targets (split keyboard detection)
# - Generates west.yml for ZMK dependency management  
# - Copies and renames keymap/config files to match shield conventions
# - Creates README.md and .gitignore for workspace documentation

# Build firmware using dynamic generation
glovebox firmware compile my_layout.keymap my_config.conf --profile corne/main

# The workspace is created at ~/.glovebox/dynamic-zmk-config/corne/ by default
# All standard ZMK west commands work in the generated workspace:
# cd ~/.glovebox/dynamic-zmk-config/corne/
# west init -l config
# west update
# west build -b nice_nano_v2 -d build/left -- -DSHIELD=corne_left
```

**Benefits:**
- **No external repositories required**: Everything generated from glovebox layout files
- **Automatic split keyboard detection**: Generates left/right targets for Corne, Lily58, Sofle, Kyria
- **Shield naming conventions**: Automatically renames files to match ZMK expectations
- **Full ZMK compatibility**: Generated workspaces work with all standard ZMK workflows

**Supported in keyboard configurations:**
- Set `config_repo_url: ""` to enable dynamic generation
- Configure `workspace_path` for custom workspace location
- All compilation strategies (`zmk_config`, `west`, `cmake`) supported

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
glovebox config set profile glove80/v25.05

# Set a boolean configuration value
glovebox config set firmware.flash.skip_existing true

# Set a list configuration value
glovebox config set keyboard_paths /path/to/keyboards,/another/path

# Show system status
glovebox status

# Install shell completion
glovebox --install-completion
```

## Supported Keyboards

- **Glove80**: Full support with MoErgo Docker build chain
- **Corne**: Standard ZMK build chain with split keyboard support
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

## CLI Reference

### Layout Commands

#### `glovebox layout compile`

Generate ZMK keymap and config files from a JSON keymap file.

```bash
glovebox layout compile [OPTIONS] JSON_FILE OUTPUT_FILE_PREFIX
```

**Arguments:**
- `JSON_FILE`: Path to keymap JSON file (use '-' for stdin)
- `OUTPUT_FILE_PREFIX`: Output directory and base filename (e.g., 'config/my_glove80')

**Options:**
- `--profile, -p`: Profile to use (e.g., 'glove80/v25.05')
- `--force`: Overwrite existing files

**Examples:**
```bash
# Using a specific profile (keyboard/firmware)
glovebox layout compile layout.json output/glove80 --profile glove80/v25.05

# Reading from stdin
cat layout.json | glovebox layout compile - output/glove80 --profile glove80/v25.05
```

#### `glovebox layout decompose`

Extract layers from a keymap file into individual layer files.

```bash
glovebox layout decompose [OPTIONS] KEYMAP_FILE OUTPUT_DIR
```

**Arguments:**
- `KEYMAP_FILE`: Path to keymap JSON file
- `OUTPUT_DIR`: Directory to save extracted files

**Options:**
- `--profile, -p`: Profile to use (e.g., 'glove80/v25.05')
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

#### `glovebox layout compose`

Merge layer files into a single keymap file.

```bash
glovebox layout compose [OPTIONS] INPUT_DIR
```

**Arguments:**
- `INPUT_DIR`: Directory with metadata.json and layers/ subdirectory

**Options:**
- `--output, -o`: Output keymap JSON file path
- `--profile, -p`: Profile to use (e.g., 'glove80/v25.05')
- `--force`: Overwrite existing files

```bash
glovebox layout merge [OPTIONS] INPUT_DIR
```

**Arguments:**
- `INPUT_DIR`: Directory with metadata.json and layers/ subdirectory

**Options:**
- `--output, -o`: Output keymap JSON file path
- `--force`: Overwrite existing files

#### `glovebox layout show`

Display keymap layout in terminal.

```bash
glovebox layout show [OPTIONS] JSON_FILE
```

**Arguments:**
- `JSON_FILE`: Path to keyboard layout JSON file

**Options:**
- `--key-width, -w`: Width for displaying each key (default: 10)

#### `glovebox layout validate`

Validate keymap syntax and structure.

```bash
glovebox layout validate JSON_FILE
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
- `--keyboard, -k`: Target keyboard (use --profile for combined config)
- `--firmware, -f`: Firmware version (use --profile for combined config)
- `--branch`: Git branch to use (overrides profile settings)
- `--repo`: Git repository (overrides profile settings)
- `--jobs, -j`: Number of parallel jobs
- `--verbose, -v`: Enable verbose build output

**Docker User Context Override Options (NEW):**
- `--docker-uid`: Manual Docker UID override (takes precedence over auto-detection and config)
- `--docker-gid`: Manual Docker GID override (takes precedence over auto-detection and config)
- `--docker-username`: Manual Docker username override (takes precedence over auto-detection and config)
- `--docker-home`: Custom Docker home directory override (host path to map as container home)
- `--docker-container-home`: Custom container home directory path (default: /tmp)
- `--no-docker-user-mapping`: Disable Docker user mapping entirely

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
   - **Optional Sections**: Supports keyboards with optional `keymap` and `firmwares` sections

9. **Configuration Components**:
   - `get_available_keyboards()`: Lists available keyboard configurations
   - `load_keyboard_config()`: Loads typed configuration for a specific keyboard
   - `create_keyboard_profile()`: Creates a profile for a keyboard and firmware variant
   - `create_config_file_adapter()`: Creates an adapter for a specific config type

#### Usage Examples:

**Keyboard Configuration Loading**:
```python
from glovebox.config.keyboard_profile import load_keyboard_config

# Load keyboard configuration as a typed object
keyboard_config = load_keyboard_config("glove80")

# Access properties directly with IDE autocompletion
print(keyboard_config.description)
print(keyboard_config.vendor)
print(keyboard_config.key_count)
```

**Keyboard Profile Usage**:
```python
from glovebox.config.keyboard_profile import create_keyboard_profile

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
log_level = user_config._config.log_level
profile = user_config._config.profile

# Set and save configuration
user_config.set("profile", "glove80/v25.05")
user_config.save()
```

**Layout Service Usage**:
```python
from glovebox.layout import create_layout_service
from glovebox.layout.models import LayoutData
from pathlib import Path

# Create layout service
layout_service = create_layout_service()

# Load and validate layout data
with Path("my_layout.json").open() as f:
    layout_data = LayoutData.model_validate_json(f.read())

# Generate layout files
result = layout_service.generate(profile, layout_data, "output/my_layout")

# Access generated files
print(f"Keymap file: {result.keymap_path}")
print(f"Config file: {result.conf_path}")
```

**Component Service Usage**:
```python
from glovebox.layout import create_layout_component_service
from pathlib import Path

# Create component service
component_service = create_layout_component_service()

# Extract layout into components
result = component_service.extract_components(layout_data, Path("output/components"))

# Merge components back into layout
merged_layout = component_service.combine_components(metadata_layout, Path("output/components/layers"))
```


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

#### Optional Configuration Sections

As of the latest version, keyboard configurations support **optional `keymap` and `firmwares` sections**. This enables:

1. **Minimal Configurations**: Keyboards can be defined with only the core required fields:
   ```yaml
   # keyboards/minimal_keyboard.yaml
   keyboard: minimal_keyboard
   description: Minimal keyboard configuration
   vendor: Custom Keyboards
   key_count: 60
   
   # Required sections
   flash:
     method: mass_storage
     query: vendor=Custom
     usb_vid: 0x1234
     usb_pid: 0x5678
   
   build:
     method: docker
     docker_image: zmk-build
     repository: zmkfirmware/zmk
     branch: main
   
   # keymap and firmwares sections are optional
   ```

2. **Firmware-Only Configurations**: Define firmware variants without keymap templates:
   ```yaml
   keyboard: firmware_only
   # ... other required fields ...
   
   firmwares:
     stable:
       version: v1.0
       description: Stable firmware
       build_options:
         repository: custom/zmk
         branch: stable
   # No keymap section needed
   ```

3. **Keymap-Only Configurations**: Define keymap templates without firmware variants:
   ```yaml
   keyboard: keymap_only
   # ... other required fields ...
   
   keymap:
     includes: ['#include <dt-bindings/zmk/keys.h>']
     formatting:
       default_key_width: 8
       key_gap: '  '
     system_behaviors: []
     kconfig_options: {}
   # No firmwares section needed
   ```

This flexibility allows for more modular configuration management and supports keyboards at different stages of development or with specific use cases.

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
├── models/                  # Shared data models
├── layout/                  # Layout domain (JSON→DTSI conversion, formatting, components)
│   ├── models.py            # Layout-specific data models
│   ├── service.py           # Main layout operations
│   ├── component_service.py # Layer extraction/merging
│   ├── display_service.py   # Layout visualization
│   ├── generator.py         # DTSI generation and formatting
│   ├── behavior_formatter.py # Behavior formatting
│   └── utils.py             # Layout utility functions
├── firmware/                # Firmware domain (build and flash operations)
│   ├── build_service.py     # Firmware compilation using Docker
│   └── flash/               # Flash subdomain (USB devices, firmware flashing)
│       ├── models.py        # Flash-specific data models
│       ├── service.py       # Main flash operations
│       ├── os_adapters.py   # Platform-specific implementations
│       ├── flash_operations.py # High-level flash operations
│       └── usb_monitor.py   # Cross-platform USB monitoring
├── services/                # Cross-domain services
│   ├── base_service.py      # Service base patterns
│   └── behavior_service.py  # Behavior registry
├── adapters/                # External system interfaces
├── config/                  # Configuration and profiles
├── protocols/               # Interface definitions
└── cli/                     # Command-line interface
```

### Architecture Principles

- **Domain-Driven Design**: Business logic organized by domains (layout, firmware)
- **Service Layer**: Domain services with single responsibility
- **Hierarchical Organization**: Firmware domain contains flash subdomain
- **Adapter Pattern**: External system interfaces (Docker, USB, File, Template, Config)
- **Profile System**: Type-safe profiles combining keyboard + firmware configs
- **Factory Functions**: Consistent creation patterns for services and components
- **Protocol-Based Interfaces**: Type-safe abstractions with runtime checking
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

### Debug Logging and Troubleshooting

Glovebox provides comprehensive debug tracing with automatic stack traces and multiple verbosity levels:

```bash
# Verbose flag hierarchy (with precedence: --debug > -vv > -v > config > default)
glovebox --debug [command]     # DEBUG level + stack traces (highest priority)
glovebox -vv [command]         # DEBUG level + stack traces  
glovebox -v [command]          # INFO level + stack traces
glovebox [command]             # User config or WARNING level (clean output)

# Examples with common commands
glovebox --debug status                                    # Debug keyboard detection
glovebox -vv layout compile layout.json output/           # Debug layout generation
glovebox -v firmware compile keymap.keymap config.conf    # Info level firmware build

# Log to file for persistent debugging
glovebox --debug --log-file debug.log firmware compile keymap.keymap config.conf

# Combine with profile for full context
glovebox --debug layout compile layout.json output/ --profile glove80/v25.05
```

**Key Features:**
- **Automatic Stack Traces**: All verbose flags (`-v`, `-vv`, `--debug`) show stack traces on errors
- **Clean Error Messages**: No verbose flags = user-friendly error messages only
- **Flag Precedence**: `--debug` > `-vv` > `-v` > user config > WARNING (default)
- **File Logging**: Persist debug information with `--log-file`

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please read CONTRIBUTING.md for guidelines.

## Support

- Issues: GitHub Issues
- Documentation: docs/
- Examples: examples/
