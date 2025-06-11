# Glovebox

A comprehensive tool for ZMK keyboard firmware management, supporting multiple keyboards with different build chains. Glovebox provides keymap building, firmware compilation, device flashing, and configuration management for ZMK-based keyboards.

## Features

- **Multi-Keyboard Support**: Extensible architecture supporting different keyboard types
- **Keymap Building**: Convert JSON layouts to ZMK keymap and configuration files
- **Firmware Building**: Docker-based ZMK build chain with extensible architecture
- **Dynamic ZMK Config Generation**: Create complete ZMK config workspaces on-the-fly without external repositories
- **Device Flashing**: USB device detection and firmware flashing with retry logic
- **Configuration Management**: Profile-based configuration system with inheritance
- **Keyboard-Only Profiles**: Minimal configurations for flashing operations without keymap generation
- **Layout Visualization**: Display keyboard layouts in terminal
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

### Installation

#### Requirements
- Python 3.11 or higher
- Docker (required for firmware building)
- **Cross-Platform Device Flashing**:
  - **Linux**: udisksctl (part of udisks2 package)
  - **macOS**: diskutil (built-in)
  - **Windows**: Not yet supported

#### Install from PyPI
```bash
pip install glovebox
```

#### Install from Source
```bash
git clone https://github.com/your-org/glovebox.git
cd glovebox
pip install -e .
```

### Basic Usage

#### Build a Keymap
```bash
# Build a keymap with a specific keyboard profile
glovebox layout compile my_layout.json output/my_keymap --profile glove80/v25.05

# Read from stdin
cat my_layout.json | glovebox layout compile - output/my_keymap --profile glove80/v25.05

# Force overwrite of existing files
glovebox layout compile my_layout.json output/my_keymap --profile glove80/v25.05 --force
```

#### Build Firmware
```bash
# Build firmware with default settings using profile
glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05

# Build with custom output directory
glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 --output-dir build/glove80

# Specify custom branch and repository (overrides profile settings)
glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 --branch dev --repo custom/zmk-fork
```

#### Flash Firmware
```bash
# Flash firmware to detected devices with profile
glovebox firmware flash glove80.uf2 --profile glove80/v25.05

# Auto-detect keyboard from filename
glovebox firmware flash glove80.uf2

# Flash with custom device query
glovebox firmware flash firmware.uf2 --profile glove80/v25.05 --query "vendor=Adafruit and serial~=GLV80-.*"

# Flash multiple devices
glovebox firmware flash firmware.uf2 --profile glove80/v25.05 --count 2
```

## Supported Keyboards

- **Glove80**: Full support with MoErgo Docker build chain
- **Corne**: Standard ZMK build chain with split keyboard support
- **Extensible**: Architecture designed for easy addition of new keyboards

## Advanced Features

### Keyboard-Only Profiles

Use minimal keyboard configurations for operations that don't require keymap generation:

```bash
# Check keyboard status using keyboard-only profile  
glovebox status --profile glove80

# Flash pre-built firmware using keyboard-only profile
glovebox firmware flash firmware.uf2 --profile glove80

# List available configurations
glovebox config list --profile glove80
```

**Use Cases:**
- **Flashing Operations**: Flash firmware without needing full keymap configuration
- **Status Checks**: Query keyboard information and USB device detection
- **Minimal Setups**: Simple configurations with only essential keyboard details

### Dynamic ZMK Config Generation

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
```

**Benefits:**
- **No external repositories required**: Everything generated from glovebox layout files
- **Automatic split keyboard detection**: Generates left/right targets for Corne, Lily58, Sofle, Kyria
- **Shield naming conventions**: Automatically renames files to match ZMK expectations
- **Full ZMK compatibility**: Generated workspaces work with all standard ZMK workflows

### Docker Volume Permission Handling

Glovebox automatically handles Docker volume permission issues that can occur when building firmware on Linux/macOS systems:

```bash
# Volume permissions are automatically managed
glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05

# The system automatically:
# - Detects current user ID (UID) and group ID (GID)  
# - Adds --user UID:GID flag to Docker commands
# - Ensures build artifacts have correct host permissions
# - Works transparently across Linux and macOS platforms
```

**Manual Override Options:**
```bash
# Override UID/GID manually
glovebox firmware compile keymap.keymap config.conf --docker-uid 1001 --docker-gid 1001

