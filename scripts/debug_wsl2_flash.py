#!/usr/bin/env python3
"""
WSL2 Flash Debugging CLI Script

This script provides debugging utilities for WSL2 flash operations,
allowing you to test device detection, path conversion, and flash adapter functionality.

Usage:
    python scripts/debug_wsl2_flash.py [command]

Commands:
    env                    - Show environment information
    list-devices          - List all removable USB devices
    test-paths            - Test path conversion utilities
    test-powershell       - Test PowerShell interop
    test-adapter          - Test WSL2 flash adapter
    mock-flash <file>     - Mock firmware flash operation
    help                  - Show this help message
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import after path setup to avoid E402 linting issues
from glovebox.firmware.flash.models import BlockDevice  # noqa: E402
from glovebox.firmware.flash.os_adapters import (  # noqa: E402
    WSL2FlashOS,
    is_wsl2,
    windows_to_wsl_path,
    wsl_to_windows_path,
)


def print_header(title: str) -> None:
    """Print a formatted header."""
    print(f"\n{'=' * 60}")
    print(f" {title}")
    print(f"{'=' * 60}")


def print_section(title: str) -> None:
    """Print a formatted section header."""
    print(f"\n{'-' * 40}")
    print(f" {title}")
    print(f"{'-' * 40}")


def cmd_env() -> None:
    """Show environment information."""
    print_header("Environment Information")

    import platform
    print(f"Platform: {platform.system()}")
    print(f"Platform Version: {platform.version()}")
    print(f"Architecture: {platform.architecture()}")
    print(f"Machine: {platform.machine()}")

    print_section("WSL2 Detection")
    wsl2_detected = is_wsl2()
    print(f"WSL2 Detected: {wsl2_detected}")

    if wsl2_detected:
        try:
            with Path("/proc/version").open() as f:
                proc_version = f.read().strip()
            print(f"Proc Version: {proc_version}")
        except Exception as e:
            print(f"Error reading /proc/version: {e}")

    print_section("Tool Availability")
    tools = ["wslpath", "powershell.exe", "cmd.exe"]
    for tool in tools:
        try:
            result = subprocess.run([tool, "--help"], capture_output=True, timeout=5)
            available = result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            available = False
        print(f"{tool}: {'✓ Available' if available else '✗ Not Available'}")


def cmd_list_devices() -> None:
    """List all removable USB devices."""
    print_header("Removable USB Devices")

    print_section("PowerShell Device Query")
    try:
        ps_command = (
            "Get-WmiObject -Class Win32_LogicalDisk | "
            "Where-Object {$_.DriveType -eq 2} | "
            "Select-Object Caption, VolumeName, Size, FreeSpace, FileSystem | "
            "ConvertTo-Json"
        )

        result = subprocess.run(
            ["powershell.exe", "-Command", ps_command],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        )

        if not result.stdout.strip():
            print("No removable drives found.")
            return

        drives_data = json.loads(result.stdout)
        if isinstance(drives_data, dict):
            drives_data = [drives_data]

        print(f"Found {len(drives_data)} removable drive(s):")

        for i, drive in enumerate(drives_data, 1):
            print(f"\n  Drive {i}:")
            print(f"    Caption: {drive.get('Caption', 'N/A')}")
            print(f"    Volume Name: {drive.get('VolumeName', 'N/A')}")
            print(f"    Size: {drive.get('Size', 'N/A')} bytes")
            print(f"    Free Space: {drive.get('FreeSpace', 'N/A')} bytes")
            print(f"    File System: {drive.get('FileSystem', 'N/A')}")

            # Test path conversion
            drive_letter = drive.get('Caption', '')
            if drive_letter:
                try:
                    wsl_path = windows_to_wsl_path(drive_letter + "\\")
                    print(f"    WSL2 Path: {wsl_path}")

                    # Test accessibility
                    accessible = Path(wsl_path).exists()
                    print(f"    Accessible: {'✓' if accessible else '✗'}")
                except Exception as e:
                    print(f"    Path Conversion Error: {e}")

    except subprocess.CalledProcessError as e:
        print(f"PowerShell command failed: {e}")
        print(f"Error output: {e.stderr}")
    except subprocess.TimeoutExpired:
        print("PowerShell command timed out")
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON output: {e}")
        print(f"Raw output: {result.stdout}")
    except Exception as e:
        print(f"Unexpected error: {e}")

    print_section("Physical USB Devices")
    try:
        ps_command = (
            "Get-WmiObject -Class Win32_DiskDrive | "
            "Where-Object {$_.InterfaceType -eq 'USB'} | "
            "Select-Object Caption, Model, Size, MediaType | "
            "ConvertTo-Json"
        )

        result = subprocess.run(
            ["powershell.exe", "-Command", ps_command],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        )

        if result.stdout.strip():
            usb_devices = json.loads(result.stdout)
            if isinstance(usb_devices, dict):
                usb_devices = [usb_devices]

            print(f"Found {len(usb_devices)} USB device(s):")
            for i, device in enumerate(usb_devices, 1):
                print(f"\n  USB Device {i}:")
                print(f"    Caption: {device.get('Caption', 'N/A')}")
                print(f"    Model: {device.get('Model', 'N/A')}")
                print(f"    Size: {device.get('Size', 'N/A')} bytes")
                print(f"    Media Type: {device.get('MediaType', 'N/A')}")
        else:
            print("No USB storage devices found.")

    except Exception as e:
        print(f"USB device query failed: {e}")


def cmd_test_paths() -> None:
    """Test path conversion utilities."""
    print_header("Path Conversion Testing")

    test_paths = [
        ("C:\\", "Basic C drive"),
        ("E:\\", "USB drive E"),
        ("D:\\folder\\file.txt", "File path"),
        ("/mnt/c/", "WSL2 C mount"),
        ("/mnt/e/firmware.uf2", "WSL2 firmware file"),
        ("/home/user/test.txt", "Linux path"),
    ]

    for test_path, description in test_paths:
        print_section(f"Testing: {description}")
        print(f"Input: {test_path}")

        if test_path.startswith("/"):
            # WSL to Windows conversion
            try:
                converted = wsl_to_windows_path(test_path)
                print(f"WSL → Windows: {converted}")

                # Try reverse conversion
                try:
                    back_converted = windows_to_wsl_path(converted)
                    print(f"Round-trip: {back_converted}")
                    if back_converted == test_path:
                        print("✓ Round-trip successful")
                    else:
                        print("✗ Round-trip failed")
                except Exception as e:
                    print(f"✗ Reverse conversion failed: {e}")

            except Exception as e:
                print(f"✗ WSL → Windows conversion failed: {e}")
        else:
            # Windows to WSL conversion
            try:
                converted = windows_to_wsl_path(test_path)
                print(f"Windows → WSL: {converted}")

                # Try reverse conversion
                try:
                    back_converted = wsl_to_windows_path(converted)
                    print(f"Round-trip: {back_converted}")
                    if back_converted == test_path:
                        print("✓ Round-trip successful")
                    else:
                        print("✗ Round-trip failed")
                except Exception as e:
                    print(f"✗ Reverse conversion failed: {e}")

            except Exception as e:
                print(f"✗ Windows → WSL conversion failed: {e}")


def cmd_test_powershell() -> None:
    """Test PowerShell interop."""
    print_header("PowerShell Interop Testing")

    tests = [
        ("echo 'Hello WSL2'", "Basic echo test"),
        ("Get-Date", "Get current date"),
        ("$PSVersionTable | ConvertTo-Json", "PowerShell version info"),
        ("Test-Path 'C:\\'", "Test path accessibility"),
        ("Get-WmiObject -Class Win32_ComputerSystem | Select-Object Name | ConvertTo-Json", "WMI test"),
    ]

    for command, description in tests:
        print_section(description)
        print(f"Command: {command}")

        try:
            start_time = time.time()
            result = subprocess.run(
                ["powershell.exe", "-Command", command],
                capture_output=True,
                text=True,
                timeout=10,
            )
            duration = time.time() - start_time

            print(f"Duration: {duration:.2f}s")
            print(f"Return Code: {result.returncode}")

            if result.stdout:
                print(f"Output: {result.stdout.strip()}")
            if result.stderr:
                print(f"Error: {result.stderr.strip()}")

            if result.returncode == 0:
                print("✓ Success")
            else:
                print("✗ Failed")

        except subprocess.TimeoutExpired:
            print("✗ Timeout")
        except Exception as e:
            print(f"✗ Exception: {e}")


def cmd_test_adapter() -> None:
    """Test WSL2 flash adapter."""
    print_header("WSL2 Flash Adapter Testing")

    print_section("Adapter Initialization")
    try:
        adapter = WSL2FlashOS()
        print("✓ WSL2FlashOS adapter created successfully")
    except Exception as e:
        print(f"✗ Failed to create adapter: {e}")
        return

    print_section("Device Path Testing")
    test_device_names = ["E:", "F:", "sda", "disk1"]
    for device_name in test_device_names:
        try:
            device_path = adapter.get_device_path(device_name)
            print(f"{device_name} → {device_path}")
        except Exception as e:
            print(f"✗ {device_name} failed: {e}")

    print_section("Mock Device Mount Test")
    # Create a mock BlockDevice for testing
    mock_device = BlockDevice(
        name="test_device",
        device_node="/dev/test",
        label="TEST_DEVICE",
        type="usb",
        removable=True,
    )

    try:
        mount_points = adapter.mount_device(mock_device)
        print(f"Mock device mount points: {mount_points}")

        if mount_points:
            print("✓ Found mount points")
            for mp in mount_points:
                accessible = Path(mp).exists()
                print(f"  {mp}: {'✓ Accessible' if accessible else '✗ Not accessible'}")
        else:
            print("No mount points found (expected if no removable drives)")

    except Exception as e:
        print(f"✗ Mount test failed: {e}")


def cmd_mock_flash(firmware_file: str) -> None:
    """Mock firmware flash operation."""
    print_header(f"Mock Flash Operation: {firmware_file}")

    firmware_path = Path(firmware_file)
    if not firmware_path.exists():
        print(f"✗ Firmware file not found: {firmware_file}")
        return

    print(f"Firmware file: {firmware_path}")
    print(f"File size: {firmware_path.stat().st_size} bytes")

    print_section("Adapter Initialization")
    try:
        adapter = WSL2FlashOS()
        print("✓ WSL2FlashOS adapter created")
    except Exception as e:
        print(f"✗ Failed to create adapter: {e}")
        return

    print_section("Device Detection")
    mock_device = BlockDevice(
        name="mock_flash_device",
        device_node="/dev/mock",
        label="MOCK_FLASH",
        type="usb",
        removable=True,
    )

    try:
        mount_points = adapter.mount_device(mock_device)
        print(f"Available mount points: {mount_points}")

        if not mount_points:
            print("✗ No mount points available for mock flash")
            return

        # Use the first mount point
        mount_point = mount_points[0]
        print(f"Using mount point: {mount_point}")

        print_section("Mock File Copy")
        success = adapter.copy_firmware_file(firmware_path, mount_point)
        if success:
            print("✓ Mock firmware copy successful")

            print_section("File System Sync")
            sync_success = adapter.sync_filesystem(mount_point)
            if sync_success:
                print("✓ File system sync successful")
            else:
                print("✗ File system sync failed")

            print_section("Device Unmount")
            unmount_success = adapter.unmount_device(mock_device)
            if unmount_success:
                print("✓ Device unmount successful")
            else:
                print("✗ Device unmount failed")
        else:
            print("✗ Mock firmware copy failed")

    except Exception as e:
        print(f"✗ Mock flash operation failed: {e}")


def cmd_help() -> None:
    """Show help message."""
    print(__doc__)


def main() -> None:
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        cmd_help()
        return

    command = sys.argv[1].lower()

    if command == "env":
        cmd_env()
    elif command == "list-devices":
        cmd_list_devices()
    elif command == "test-paths":
        cmd_test_paths()
    elif command == "test-powershell":
        cmd_test_powershell()
    elif command == "test-adapter":
        cmd_test_adapter()
    elif command == "mock-flash":
        if len(sys.argv) < 3:
            print("Error: mock-flash requires a firmware file path")
            print("Usage: python debug_wsl2_flash.py mock-flash /path/to/firmware.uf2")
            return
        cmd_mock_flash(sys.argv[2])
    elif command == "help":
        cmd_help()
    else:
        print(f"Unknown command: {command}")
        cmd_help()


if __name__ == "__main__":
    main()
