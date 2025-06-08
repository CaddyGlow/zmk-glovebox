"""OS-specific implementations for flash operations."""

import logging
import os
import platform
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional


if TYPE_CHECKING:
    from glovebox.protocols.flash_os_protocol import FlashOSProtocol

from glovebox.core.errors import FlashError
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
                logger.warning(f"Could not mount device {device_path}")

        except subprocess.TimeoutExpired as e:
            raise OSError(f"Timeout mounting device {device_path}") from e
        except Exception as e:
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
                logger.debug(f"Successfully unmounted {device_path}")
            else:
                logger.debug(
                    f"Unmount finished with exit code {result.returncode}, device likely disconnected"
                )
                # Consider it successful if device disconnected
                unmounted = True

        except subprocess.TimeoutExpired:
            logger.debug(f"Unmount timed out for {device_path}, likely expected")
            unmounted = True  # Device probably disconnected
        except Exception as e:
            logger.warning(f"Error during unmount: {e}")

        return unmounted

    def copy_firmware_file(self, firmware_file: Path, mount_point: str) -> bool:
        """Copy firmware file to mounted device on Linux."""
        try:
            dest_path = Path(mount_point) / firmware_file.name
            logger.info(f"Copying {firmware_file} to {dest_path}")
            shutil.copy2(firmware_file, mount_point)
            return True
        except Exception as e:
            logger.error(f"Failed to copy firmware file: {e}")
            return False

    def sync_filesystem(self, mount_point: str) -> bool:
        """Sync filesystem on Linux."""
        try:
            # fsync the directory containing the new file
            fd = os.open(mount_point, os.O_RDONLY)
            os.fsync(fd)
            os.close(fd)
            logger.debug(f"fsync successful on directory {mount_point}")
            return True
        except OSError as e:
            logger.warning(f"Could not fsync mount point directory {mount_point}: {e}")
            return False
        except Exception as e:
            logger.warning(f"Unexpected error during fsync: {e}")
            return False


class MacOSFlashOS:
    """macOS-specific flash operations using diskutil."""

    def get_device_path(self, device_name: str) -> str:
        """Get the full device path for a device name on macOS."""
        return f"/dev/{device_name}"

    def mount_device(self, device: BlockDevice) -> list[str]:
        """Mount device using diskutil on macOS."""
        mount_points = []

        try:
            # First try to mount the whole disk
            result = subprocess.run(
                ["diskutil", "mount", device.name],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            if result.returncode == 0:
                mount_point = self._extract_mount_point_from_output(result.stdout)
                if mount_point:
                    mount_points.append(mount_point)
            else:
                # Try mounting partitions if whole disk mount failed
                logger.debug("Whole disk mount failed, trying partitions")
                for partition in device.partitions:
                    part_result = subprocess.run(
                        ["diskutil", "mount", partition],
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
                logger.warning(f"No mount points found for device {device.name}")

        except subprocess.TimeoutExpired as e:
            raise OSError(f"Timeout mounting device {device.name}") from e
        except Exception as e:
            raise OSError(f"Failed to mount device {device.name}: {e}") from e

        return mount_points

    def _extract_mount_point_from_output(self, output: str) -> str | None:
        """Extract mount point from diskutil output."""
        # diskutil output: "Volume NAME on disk1s1 mounted on /Volumes/NAME"
        if "mounted on" in output:
            mount_point = output.split("mounted on")[-1].strip()
            return mount_point
        return None

    def unmount_device(self, device: BlockDevice) -> bool:
        """Unmount device using diskutil on macOS."""
        unmounted = False

        try:
            # Try to unmount all mount points for this device
            if device.mountpoints:
                for mount_point in device.mountpoints.values():
                    result = subprocess.run(
                        ["diskutil", "unmount", mount_point],
                        capture_output=True,
                        text=True,
                        timeout=5,
                        check=False,
                    )
                    if result.returncode == 0:
                        logger.debug(
                            f"Successfully unmounted {device.name} from {mount_point}"
                        )
                        unmounted = True

            # Also try unmounting by device name
            result = subprocess.run(
                ["diskutil", "unmount", device.name],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0:
                logger.debug(f"Successfully unmounted device {device.name}")
                unmounted = True

        except subprocess.TimeoutExpired:
            logger.debug(f"Unmount timed out for {device.name}, likely expected")
            unmounted = True  # Device probably disconnected
        except Exception as e:
            logger.warning(f"Error during unmount: {e}")

        return unmounted

    def copy_firmware_file(self, firmware_file: Path, mount_point: str) -> bool:
        """Copy firmware file to mounted device on macOS."""
        try:
            dest_path = Path(mount_point) / firmware_file.name
            logger.info(f"Copying {firmware_file} to {dest_path}")
            shutil.copy2(firmware_file, mount_point)
            return True
        except Exception as e:
            logger.error(f"Failed to copy firmware file: {e}")
            return False

    def sync_filesystem(self, mount_point: str) -> bool:
        """Sync filesystem on macOS."""
        try:
            # Use sync command on macOS
            subprocess.run(["sync"], check=True, timeout=5)
            logger.debug("sync command completed successfully")
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.warning(f"sync command failed: {e}")
            return False
        except Exception as e:
            logger.warning(f"Unexpected error during sync: {e}")
            return False


class StubFlashOS:
    """Stub implementation for unsupported platforms."""

    def get_device_path(self, device_name: str) -> str:
        """Stub implementation that raises an error."""
        raise OSError(f"Flash operations not supported on {platform.system()}")

    def mount_device(self, device: BlockDevice) -> list[str]:
        """Stub implementation that raises an error."""
        raise OSError(f"Flash operations not supported on {platform.system()}")

    def unmount_device(self, device: BlockDevice) -> bool:
        """Stub implementation that raises an error."""
        raise OSError(f"Flash operations not supported on {platform.system()}")

    def copy_firmware_file(self, firmware_file: Path, mount_point: str) -> bool:
        """Stub implementation that raises an error."""
        raise OSError(f"Flash operations not supported on {platform.system()}")

    def sync_filesystem(self, mount_point: str) -> bool:
        """Stub implementation that raises an error."""
        raise OSError(f"Flash operations not supported on {platform.system()}")


def create_flash_os_adapter() -> "FlashOSProtocol":
    """Factory function to create the appropriate flash OS adapter."""
    system = platform.system()

    if system == "Linux":
        logger.debug("Creating Linux flash OS adapter")
        return LinuxFlashOS()
    elif system == "Darwin":
        logger.debug("Creating macOS flash OS adapter")
        return MacOSFlashOS()
    else:
        logger.warning(f"Unsupported platform: {system}, using stub adapter")
        return StubFlashOS()
