#!/usr/bin/env python3
"""
## Flashing procedure

The bootloader mode is activated by holding down the reset button while plugging in the USB cable.

The device will show up as a USB mass storage device.

We should wait for the device to show up as a USB mass storage device before flashing the
firmware file.

To flash the firmware file, we should copy the firmware file to the USB mass storage device.

For that we will mount the USB mass storage with `gio` and copy the firmware file to it.

The device disconnects quickly after flashing the firmware file so we may not unmount properly.

We repeat the step with the second part of the device.

```
[242930.757646] usb 1-6.4: new full-speed USB device number 11 using xhci_hcd
[242930.844467] usb 1-6.4: New USB device found, idVendor=239a, idProduct=0029, bcdDevice= 1.00
[242930.844475] usb 1-6.4: New USB device strings: Mfr=1, Product=2, SerialNumber=3
[242930.844479] usb 1-6.4: Product: Glove80 LH Bootloader
[242930.844482] usb 1-6.4: Manufacturer: MoErgo
[242930.844484] usb 1-6.4: SerialNumber: GLV80-99287219E27D6FC3
[242930.857090] cdc_acm 1-6.4:1.0: ttyACM0: USB ACM device
[242930.857494] usb-storage 1-6.4:1.2: USB Mass Storage device detected
[242930.858028] scsi host8: usb-storage 1-6.4:1.2
[242931.904692] scsi host8: scsi scan: INQUIRY result too short (5), using 36
[242931.904704] scsi 8:0:0:0: Direct-Access     Adafruit nRF UF2          1.0  PQ: 0 ANSI: 2
[242931.908576] sd 8:0:0:0: [sda] 65801 512-byte logical blocks: (33.7 MB/32.1 MiB)
[242931.908842] sd 8:0:0:0: [sda] Write Protect is off
[242931.908846] sd 8:0:0:0: [sda] Mode Sense: 03 00 00 00
[242931.909089] sd 8:0:0:0: [sda] No Caching mode page found
[242931.909092] sd 8:0:0:0: [sda] Assuming drive cache: write through
[242931.936921]  sda:
[242931.936954] sd 8:0:0:0: [sda] Attached SCSI removable disk
[242959.809710] usb 1-6.4: reset full-speed USB device number 11 using xhci_hcd
[242959.883953] usb 1-6.4: device firmware changed
[242959.884811] usb 1-6.4: USB disconnect, device number 11
```

Second part

```
[242898.835185] usb 1-6.4: Product: Glove80 RH Bootloader
[242898.835187] usb 1-6.4: Manufacturer: MoErgo
[242898.835189] usb 1-6.4: SerialNumber: GLV80-735A88B1887FDE8B
[242898.867504] cdc_acm 1-6.4:1.0: ttyACM0: USB ACM device
[242898.867516] usbcore: registered new interface driver cdc_acm
[242898.867517] cdc_acm: USB Abstract Control Model driver for USB modems and ISDN adapters
[242898.868754] usb-storage 1-6.4:1.2: USB Mass Storage device detected
[242898.868864] scsi host8: usb-storage 1-6.4:1.2
[242898.868934] usbcore: registered new interface driver usb-storage
[242898.870670] usbcore: registered new interface driver uas
[242899.905891] scsi host8: scsi scan: INQUIRY result too short (5), using 36
[242899.905903] scsi 8:0:0:0: Direct-Access     Adafruit nRF UF2          1.0  PQ: 0 ANSI: 2
[242899.921888] sd 8:0:0:0: [sda] 65801 512-byte logical blocks: (33.7 MB/32.1 MiB)
[242899.922167] sd 8:0:0:0: [sda] Write Protect is off
[242899.922170] sd 8:0:0:0: [sda] Mode Sense: 03 00 00 00
[242899.922466] sd 8:0:0:0: [sda] No Caching mode page found
[242899.922468] sd 8:0:0:0: [sda] Assuming drive cache: write through
[242899.949218]  sda:
[242899.949247] sd 8:0:0:0: [sda] Attached SCSI removable disk
```

```
Every 1.0s: lsblk --raw -O --paths && ls -l /dev/disk/by-id/                                                                             culixa: Fri Apr  4 10:12:54 2025

ALIGNMENT ID-LINK ID DISC-ALN DAX DISC-GRAN DISK-SEQ DISC-MAX DISC-ZERO FSAVAIL FSROOTS FSSIZE FSTYPE FSUSED FSUSE% FSVER GROUP HCTL HOTPLUG KNAME LABEL LOG-SEC MAJ:MIN
MAJ MIN MIN-IO MODE MODEL MQ NAME OPT-IO OWNER PARTFLAGS PARTLABEL PARTN PARTTYPE PARTTYPENAME PARTUUID PATH PHY-SEC PKNAME PTTYPE PTUUID RA RAND REV RM RO ROTA RQ-SIZE
SCHED SERIAL SIZE START STATE SUBSYSTEMS MOUNTPOINT MOUNTPOINTS TRAN TYPE UUID VENDOR WSAME WWN ZONED ZONE-SZ ZONE-WGRAN ZONE-APP ZONE-NR ZONE-OMAX ZONE-AMAX
0 usb-Adafruit_nRF_UF2_GLV80-735A88B1887FDE8B-0:0 Adafruit_nRF_UF2_GLV80-735A88B1887FDE8B-0:0 0 0 512B 17 0B 0    vfat   FAT16 disk 8:0:0:0 1 /dev/sda GLV80RHBOOT 512 8:
0 8 0 512 brw-rw---- nRF\x20UF2 \x20\x201 /dev/sda 0 root       /dev/sda 512    128 1 1.0 1 0 1 2 mq-deadline GLV80-735A88B1887FDE8B 32.1M  running block:scsi:usb:pci
usb disk 0042-0042 Adafruit 0B  none 0B 0B 0B 0 0 0
```

- ID-LINK: usb-Adafruit_nRF_UF2_GLV80-735A88B1887FDE8B-0:0
- ID: Adafruit_nRF_UF2_GLV80-735A88B1887FDE8B-0:0
- LABEL: GLV80RHBOOT
- MODEL: nRF\x20UF2\x20\x201
- NAME: /dev/sda
- PATH: /dev/sda
- SERIAL: GLV80-735A88B1887FDE8B
- STATE: running
- UUID: 0042-0042
- VENDOR: Adafruit
"""

