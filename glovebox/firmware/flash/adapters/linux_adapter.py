"""Linux-specific flash operations using udisksctl."""

import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING

from glovebox.core.structlog_logger import get_struct_logger


if TYPE_CHECKING:
    pass

from glovebox.firmware.flash.models import BlockDevice


logger = get_struct_logger(__name__)


class LinuxFlashOS:
    """Linux-specific flash operations using udisksctl."""

    def get_device_path(self, device_name: str) -> str:
        """Get the full device path for a device name on Linux."""
        return f"/dev/{device_name}"

    def mount_device(self, device: BlockDevice) -> list[str]:
        """Mount device using udisksctl on Linux."""
        mount_points = []
        device_path = self.get_device_path(device.name)

        # Check if device node exists
        if not Path(device_path).exists():
            logger.warning(
                "device_node_does_not_exist_waiting", device_path=device_path
            )
            # Wait up to 3 seconds for device node to appear
            for _ in range(30):
                if Path(device_path).exists():
                    logger.info("device_node_now_available", device_path=device_path)
                    break
                time.sleep(0.1)
            else:
                raise OSError(
                    f"Device node {device_path} did not appear after 3 seconds"
                )

        # Check if udisksctl exists
        if not shutil.which("udisksctl"):
            raise OSError("`udisksctl` command not found. Please install udisks2.")

        try:
            # Try to mount the whole device first
            result = subprocess.run(
                ["udisksctl", "mount", "--no-user-interaction", "-b", device_path],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            if result.returncode == 0:
                mount_point = self._extract_mount_point_from_output(result.stdout)
                if mount_point:
                    # Verify the mount point actually exists (device might have crashed)
                    if Path(mount_point).exists():
                        mount_points.append(mount_point)
                        logger.debug("mount_point_verified", mount_point=mount_point)
                    else:
                        logger.warning(
                            "Mount reported success but mount point %s doesn't exist (device may have crashed)",
                            mount_point,
                        )
            elif "already mounted" in result.stderr.lower():
                # Device already mounted, get mount point from udisksctl info
                mount_point = self._get_mount_point_from_info(device_path)
                if mount_point and Path(mount_point).exists():
                    mount_points.append(mount_point)
                    logger.debug(
                        "Already mounted, mount point verified: %s", mount_point
                    )
            elif "not authorized" in result.stderr.lower():
                raise PermissionError(
                    f"Authorization failed for mounting {device_path}"
                )
            else:
                # Try mounting partitions
                for partition in device.partitions:
                    part_path = self.get_device_path(partition)
                    part_result = subprocess.run(
                        [
                            "udisksctl",
                            "mount",
                            "--no-user-interaction",
                            "-b",
                            part_path,
                        ],
                        capture_output=True,
                        text=True,
                        timeout=10,
                        check=False,
                    )
                    if part_result.returncode == 0:
                        mount_point = self._extract_mount_point_from_output(
                            part_result.stdout
                        )
                        if mount_point and Path(mount_point).exists():
                            mount_points.append(mount_point)
                            logger.debug(
                                "Partition mount point verified: %s", mount_point
                            )

            if not mount_points:
                logger.warning("could_not_mount_device", device_path=device_path)

        except subprocess.TimeoutExpired as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error(
                "Timeout mounting device %s: %s", device_path, e, exc_info=exc_info
            )
            raise OSError(f"Timeout mounting device {device_path}") from e
        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error(
                "Failed to mount device %s: %s", device_path, e, exc_info=exc_info
            )
            raise OSError(f"Failed to mount device {device_path}: {e}") from e

        return mount_points

    def _extract_mount_point_from_output(self, output: str) -> str | None:
        """Extract mount point from udisksctl output."""
        # Example output: "Mounted /dev/sda at /run/media/user/GLV80RHBOOT"
        mount_point_match = re.search(r" at (/\S+)", output)
        if mount_point_match:
            return mount_point_match.group(1).strip()
        return None

    def _get_mount_point_from_info(self, device_path: str) -> str | None:
        """Get mount point from udisksctl info command."""
        try:
            info_result = subprocess.run(
                ["udisksctl", "info", "-b", device_path],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )

            # Look for MountPoints line
            mount_point_line = re.search(
                r"^\s*MountPoints?:\s*(/\S+)", info_result.stdout, re.MULTILINE
            )
            if mount_point_line:
                return mount_point_line.group(1).strip()

            # Handle cases where MountPoints might be on the next line
            lines = info_result.stdout.splitlines()
            for i, line in enumerate(lines):
                if "MountPoints:" in line and i + 1 < len(lines):
                    possible_mount = lines[i + 1].strip()
                    if possible_mount.startswith("/"):
                        return possible_mount

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass

        return None

    def unmount_device(self, device: BlockDevice) -> bool:
        """Unmount device using udisksctl on Linux."""
        device_path = self.get_device_path(device.name)
        unmounted = False

        try:
            # Try to unmount with --force as device might disconnect
            result = subprocess.run(
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
                timeout=5,
                check=False,
            )

            if result.returncode == 0:
                unmounted = True
                logger.debug("successfully_unmounted", device_path=device_path)
            else:
                logger.debug(
                    "Unmount finished with exit code %s, device likely disconnected",
                    result.returncode,
                )
                # Consider it successful if device disconnected
                unmounted = True

        except subprocess.TimeoutExpired:
            logger.debug("unmount_timed_out_likely_expected", device_path=device_path)
            unmounted = True  # Device probably disconnected
        except Exception as e:
            logger.warning("error_during_unmount", error=str(e))

        return unmounted

    def copy_firmware_file(self, firmware_file: Path, mount_point: str) -> bool:
        """Copy firmware file to mounted device on Linux."""
        try:
            dest_path = Path(mount_point) / firmware_file.name
            logger.info(
                "copying_firmware_file",
                firmware_file=str(firmware_file),
                dest_path=str(dest_path),
            )
            shutil.copy2(firmware_file, mount_point)
            return True
        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error(
                "failed_to_copy_firmware_file", error=str(e), exc_info=exc_info
            )
            return False

    def sync_filesystem(self, mount_point: str) -> bool:
        """Sync filesystem on Linux."""
        try:
            # fsync the directory containing the new file
            fd = os.open(mount_point, os.O_RDONLY)
            os.fsync(fd)
            os.close(fd)
            logger.debug("fsync_successful_on_directory", mount_point=mount_point)
            return True
        except OSError as e:
            logger.warning(
                "Could not fsync mount point directory %s: %s", mount_point, e
            )
            return False
        except Exception as e:
            logger.warning("unexpected_error_during_fsync", error=str(e))
            return False
