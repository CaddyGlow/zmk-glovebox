# Getting Started with Glovebox

This guide will walk you through your first layout compilation and firmware flash using Glovebox.

## Prerequisites

- Glovebox installed and configured (see [Installation Guide](installation.md))
- Docker running and accessible
- A keyboard layout JSON file (from Layout Editor or examples)
- Your keyboard connected (for flashing)

## Understanding the Workflow

Glovebox follows a clear pipeline:

```
JSON Layout → ZMK Files → Firmware → Flash to Keyboard
```

1. **JSON Layout**: Human-readable layout from Layout Editor
2. **ZMK Files**: `.keymap` and `.conf` files for ZMK firmware
3. **Firmware**: Compiled `.uf2` binary file
4. **Flash**: Transfer firmware to keyboard

## Your First Layout Compilation

### Step 1: Get a Layout File

You can use an example layout or create your own:

```bash
# Download an example layout
curl -O https://raw.githubusercontent.com/moergo-sc/zmk/main/app/boards/arm/glove80/glove80.json

# Or use a local layout file you've created
# my_layout.json
```

### Step 2: Check Available Profiles

Profiles define keyboard and firmware combinations:

```bash
# List all available profiles
glovebox profile list

# Show details for a specific profile
glovebox profile show glove80/v25.05

# List available keyboards
glovebox profile list --keyboards-only
```

### Step 3: Compile Layout to ZMK Files

Convert your JSON layout to ZMK keymap and config files:

```bash
# Basic compilation
glovebox layout compile my_layout.json output/ --profile glove80/v25.05

# With validation
glovebox layout compile my_layout.json output/ --profile glove80/v25.05 --validate

# Verbose output
glovebox layout compile my_layout.json output/ --profile glove80/v25.05 --verbose
```

**Output files:**
- `output/my_layout.keymap` - ZMK keymap file
- `output/my_layout.conf` - ZMK configuration file

### Step 4: Build Firmware

Compile ZMK files into firmware:

```bash
# Build firmware from the generated files
glovebox firmware compile output/my_layout.keymap output/my_layout.conf output/firmware/ --profile glove80/v25.05

# Or build directly from JSON (combines steps 3 and 4)
glovebox firmware compile my_layout.json output/firmware/ --profile glove80/v25.05
```

**Output files:**
- `output/firmware/glove80_lh.uf2` - Left hand firmware
- `output/firmware/glove80_rh.uf2` - Right hand firmware

### Step 5: Flash Firmware

Transfer firmware to your keyboard:

```bash
# Check connected devices
glovebox firmware devices

# Flash firmware (put keyboard in bootloader mode first)
glovebox firmware flash output/firmware/glove80_lh.uf2 --profile glove80

# Flash both hands
glovebox firmware flash output/firmware/glove80_lh.uf2 --profile glove80
glovebox firmware flash output/firmware/glove80_rh.uf2 --profile glove80
```

## Complete Example Workflow

Here's a complete example from start to finish:

```bash
# 1. Check system status
glovebox status

# 2. Set up default profile
glovebox config edit --set profile=glove80/v25.05

# 3. Get an example layout
curl -O https://raw.githubusercontent.com/moergo-sc/zmk/main/examples/glove80_basic.json

# 4. Validate the layout
glovebox layout validate glove80_basic.json --profile glove80/v25.05

# 5. Compile to firmware in one step
glovebox firmware compile glove80_basic.json firmware/ --profile glove80/v25.05

# 6. Put keyboard in bootloader mode and flash
glovebox firmware devices  # Verify device is detected
glovebox firmware flash firmware/glove80_lh.uf2 --profile glove80
```

## Understanding Profiles

Profiles combine keyboard hardware specs with firmware versions:

### Profile Format
- **Full profile**: `keyboard/firmware` (e.g., `glove80/v25.05`)
- **Keyboard-only**: `keyboard` (e.g., `glove80`) - uses default firmware

