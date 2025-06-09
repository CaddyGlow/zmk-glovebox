# Keyboard Configuration Development Guide

## Overview

This guide helps developers create, validate, and share keyboard configurations for Glovebox. Whether you're developing configurations for a new keyboard, creating variants of existing keyboards, or contributing to the community, this document provides comprehensive guidance.

## Keyboard Configuration Anatomy

### Complete Configuration Structure

```yaml
# Basic keyboard metadata
keyboard: "my_awesome_keyboard"           # Required: Unique identifier
description: "Custom 40% split keyboard" # Required: Human-readable description
vendor: "Your Company"                    # Required: Manufacturer or creator
key_count: 42                            # Required: Total number of keys
version: "1.0.0"                         # Recommended: Semantic version
homepage: "https://example.com/keyboard"  # Optional: Documentation URL
repository: "https://github.com/user/kb" # Optional: Source repository
license: "MIT"                           # Optional: License information

# Flash configuration (Required)
flash:
  method: "mass_storage"                  # Required: Flash method
  query: "vendor=Example and removable=true" # Required: USB device query
  usb_vid: "0x1234"                      # Required: USB Vendor ID
  usb_pid: "0x5678"                      # Required: USB Product ID

# Build configuration (Required)
build:
  method: "docker"                       # Required: Build method
  docker_image: "zmk-build"              # Required: Docker image name
  repository: "zmkfirmware/zmk"          # Required: ZMK repository
  branch: "main"                         # Required: Default branch

# Firmware configurations (Optional)
firmwares:
  stable:
    version: "stable"
    description: "Stable firmware build"
    build_options:
      repository: "zmkfirmware/zmk"
      branch: "main"
    kconfig:                             # Optional: Firmware-specific options
      EXPERIMENTAL_FEATURE:
        name: "CONFIG_EXPERIMENTAL_FEATURE"
        type: "bool"
        default: false
        description: "Enable experimental feature"

# Keymap configuration (Optional but recommended)
keymap:
  includes:                              # Required: ZMK includes
    - "#include <behaviors.dtsi>"
    - "#include <dt-bindings/zmk/keys.h>"
    - "#include <dt-bindings/zmk/bt.h>"
  
  formatting:                            # Required: Layout formatting
    default_key_width: 8
    key_gap: "  "
    base_indent: ""
    rows:                                # Key position matrix
      - [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
      - [12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23]
      - [24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35]
      - [36, 37, 38, 39, 40, 41]

  kconfig_options:                       # Optional: Keyboard kconfig options
    DEEP_SLEEP:
      name: "CONFIG_ZMK_SLEEP"
      type: "bool"
      default: false
      description: "Enable deep sleep mode"
  
  system_behaviors: [...]                # Optional: Custom behaviors
  keymap_dtsi: |                        # Optional: Custom DTSI template
    /* Custom keymap template */
  system_behaviors_dts: |               # Optional: Custom behavior definitions
    /* Custom behavior implementations */
  key_position_header: |                # Optional: Key position definitions
    /* Custom key position macros */
```

## Getting Started

### 1. Create from Template

Generate a basic keyboard configuration template:

```bash
# Generate basic template
glovebox config template basic --output my_keyboard.yaml

# Generate from existing keyboard
glovebox config template --from glove80 --output my_keyboard.yaml

# List available templates
glovebox config template --list
```

### 2. Minimal Configuration

Start with a minimal configuration for testing:

```yaml
keyboard: "test_keyboard"
description: "Test keyboard configuration"
vendor: "Developer"
key_count: 36

flash:
  method: "mass_storage"
  query: "vendor=Test and removable=true"
  usb_vid: "0x1234"
  usb_pid: "0x5678"

build:
  method: "docker"
  docker_image: "zmk-build"
  repository: "zmkfirmware/zmk"
  branch: "main"
```

### 3. Validate Early and Often

```bash
# Validate during development
glovebox config validate ./my_keyboard.yaml

# Strict validation (recommended for final configs)
glovebox config validate ./my_keyboard.yaml --strict

# Verbose output for debugging
glovebox config validate ./my_keyboard.yaml --verbose
```

## Configuration Sections

### Required Sections

#### Keyboard Metadata

```yaml
keyboard: "unique_keyboard_name"        # No spaces, kebab-case recommended
description: "Descriptive keyboard name"
vendor: "Manufacturer or Creator"
key_count: 42                          # Must match actual key count
```

**Best practices:**
- Use kebab-case for keyboard names (e.g., `my-split-keyboard`)
- Keep descriptions concise but descriptive
- Use consistent vendor naming across configurations
- Ensure key_count matches the actual physical key count

#### Flash Configuration

