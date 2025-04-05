#!/usr/bin/env python3
"""
## Flashing procedure

The bootloader mode is activated by holding down the reset button while plugging in the USB cable.

The device will show up as a USB mass storage device.

We should wait for the device to show up as a USB mass storage device before flashing the
firmware file.

To flash the firmware file, we should copy the firmware file to the USB mass storage device.

For that we will mount the USB mass storage with `udisksctl` (preferred) or `gio` and copy the firmware file to it.

The device disconnects quickly after flashing the firmware file so we may not unmount properly.

We repeat the step with the second part of the device.

Example device identification using the new lsblk library might rely on fields like:
- name: sda, sdb, disk0, disk1
- model: 'nRF UF2   1.0', 'Product Name'
- vendor: 'Adafruit', 'Vendor Name'
- removable: True
- type: 'disk', 'removable'
"""

import os
import sys
import time
import subprocess
import re
import shutil
import platform
import logging
from typing import List, Tuple, Optional

# Import from the local lsblk module
from .lsblk import get_block_devices, BlockDevice, BlockDeviceError, format_size

logger = logging.getLogger(__name__)


def parse_query(query_str: str) -> List[Tuple[str, str, str]]:
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


def evaluate_condition(
    device: BlockDevice, field: str, operator: str, value: str
) -> bool:
    """
    Evaluate a single condition against a BlockDevice object.

    Args:
        device: BlockDevice object
        field: Field name (attribute) to check
        operator: One of "=", "!=", "~="
        value: Value to compare against

    Returns:
        Boolean indicating if the condition is met
    """
    # Get the device attribute value, convert to lowercase string for comparison
    try:
        device_value = str(getattr(device, field.lower(), "")).lower()
        value = value.lower()

        if operator == "=":
            return device_value == value
        elif operator == "!=":
            return device_value != value
        elif operator == "~=":
            # Use re.IGNORECASE for case-insensitive regex matching
            return bool(re.search(value, device_value, re.IGNORECASE))
        else:
            logger.warning(f"Unsupported operator: {operator}")
            return False
    except AttributeError:
        logger.debug(f"Device {device.name} does not have attribute '{field.lower()}'")
        return False
    except Exception as e:
        logger.error(
            f"Error evaluating condition ({field} {operator} {value}) on device {device.name}: {e}"
        )
        return False


def get_device_path(device_name: str) -> str:
    """Construct the full device path based on the OS."""
    system = platform.system().lower()
    if system == "linux" or system == "darwin":
        return f"/dev/{device_name}"
    elif system == "windows":
        # Windows path might need different handling depending on the tool (udisksctl won't work)
        # For now, just return the name, assuming a Windows-specific tool would be used.
        # This part needs refinement if Windows support is fully implemented for flashing.
        logger.warning("Windows flashing path construction might need adjustment.")
        return device_name
    else:
        logger.warning(f"Unsupported OS for device path construction: {system}")
        return device_name


def wait_for_device(query_str: str, timeout: int = 60) -> BlockDevice:
    """
    Wait for a device matching the query string to appear using the lsblk library.

    Args:
        query_str: Query string in format "field1=value1 and field2!=value2 and field3~=regex_pattern"
                   Uses BlockDevice attributes like 'name', 'model', 'vendor', 'size', 'removable'.
        timeout: Maximum time to wait in seconds

    Returns:
        BlockDevice object if found.

    Raises:
        TimeoutError: If no matching device is found within the timeout.
        BlockDeviceError: If there's an error retrieving block devices.
    """
    logger.info(f"Waiting for device matching '{query_str}' to appear...")
    try:
        conditions = parse_query(query_str)
    except ValueError as e:
        logger.error(f"Invalid query string: {e}")
        raise ValueError(f"Invalid query string: {e}") from e

    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            devices = get_block_devices()
            logger.debug(f"Found {len(devices)} block devices.")

            for device in devices:
                logger.debug(
                    f"Checking device: Name={device.name}, Model='{device.model}', Vendor='{device.vendor}', "
                    f"Size={format_size(device.size)}, Removable={device.removable}, Type={device.type}"
                )

                # Check if all conditions are met
                all_conditions_met = True
                if (
                    not conditions
                ):  # If query is empty, match first removable device? Or require query?
                    all_conditions_met = False  # Require a query for safety

                for field, operator, value in conditions:
                    if not evaluate_condition(device, field, operator, value):
                        all_conditions_met = False
                        break

                if all_conditions_met:
                    logger.info(
                        f"Found matching device: Name={device.name}, Model='{device.model}', Vendor='{device.vendor}'"
                    )
                    return device

        except BlockDeviceError as e:
            logger.warning(f"Error getting block devices: {e}")
            # Don't exit immediately, maybe the error is transient
        except Exception as e:
            logger.error(f"Unexpected error while waiting for device: {e}")
            # Depending on the error, might want to retry or raise
            raise  # Re-raise unexpected errors

        time.sleep(1)

    logger.error(
        f"Timeout: Device matching '{query_str}' not found after {timeout} seconds."
    )
    raise TimeoutError(
        f"Device matching '{query_str}' not found after {timeout} seconds."
    )


