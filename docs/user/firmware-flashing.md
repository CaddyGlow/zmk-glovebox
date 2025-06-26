# Firmware Flashing

This guide covers flashing compiled firmware to your keyboard using Glovebox.

## Overview

Glovebox provides automated firmware flashing with intelligent device detection and safety features. It supports multiple keyboard types and operating systems with a unified interface.

## Quick Start

### Basic Flashing

```bash
# Flash firmware with auto-detection
glovebox firmware flash firmware.uf2 --profile glove80

# Complete workflow: build and flash
glovebox layout compile layout.json --output build/firmware --profile glove80/v25.05
glovebox firmware flash build/firmware.uf2 --profile glove80
```

### Bootloader Mode

Before flashing, put your keyboard in bootloader mode:

**Glove80:**
- Press and hold the reset button on the back
- Or hold Fn+F4 for 5 seconds (if current firmware supports it)

**Corne/Other keyboards:**
- Press the reset button twice quickly
- Or bridge the reset pins twice quickly

**Nice!Nano controllers:**
- Press the reset button twice quickly
- The blue LED should pulse when in bootloader mode

## Device Detection

### Automatic Detection

Glovebox automatically detects keyboards in bootloader mode:

```bash
# Auto-detect and flash
glovebox firmware flash firmware.uf2 --profile glove80

# Wait longer for device detection (default: 30 seconds)
glovebox firmware flash firmware.uf2 --profile glove80 --timeout 60

# Show detection process
glovebox firmware flash firmware.uf2 --profile glove80 --verbose
```

### Manual Device Specification

If auto-detection fails, specify the device manually:

```bash
# Linux
glovebox firmware flash firmware.uf2 --device /dev/sdb

# macOS
glovebox firmware flash firmware.uf2 --device /dev/disk2

# Windows
glovebox firmware flash firmware.uf2 --device E:
```

### Device Identification

Find your keyboard device:

```bash
# Linux - list block devices
lsblk
dmesg | tail  # Check recent USB events

# macOS - list disks
diskutil list
system_profiler SPUSBDataType | grep -A 5 -B 5 "Vendor Name"

# Windows - list drives
wmic logicaldisk list
# Or check in File Explorer for new drive
```

## Supported Devices

### Device Patterns

Glovebox recognizes keyboards by these patterns:

**Glove80:**
- Label: `GLOVE80`, `GLOVE80LH`, `GLOVE80RH`
- Vendor: `1d50` (OpenMoko)
- Product: `615e`

**Nice!Nano:**
- Label: `NICENANO`
- Vendor: `1209` (Generic)
- Product: `0001`

**Generic UF2 Bootloaders:**
- Label patterns: `*BOOT*`, `*UF2*`
- File system: FAT32 with UF2 bootloader

### Custom Device Patterns

Add custom device patterns for new keyboards:

```yaml
# ~/.glovebox/config.yml
flashing:
  device_patterns:
    - "/dev/disk/by-label/MYBOARD*"
    - "/dev/disk/by-label/CUSTOM*"
```

## Flashing Process

### Safety Features

Glovebox includes multiple safety checks:

1. **Device Validation**: Ensures target is a valid UF2 bootloader
2. **Firmware Verification**: Checks firmware file integrity
3. **Confirmation Prompts**: Asks for confirmation before flashing
4. **Timeout Protection**: Prevents hanging on device detection

### Flashing Steps

```bash
# 1. Put keyboard in bootloader mode
# 2. Run flash command
glovebox firmware flash firmware.uf2 --profile glove80

# The process:
# - Detects bootloader device
# - Validates firmware file
# - Confirms flash operation
# - Copies firmware to device
# - Waits for completion
# - Verifies successful flash
```

### Confirmation and Safety

```bash
# Skip confirmation prompts (careful!)
glovebox firmware flash firmware.uf2 --profile glove80 --force

# Dry run - show what would be flashed without doing it
glovebox firmware flash firmware.uf2 --profile glove80 --dry-run

# Auto-confirm for automation
glovebox config edit --set flashing.auto_confirm=true
```