```yaml
flash:
  method: "mass_storage"               # Currently only mass_storage supported
  query: "vendor=YourVendor and product~=YourProduct.* and removable=true"
  usb_vid: "0x1234"                   # Hexadecimal USB Vendor ID
  usb_pid: "0x5678"                   # Hexadecimal USB Product ID
```

**USB Device Query Syntax:**
- `vendor=VendorName` - Exact vendor match
- `product~=Pattern.*` - Regex pattern for product name
- `serial~=Pattern.*` - Regex pattern for serial number
- `removable=true` - Require removable device
- `and`, `or` - Logical operators

**Finding USB IDs:**
```bash
# Linux
lsusb

# macOS
system_profiler SPUSBDataType

# Windows
Get-PnpDevice -Class USB
```

#### Build Configuration

```yaml
build:
  method: "docker"                     # Currently only docker supported
  docker_image: "zmk-build"            # Docker image for building
  repository: "zmkfirmware/zmk"        # ZMK repository URL
  branch: "main"                       # Default branch for builds
```

**Common repositories:**
- `zmkfirmware/zmk` - Official ZMK
- `urob/zmk` - Popular community fork
- `caksoylar/zmk` - Community fork with extra features
- Custom forks for specialized features

### Optional Sections

#### Firmware Configurations

```yaml
firmwares:
  stable:
    version: "stable"
    description: "Stable release firmware"
    build_options:
      repository: "zmkfirmware/zmk"
      branch: "main"
  
  experimental:
    version: "experimental"
    description: "Experimental features"
    build_options:
      repository: "urob/zmk"
      branch: "main"
    kconfig:
      EXPERIMENTAL_MOUSE:
        name: "CONFIG_ZMK_MOUSE"
        type: "bool"
        default: true
        description: "Enable mouse emulation"
```

#### Keymap Configuration

The keymap section defines how layouts are formatted and what ZMK features are available:

```yaml
keymap:
  includes:
    - "#include <behaviors.dtsi>"
    - "#include <dt-bindings/zmk/keys.h>"
    - "#include <dt-bindings/zmk/bt.h>"
    - "#include <dt-bindings/zmk/rgb.h>"
  
  formatting:
    default_key_width: 8               # Character width for key formatting
    key_gap: "  "                      # Spacing between keys
    base_indent: ""                    # Base indentation for keymap
    rows:                              # Physical key layout matrix
      - [0, 1, 2, 3, 4, 5]             # Row 0: keys 0-5
      - [6, 7, 8, 9, 10, 11]           # Row 1: keys 6-11
      - [12, 13, 14, 15, 16, 17]       # Row 2: keys 12-17
      # ... continue for all rows
```

**Row matrix guidelines:**
- Each number represents a physical key position
- Numbers should be consecutive starting from 0
- Use -1 for empty positions in the visual layout
- Total count should match `key_count`

#### KConfig Options

Define available configuration options for the keyboard:

```yaml
kconfig_options:
  DEEP_SLEEP:
    name: "CONFIG_ZMK_SLEEP"
    type: "bool"
    default: false
    description: "Enable deep sleep mode"
  
  SLEEP_TIMEOUT:
    name: "CONFIG_ZMK_IDLE_SLEEP_TIMEOUT"
    type: "int"
    default: 900000
    description: "Sleep timeout in milliseconds"
  
  COMBO_COUNT:
    name: "CONFIG_ZMK_COMBO_MAX_PRESSED_COMBOS"
    type: "int"
    default: 4
    description: "Maximum simultaneous combos"
```

**KConfig types:**
- `bool` - True/false options
- `int` - Integer values
- `string` - Text values
- `choice` - Multiple choice options

#### System Behaviors

Define custom ZMK behaviors available for the keyboard:

```yaml
system_behaviors:
  - code: "&custom_behavior"
    name: "Custom Behavior"
    description: "Custom behavior implementation"
    url: "https://docs.example.com/behaviors"
    expected_params: 2
    origin: "custom"
    params:
      - "parameter1"
      - "parameter2"
```

## Development Workflow

### 1. Planning Phase

**Research the keyboard:**
- Identify the microcontroller (usually nRF52840 for ZMK)
- Determine the key matrix layout
- Find USB VID/PID information
- Check for existing ZMK support

**Define requirements:**
- Number of keys and layout
- Special features (RGB, OLED, rotary encoders)
- Firmware variants needed
- Target user experience

### 2. Initial Configuration

**Start with basics:**
```bash
# Create initial config
glovebox config template basic --output my_keyboard.yaml

# Edit the configuration
vim my_keyboard.yaml

# Validate frequently
glovebox config validate my_keyboard.yaml
```

**Focus on essentials:**
1. Correct keyboard metadata
2. Working flash configuration
3. Valid build configuration
4. Basic keymap formatting

### 3. Testing and Iteration

