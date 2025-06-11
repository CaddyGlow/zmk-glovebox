# Adding New Keyboard Support

This guide walks through adding support for a new keyboard to Glovebox. We'll cover the configuration structure, testing, and integration steps.

## Overview

Adding a new keyboard involves:
1. **Creating keyboard configuration** - YAML file defining the keyboard
2. **Defining firmware variants** - Different firmware options for the keyboard
3. **Setting up build configuration** - Docker images and build processes
4. **Configuring flash settings** - USB device detection and flashing
5. **Testing the configuration** - Validating the setup works correctly

## Step 1: Create Keyboard Configuration

Create a new YAML file in the `keyboards/` directory:

```yaml
# keyboards/my_custom_board.yaml
keyboard: my_custom_board
description: My Custom 60% Mechanical Keyboard
vendor: Custom Keyboards Inc
key_count: 61
version: v1.0.0

# Flash configuration - how to detect and flash the keyboard
flash:
  method: mass_storage              # Flash method (mass_storage, dfu, etc.)
  query: vendor=Custom and removable=true  # USB device query
  usb_vid: 0x1234                  # USB Vendor ID (hexadecimal)
  usb_pid: 0x5678                  # USB Product ID (hexadecimal)
  timeout: 60                      # Flash timeout in seconds

# Build configuration - how to compile firmware
build:
  method: docker                   # Build method (docker, cmake, etc.)
  docker_image: zmk-build         # Docker image for building
  docker_tag: latest              # Docker image tag
  repository: zmkfirmware/zmk     # Git repository URL
  branch: main                    # Default git branch
  parallel_jobs: 4                # Number of parallel build jobs
  clean_build: false              # Whether to clean before building
  
  # Docker user mapping (optional)
  enable_user_mapping: true
  detect_user_automatically: true

# Available firmware variants
firmwares:
  stable:
    description: Stable firmware for daily use
    version: v1.0
    branch: main
    
  beta:
    description: Beta firmware with experimental features
    version: v1.1-beta
    branch: beta
    kconfig_options:
      CONFIG_ZMK_RGB_UNDERGLOW: "y"
      CONFIG_ZMK_BACKLIGHT: "y"
      
  wireless:
    description: Wireless-optimized firmware
    version: v1.0-wireless
    branch: main
    kconfig_options:
      CONFIG_ZMK_BLE: "y"
      CONFIG_ZMK_USB: "n"
      CONFIG_BT_CTLR_TX_PWR_PLUS_8: "y"

# Keymap configuration (optional - enables layout generation)
keymap:
  includes:
    - "#include <dt-bindings/zmk/keys.h>"
    - "#include <dt-bindings/zmk/bt.h>"
    - "#include <dt-bindings/zmk/rgb.h>"
  
  # Template for generating keymap files
  templates:
    keymap: |
      #include <behaviors.dtsi>
      {{ resolved_includes }}
      
      / {
          keymap {
              compatible = "zmk,keymap";
              {{ keymap_node }}
          };
      };
    
    kconfig: |
      # Generated configuration for {{ keyboard_name }}
      CONFIG_ZMK_KEYBOARD_NAME="{{ keyboard_name }}"
      {{ kconfig_options }}

  # Behavior configuration
  system_behaviors:
    - name: "kp"
      display_name: "Key Press"
      description: "Standard key press"
      params:
        - name: "key"
          type: "string"
          description: "Key code to press"
          
    - name: "mt"
      display_name: "Mod-Tap"
      description: "Modifier when held, key when tapped"
      params:
        - name: "modifier"
          type: "string"
          description: "Modifier key"
        - name: "key"
          type: "string"
          description: "Key when tapped"

  # Kconfig options for this keyboard
  kconfig_options:
    CONFIG_ZMK_KEYBOARD_NAME: "my_custom_board"
    CONFIG_ZMK_DISPLAY: "y"
    CONFIG_ZMK_DISPLAY_STATUS_SCREEN_BUILT_IN: "y"

# Display configuration (optional - for layout visualization)
display:
  layout:
    # Physical layout definition for visualization
    rows: 5
    cols: 14
    key_positions:
      # Define physical key positions (row, col, width, height)
      - [0, 0, 1, 1]  # ESC key
      - [0, 1, 1, 1]  # 1 key
      # ... more key positions
      
  formatting:
    default_key_width: 8
    key_gap: "  "
    layer_separator: "\n\n"
    show_layer_names: true

# Validation limits (optional)
validation:
  max_layers: 32
  max_behaviors: 1000
  max_combos: 500
  max_macros: 100
```

