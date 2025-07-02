# Device Management Guide

This guide covers how to use Glovebox's device management features to detect, query, and work with USB devices for firmware flashing and development.

## Overview

Glovebox provides comprehensive USB device detection and management capabilities, allowing you to:

- **List and identify** connected USB devices
- **Filter devices** by various criteria
- **Query devices** with flexible pattern matching
- **Flash firmware** to target devices
- **Monitor device** connection and status

## Understanding Device Detection

### Device Types

Glovebox detects multiple types of USB devices:

- **Storage Devices**: USB drives, SD cards, removable storage (default focus)
- **Input Devices**: Keyboards, mice, trackballs, touchpads
- **HID Devices**: Human Interface Devices (keyboards in bootloader mode)
- **USB Hubs**: USB hub controllers and concentrators
- **Raw Interfaces**: Low-level device interfaces (hidraw, hiddev)
- **System Devices**: Built-in controllers and system interfaces

### Device Information

For each detected device, Glovebox provides:

- **Name**: Human-readable device description
- **Vendor/Model**: Manufacturer and model identification
- **Vendor ID (VID)**: USB vendor identifier (hex)
- **Product ID (PID)**: USB product identifier (hex)
- **Serial Number**: Unique device identifier
- **Path**: Device node path (e.g., `/dev/sda`, `/dev/input/event0`)
- **Subsystem**: Device subsystem type (block, input, usb, etc.)
- **Removable Status**: Whether the device is removable
- **Connection Details**: USB bus location and hierarchy

## Basic Device Listing

### Default Behavior

By default, `glovebox firmware devices` shows only removable storage devices:

```bash
# List removable storage devices (default)
glovebox firmware devices
```

**Output:**
```
✓ Found 1 device(s)
  • Kingston DataTraveler_3.0 (sda) - Serial: E0D55E6C38BBF71098310774 - VID: 0951 - PID: 1666 - Path: /dev/sda
```

This default filtering focuses on devices typically used for firmware flashing.

### Show All Devices

Use the `--all/-a` flag to show all connected USB devices:

```bash
# Show all USB devices (bypass filtering)
glovebox firmware devices --all
glovebox firmware devices -a
```

**Output:**
```
✓ Found 92 device(s)
  • MoErgo Glove80_Left (event27) - Serial: moergo.com:GLV80-123456 - VID: 16c0 - PID: 27db - Path: /dev/input/event27
  • Kingston DataTraveler_3.0 (sda) - Serial: E0D55E6C38BBF71098310774 - VID: 0951 - PID: 1666 - Path: /dev/sda
  • Ploopy_Corporation Ploopy_Adept_Trackball (mouse1) - Serial: - VID: 5043 - PID: 5c47 - Path: /dev/input/mouse1
  • [... 89 more devices ...]
```

### Output Formats

Choose different output formats for various use cases:

```bash
# Default text output
glovebox firmware devices --all

# JSON output for scripting
glovebox firmware devices --all --output-format json

# Table format for structured view
glovebox firmware devices --all --output-format table
```

## Device Querying

### Query Syntax

Use the `--query/-q` flag with flexible pattern matching:

```bash
# Basic syntax
glovebox firmware devices --query "property=value"
glovebox firmware devices --query "property~=pattern"
```

### Query Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `=` | Exact match | `removable=true` |
| `~=` | Regex/pattern match | `serial~=.*BBF.*` |
| `and` | Logical AND | `removable=true and vendor~=Kingston` |
| `or` | Logical OR | `subsystem=input or subsystem=block` |
| `not` | Logical NOT | `not removable=false` |

### Queryable Properties

You can query devices by these properties:

- **`removable`** - true/false for removable devices
- **`serial`** - Device serial number
- **`vendor`** - Vendor name or ID
- **`model`** - Model name
- **`name`** - Device name/description
- **`subsystem`** - Device subsystem (input, block, usb, etc.)
- **`device_type`** - Device type (usb_input, usb_storage, etc.)
- **`path`** - Device node path
- **`vendor_id`** - USB vendor ID
- **`product_id`** - USB product ID

## Common Query Examples

### By Device Type

```bash
# All removable devices (explicit)
glovebox firmware devices --query "removable=true"

# All non-removable devices
glovebox firmware devices --query "removable=false" --all

# All input devices (keyboards, mice)
glovebox firmware devices --query "subsystem=input" --all

# All storage devices
glovebox firmware devices --query "subsystem=block" --all
```

### By Vendor/Model/IDs