# Specify custom username
glovebox firmware compile keymap.keymap config.conf --docker-username myuser

# Complete manual override
glovebox firmware compile keymap.keymap config.conf \
  --docker-uid 1001 --docker-gid 1001 --docker-username myuser \
  --docker-home /custom/home --docker-container-home /home/myuser

# Disable user mapping entirely
glovebox firmware compile keymap.keymap config.conf --no-docker-user-mapping
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

#### `glovebox layout decompose`
Extract layers from a keymap file into individual layer files.

```bash
glovebox layout decompose [OPTIONS] KEYMAP_FILE OUTPUT_DIR
```

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

**Options:**
- `--output, -o`: Output keymap JSON file path
- `--force`: Overwrite existing files

#### `glovebox layout show`
Display keymap layout in terminal.

```bash
glovebox layout show [OPTIONS] JSON_FILE
```

**Options:**
- `--key-width, -w`: Width for displaying each key (default: 10)

### Firmware Commands

#### `glovebox firmware compile`
Compile firmware from keymap and config files.

```bash
glovebox firmware compile [OPTIONS] KEYMAP_FILE KCONFIG_FILE
```

**Options:**
- `--profile, -p`: Profile to use (e.g., 'glove80/v25.05')
- `--output-dir, -o`: Build output directory (default: build)
- `--branch`: Git branch to use (overrides profile settings)
- `--repo`: Git repository (overrides profile settings)
- `--jobs, -j`: Number of parallel jobs
- `--verbose, -v`: Enable verbose build output

**Docker User Context Override Options:**
- `--docker-uid`: Manual Docker UID override
- `--docker-gid`: Manual Docker GID override
- `--docker-username`: Manual Docker username override
- `--docker-home`: Custom Docker home directory override
- `--docker-container-home`: Custom container home directory path
- `--no-docker-user-mapping`: Disable Docker user mapping entirely

#### `glovebox firmware flash`
Flash firmware to USB devices.

```bash
glovebox firmware flash [OPTIONS] FIRMWARE_FILE
```

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

### Configuration Commands

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

#### `glovebox status`
Show system status and diagnostics.

```bash
glovebox status [OPTIONS]
```

**Options:**
- `--profile, -p`: Profile to use for keyboard-specific checks

### Shell Completion

```bash
# Install completion for current shell
glovebox --install-completion

# Show completion for current shell
glovebox --show-completion
```

## Configuration

### Configuration System

Glovebox uses a comprehensive type-safe configuration system:

1. **Keyboard Configurations**: YAML files that define keyboard-specific configurations
2. **Firmware Configurations**: Multiple firmware variants per keyboard
3. **User Configuration**: User-specific settings with multi-source precedence
4. **KeyboardProfile**: Unified access to keyboard and firmware configuration

### Example Keyboard Configuration

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
```

### Adding New Keyboards

To add support for a new keyboard:

1. Create a keyboard configuration YAML file in `keyboards/`
2. Define flash configuration, build settings, and firmware variants
3. Test configuration discovery with `glovebox config list`

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

### Debug Logging

Glovebox provides comprehensive debug tracing with automatic stack traces:

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
```

**Key Features:**
- **Automatic Stack Traces**: All verbose flags (`-v`, `-vv`, `--debug`) show stack traces on errors
- **Clean Error Messages**: No verbose flags = user-friendly error messages only
- **Flag Precedence**: `--debug` > `-vv` > `-v` > user config > WARNING (default)
- **File Logging**: Persist debug information with `--log-file`

## Development

### Development Installation

```bash
git clone https://github.com/your-org/glovebox.git
cd glovebox
pip install -e ".[dev]"
pre-commit install
```

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

# Type checking
mypy glovebox/

# Pre-commit hooks (recommended)
pre-commit install
pre-commit run --all-files
```

## Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/new-keyboard`
3. Make changes following code conventions
4. Add tests for new functionality
5. Run quality checks: `ruff check . && ruff format . && pytest`
6. Submit pull request

## License

MIT License - see LICENSE file for details.

## Support

- Issues: GitHub Issues
- Documentation: docs/
- Examples: examples/