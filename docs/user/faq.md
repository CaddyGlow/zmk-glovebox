# Frequently Asked Questions (FAQ)

This page answers common questions about Glovebox usage, troubleshooting, and best practices.

## General Questions

### What is Glovebox?

Glovebox is a comprehensive command-line tool for managing ZMK keyboard firmware. It transforms keyboard layouts from JSON files into ZMK keymap and configuration files, builds firmware using Docker-based toolchains, and flashes firmware to keyboards.

### What keyboards does Glovebox support?

Glovebox supports any keyboard that works with ZMK firmware, including:

- **Glove80** (MoErgo) - Full native support
- **Corne (CRKBD)** - Popular 42-key split keyboard
- **Lily58** - 58-key split with number row  
- **Planck** - Compact 40% ortholinear
- **Custom keyboards** - Any ZMK-compatible keyboard with proper configuration

### Do I need Docker to use Glovebox?

Yes, Docker is required for firmware building. Glovebox uses Docker containers with pre-configured ZMK build environments to ensure consistent, reproducible builds across different operating systems.

### Can I use Glovebox without an internet connection?

Limited functionality works offline:
- ✓ Layout editing and validation
- ✓ JSON to ZMK file conversion
- ✗ Firmware building (requires Docker images)
- ✗ Library operations (requires network access)
- ✗ Profile updates

## Installation and Setup

### Why does `glovebox` command not work after installation?

This usually indicates a PATH issue:

```bash
# Check if glovebox is installed
pip show glovebox

# Find installation location
python -m site --user-base

# Add to PATH (Linux/macOS)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Verify
which glovebox
glovebox --version
```

### How do I fix Docker permission errors?

On Linux, add your user to the docker group:

```bash
sudo usermod -aG docker $USER
# Log out and back in, then test:
docker run hello-world
```

### What Python version do I need?

Glovebox requires Python 3.11 or newer:

```bash
python --version  # Should show 3.11+
# If not, install Python 3.11+ and use:
python3.11 -m pip install glovebox
```

## Configuration and Profiles

### How do I set a default keyboard profile?

```bash
# Set default profile for your keyboard
glovebox config edit --set profile=glove80/v25.05

# Verify setting
glovebox config edit --get profile

# Use in commands (profile will be applied automatically)
glovebox layout compile my_layout.json output/
```

### What's the difference between `glove80/v25.05` and `glove80`?

- `glove80/v25.05` - Specific keyboard and firmware version
- `glove80` - Keyboard only, uses default firmware version

Use the full format for reproducible builds, keyboard-only for device operations.

### How do I add custom keyboard profiles?

```bash
# Add custom profile directory
glovebox config edit --add profiles_paths=/path/to/custom/keyboards

# Create profile file (YAML format)
# /path/to/custom/keyboards/my_keyboard.yaml
```

See the [Profiles Guide](profiles.md) for detailed custom profile creation.

### Where is my configuration file stored?

- **Linux/macOS**: `~/.config/glovebox/config.yaml`
- **Windows**: `%APPDATA%\glovebox\config.yaml`

```bash
# View current configuration
glovebox config show

# Edit configuration file directly
glovebox config edit
```

## Layout Operations

### How do I convert a Layout Editor JSON to firmware?

```bash
# Single command: JSON → firmware
glovebox firmware compile my_layout.json firmware/ --profile glove80/v25.05

# Two-step process: JSON → ZMK files → firmware  
glovebox layout compile my_layout.json zmk_files/ --profile glove80/v25.05
glovebox firmware compile zmk_files/my_layout.keymap firmware/ --profile glove80/v25.05
```

### Why does my layout validation fail?

Common causes:

1. **JSON syntax errors**: Use `python -m json.tool layout.json` to check
2. **Missing required fields**: Ensure `version`, `keyboard`, `layers` are present
3. **Invalid behavior references**: Check behavior names and parameters
4. **Profile incompatibility**: Verify layout works with target keyboard

```bash
# Detailed validation
glovebox layout validate layout.json --profile glove80/v25.05 --verbose
```

### How do I edit specific fields in a layout?

```bash
# Get field values
glovebox layout edit layout.json --get title,version

# Set field values  
glovebox layout edit layout.json --set title="My Layout" --set version="2.0"

# Edit array elements
glovebox layout edit layout.json --set layers[0].name="Base"

# Edit nested objects
glovebox layout edit layout.json --set metadata.author="John Doe"
```