**Install for testing:**
```bash
# Install development version
glovebox config install ./my_keyboard.yaml --name my_keyboard_dev

# Test with actual layouts
glovebox layout compile test_layout.json output/ --profile my_keyboard_dev/stable

# Remove and reinstall during development
glovebox config remove my_keyboard_dev
glovebox config install ./my_keyboard.yaml --name my_keyboard_dev
```

**Test scenarios:**
- Layout compilation works correctly
- Key positions map correctly
- Firmware builds successfully
- Flash process works on real hardware

### 4. Advanced Features

**Add firmware variants:**
```yaml
firmwares:
  stable:
    version: "stable"
    description: "Stable firmware"
    build_options:
      repository: "zmkfirmware/zmk"
      branch: "main"
  
  rgb:
    version: "rgb"
    description: "RGB underglow support"
    build_options:
      repository: "zmkfirmware/zmk"
      branch: "main"
    kconfig:
      RGB_UNDERGLOW:
        name: "CONFIG_ZMK_RGB_UNDERGLOW"
        type: "bool"
        default: true
        description: "Enable RGB underglow"
```

**Add custom behaviors:**
```yaml
system_behaviors:
  - code: "&custom_macro"
    name: "Custom Macro"
    description: "Keyboard-specific macro behavior"
    expected_params: 1
    origin: "keyboard"
    params: ["macro_id"]
```

### 5. Documentation and Sharing

**Complete metadata:**
```yaml
keyboard: "my_awesome_keyboard"
description: "42-key split ortholinear keyboard"
vendor: "Your Name"
key_count: 42
version: "1.0.0"
homepage: "https://github.com/yourname/keyboard-docs"
repository: "https://github.com/yourname/keyboard-configs"
license: "MIT"
```

**Validation for sharing:**
```bash
# Strict validation ensures completeness
glovebox config validate my_keyboard.yaml --strict

# Check for best practices
glovebox config validate my_keyboard.yaml --verbose
```

## Common Patterns

### Split Keyboards

```yaml
keyboard: "my_split_keyboard"
description: "Custom split ergonomic keyboard"
key_count: 58                          # Total for both halves

flash:
  method: "mass_storage"
  query: "vendor=MyVendor and product~=MySplit.* and removable=true"
  usb_vid: "0x1234"
  usb_pid: "0x5678"

keymap:
  formatting:
    default_key_width: 8
    key_gap: "  "
    rows:
      # Left half
      - [0, 1, 2, 3, 4, 5, -1, -1, -1, -1, -1, -1, -1, 29, 30, 31, 32, 33, 34]
      - [6, 7, 8, 9, 10, 11, -1, -1, -1, -1, -1, -1, -1, 35, 36, 37, 38, 39, 40]
      # ... continue pattern
```

### Ortholinear Keyboards

```yaml
keyboard: "ortho_keyboard"
description: "4x12 ortholinear keyboard"
key_count: 48

keymap:
  formatting:
    default_key_width: 6
    key_gap: " "
    rows:
      - [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
      - [12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23]
      - [24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35]
      - [36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47]
```

### RGB Underglow Support

```yaml
firmwares:
  rgb:
    version: "rgb"
    description: "RGB underglow support"
    build_options:
      repository: "zmkfirmware/zmk"
      branch: "main"
    kconfig:
      RGB_UNDERGLOW:
        name: "CONFIG_ZMK_RGB_UNDERGLOW"
        type: "bool"
        default: true
        description: "Enable RGB underglow"
      
      RGB_UNDERGLOW_AUTO_OFF_IDLE:
        name: "CONFIG_ZMK_RGB_UNDERGLOW_AUTO_OFF_IDLE"
        type: "bool"
        default: true
        description: "Auto-disable RGB when idle"

keymap:
  includes:
    - "#include <dt-bindings/zmk/rgb.h>"
  
  system_behaviors:
    - code: "&rgb_ug"
      name: "RGB Underglow"
      description: "RGB underglow control"
      expected_params: 1
      origin: "zmk"
      params: ["command"]
```

### OLED Display Support

```yaml
firmwares:
  oled:
    version: "oled"
    description: "OLED display support"
    kconfig:
      DISPLAY:
        name: "CONFIG_ZMK_DISPLAY"
        type: "bool"
        default: true
        description: "Enable OLED display"
      
      DISPLAY_STATUS_SCREEN_BUILT_IN:
        name: "CONFIG_ZMK_DISPLAY_STATUS_SCREEN_BUILT_IN"
        type: "bool"
        default: true
        description: "Built-in status screen"
```

## Validation and Quality

### Validation Checklist

**Required sections:**
- [ ] keyboard, description, vendor, key_count present
- [ ] flash section complete with all fields
- [ ] build section complete with all fields
- [ ] USB VID/PID are valid hexadecimal
- [ ] key_count matches actual key positions

