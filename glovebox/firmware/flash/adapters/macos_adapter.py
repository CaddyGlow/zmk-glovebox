"""macOS-specific flash operations using diskutil."""

import logging
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from glovebox.protocols.flash_os_protocol import FlashOSProtocol

from glovebox.firmware.flash.models import BlockDevice


logger = logging.getLogger(__name__)


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
                logger.warning("No mount points found for device %s", device.name)

        except subprocess.TimeoutExpired as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error("Timeout mounting device %s", device.name, exc_info=exc_info)
            raise OSError(f"Timeout mounting device {device.name}") from e
        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error(
                "Failed to mount device %s: %s", device.name, e, exc_info=exc_info
            )
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
                            "Successfully unmounted %s from %s",
                            device.name,
                            mount_point,
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
                logger.debug("Successfully unmounted device %s", device.name)
                unmounted = True

        except subprocess.TimeoutExpired:
            logger.debug("Unmount timed out for %s, likely expected", device.name)
            unmounted = True  # Device probably disconnected
        except Exception as e:
            logger.warning("Error during unmount: %s", e)

        return unmounted

    def copy_firmware_file(self, firmware_file: Path, mount_point: str) -> bool:
        """Copy firmware file to mounted device on macOS."""
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
        """Sync filesystem on macOS."""
        try:
            # Use sync command on macOS
            subprocess.run(["sync"], check=True, timeout=5)
            logger.debug("sync command completed successfully")
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.warning("sync command failed: %s", e)
            return False
        except Exception as e:
            logger.warning("Unexpected error during sync: %s", e)
            return False
