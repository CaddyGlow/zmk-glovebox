# Glovebox

A comprehensive tool for ZMK keyboard firmware management, supporting multiple keyboards with different build chains. Glovebox provides keymap building, firmware compilation, device flashing, and configuration management for ZMK-based keyboards.

## Features

- **Multi-Keyboard Support**: Extensible modular architecture with YAML-based configuration system
- **Keymap Building**: Convert JSON layouts to ZMK keymap and configuration files
- **Keymap Version Management**: Upgrade custom layouts while preserving customizations when new master versions are released
- **Advanced Compilation Strategies**: Multiple compilation methods (zmk_config, west, cmake, make, ninja, custom)
- **Dynamic ZMK Config Generation**: Create complete ZMK config workspaces on-the-fly without external repositories
- **Intelligent Caching System**: Domain-agnostic caching with filesystem and memory backends
- **Device Flashing**: Cross-platform USB device detection and firmware flashing with retry logic
- **Modular Configuration System**: YAML-based configuration with includes and inheritance
- **Keyboard-Only Profiles**: Minimal configurations for flashing operations without keymap generation
- **Layout Visualization**: Display keyboard layouts in terminal with customizable formatting
- **Build Matrix Support**: GitHub Actions style build matrices with automatic split keyboard detection
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

#### Keymap Version Management (NEW)
```bash
# Import master layout versions for upgrades
glovebox layout import-master ~/Downloads/glorious-v42.json v42

# Upgrade your custom layout preserving all customizations  
glovebox layout upgrade my-custom-v41.json --to-master v42

# Compare layouts to see what changed
glovebox layout diff layout-v41.json layout-v42.json

# List available master versions
glovebox layout list-masters glove80
```

**Perfect for:**
- Keeping custom layouts updated with new master releases
- Preserving your personal customizations (layers, behaviors, config)
- Zero-downtime upgrades with automatic rollback capability
- Tracking firmware builds and maintaining version history

## Supported Keyboards

- **Glove80**: Full support with MoErgo Nix toolchain and modular configuration
- **Corne**: Standard ZMK build chain with split keyboard support and dynamic generation
- **Extensible**: Modular YAML-based architecture designed for easy addition of new keyboards

### Configuration System

Keyboards are now configured using a modular YAML system:

```yaml
# keyboards/my_keyboard.yaml
includes:
  - "my_keyboard/main.yaml"

# keyboards/my_keyboard/main.yaml
keyboard: "my_keyboard"
description: "My Custom Keyboard"
includes:
  - "hardware.yaml"     # Hardware specifications
  - "firmwares.yaml"    # Firmware variants
  - "strategies.yaml"   # Compilation strategies
  - "behaviors.yaml"    # Behavior definitions
```

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

### Advanced Compilation System

Glovebox provides multiple compilation strategies with intelligent caching:

#### Direct Strategy Selection

```bash
# Use specific compilation strategy via CLI
glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 --strategy zmk_config
glovebox firmware compile keymap.keymap config.conf --profile corne/main --strategy west
```

**Available Strategies:**
- **zmk_config**: GitHub Actions style builds with dynamic workspace generation
- **west**: Traditional west workspace builds
- **cmake**: Direct CMake builds
- **make**: Makefile-based builds
- **ninja**: Ninja build system
- **custom**: User-defined build commands

#### Dynamic ZMK Config Generation

```bash
# Enable dynamic generation by using zmk_config strategy
# This automatically creates a complete ZMK workspace from your glovebox layout files

# The system automatically:
# - Creates build.yaml with appropriate targets (split keyboard detection)
# - Generates west.yml for ZMK dependency management  
# - Copies and renames keymap/config files to match shield conventions
# - Creates README.md and .gitignore for workspace documentation

# Build firmware using dynamic generation
glovebox firmware compile my_layout.keymap my_config.conf --profile corne/main --strategy zmk_config

# The workspace is created at ~/.glovebox/cache/workspaces/corne/ by default
```

**Benefits:**
- **No external repositories required**: Everything generated from glovebox layout files
- **Automatic split keyboard detection**: Generates left/right targets for Corne, Lily58, Sofle, Kyria
- **Shield naming conventions**: Automatically renames files to match ZMK expectations
- **Full ZMK compatibility**: Generated workspaces work with all standard ZMK workflows
- **Intelligent Caching**: Multi-tier caching system dramatically reduces compilation times by reusing shared ZMK dependencies
- **Build Matrix Support**: GitHub Actions style build matrices with parallel compilation

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

#### Modular Configuration Structure

```yaml
# keyboards/glove80.yaml (main entry point)
includes:
  - "glove80/main.yaml"

# keyboards/glove80/main.yaml
keyboard: "glove80"
description: "MoErgo Glove80 split ergonomic keyboard"
vendor: "MoErgo"
key_count: 80

includes:
  - "hardware.yaml"     # Hardware specifications
  - "firmwares.yaml"    # Firmware variants
  - "strategies.yaml"   # Compilation strategies
  - "kconfig.yaml"      # Kconfig options
  - "behaviors.yaml"    # Behavior definitions

# keyboards/glove80/strategies.yaml
compile_methods:
  - type: "moergo"
    image: "glove80-zmk-config-docker"
    repository: "moergo-sc/zmk"
    branch: "v25.05"
    build_matrix:
      board: ["glove80_lh", "glove80_rh"]
    docker_user:
      enable_user_mapping: false

# keyboards/glove80/firmwares.yaml
firmwares:
  v25.05:
    description: "Stable MoErgo firmware v25.05"
    version: "v25.05"
    branch: "v25.05"
```

### Adding New Keyboards

To add support for a new keyboard:

1. **Create modular configuration structure:**
   ```bash
   keyboards/
   ├── my_keyboard.yaml        # Main entry point
   └── my_keyboard/
       ├── main.yaml           # Core configuration
       ├── hardware.yaml       # Hardware specs
       ├── firmwares.yaml      # Firmware variants
       ├── strategies.yaml     # Compilation methods
       ├── kconfig.yaml        # Kconfig options
       └── behaviors.yaml      # Behavior definitions
   ```

2. **Define compilation strategies and flash configuration**
3. **Add firmware variants for different builds**
4. **Test configuration discovery with `glovebox config list`**
5. **Test compilation with `glovebox firmware compile --profile my_keyboard/firmware_version`**

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

# Using uv (recommended)
uv sync
pre-commit install

# Or using pip
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
# Using make (recommended)
make lint          # Run linting checks
make format        # Format code and fix issues
make test          # Run all tests
make coverage      # Run tests with coverage

# Manual commands
ruff check . --fix  # Lint and fix
ruff format .       # Format code
mypy glovebox/      # Type checking

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