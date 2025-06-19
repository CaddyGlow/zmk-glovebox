# WSL2 Flash Debugging Tools

This directory contains debugging utilities for WSL2 flash operations in glovebox.

## Scripts

### `debug_wsl2_flash.py`
Comprehensive debugging CLI for WSL2 flash functionality.

### `debug-wsl2` 
Bash wrapper script for easier execution.

## Usage

### Basic Commands

```bash
# Show environment and WSL2 detection info
./scripts/debug-wsl2 env

# List all removable USB devices 
./scripts/debug-wsl2 list-devices

# Test path conversion utilities
./scripts/debug-wsl2 test-paths

# Test PowerShell interop functionality
./scripts/debug-wsl2 test-powershell

# Test WSL2 flash adapter initialization
./scripts/debug-wsl2 test-adapter

# Diagnose drive mounting issues
./scripts/debug-wsl2 diagnose-drive

# Mock firmware flash operation
./scripts/debug-wsl2 mock-flash /path/to/firmware.uf2

# Show help
./scripts/debug-wsl2 help
```

### Alternative Usage

```bash
# Direct Python execution
python3 scripts/debug_wsl2_flash.py env

# With uv
uv run python scripts/debug_wsl2_flash.py env
```

## Command Details

### `env`
Shows comprehensive environment information:
- Platform detection (Linux/Windows/macOS)
- WSL2 detection via `/proc/version`
- Tool availability (`wslpath`, `powershell.exe`, `cmd.exe`)

**Example Output:**
```
============================================================
 Environment Information
============================================================
Platform: Linux
WSL2 Detected: True
Proc Version: Linux version 5.15.0-microsoft-standard-WSL2

----------------------------------------
 Tool Availability  
----------------------------------------
wslpath: ✓ Available
powershell.exe: ✓ Available
cmd.exe: ✓ Available
```

### `list-devices`
Discovers and lists USB storage devices:
- Uses PowerShell WMI queries to find removable drives
- Shows drive details (caption, volume name, size, filesystem)
- Tests path conversion for each drive
- Lists physical USB devices

**Example Output:**
```
============================================================
 Removable USB Devices
============================================================

Found 1 removable drive(s):

  Drive 1:
    Caption: E:
    Volume Name: GLV80RHBOOT
    Size: 16777216 bytes
    Free Space: 12582912 bytes
    File System: FAT32
    WSL2 Path: /mnt/e/
    Accessible: ✓
```

### `test-paths`
Tests bidirectional path conversion:
- Windows paths → WSL2 paths
- WSL2 paths → Windows paths  
- Round-trip conversion validation

**Example Output:**
```
----------------------------------------
 Testing: USB drive E
----------------------------------------
Input: E:\
Windows → WSL: /mnt/e/
Round-trip: E:\
✓ Round-trip successful
```

### `test-powershell`
Validates PowerShell interop functionality:
- Basic echo commands
- Date/time operations
- WMI queries
- JSON output parsing
- Performance timing

### `test-adapter`
Tests WSL2FlashOS adapter:
- Adapter initialization
- Device path conversion
- Mock device mounting
- Error handling validation

### `diagnose-drive`
Comprehensive drive mounting diagnostics:
- Detects all removable drives via PowerShell
- Tests PowerShell accessibility for each drive
- Tests wslpath conversion for each drive
- Verifies WSL2 path accessibility
- Provides specific troubleshooting recommendations
- Suggests manual mounting commands if needed

**Example Output:**
```
Drive 1: E:
  Volume Name: BACKUP02
  Size: 30927880192 bytes
  File System: FAT32
  PowerShell Accessible: ✓
  wslpath Conversion: ✗
  Fallback Path: /mnt/e/
  Fallback Accessible: ✗

Recommendations:
  • wslpath command fails for this drive
  • This may indicate the drive is not properly mounted in WSL2
  • Try running: sudo mount -t drvfs E: /mnt/e (replace E: with your drive letter)
```

### `mock-flash`
Simulates complete firmware flash operation:
- File validation
- Device detection
- File copying
- Filesystem sync
- Device unmounting

**Usage:**
```bash
# Create a test firmware file
echo "mock firmware content" > /tmp/test_firmware.uf2

# Run mock flash
./scripts/debug-wsl2 mock-flash /tmp/test_firmware.uf2
```

## Troubleshooting

### WSL2 Not Detected
If WSL2 detection fails:
1. Verify you're running inside WSL2 (not WSL1)
2. Check `/proc/version` contains "microsoft"
3. Ensure Windows interop is enabled

### PowerShell Not Available
If PowerShell commands fail:
1. Verify Windows interop is enabled: `cat /proc/sys/fs/binfmt_misc/WSLInterop`
2. Try running: `powershell.exe -Command "echo test"`
3. Check WSL2 configuration

### Path Conversion Errors
If `wslpath` fails:
1. Ensure `wslpath` is available: `which wslpath`
2. Test manually: `wslpath -u "C:\\"`
3. Verify WSL2 is properly configured

### No Devices Found
If no USB devices are detected:
1. Ensure USB devices are attached to Windows host
2. Check if devices are mounted in Windows
3. Verify PowerShell WMI queries work: `powershell.exe -Command "Get-WmiObject Win32_LogicalDisk"`

## Development

### Adding New Tests
To add new debugging functionality:

1. Create a new `cmd_*()` function
2. Add command parsing in `main()`
3. Update help documentation
4. Test thoroughly

### Error Handling
All commands should:
- Handle missing tools gracefully
- Provide informative error messages
- Include timing information for performance analysis
- Log both success and failure cases

## Integration

This debugging script integrates with the main glovebox WSL2 flash functionality:
- Uses same adapter classes and utilities
- Tests actual code paths used in production
- Validates environment before attempting operations
- Provides actionable troubleshooting information