```bash
# Devices from specific vendor
glovebox firmware devices --query "vendor~=MoErgo" --all
glovebox firmware devices --query "vendor~=Kingston" --all

# By USB Vendor ID (VID)
glovebox firmware devices --query "vendor_id=16c0" --all
glovebox firmware devices --query "vendor_id~=0951" --all

# By USB Product ID (PID)
glovebox firmware devices --query "product_id=27db" --all
glovebox firmware devices --query "product_id=1666" --all

# By VID:PID combination
glovebox firmware devices --query "vendor_id=16c0 and product_id=27db" --all

# Specific device models
glovebox firmware devices --query "model~=Glove80" --all
glovebox firmware devices --query "name~=.*Trackball.*" --all
```

### By Serial Number

```bash
# Devices with serial numbers
glovebox firmware devices --query "serial~=.+" --all

# Specific serial pattern
glovebox firmware devices --query "serial~=.*BBF.*" --all
glovebox firmware devices --query "serial~=GLV80-.*" --all

# Exact serial match
glovebox firmware devices --query "serial=E0D55E6C38BBF71098310774" --all
```

### By Device Path

```bash
# Event devices (input events)
glovebox firmware devices --query "path~=.*/event.*" --all

# HID raw devices
glovebox firmware devices --query "path~=.*/hidraw.*" --all

# Block devices
glovebox firmware devices --query "path~=.*/sd.*" --all

# USB bus devices
glovebox firmware devices --query "path~=.*/usb/.*" --all
```

### Complex Queries

```bash
# Removable devices with serial numbers
glovebox firmware devices --query "removable=true and serial~=.+"

# Input devices from specific vendor
glovebox firmware devices --query "subsystem=input and vendor~=MoErgo" --all

# Storage devices excluding partitions
glovebox firmware devices --query "subsystem=block and not name~=.*[0-9]$" --all

# USB devices with specific vendor ID
glovebox firmware devices --query "vendor_id=16C0" --all
```

## Specialized Device Types

### Keyboard Devices

```bash
# All keyboard-related devices
glovebox firmware devices --query "name~=.*[Kk]eyboard.*" --all

# Keyboards in bootloader mode (often HID devices)
glovebox firmware devices --query "subsystem=input and vendor~=.*keyboard.*" --all

# MoErgo keyboards specifically (by vendor name)
glovebox firmware devices --query "vendor~=MoErgo" --all

# MoErgo keyboards by VID (more reliable)
glovebox firmware devices --query "vendor_id=16c0" --all

# Specific keyboard models by VID:PID
glovebox firmware devices --query "vendor_id=16c0 and product_id=27db" --all  # Glove80 normal mode
glovebox firmware devices --query "vendor_id=16c0 and product_id=27da" --all  # Glove80 bootloader mode

# QMK/ZMK keyboards (common VIDs)
glovebox firmware devices --query "vendor_id=feed" --all  # QMK default
glovebox firmware devices --query "vendor_id=239a" --all  # Adafruit boards
```

### Mouse and Pointing Devices

```bash
# All mice and pointing devices
glovebox firmware devices --query "name~=.*[Mm]ouse.*" --all
glovebox firmware devices --query "name~=.*[Tt]rackball.*" --all

# Mouse event interfaces
glovebox firmware devices --query "path~=.*/mouse.*" --all
```

### Storage and Firmware Targets

```bash
# Removable storage (firmware targets)
glovebox firmware devices --query "removable=true and subsystem=block"

# USB flash drives specifically
glovebox firmware devices --query "removable=true and vendor~=Kingston"
glovebox firmware devices --query "removable=true and model~=.*DataTraveler.*"

# Devices suitable for flashing
glovebox firmware devices --query "removable=true and serial~=.+"
```

## Integration with Flashing

### Device Selection for Flashing

The devices command integrates with firmware flashing:

```bash
# List devices, then flash by vendor name
glovebox firmware devices --query "vendor~=MoErgo"
glovebox firmware flash firmware.uf2 --query "vendor~=MoErgo" --profile glove80

# Use VID for reliable vendor identification
glovebox firmware devices --query "vendor_id=16c0"
glovebox firmware flash firmware.uf2 --query "vendor_id=16c0" --profile glove80

# Target specific keyboard model by VID:PID
glovebox firmware devices --query "vendor_id=16c0 and product_id=27db"
glovebox firmware flash firmware.uf2 --query "vendor_id=16c0 and product_id=27db" --profile glove80

# Wait for bootloader mode (different PID)
glovebox firmware flash firmware.uf2 --query "vendor_id=16c0 and product_id=27da" --profile glove80 --wait

# Use serial for precise targeting
glovebox firmware devices --query "serial~=GLV80-.*"
glovebox firmware flash firmware.uf2 --query "serial~=GLV80-.*" --profile glove80
```

### Profile-Based Device Queries

Profiles can define default device queries:

```bash
# Use profile's default device query
glovebox firmware devices --profile glove80

# Override profile query
glovebox firmware devices --profile glove80 --query "serial~=.*specific.*"
```

