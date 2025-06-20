"""Linux-specific flash operations using udisksctl."""

import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from glovebox.protocols.flash_os_protocol import FlashOSProtocol

from glovebox.firmware.flash.models import BlockDevice


logger = logging.getLogger(__name__)


class LinuxFlashOS:
    """Linux-specific flash operations using udisksctl."""

    def get_device_path(self, device_name: str) -> str:
        """Get the full device path for a device name on Linux."""
        return f"/dev/{device_name}"

    def mount_device(self, device: BlockDevice) -> list[str]:
        """Mount device using udisksctl on Linux."""
        mount_points = []
        device_path = self.get_device_path(device.name)

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
                    mount_points.append(mount_point)
            elif "already mounted" in result.stderr.lower():
                # Device already mounted, get mount point from udisksctl info
                mount_point = self._get_mount_point_from_info(device_path)
                if mount_point:
                    mount_points.append(mount_point)
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
                        if mount_point:
                            mount_points.append(mount_point)

            if not mount_points:
                logger.warning("Could not mount device %s", device_path)

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
                logger.debug("Successfully unmounted %s", device_path)
            else:
                logger.debug(
                    "Unmount finished with exit code %s, device likely disconnected",
                    result.returncode,
                )
                # Consider it successful if device disconnected
                unmounted = True

        except subprocess.TimeoutExpired:
            logger.debug("Unmount timed out for %s, likely expected", device_path)
            unmounted = True  # Device probably disconnected
        except Exception as e:
            logger.warning("Error during unmount: %s", e)

        return unmounted

    def copy_firmware_file(self, firmware_file: Path, mount_point: str) -> bool:
        """Copy firmware file to mounted device on Linux."""
        try:
            dest_path = Path(mount_point) / firmware_file.name
            logger.info("Copying %s to %s", firmware_file, dest_path)
            shutil.copy2(firmware_file, mount_point)
            return True
        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error("Failed to copy firmware file: %s", e, exc_info=exc_info)
            return False

    def sync_filesystem(self, mount_point: str) -> bool:
        """Sync filesystem on Linux."""
        try:
            # fsync the directory containing the new file
            fd = os.open(mount_point, os.O_RDONLY)
            os.fsync(fd)
            os.close(fd)
            logger.debug("fsync successful on directory %s", mount_point)
            return True
        except OSError as e:
            logger.warning(
                "Could not fsync mount point directory %s: %s", mount_point, e
            )
            return False
        except Exception as e:
            logger.warning("Unexpected error during fsync: %s", e)
            return False