### Can I merge layouts from different sources?

Yes, using split and merge operations:

```bash
# Split layouts into components
glovebox layout split layout1.json components1/
glovebox layout split layout2.json components2/

# Manually combine components, then merge
glovebox layout merge combined_components/ merged_layout.json
```

## Firmware Building

### Why do firmware builds take so long?

First builds download Docker images and ZMK dependencies. Subsequent builds are much faster due to caching:

```bash
# Pre-warm cache for faster builds
glovebox cache workspace create zmk --profile glove80/v25.05

# Show cache status
glovebox cache show
```

### How do I build firmware for multiple keyboards?

```bash
# Build for different profiles
glovebox firmware compile layout.json firmware_glove80/ --profile glove80/v25.05
glovebox firmware compile layout.json firmware_corne/ --profile corne/main

# Batch processing
for profile in glove80/v25.05 corne/main lily58/main; do
  glovebox firmware compile layout.json "firmware_${profile%/*}/" --profile "$profile"
done
```

### What do I do if firmware build fails?

1. **Check Docker**: Ensure Docker is running and accessible
2. **Try verbose build**: Add `--verbose` for detailed error information
3. **Clean build**: Use `--clean` to ignore cache
4. **Validate layout**: Ensure layout is valid for the target profile

```bash
# Debugging build failures
glovebox status --verbose
glovebox firmware compile layout.json output/ --profile glove80/v25.05 --verbose --clean
```

### How do I enable specific ZMK features?

Use configuration parameters during build:

```bash
# Enable RGB underglow
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --define CONFIG_ZMK_RGB_UNDERGLOW=y

# Enable display support
glovebox firmware compile layout.json firmware/ \
  --profile corne/main \
  --define CONFIG_ZMK_DISPLAY=y
```

## Device Flashing

### How do I put my keyboard in bootloader mode?

Methods vary by keyboard:

- **Glove80**: Double-tap reset button on back
- **Nice!Nano boards**: Double-tap reset button rapidly
- **Pro Micro boards**: Short RST to GND twice rapidly
- **RP2040 boards**: Hold BOOT while plugging in USB

```bash
# Check if device is detected
glovebox firmware devices

# Wait for device to appear
glovebox firmware flash firmware.uf2 --profile glove80 --wait
```

### Why can't Glovebox detect my keyboard?

1. **Bootloader mode**: Ensure keyboard is in bootloader mode
2. **USB permissions**: Check USB device permissions (Linux)
3. **Driver issues**: Ensure proper drivers are installed (Windows)
4. **USB cable**: Try a different cable or port

```bash
# Check USB device detection
lsusb  # Linux
system_profiler SPUSBDataType | grep -A5 -B5 keyboard  # macOS

# Check device permissions
ls -la /dev/ttyACM* /dev/ttyUSB*  # Linux

# Test device access
glovebox firmware devices --verbose
```

### How do I flash split keyboards?

Flash each half separately:

```bash
# Put left half in bootloader mode
glovebox firmware flash firmware/glove80_lh.uf2 --profile glove80

# Put right half in bootloader mode  
glovebox firmware flash firmware/glove80_rh.uf2 --profile glove80
```

### Can I flash without using Glovebox?

Yes, firmware files are standard UF2 format:

```bash
# Manual flash (when keyboard appears as USB drive)
cp firmware/glove80_lh.uf2 /media/KEYBOARD/

# Or use other flashing tools
# dfu-util, etc.
```

## Performance and Caching

### How do I speed up builds?

1. **Enable caching**: `glovebox config edit --set cache_strategy=shared`
2. **Pre-warm cache**: Create workspaces for your profiles
3. **Use SSD storage**: Fast disk improves Docker performance
4. **Allocate Docker resources**: Increase Docker memory/CPU limits

```bash
# Optimize cache settings
glovebox config edit --set cache_ttls.compilation=7200

# Pre-create workspaces
glovebox cache workspace create zmk --profile glove80/v25.05
```

### How much disk space does Glovebox use?

Typical usage:
- **Docker images**: 2-4 GB
- **Build cache**: 500MB - 2GB
- **Workspaces**: 200-500MB each
- **User data**: <100MB