## Practical Workflows

### Development Workflow

```bash
# 1. Check all connected devices
glovebox firmware devices --all

# 2. Identify target keyboards
glovebox firmware devices --query "vendor~=MoErgo"

# 3. Monitor specific device
glovebox firmware devices --query "serial=GLV80-123456"

# 4. Flash firmware to specific device
glovebox firmware flash firmware.uf2 --query "serial=GLV80-123456" --profile glove80
```

### Troubleshooting Workflow

```bash
# 1. Check if device is detected
glovebox firmware devices --all | grep -i keyboard

# 2. Verify device properties
glovebox firmware devices --query "vendor~=MoErgo" --output-format json

# 3. Test device accessibility
glovebox firmware devices --query "path~=/dev/input/event.*" --all

# 4. Check device permissions
ls -la /dev/input/event*
```

### Multi-Device Management

```bash
# List all keyboards for batch operations
glovebox firmware devices --query "subsystem=input and name~=.*keyboard.*" --all

# Find devices by manufacturer for team standardization
glovebox firmware devices --query "vendor~=MoErgo" --all

# Monitor removable devices for security
glovebox firmware devices --query "removable=true" --output-format json
```

## Advanced Features

### Device Monitoring

While the devices command provides snapshots, you can monitor device changes:

```bash
# Monitor device connections in scripts
while true; do
  echo "$(date): Device count: $(glovebox firmware devices --all --output-format json | jq '.device_count')"
  sleep 5
done

# Watch for specific device connections
watch -n 2 'glovebox firmware devices --query "vendor~=MoErgo"'
```

### Scripting Integration

```bash
# Extract device information for scripts
DEVICE_SERIAL=$(glovebox firmware devices --query "vendor~=MoErgo" --output-format json | jq -r '.devices[0].serial')

# Count devices by type
INPUT_COUNT=$(glovebox firmware devices --query "subsystem=input" --all --output-format json | jq '.device_count')

# Generate device reports
glovebox firmware devices --all --output-format json > device_report_$(date +%Y%m%d).json
```

### Filtering and Processing

```bash
# Combine with system tools
glovebox firmware devices --all --output-format json | jq '.devices[] | select(.vendor | contains("MoErgo"))'

# Create device inventory
glovebox firmware devices --all --output-format json | jq -r '.devices[] | "\(.vendor) \(.model) - \(.serial)"' | sort
```

## Troubleshooting

### Common Issues

#### No Devices Found
```bash
# Check USB subsystem
lsusb

# Verify permissions
groups $USER | grep -E "(input|disk|storage)"

# Check udev rules
ls -la /etc/udev/rules.d/
```

#### Device Not Detected
```bash
# Force USB rescan
sudo udevadm trigger

# Check device in bootloader mode
glovebox firmware devices --query "subsystem=input" --all

# Verify cable and connection
dmesg | tail -20
```

#### Permission Errors
```bash
# Add user to required groups (Linux)
sudo usermod -aG input,disk,storage $USER

# Check device permissions
ls -la /dev/sda /dev/input/event*

# Fix SELinux context (if applicable)
sudo restorecon -v /dev/sda
```

### Debugging Commands

```bash
# Verbose device information
glovebox firmware devices --all --output-format json | jq '.'

# System-level USB information
lsusb -v
udevadm info --query=all --name=/dev/sda

# Check Glovebox device detection
glovebox status --verbose
```

## Best Practices

### 1. Use Specific Queries
```bash
# Good: Specific device targeting
glovebox firmware devices --query "serial=GLV80-123456"

# Avoid: Overly broad queries
glovebox firmware devices --query "name~=.*"
```

### 2. Combine with Profiles
```bash
# Leverage profile-specific settings
glovebox firmware devices --profile glove80

# Override when needed
glovebox firmware devices --profile glove80 --query "serial~=.*test.*"
```

### 3. Use Appropriate Output Formats
```bash
# Human reading: default text
glovebox firmware devices

# Automation: JSON
glovebox firmware devices --output-format json

# Data analysis: table
glovebox firmware devices --all --output-format table
```

### 4. Security Considerations
```bash
# Monitor for unauthorized devices
glovebox firmware devices --query "removable=true" --output-format json > security_check.json

# Verify device identity before flashing
glovebox firmware devices --query "serial=expected_serial" | grep -q "expected_vendor"
```

### 5. Document Device Configurations
```bash
# Create device inventory
echo "# Device Inventory - $(date)" > device_inventory.md
glovebox firmware devices --all --output-format json | jq -r '.devices[] | "- \(.vendor) \(.model) (\(.serial))"' >> device_inventory.md
```

---

*Device management is essential for reliable firmware development and deployment. Understanding these commands and query patterns will help you efficiently work with USB devices in your ZMK development workflow.*