import os
import sys
import time
import subprocess
import re
import shutil
import json

import logging

logger = logging.getLogger(__name__)


def parse_query(query_str):
    """
    Parse a query string into a list of conditions.

    Format: "field1=value1 and field2!=value2 and field3~=regex_pattern"

    Returns:
        List of tuples: [(field, operator, value), ...]
    """
    conditions = []
    parts = query_str.split(" and ")

    for part in parts:
        part = part.strip()
        if "!=" in part:
            field, value = part.split("!=", 1)
            conditions.append((field.strip(), "!=", value.strip()))
        elif "~=" in part:
            field, value = part.split("~=", 1)
            conditions.append((field.strip(), "~=", value.strip()))
        elif "=" in part:
            field, value = part.split("=", 1)
            conditions.append((field.strip(), "=", value.strip()))
        else:
            raise ValueError(f"Invalid query condition: {part}")

    return conditions


def evaluate_condition(device, field, operator, value):
    """
    Evaluate a single condition against a device.

    Args:
        device: Device dictionary
        field: Field name to check
        operator: One of "=", "!=", "~="
        value: Value to compare against

    Returns:
        Boolean indicating if the condition is met
    """
    # Get the device value, convert to lowercase string for comparison
    device_value = str(device.get(field.lower(), "")).lower()
    value = value.lower()

    if operator == "=":
        return device_value == value
    elif operator == "!=":
        return device_value != value
    elif operator == "~=":
        return bool(re.search(value, device_value))

    return False


def get_devices_json():
    """Get device information using lsblk JSON output format"""
    result = subprocess.run(
        ["lsblk", "--json", "-O", "--paths"],
        capture_output=True,
        text=True,
        check=True,
    )
    devices_data = json.loads(result.stdout)
    logger.debug(f"get_devices_json: {devices_data.get('blockdevices', [])}")
    return devices_data.get("blockdevices", [])