```bash
# Check cache usage
glovebox cache show --verbose

# Clean old data
glovebox cache clear --older-than 7d
```

### How do I clean up Glovebox data?

```bash
# Clear build cache
glovebox cache clear

# Clean workspaces
glovebox cache workspace cleanup

# Clean Docker (frees most space)
docker system prune -a

# Reset configuration (CAUTION: removes all settings)
rm -rf ~/.config/glovebox/
```

## Library and MoErgo Integration

### How do I access MoErgo layout libraries?

```bash
# Login to MoErgo services
glovebox moergo login

# Search layouts
glovebox library search "gaming layout"

# Fetch layout by UUID
glovebox library fetch @12345678-1234-1234-1234-123456789abc
```

### Why can't I connect to MoErgo services?

1. **Account required**: You need a MoErgo account
2. **Network access**: Check internet connectivity
3. **Credentials**: Ensure valid login credentials
4. **Service status**: MoErgo services may be temporarily unavailable

```bash
# Check MoErgo status
glovebox moergo status

# Re-login if needed
glovebox moergo logout
glovebox moergo login
```

### Can I use Glovebox without MoErgo services?

Yes, Glovebox works completely independently. MoErgo integration is optional and only required for:
- Accessing MoErgo layout libraries
- Fetching layouts by UUID
- Uploading layouts to MoErgo cloud

## Troubleshooting

### What should I check when something isn't working?

Always start with system diagnostics:

```bash
# Comprehensive system check
glovebox status --verbose

# Check configuration
glovebox config show --validate

# Test basic functionality
glovebox profile list
```

### How do I get help with errors?

1. **Read error messages carefully** - they often contain specific solutions
2. **Check the [Troubleshooting Guide](troubleshooting.md)**
3. **Run with verbose output**: Add `--verbose` to commands
4. **Check system status**: `glovebox status --verbose`
5. **Search documentation** for your specific error

### How do I report bugs?

When reporting issues, include:

```bash
# System information
glovebox status --verbose > system_info.txt

# Configuration (remove sensitive data)
glovebox config show --format yaml > config.yaml

# Error logs with verbose output
glovebox command --verbose 2>&1 | tee error.log

# Steps to reproduce the issue
```

### How do I reset Glovebox to default state?

```bash
# CAUTION: This removes all configuration and cache
rm -rf ~/.config/glovebox/
rm -rf ~/.cache/glovebox/
glovebox cache clear
docker system prune -a

# Verify clean state
glovebox status
```

## Best Practices

### How should I organize my layout projects?

```bash
# Recommended project structure
my_keyboard/
├── layouts/          # Source layout files
├── firmware/         # Generated firmware (not in git)
├── backups/          # Layout backups
├── scripts/          # Build/deploy scripts
└── docs/            # Documentation
```

### What should I backup?

Essential data to backup:
- Layout JSON files
- Custom profile configurations
- Glovebox configuration file
- Build scripts and documentation

```bash
# Backup script example
cp -r ~/.config/glovebox/ backup/config/
cp -r my_layouts/ backup/layouts/
```

### How do I stay updated?

```bash
# Check for Glovebox updates
pip list --outdated | grep glovebox
pip install --upgrade glovebox

# Check for ZMK/profile updates
glovebox config check-updates

# Update profiles
glovebox profile update
```

### What are the security considerations?

- **Credentials**: Glovebox stores MoErgo credentials securely using keyring
- **Docker**: Builds run in isolated Docker containers
- **Network**: Only communicates with configured services (MoErgo, GitHub)
- **Files**: Only accesses files you specify and configuration directories

## Getting More Help

### Where can I find more documentation?

- **[User Documentation](index.md)** - Complete user guides
- **[CLI Reference](cli-reference.md)** - All commands and options
- **[Troubleshooting Guide](troubleshooting.md)** - Problem solving
- **[Workflows](workflows.md)** - Common usage patterns

### How can I contribute or get community help?

- **GitHub Repository**: Source code, issues, and discussions
- **Community Forums**: User discussions and help
- **Documentation**: Contributions to improve guides
- **Bug Reports**: Help improve Glovebox by reporting issues

---

*If your question isn't answered here, check the other documentation sections or consult the community resources.*