## Platform-Specific Instructions

### Linux

**Setup:**
```bash
# Add user to dialout group for USB access
sudo usermod -aG dialout $USER
# Log out and back in

# Install udev rules for keyboard access (optional)
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="1d50", ATTRS{idProduct}=="615e", MODE="0666"' | sudo tee /etc/udev/rules.d/99-glove80.rules
sudo udevadm control --reload-rules
```

**Device Detection:**
```bash
# Monitor USB events
dmesg -w

# List USB devices
lsusb

# Check block devices
lsblk -f

# Check mounted filesystems
mount | grep -i uf2
mount | grep -i boot
```

**Flashing:**
```bash
# Standard flashing
glovebox firmware flash firmware.uf2 --profile glove80

# Manual device specification
glovebox firmware flash firmware.uf2 --device /dev/sdb

# Use sudo if permission issues
sudo glovebox firmware flash firmware.uf2 --profile glove80
```

### macOS

**Setup:**
No special setup required. macOS handles UF2 bootloaders automatically.

**Device Detection:**
```bash
# List all disks
diskutil list

# Monitor disk events
diskutil activity

# Check USB system info
system_profiler SPUSBDataType

# Check mounted volumes
ls /Volumes/
```

**Flashing:**
```bash
# Standard flashing
glovebox firmware flash firmware.uf2 --profile glove80

# Manual device specification
glovebox firmware flash firmware.uf2 --device /dev/disk2

# Unmount before flashing if needed
diskutil unmount /dev/disk2
glovebox firmware flash firmware.uf2 --device /dev/disk2
```

### Windows

**Setup:**
Install USB drivers if needed (usually automatic for UF2 bootloaders).

**Device Detection:**
```cmd
# List drives
wmic logicaldisk list

# Check in Device Manager
devmgmt.msc

# Check in File Explorer
# Look for new removable drive when keyboard is in bootloader mode
```

**Flashing:**
```cmd
# Standard flashing
glovebox firmware flash firmware.uf2 --profile glove80

# Manual device specification
glovebox firmware flash firmware.uf2 --device E:

# Using PowerShell
glovebox firmware flash firmware.uf2 --device E:
```

## Advanced Options

### Configuration

```yaml
# ~/.glovebox/config.yml
flashing:
  # Default timeout for device detection
  device_timeout: 30
  
  # Auto-confirm flash operations
  auto_confirm: false
  
  # Detection method
  detection_method: "auto"  # auto, udev, polling
  
  # Custom device patterns
  device_patterns:
    - "/dev/disk/by-label/GLOVE80*"
    - "/dev/disk/by-label/NICENANO*"
    - "/Volumes/GLOVE80*"
    - "E:\\GLOVE80*"
```

### Batch Flashing

```bash
# Flash multiple firmware files
for firmware in build/*.uf2; do
  echo "Flashing $(basename $firmware)"
  echo "Put keyboard in bootloader mode and press Enter..."
  read
  glovebox firmware flash "$firmware" --profile glove80
done
```

### Automated Flashing

```bash
# Script for automated flashing
#!/bin/bash

FIRMWARE="$1"
PROFILE="$2"

if [[ -z "$FIRMWARE" || -z "$PROFILE" ]]; then
  echo "Usage: $0 firmware.uf2 profile"
  exit 1
fi

echo "Put keyboard in bootloader mode..."
glovebox firmware flash "$FIRMWARE" --profile "$PROFILE" --timeout 60

if [[ $? -eq 0 ]]; then
  echo "Flash successful!"
else
  echo "Flash failed!"
  exit 1
fi
```

## Troubleshooting

### Device Not Found

**Problem:** Cannot detect keyboard device

