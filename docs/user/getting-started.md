# Getting Started with Glovebox

This guide will help you install Glovebox, configure your first keyboard profile, and build your first firmware.

## Installation

### Prerequisites

Before installing Glovebox, ensure you have:

- **Python 3.11 or higher**
- **Docker** (required for firmware building)
- **Platform-specific tools**:
  - **Linux**: `udisksctl` (usually pre-installed)
  - **macOS**: `diskutil` (built-in)
  - **Windows**: Not yet supported for flashing

### Install Glovebox

#### From PyPI (Recommended)
```bash
pip install glovebox
```

#### From Source
```bash
git clone https://github.com/your-org/glovebox.git
cd glovebox
pip install -e .
```

### Verify Installation

```bash
# Check Glovebox is installed
glovebox --version

# Check Docker is available
docker --version

# Check system status
glovebox status
```

## Understanding Profiles

Glovebox uses **profiles** to combine keyboard and firmware configurations:

- **Full Profile**: `keyboard/firmware` (e.g., `glove80/v25.05`)
- **Keyboard-Only Profile**: `keyboard` (e.g., `glove80`)

```bash
# List available keyboards and firmwares
glovebox config list

# Show keyboard details
glovebox config show glove80

# Show firmware variants
glovebox config firmwares glove80
```

## Your First Build

### Step 1: Get a Layout File

You can get a layout file from:
1. **Glove80 Layout Editor**: Download JSON from [my.glove80.com](https://my.glove80.com/#/edit)
2. **Sample layouts**: Use examples from the repository
3. **Create manually**: Write your own JSON layout

For this example, we'll create a simple layout:

```json
{
  "metadata": {
    "name": "My First Layout",
    "description": "A simple test layout"
  },
  "layers": [
    {
      "name": "DEFAULT",
      "bindings": [
        {"key": 0, "binding": "&kp ESC"},
        {"key": 1, "binding": "&kp Q"},
        {"key": 2, "binding": "&kp W"},
        {"key": 3, "binding": "&kp E"},
        {"key": 4, "binding": "&kp R"}
      ]
    }
  ],
  "behaviors": {
    "macros": [],
    "hold_taps": [],
    "combos": []
  },
  "config": []
}
```

Save this as `my_first_layout.json`.

### Step 2: Generate ZMK Files

Convert your JSON layout to ZMK files:

```bash
# Generate keymap and config files
glovebox layout compile my_first_layout.json output/my_first --profile glove80/v25.05

# Check generated files
ls -la output/
# Should show: my_first.keymap, my_first.conf, my_first.json
```

### Step 3: Build Firmware

Compile the ZMK files into firmware:

```bash
# Build firmware using Docker
glovebox firmware compile output/my_first.keymap output/my_first.conf --profile glove80/v25.05

# Check build output
ls -la build/
# Should show firmware files (.uf2)
```

### Step 4: Flash Firmware

Flash the firmware to your keyboard:

```bash
# Put your keyboard in bootloader mode, then:
glovebox firmware flash build/glove80.uf2 --profile glove80/v25.05

# For keyboards with left/right halves:
# Flash each half separately when they appear in bootloader mode
```

## Working with Components

For complex layouts, you can work with individual components:

### Extract Components
```bash
# Split layout into manageable pieces
glovebox layout decompose my_complex_layout.json components/

# This creates:
# components/
# ├── metadata.json
# ├── device.dtsi (if custom device tree)
# ├── keymap.dtsi (if custom behaviors)
# └── layers/
#     ├── DEFAULT.json
#     ├── LOWER.json
#     └── RAISE.json
```

### Edit Individual Layers
```bash
# Edit individual layer files
nano components/layers/DEFAULT.json
nano components/layers/LOWER.json
```

### Merge Components
```bash
# Combine edited components back into a complete layout
glovebox layout compose components/ --output modified_layout.json

# Generate ZMK files from modified layout
glovebox layout compile modified_layout.json output/modified --profile glove80/v25.05
```

## Configuration

### User Configuration

Set up your personal preferences:

```bash
# Set default profile
glovebox config set profile glove80/v25.05

# Set default output directory
glovebox config set output_dir ~/keyboard_builds

# Enable verbose logging
glovebox config set log_level INFO

# Show current configuration
glovebox config show
```

### Configuration File

Glovebox uses `~/.config/glovebox/config.yaml`:

```yaml
# Default profile
profile: glove80/v25.05

# Logging
log_level: INFO
log_file: ~/.local/share/glovebox/debug.log

# Firmware settings
firmware:
  flash:
    timeout: 120
    skip_existing: false
  docker:
    enable_user_mapping: true

# Custom keyboard paths
keyboard_paths:
  - ~/my_keyboards
```

## Debug and Troubleshooting

### Debug Logging

Use verbose flags to diagnose issues:

```bash
# Debug levels (most to least verbose)
glovebox --debug layout compile layout.json output/  # Full debug
glovebox -vv firmware compile keymap.keymap config.conf  # Debug + stack traces
glovebox -v firmware flash firmware.uf2  # Info + stack traces

# Log to file
glovebox --debug --log-file debug.log firmware compile keymap.keymap config.conf
```

### Common Issues

**Docker not found:**
```bash
# Check Docker installation
docker --version

# Start Docker (Linux)
sudo systemctl start docker

# Test Docker access
docker run hello-world
```

**Device not detected:**
```bash
# List detected devices
glovebox firmware devices --profile glove80/v25.05

# Check device is in bootloader mode
# Verify USB query matches your device
```

**Build failures:**
```bash
# Check build logs
glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 --verbose

# Clean build
glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 --clean
```

## Next Steps

### Explore Features
- **[Keyboard Profiles](keyboard-profiles.md)** - Learn about profile management
- **[Layout Editing](layout-editing.md)** - Advanced layout techniques
- **[Firmware Building](firmware-building.md)** - Build system details

### Advanced Usage
- **[Dynamic Generation](dynamic-generation.md)** - On-the-fly workspace creation
- **[Docker Configuration](docker-configuration.md)** - Custom Docker settings
- **[Custom Keyboards](custom-keyboards.md)** - Add your own keyboard

### Get Help
- **[Troubleshooting](troubleshooting.md)** - Common problems and solutions
- **GitHub Issues** - Report bugs or request features
- **GitHub Discussions** - Ask questions and get help

## Quick Reference

### Essential Commands
```bash
# Layout operations
glovebox layout compile layout.json output/name --profile keyboard/firmware
glovebox layout decompose layout.json components/
glovebox layout compose components/ --output new_layout.json
glovebox layout show layout.json

# Firmware operations  
glovebox firmware compile keymap.keymap config.conf --profile keyboard/firmware
glovebox firmware flash firmware.uf2 --profile keyboard/firmware

# Configuration
glovebox config list
glovebox config show keyboard_name
glovebox status

# Debug
glovebox --debug [command]
glovebox -v [command]
```

### Profile Patterns
```bash
# Full profiles (keyboard + firmware)
--profile glove80/v25.05
--profile corne/main

# Keyboard-only profiles (for flashing pre-built firmware)
--profile glove80
--profile corne
```

You're now ready to start building custom keyboard firmware with Glovebox!