**Recommended sections:**
- [ ] version field with semantic versioning
- [ ] homepage or repository for documentation
- [ ] At least one firmware configuration
- [ ] keymap section with proper formatting

**Quality checks:**
- [ ] Description is clear and descriptive
- [ ] Vendor name is consistent
- [ ] USB query string works correctly
- [ ] Key matrix matches physical layout
- [ ] All KConfig options have descriptions

### Automated Validation

```bash
# Basic validation
glovebox config validate my_keyboard.yaml

# Strict validation (all optional fields required)
glovebox config validate my_keyboard.yaml --strict

# Verbose validation with detailed feedback
glovebox config validate my_keyboard.yaml --verbose
```

### Manual Testing

**Test installation:**
```bash
glovebox config install ./my_keyboard.yaml --name test_install
glovebox config show-keyboard test_install
glovebox config remove test_install
```

**Test layout compilation:**
```bash
# Create test layout
glovebox config install ./my_keyboard.yaml --name test_kb
glovebox layout compile test_layout.json output/ --profile test_kb/stable
```

**Test firmware building:**
```bash
# Build firmware with the configuration
glovebox firmware compile output/test.keymap output/test.conf --profile test_kb/stable
```

## Contributing to Community

### Preparation for Sharing

**Complete configuration:**
```yaml
keyboard: "awesome_split_v2"
description: "Awesome Split Keyboard v2"
vendor: "Awesome Keyboards"
key_count: 56
version: "1.0.0"
homepage: "https://awesome-keyboards.com/split-v2"
repository: "https://github.com/awesome-keyboards/configs"
license: "MIT"
```

**Documentation:**
- README with keyboard details
- Installation instructions
- Build guide references
- Layout examples

**Testing:**
- Validate with strict mode
- Test with multiple layout files
- Verify firmware builds successfully
- Test on actual hardware

### Publishing

**GitHub repository structure:**
```
keyboard-configs/
├── README.md
├── keyboards/
│   ├── awesome-split-v2.yaml
│   ├── awesome-60.yaml
│   └── awesome-ortho.yaml
├── layouts/
│   ├── awesome-split-default.json
│   └── awesome-split-gaming.json
└── docs/
    ├── installation.md
    └── customization.md
```

**Installation instructions:**
```markdown
## Installation

Install this keyboard configuration with Glovebox:

```bash
glovebox config install https://raw.githubusercontent.com/awesome-keyboards/configs/main/keyboards/awesome-split-v2.yaml
```

## Usage

Use the keyboard in layouts:

```bash
glovebox layout compile my_layout.json output/ --profile awesome-split-v2/stable
```
```

### Community Guidelines

**Naming conventions:**
- Use kebab-case for keyboard names
- Include version numbers for variants
- Use descriptive but concise names

**Quality standards:**
- All configurations must pass strict validation
- Include comprehensive metadata
- Provide clear documentation
- Test with real hardware

**Maintenance:**
- Respond to user issues
- Keep configurations updated
- Tag stable releases
- Document breaking changes

## Advanced Topics

### Custom DTSI Templates

For keyboards requiring custom ZMK device tree code:

```yaml
keymap:
  keymap_dtsi: |
    /*
     * Custom keymap template for special keyboard features
     */
    / {
        keymap {
            compatible = "zmk,keymap";
            
            default_layer {
                bindings = <
                    {{ keymap_content }}
                >;
            };
        };
    };
    
    /* Custom hardware definitions */
    &encoder_1 {
        status = "okay";
    };
```

### Multiple Build Targets

For keyboards with multiple variants:

```yaml
firmwares:
  left:
    version: "left"
    description: "Left half firmware"
    build_options:
      repository: "zmkfirmware/zmk"
      branch: "main"
      shield: "my_keyboard_left"
  
  right:
    version: "right"
    description: "Right half firmware"
    build_options:
      repository: "zmkfirmware/zmk"
      branch: "main"
      shield: "my_keyboard_right"
```

### Integration with Hardware Features

For keyboards with special hardware:

```yaml
firmwares:
  full_featured:
    version: "full"
    description: "All features enabled"
    kconfig:
      ENCODER:
        name: "CONFIG_EC11"
        type: "bool"
        default: true
        description: "Enable rotary encoder"
      
      UNDERGLOW:
        name: "CONFIG_ZMK_RGB_UNDERGLOW"
        type: "bool"
        default: true
        description: "Enable RGB underglow"
      
      POINTING:
        name: "CONFIG_ZMK_MOUSE"
        type: "bool"
        default: true
        description: "Enable mouse emulation"
```

This development guide provides comprehensive coverage for creating high-quality keyboard configurations that work seamlessly with Glovebox and can be shared with the community.