## Step 2: Minimal Configuration (Keyboard-Only)

For simpler setups or flashing-only operations, you can create a minimal configuration:

```yaml
# keyboards/simple_board.yaml
keyboard: simple_board
description: Simple Board (Flash Only)
vendor: Simple Electronics
key_count: 40

# Required: Flash configuration
flash:
  method: mass_storage
  query: vendor=Simple and removable=true
  usb_vid: 0x9999
  usb_pid: 0x0001

# Required: Build configuration  
build:
  method: docker
  docker_image: zmk-build
  repository: zmkfirmware/zmk
  branch: main

# Optional sections omitted (keymap, firmwares)
# This creates a "keyboard-only" profile suitable for flashing pre-built firmware
```

## Step 3: Test Configuration Discovery

Test that your configuration is discoverable:

```bash
# List available keyboards (should include your new keyboard)
glovebox config list

# Show your keyboard configuration
glovebox config show my_custom_board

# List available firmware variants
glovebox config firmwares my_custom_board

# Show specific firmware configuration
glovebox config firmware my_custom_board stable
```

## Step 4: Test Profile Creation

Test creating profiles for your keyboard:

```python
from glovebox.config import create_keyboard_profile

# Test full profile creation
try:
    profile = create_keyboard_profile("my_custom_board", "stable")
    print(f"Created profile: {profile.keyboard_name}/{profile.firmware_version}")
    print(f"Description: {profile.keyboard_config.description}")
    print(f"Vendor: {profile.keyboard_config.vendor}")
except Exception as e:
    print(f"Profile creation failed: {e}")

# Test keyboard-only profile
try:
    keyboard_only = create_keyboard_profile("my_custom_board")
    print(f"Created keyboard-only profile: {keyboard_only.keyboard_name}")
    print(f"Has firmware: {keyboard_only.firmware_config is not None}")
except Exception as e:
    print(f"Keyboard-only profile creation failed: {e}")
```

## Step 5: Configure Build System

### Docker Image Setup

If using a custom Docker image, ensure it's available:

```bash
# Pull existing ZMK build image
docker pull zmkfirmware/zmk-build-arm:stable

# Or build custom image
# Create Dockerfile for your build environment
cat > Dockerfile << EOF
FROM zmkfirmware/zmk-build-arm:stable

# Add any custom build dependencies
RUN apt-get update && apt-get install -y \\
    your-custom-tools

# Set up any custom environment
ENV CUSTOM_VAR=value

WORKDIR /workspace
EOF

# Build custom image
docker build -t my-custom-zmk-build .
```

### Update Configuration

```yaml
# Update build section in your keyboard config
build:
  method: docker
  docker_image: my-custom-zmk-build  # Use your custom image
  docker_tag: latest
  repository: your-org/zmk-fork     # Your ZMK fork if needed
  branch: custom-features           # Your custom branch
```

## Step 6: Test Firmware Building

Test firmware compilation with your configuration:

```bash
# Create test keymap and config files
cat > test_keymap.keymap << 'EOF'
#include <behaviors.dtsi>
#include <dt-bindings/zmk/keys.h>

/ {
    keymap {
        compatible = "zmk,keymap";
        
        default_layer {
            bindings = <
                &kp ESC   &kp Q   &kp W   &kp E   &kp R
                &kp TAB   &kp A   &kp S   &kp D   &kp F
                &kp LSHFT &kp Z   &kp X   &kp C   &kp V
            >;
        };
    };
};
EOF

cat > test_config.conf << 'EOF'
CONFIG_ZMK_KEYBOARD_NAME="my_custom_board"
CONFIG_ZMK_DISPLAY=y
EOF

# Test firmware compilation
glovebox firmware compile test_keymap.keymap test_config.conf \
    --profile my_custom_board/stable \
    --output-dir build/test/

# Check build results
ls -la build/test/
```

## Step 7: Configure USB Device Detection

### Find USB Device Information

Connect your keyboard in bootloader/flash mode and identify USB details:

```bash
# Linux - list USB devices
lsusb
# Look for your device, note Vendor:Product IDs

# Linux - detailed device info
udevadm info --name=/dev/sdb --attribute-walk
# Replace /dev/sdb with your device

# macOS - list devices
system_profiler SPUSBDataType
# Look for your keyboard device

# Windows - use Device Manager or PowerShell
Get-PnpDevice -PresentOnly | Where-Object {$_.Class -eq "USB"}
```

### Update Device Query

Update your configuration with the correct USB information:

```yaml
flash:
  method: mass_storage
  query: vendor=YourVendor and product=YourProduct and removable=true
  usb_vid: 0x1234  # Your actual Vendor ID
  usb_pid: 0x5678  # Your actual Product ID
```

### Test Device Detection

```bash
# Test device detection with your configuration
glovebox firmware flash --list-devices --profile my_custom_board/stable

# Test flash operation (with dummy firmware file for testing)
touch test_firmware.uf2
glovebox firmware flash test_firmware.uf2 --profile my_custom_board/stable --dry-run
```

## Step 8: Test Layout Generation (Optional)

If your configuration includes keymap support:

```bash
# Create test layout JSON
cat > test_layout.json << 'EOF'
{
    "metadata": {
        "name": "Test Layout",
        "description": "Test layout for my custom board"
    },
    "layers": [
        {
            "name": "DEFAULT",
            "bindings": [
                {"key": 0, "binding": "&kp ESC"},
                {"key": 1, "binding": "&kp Q"},
                {"key": 2, "binding": "&kp W"}
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
EOF

# Test layout compilation
glovebox layout compile test_layout.json output/test_layout \
    --profile my_custom_board/stable

# Check generated files
ls -la output/
cat output/test_layout.keymap
cat output/test_layout.conf
```

## Step 9: Add Configuration Validation

Create validation tests for your configuration:

```python
# tests/test_my_custom_board.py
import pytest
from glovebox.config import create_keyboard_profile
from glovebox.config.keyboard_profile import load_keyboard_config
from pydantic import ValidationError

def test_my_custom_board_config():
    """Test my_custom_board configuration loads correctly."""
    config = load_keyboard_config("my_custom_board")
    
    assert config.keyboard == "my_custom_board"
    assert config.vendor == "Custom Keyboards Inc"
    assert config.key_count == 61
    
    # Test firmware variants
    assert "stable" in config.firmwares
    assert "beta" in config.firmwares
    assert "wireless" in config.firmwares

def test_my_custom_board_profile_creation():
    """Test profile creation for my_custom_board."""
    # Test full profile
    profile = create_keyboard_profile("my_custom_board", "stable")
    assert profile.keyboard_name == "my_custom_board"
    assert profile.firmware_version == "stable"
    assert profile.firmware_config is not None
    
    # Test keyboard-only profile
    keyboard_only = create_keyboard_profile("my_custom_board")
    assert keyboard_only.keyboard_name == "my_custom_board"
    assert keyboard_only.firmware_version is None

def test_my_custom_board_build_config():
    """Test build configuration."""
    profile = create_keyboard_profile("my_custom_board", "stable")
    build_config = profile.keyboard_config.build
    
    assert build_config.method == "docker"
    assert build_config.docker_image == "zmk-build"
    assert build_config.repository == "zmkfirmware/zmk"

def test_my_custom_board_flash_config():
    """Test flash configuration."""
    profile = create_keyboard_profile("my_custom_board", "stable")
    flash_config = profile.keyboard_config.flash
    
    assert flash_config.method == "mass_storage"
    assert flash_config.usb_vid == 0x1234
    assert flash_config.usb_pid == 0x5678
    assert "vendor=Custom" in flash_config.query

# Run tests
# pytest tests/test_my_custom_board.py -v
```