def get_devices_raw():
    """
    Get device information using lsblk raw output format (optimized).
    Handles consecutive spaces as delimiters.
    """
    try:
        # Ensure text=True and specify encoding for consistent string handling
        result = subprocess.run(
            ["lsblk", "--raw", "-O", "--paths"],
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",  # Explicitly set encoding
        )
    except FileNotFoundError:
        print("Error: 'lsblk' command not found. Is it installed and in PATH?")
        return []
    except subprocess.CalledProcessError as e:
        # Provide more context on error
        print(f"Error running lsblk: {e}")
        print(f"Stderr: {e.stderr}")
        return []
    except Exception as e:
        # Catch other potential errors during subprocess execution
        print(f"An unexpected error occurred: {e}")
        return []

    lines = (
        result.stdout.strip().splitlines()
    )  # strip() removes leading/trailing whitespace
    if not lines or len(lines) < 2:  # Need at least a header and one data line
        return []

    # Header Parsing
    # Use regex to handle potential multiple spaces between headers robustly
    # Headers might start with spaces depending on the 'lsblk' version/output,
    # so strip the line first.
    header_line = lines[0].strip()
    headers = [h.lower() for h in re.split(r"\s+", header_line)]
    num_headers = len(headers)
    if num_headers == 0:
        return []  # No headers found

    # Data Line Parsing
    devices = []
    for line in lines[1:]:
        values = {}
        current_field_start = 0
        header_index = 0
        line_len = len(line)  # Cache length for minor optimization

        # Iterate through the line character by character with index
        for i, char in enumerate(line):
            if char == " ":
                # Found a delimiter (space)
                if (
                    header_index < num_headers
                ):  # Avoid index error if line has too many fields
                    # Extract the field based on start index and current position
                    field_value = line[current_field_start:i].strip()
                    # Assign None if field is empty after stripping, else the value
                    values[headers[header_index]] = field_value if field_value else None
                header_index += 1
                # Next field starts after this space
                current_field_start = i + 1

        # Handle the last field
        # After the loop, the remaining part of the string is the last field
        if header_index < num_headers:
            # Check if there are any characters left for the last field
            if current_field_start <= line_len:
                # Slice from the start of the last field to the end of the line
                field_value = line[current_field_start:line_len].strip()
                values[headers[header_index]] = field_value if field_value else None
            else:
                # This happens if the line ends with one or more spaces
                # The last field(s) are effectively empty
                values[headers[header_index]] = None
            header_index += 1

        # Fill missing trailing fields
        # If the line had fewer fields (e.g., ended with multiple spaces)
        # than headers, fill the remaining ones with None.
        while header_index < num_headers:
            values[headers[header_index]] = None
            header_index += 1

        # Optional: Add only if the number of parsed values matches headers exactly
        # if len(values) == num_headers:
        devices.append(values)
        # else:
        #    print(f"Warning: Field count mismatch for line: {line[:50]}...") # Log mismatch

    return devices


def wait_for_device(query_str, timeout=60):
    """
    Wait for a device matching the query string to appear.

    Args:
        query_str: Query string in format "field1=value1 and field2!=value2 and field3~=regex_pattern"
        timeout: Maximum time to wait in seconds

    Returns:
        Device dictionary if found, raises TimeoutError otherwise
    """
    logger.info(f"Waiting for device matching '{query_str}' to appear...")
    conditions = parse_query(query_str)

    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # Use JSON format if supported, otherwise fall back to raw format
            if False and check_lsblk_version():
                devices = get_devices_json()
            else:
                devices = get_devices_raw()

            for device in devices:
                logger.debug(f"device: {device}")

                # Check if all conditions are met
                all_conditions_met = True
                for field, operator, value in conditions:
                    if not evaluate_condition(device, field, operator, value):
                        all_conditions_met = False
                        break

                if all_conditions_met:
                    logger.info(
                        f"Found device {device.get('path')} {device.get('label')} {device.get('model')} {device.get('serial')}"
                    )
                    return device
        except subprocess.CalledProcessError as e:
            logger.warning(f"Error running lsblk: {e}")
        except Exception as e:
            # logger.warning(f"Unexpected error: {e}")
            raise e

        time.sleep(1)
    raise TimeoutError()