### Common Profiles
```bash
# Glove80 keyboards
glove80/v25.05    # MoErgo Glove80 with v25.05 firmware
glove80/main      # Glove80 with latest main branch

# Generic ZMK keyboards
corne/main        # Corne keyboard with main ZMK
lily58/main       # Lily58 keyboard with main ZMK
```

### Setting Default Profile
```bash
# Set global default
glovebox config edit --set profile=glove80/v25.05

# Use profile for single command
glovebox layout compile my_layout.json output/ --profile corne/main
```

## Working with Different Keyboards

### Glove80 (Split)
```bash
# Compile for Glove80
glovebox firmware compile layout.json output/ --profile glove80/v25.05

# Flash left hand
glovebox firmware flash output/glove80_lh.uf2 --profile glove80

# Flash right hand  
glovebox firmware flash output/glove80_rh.uf2 --profile glove80
```

### Single-Board Keyboards
```bash
# Compile for Corne
glovebox firmware compile layout.json output/ --profile corne/main

# Flash single firmware
glovebox firmware flash output/corne.uf2 --profile corne
```

## Useful Commands for Beginners

### Validation and Testing
```bash
# Validate layout without building
glovebox layout validate my_layout.json --profile glove80/v25.05

# Show layout details
glovebox layout show my_layout.json --profile glove80/v25.05

# Preview compiled keymap
glovebox layout compile my_layout.json --output-stdout --profile glove80/v25.05
```

### Configuration Management
```bash
# Show current configuration
glovebox config show

# Edit configuration interactively
glovebox config edit --interactive

# Show profile details
glovebox profile show glove80/v25.05
```

### Cache and Performance
```bash
# Show cache status
glovebox cache show

# Clear cache if needed
glovebox cache clear

# Show build workspace
glovebox cache workspace show
```

## Understanding Output

### Success Messages
- **Layout validated successfully**
- **Compilation completed**
- **Firmware built successfully**
- **Device flashed successfully**

### Common Warnings
- ⚠ **Cache miss - downloading dependencies**
- ⚠ **Docker image update available**
- ⚠ **Device in wrong mode**

### Error Indicators
- ✗ **Layout validation failed**
- ✗ **Compilation failed**
- ✗ **Device not found**

## Tips for Success

### 1. Always Validate First
```bash
# Check layout before building
glovebox layout validate my_layout.json --profile glove80/v25.05
```

### 2. Use System Status
```bash
# Check everything is working
glovebox status --verbose
```

### 3. Keep Cache Warm
```bash
# Pre-download dependencies
glovebox cache workspace create zmk --profile glove80/v25.05
```

### 4. Backup Working Layouts
```bash
# Export successful layouts
cp my_layout.json backups/my_layout_$(date +%Y%m%d).json
```

### 5. Use Dry Run for Testing
```bash
# Test without actual flashing
glovebox firmware flash firmware.uf2 --profile glove80 --dry-run
```

## Common First-Time Issues

### Docker Not Running
```bash
# Check Docker status
docker --version
sudo systemctl start docker  # Linux
```

### USB Permissions
```bash
# Check device access
glovebox firmware devices
# See installation guide for USB setup
```

### Profile Not Found
```bash
# List available profiles
glovebox profile list
# Use exact profile name
```

### Layout Validation Errors
```bash
# Check layout format
glovebox layout validate my_layout.json --verbose
# Fix JSON syntax or structure
```

## Next Steps

Now that you've completed your first compilation:

1. **[Layout Commands](layout-commands.md)** - Learn advanced layout operations
2. **[Configuration](configuration.md)** - Customize Glovebox for your workflow
3. **[Profiles](profiles.md)** - Set up multiple keyboard profiles
4. **[Workflows](workflows.md)** - Common usage patterns and examples

## Getting Help

If you run into issues:

```bash
# Check system diagnostics
glovebox status --verbose

# Get command help
glovebox layout compile --help
glovebox firmware flash --help

# Show configuration
glovebox config show
```

Visit the [Troubleshooting Guide](troubleshooting.md) for solutions to common problems.

---

*Congratulations! You've successfully compiled and flashed your first keyboard firmware with Glovebox.*