## Step 10: Documentation and Examples

Create documentation for your keyboard:

```markdown
# My Custom Board Support

## Overview
My Custom Board is a 60% mechanical keyboard with the following features:
- 61 keys in standard 60% layout
- USB-C connectivity
- RGB underglow support
- Rotary encoder

## Firmware Variants

### Stable (recommended)
- Stable firmware for daily use
- All basic features enabled
- Profile: `my_custom_board/stable`

### Beta
- Experimental features
- RGB underglow enabled
- Profile: `my_custom_board/beta`

### Wireless
- Bluetooth optimized
- Extended battery life
- Profile: `my_custom_board/wireless`

## Usage Examples

### Build and Flash Firmware
```bash
# Generate layout
glovebox layout compile my_layout.json output/my_board --profile my_custom_board/stable

# Build firmware
glovebox firmware compile output/my_board.keymap output/my_board.conf --profile my_custom_board/stable

# Flash firmware
glovebox firmware flash build/my_custom_board.uf2 --profile my_custom_board/stable
```

### Troubleshooting
- **Device not detected**: Ensure keyboard is in bootloader mode
- **Build failures**: Check Docker is running and image is available
- **Flash failures**: Verify USB device query matches your keyboard
```

## Common Issues and Solutions

### Configuration Not Found
```
Error: Keyboard configuration 'my_board' not found
```
**Solution**: Ensure YAML file is in `keyboards/` directory and named correctly.

### Invalid Configuration
```
Error: Validation error in keyboard configuration
```
**Solution**: Check YAML syntax and required fields. Use a YAML validator.

### Docker Build Failures
```
Error: Docker image 'custom-build' not found
```
**Solution**: Ensure Docker image exists locally or can be pulled from registry.

### USB Device Not Detected
```
Error: No devices found matching query
```
**Solution**: 
1. Check device is in bootloader/flash mode
2. Verify USB VID/PID are correct
3. Test device query with `--list-devices`

### Profile Creation Errors
```
Error: Firmware version 'v2.0' not found for keyboard 'my_board'
```
**Solution**: Check firmware version exists in `firmwares` section of configuration.

## Best Practices

1. **Use descriptive names**: Choose clear keyboard and firmware names
2. **Test incrementally**: Test each section as you build the configuration
3. **Document variants**: Clearly describe what each firmware variant provides
4. **Validate thoroughly**: Test all firmware variants and profile combinations
5. **Include examples**: Provide working examples of layouts and commands
6. **Version control**: Keep configuration in git with semantic versioning
7. **Follow conventions**: Use consistent naming and structure patterns

## Integration Checklist

- [ ] YAML configuration file created in `keyboards/`
- [ ] Configuration discoverable with `glovebox config list`
- [ ] All firmware variants defined and testable
- [ ] Profile creation works for all variants
- [ ] Keyboard-only profile creation works
- [ ] Build configuration tested with sample firmware
- [ ] Flash configuration tested with device detection
- [ ] Layout generation works (if keymap section included)
- [ ] Validation tests written and passing
- [ ] Documentation created with examples
- [ ] Integration tested end-to-end

With these steps completed, your keyboard should be fully integrated into Glovebox and ready for use!