def mount_and_flash(device, firmware_file, max_retries=3, retry_delay=2):
    """
    Mount device and flash firmware with retry logic using udisksctl.

    Args:
        device: Device values dictionary containing path and other info
        firmware_file: Path to firmware file to flash
        max_retries: Maximum number of mount attempts
        retry_delay: Delay between retry attempts in seconds

    Returns:
        Boolean indicating success or failure

    Raises:
        Exception: If critical errors occur during the process
    """
    device_path = device["path"]
    device_label = device.get("label", "Unknown")

    for attempt in range(max_retries):
        try:
            logger.info(
                f"Mounting device {device_path} (attempt {attempt + 1}/{max_retries})..."
            )

            # Mount using udisksctl
            mount_result = subprocess.run(
                ["udisksctl", "mount", "-b", device_path],
                capture_output=True,
                text=True,
            )
            logger.debug(f"Mount result: {mount_result.stdout}")

            # Extract mount point from udisksctl output
            mount_point = None
            if mount_result.returncode == 0 and "at " in mount_result.stdout:
                # Extract mount point from successful mount output
                # Example output: "Mounted /dev/sda at /run/media/user/GLV80RHBOOT"
                mount_point = mount_result.stdout.strip().split("at ")[-1].strip()

            # If mount_point not found from output, try getting info
            if not mount_point:
                logger.debug("Getting mount point from udisksctl info...")
                info_result = subprocess.run(
                    ["udisksctl", "info", "-b", device_path],
                    capture_output=True,
                    text=True,
                    check=True,
                )

                for line in info_result.stdout.splitlines():
                    if "MountPoints:" in line and not "[]" in line:
                        # The next line should contain the mount point
                        mount_point = line.split("MountPoints:")[-1].strip()
                        if not mount_point:
                            # Check next line if split didn't work
                            for i, l in enumerate(info_result.stdout.splitlines()):
                                if "MountPoints:" in l:
                                    possible_mount = info_result.stdout.splitlines()[
                                        i + 1
                                    ].strip()
                                    if possible_mount and not possible_mount.startswith(
                                        "org."
                                    ):
                                        mount_point = possible_mount
                                        break

            if not mount_point:
                logger.warning(f"Could not find mount point for {device_path}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    continue
                return False

            logger.info(f"Device {device_label} mounted at {mount_point}")

            # Copy the firmware file
            logger.info(f"Copying {firmware_file} to {mount_point}")
            shutil.copy2(firmware_file, mount_point)
            logger.info("Firmware flashed successfully")

            # Trying to unmount, but it might fail as the device disconnects quickly
            try:
                logger.debug(f"Attempting to unmount {mount_point}")
                subprocess.run(
                    ["udisksctl", "unmount", "-b", device_path],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                logger.debug("Unmount successful")
            except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
                logger.debug(f"Unmount failed (expected): {e}")

            return True

        except Exception as e:
            logger.error(f"Error during attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logger.error("All mount attempts failed")
                raise Exception(f"Failed to flash firmware: {e}")

    return False


def parse_version(version_str):
    """
    Parse a version string into a tuple of integers

    Args:
        version_str: Version string in format "x.y.z"

    Returns:
        Tuple of integers (x, y, z)
    """
    try:
        return tuple(map(int, version_str.split(".")))
    except (ValueError, AttributeError):
        return (0, 0, 0)  # Return a default version for invalid inputs


def compare_versions(version1, version2):
    """
    Compare two version strings

    Args:
        version1: First version string
        version2: Second version string

    Returns:
        -1 if version1 < version2
         0 if version1 == version2
         1 if version1 > version2
    """
    v1_parts = parse_version(version1)
    v2_parts = parse_version(version2)

    if v1_parts < v2_parts:
        return -1
    elif v1_parts > v2_parts:
        return 1
    else:
        return 0


def check_lsblk_version():
    """
    Check if lsblk version supports JSON output (>= 2.28.2)

    Returns:
        bool: True if supported, False otherwise
    """
    try:
        result = subprocess.run(
            ["lsblk", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )

        # Extract version from output like "lsblk from util-linux 2.38.1"
        version_match = re.search(r"util-linux\s+(\d+\.\d+\.\d+)", result.stdout)
        if version_match:
            version_str = version_match.group(1)
            min_version = "2.28.2"

            # Compare versions
            if compare_versions(version_str, min_version) >= 0:
                logger.debug(f"lsblk version {version_str} supports JSON output")
                return True
            else:
                logger.warning(
                    f"lsblk version {version_str} does not support JSON output (min required: 2.28.2)"
                )
                return False
        else:
            logger.warning("Could not determine lsblk version")
            return False
    except subprocess.CalledProcessError:
        logger.warning("Failed to get lsblk version")
        return False
    except Exception as e:
        logger.warning(f"Unexpected error checking lsblk version: {e}")
        return False


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Flash firmware to the device.")
    parser.add_argument("firmware_file", help="Path to the firmware file")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument(
        "-n",
        "--count",
        type=int,
        help="Number of flashes to perform (default: infinite)",
    )
    parser.add_argument(
        "-q",
        "--query",
        type=str,
        default="label~=GLV80[RL]HBOOT",
        help="Device query string (e.g., 'label~=GLV80[RL]HBOOT and serial!=GLV80-735A88B1887FDE8B')",
    )
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    # Check lsblk version
    if not check_lsblk_version():
        logger.error(
            "This script requires lsblk version 2.28.2 or higher for JSON output support"
        )
        logger.error(
            "Please update util-linux or modify the script to use the raw output format"
        )
        sys.exit(1)

    firmware_file = args.firmware_file
    if not os.path.exists(firmware_file):
        logger.error(f"Firmware file {firmware_file} does not exist")
        sys.exit(1)

    try:
        flash_count = 0
        while args.count is None or flash_count < args.count:
            if args.count is not None:
                logger.info(f"Starting flash {flash_count + 1}/{args.count}")
            else:
                logger.info(f"Starting flash {flash_count + 1} (infinite mode)")

            logger.info("Please connect the keyboard in bootloader mode...")
            device_info = wait_for_device(args.query)
            time.sleep(1)
            if mount_and_flash(device_info, firmware_file):
                logger.info("Flashing completed successfully.")
                flash_count += 1

                if args.count is not None and flash_count >= args.count:
                    logger.info(f"Completed all {args.count} flashes.")
                    break
            else:
                logger.warning("Flashing failed. Retrying...")
    except TimeoutError:
        logger.error("Device not detected within the timeout period.")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # main()
    logging.basicConfig(level=logging.DEBUG)
    get_devices_json()
    get_devices_raw()