**Solutions:**
```bash
# Check if keyboard is in bootloader mode
# - Look for pulsing LED
# - Check if new drive appears

# Increase timeout
glovebox firmware flash firmware.uf2 --profile glove80 --timeout 120

# Manual device specification
lsblk                    # Linux
diskutil list           # macOS
wmic logicaldisk list   # Windows

glovebox firmware flash firmware.uf2 --device /dev/sdb

# Check device patterns
glovebox keyboard show glove80 --verbose
```

### Permission Denied

**Problem:** Permission denied when accessing device

**Solutions:**
```bash
# Linux - add to dialout group
sudo usermod -aG dialout $USER
# Log out and back in

# Linux - use sudo
sudo glovebox firmware flash firmware.uf2 --profile glove80

# Linux - check udev rules
ls -la /dev/disk/by-label/
```

### Device Busy

**Problem:** Device is busy or mounted

**Solutions:**
```bash
# Linux - unmount device
sudo umount /dev/sdb1

# macOS - unmount device
diskutil unmount /dev/disk2

# Close any file managers or applications using the device

# Use force option (careful!)
glovebox firmware flash firmware.uf2 --device /dev/sdb --force
```

### Flash Verification Failed

**Problem:** Firmware flash appears to complete but verification fails

**Solutions:**
```bash
# Check firmware file integrity
ls -la firmware.uf2
file firmware.uf2

# Try flashing again
glovebox firmware flash firmware.uf2 --profile glove80

# Use different USB port
# Use different USB cable

# Check keyboard compatibility
glovebox keyboard show glove80
```

### Bootloader Mode Issues

**Problem:** Cannot enter bootloader mode

**Solutions:**
```bash
# Different methods to enter bootloader:

# Hardware reset button
# - Single press: normal reset
# - Double press: bootloader mode

# Software reset (if current firmware supports it)
# - Key combination varies by keyboard
# - Check keyboard documentation

# Recovery mode
# - Some keyboards have recovery procedures
# - May require bridging specific pins

# Check current firmware
# - Old firmware may not support soft reset
# - May need to use hardware reset only
```

## Best Practices

### Safety

1. **Backup firmware**: Keep backup of working firmware
2. **Test builds**: Flash test firmware on less critical keyboards first
3. **Verify compatibility**: Ensure firmware matches keyboard hardware
4. **Use stable versions**: Prefer stable firmware versions for daily use

### Workflow

1. **Build and validate**: Always validate layouts before flashing
2. **Incremental changes**: Make small changes and test frequently
3. **Version control**: Track firmware builds and source layouts
4. **Recovery plan**: Know how to recover if firmware doesn't work

### Automation

```bash
# Complete automation workflow
#!/bin/bash

LAYOUT="$1"
PROFILE="glove80/v25.05"
BUILD_DIR="build/$(date +%Y%m%d-%H%M%S)"

# Build firmware
echo "Building firmware..."
glovebox layout compile "$LAYOUT" --output "$BUILD_DIR/firmware" --profile "$PROFILE"

if [[ $? -ne 0 ]]; then
  echo "Build failed!"
  exit 1
fi

# Flash firmware
echo "Put keyboard in bootloader mode and press Enter..."
read

echo "Flashing firmware..."
glovebox firmware flash "$BUILD_DIR/firmware.uf2" --profile glove80

if [[ $? -eq 0 ]]; then
  echo "Flash successful!"
  echo "Firmware built and flashed: $BUILD_DIR/firmware.uf2"
else
  echo "Flash failed!"
  exit 1
fi
```

### Recovery

If firmware doesn't work:

1. **Re-enter bootloader mode**: Usually possible even with broken firmware
2. **Flash known-good firmware**: Keep backup firmware files
3. **Factory reset**: Flash original factory firmware if available
4. **Hardware recovery**: Use hardware recovery procedures if needed

This guide covers all aspects of firmware flashing with Glovebox. The automated device detection and safety features make flashing reliable and safe, while the manual options provide flexibility for complex setups.