def mount_and_flash(
    device: BlockDevice, firmware_file: str, max_retries: int = 3, retry_delay: int = 2
) -> bool:
    """
    Mount device and flash firmware with retry logic using udisksctl.

    Args:
        device: BlockDevice object representing the target device.
        firmware_file: Path to firmware file to flash.
        max_retries: Maximum number of mount attempts.
        retry_delay: Delay between retry attempts in seconds.

    Returns:
        Boolean indicating success or failure.

    Raises:
        Exception: If critical errors occur during the process (e.g., udisksctl not found).
        BlockDeviceError: If the platform is not supported for mounting.
    """
    system = platform.system().lower()
    if system not in ["linux"]:
        # udisksctl is primarily a Linux tool. macOS/Windows need different approaches.
        raise BlockDeviceError(
            f"Automated mounting with udisksctl is not supported on {system}."
        )

    # Construct the full device path (e.g., /dev/sda)
    device_path = get_device_path(device.name)
    device_identifier = (
        f"{device.vendor} {device.model}"
        if device.vendor or device.model
        else device.name
    )

    # Check if udisksctl exists
    if not shutil.which("udisksctl"):
        raise FileNotFoundError(
            "`udisksctl` command not found. Please install udisks2."
        )

    for attempt in range(max_retries):
        mount_point = None
        try:
            logger.info(
                f"Attempt {attempt + 1}/{max_retries}: Mounting device {device_path} ({device_identifier})..."
            )

            # Mount using udisksctl
            mount_result = subprocess.run(
                ["udisksctl", "mount", "--no-user-interaction", "-b", device_path],
                capture_output=True,
                text=True,
                check=False,  # Don't check=True, handle errors manually
                timeout=10,  # Add a timeout
            )
            logger.debug(f"Mount command stdout: {mount_result.stdout}")
            logger.debug(f"Mount command stderr: {mount_result.stderr}")

            if mount_result.returncode != 0:
                # Check stderr for common errors
                if "already mounted" in mount_result.stderr.lower():
                    logger.warning(
                        f"Device {device_path} already mounted. Trying to find mount point."
                    )
                    # Proceed to find mount point below
                elif "not authorized" in mount_result.stderr.lower():
                    logger.error(
                        f"Authorization failed for mounting {device_path}. Check polkit rules."
                    )
                    raise PermissionError(
                        f"Authorization failed for mounting {device_path}"
                    )
                else:
                    logger.warning(
                        f"Mount command failed (exit code {mount_result.returncode}). Retrying..."
                    )
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    else:
                        logger.error(
                            f"Failed to mount {device_path} after {max_retries} attempts."
                        )
                        return False

            # Extract mount point from udisksctl output or info
            if mount_result.returncode == 0 and " at " in mount_result.stdout:
                # Example output: "Mounted /dev/sda at /run/media/user/GLV80RHBOOT"
                mount_point_match = re.search(r" at (/\S+)", mount_result.stdout)
                if mount_point_match:
                    mount_point = mount_point_match.group(1).strip()

            # If mount_point not found from output, try getting info
            if not mount_point:
                logger.debug(
                    f"Mount point not found in mount output, querying udisksctl info for {device_path}..."
                )
                try:
                    info_result = subprocess.run(
                        ["udisksctl", "info", "-b", device_path],
                        capture_output=True,
                        text=True,
                        check=True,
                        timeout=5,
                    )
                    logger.debug(f"Info command stdout: {info_result.stdout}")
                    mount_point_line = re.search(
                        r"MountPoints:\s*(/\S+)", info_result.stdout
                    )
                    if mount_point_line:
                        mount_point = mount_point_line.group(1).strip()
                    else:
                        # Handle cases where MountPoints might be on the next line (less common now)
                        lines = info_result.stdout.splitlines()
                        for i, line in enumerate(lines):
                            if "MountPoints:" in line and i + 1 < len(lines):
                                possible_mount = lines[i + 1].strip()
                                if possible_mount.startswith("/"):
                                    mount_point = possible_mount
                                    break
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                    logger.warning(
                        f"Failed to get udisksctl info for {device_path}: {e}"
                    )
                except Exception as e:
                    logger.error(f"Unexpected error getting udisksctl info: {e}")

            if not mount_point or not os.path.isdir(mount_point):
                logger.warning(
                    f"Could not reliably determine mount point for {device_path}."
                )
                if attempt < max_retries - 1:
                    logger.info(f"Retrying mount/info in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    continue
                else:
                    logger.error(
                        f"Failed to find mount point for {device_path} after {max_retries} attempts."
                    )
                    return False  # Failed to find mount point

            logger.info(f"Device {device_identifier} mounted at {mount_point}")

            # Copy the firmware file
            dest_path = os.path.join(mount_point, os.path.basename(firmware_file))
            logger.info(f"Copying {firmware_file} to {dest_path}")
            shutil.copy2(
                firmware_file, mount_point
            )  # Copy to directory, filename is preserved
            # Optional: Add fsync to ensure data is written
            try:
                fd = os.open(mount_point, os.O_RDONLY)
                os.fsync(fd)
                os.close(fd)
                logger.debug(f"fsync successful on {mount_point}")
            except OSError as e:
                logger.warning(f"Could not fsync mount point {mount_point}: {e}")
            except Exception as e:
                logger.warning(f"Unexpected error during fsync: {e}")

            logger.info("Firmware file copied successfully.")

            # Trying to unmount, but it might fail as the device disconnects quickly
            try:
                logger.debug(f"Attempting to unmount {mount_point} ({device_path})")
                # Use --force as the device might already be gone
                unmount_result = subprocess.run(
                    [
                        "udisksctl",
                        "unmount",
                        "--no-user-interaction",
                        "-b",
                        device_path,
                        "--force",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,  # Short timeout
                    check=False,  # Don't fail on error
                )
                logger.debug(f"Unmount stdout: {unmount_result.stdout}")
                logger.debug(f"Unmount stderr: {unmount_result.stderr}")
                if unmount_result.returncode == 0:
                    logger.debug("Unmount command successful")
                else:
                    logger.debug(
                        f"Unmount command finished (exit code {unmount_result.returncode}), device likely disconnected."
                    )

            except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
                logger.debug(f"Unmount failed or timed out (likely expected): {e}")
            except Exception as e:
                logger.warning(f"Unexpected error during unmount: {e}")

            return True  # Flash successful

        except FileNotFoundError as e:
            # Handle missing udisksctl specifically
            logger.error(f"Error: {e}. Please ensure udisks2 is installed.")
            raise  # Re-raise critical error
        except PermissionError as e:
            logger.error(f"Permission error during mount/flash: {e}")
            raise  # Re-raise critical error
        except Exception as e:
            logger.error(f"Error during mount/flash attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logger.error("All mount/flash attempts failed.")
                # Optionally unmount if mount_point was found but copy failed
                if mount_point:
                    try:
                        logger.info(f"Attempting cleanup unmount of {mount_point}")
                        subprocess.run(
                            [
                                "udisksctl",
                                "unmount",
                                "--no-user-interaction",
                                "-b",
                                device_path,
                                "--force",
                            ],
                            capture_output=True,
                            text=True,
                            timeout=3,
                            check=False,
                        )
                    except Exception as unmount_e:
                        logger.warning(f"Cleanup unmount failed: {unmount_e}")
                return False  # Failed after retries

    return False  # Should not be reached, but ensures return


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Flash firmware to a USB Mass Storage device (like Glove80 bootloader).",
        epilog="Example Query: 'model~=nRF.*UF2 and vendor=Adafruit and removable=true'",
    )
    parser.add_argument("firmware_file", help="Path to the firmware file (.uf2)")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose debug logging"
    )
    parser.add_argument(
        "-n",
        "--count",
        type=int,
        default=2,  # Default to flashing once
        help="Number of devices/times to flash (default: 1). Use 0 for infinite.",
    )
    parser.add_argument(
        "-q",
        "--query",
        type=str,
        # Default query targets Adafruit nRF UF2 bootloaders
        default="model~=nRF.*UF2 and vendor=Adafruit and removable=true",
        help="Device query string using BlockDevice attributes (e.g., 'model=X', 'vendor=Y', 'removable=true'). "
        "Format: 'field1=value1 and field2~=regex and field3!=value3'",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Timeout in seconds to wait for a device to appear (default: 60)",
    )
    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Suppress noisy logs from libraries if not verbose
    if not args.verbose:
        logging.getLogger("shutil").setLevel(logging.WARNING)

    # --- Sanity Checks ---
    if platform.system().lower() not in ["linux"]:
        logger.error(
            "This script currently relies on 'udisksctl' and is primarily tested on Linux."
        )
        logger.error(
            "Functionality on other OS (macOS, Windows) is limited or requires different tools."
        )
        # sys.exit(1) # Allow running, but warn heavily

    if not shutil.which("udisksctl"):
        logger.error(
            "`udisksctl` command not found. Please install the 'udisks2' package."
        )
        # sys.exit(1) # Allow running, but warn heavily

    firmware_file = args.firmware_file
    if not os.path.exists(firmware_file):
        logger.error(f"Firmware file not found: {firmware_file}")
        sys.exit(1)
    if not firmware_file.lower().endswith(".uf2"):
        logger.warning(
            f"Firmware file '{os.path.basename(firmware_file)}' does not have a .uf2 extension."
        )

    # --- Flashing Loop ---
    flash_count = 0
    max_flashes = args.count if args.count > 0 else float("inf")
    infinite_mode = args.count == 0

    try:
        while flash_count < max_flashes:
            loop_iteration = flash_count + 1
            if infinite_mode:
                logger.info(
                    f"--- Starting flash cycle {loop_iteration} (Infinite Mode) ---"
                )
            else:
                logger.info(
                    f"--- Starting flash {loop_iteration}/{int(max_flashes)} ---"
                )

            logger.info(
                "Please connect the device in bootloader mode (or ensure it's already connected)..."
            )
            try:
                device_info = wait_for_device(args.query, timeout=args.timeout)
                # Add a small delay to ensure the system fully recognizes the device files
                time.sleep(2)

                if mount_and_flash(device_info, firmware_file):
                    logger.info(
                        f"Flashing completed successfully for device {device_info.name}."
                    )
                    flash_count += 1
                    logger.info("Device should reboot shortly.")
                    # Wait a bit for the device to potentially disconnect before starting next loop
                    time.sleep(5)
                else:
                    logger.warning(
                        "Flashing failed for the detected device. Will retry device search."
                    )
                    # Add a delay before searching again to avoid tight loops on persistent errors
                    time.sleep(3)

            except TimeoutError:
                logger.error(
                    f"Device not detected within the {args.timeout}s timeout period."
                )
                if infinite_mode:
                    logger.info("Continuing to wait...")
                    time.sleep(1)  # Prevent busy-looping on timeout in infinite mode
                    continue  # Continue waiting in infinite mode
                else:
                    logger.error("Exiting.")
                    sys.exit(1)  # Exit if not in infinite mode
            except (BlockDeviceError, FileNotFoundError, PermissionError) as e:
                logger.error(f"A critical error occurred: {e}")
                logger.error("Cannot continue. Exiting.")
                sys.exit(1)
            except ValueError as e:  # Catch invalid query errors
                logger.error(f"Configuration error: {e}")
                sys.exit(1)
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt detected. Exiting.")
                break  # Exit loop cleanly
            except Exception as e:
                logger.exception(
                    f"An unexpected error occurred during flash cycle {loop_iteration}: {e}"
                )
                # Decide whether to continue or exit on unexpected errors
                if infinite_mode:
                    logger.warning(
                        "Attempting to continue in infinite mode after unexpected error..."
                    )
                    time.sleep(5)  # Delay before retrying
                else:
                    logger.error("Exiting due to unexpected error.")
                    sys.exit(1)

        if flash_count >= max_flashes and not infinite_mode:
            logger.info(
                f"Successfully completed all {int(max_flashes)} requested flashes."
            )
        elif not infinite_mode:
            logger.warning(
                f"Finished, but only completed {flash_count}/{int(max_flashes)} flashes."
            )

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt detected during main loop. Exiting.")
        sys.exit(0)


if __name__ == "__main__":
    main()
    # Example usage for testing specific parts:
    # logging.basicConfig(level=logging.DEBUG)
    # try:
    #     # Test device listing
    #     # devices = get_block_devices()
    #     # from .lsblk import print_device_info
    #     # print_device_info(devices)
    #
    #     # Test waiting (replace query with something relevant)
    #     # query = "model~=storage & vendor=generic"
    #     # print(f"Waiting for device matching: {query}")
    #     # device = wait_for_device(query, timeout=30)
    #     # print(f"Found: {device}")
    #
    # except BlockDeviceError as e:
    #     logger.error(f"Block device error: {e}")
    # except TimeoutError:
    #     logger.error("Timeout waiting for device.")
    # except Exception as e:
    #      logger.exception(f"An error occurred: {e}")
