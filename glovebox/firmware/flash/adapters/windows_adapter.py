"""Windows-specific flash adapter implementation."""

import logging
import shutil
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING


try:
    import wmi  # type: ignore[import-not-found]

    WMI_AVAILABLE = True
except ImportError:
    WMI_AVAILABLE = False

if TYPE_CHECKING:
    pass

from glovebox.firmware.flash.models import BlockDevice


logger = logging.getLogger(__name__)


class WindowsFlashOS:
    """Windows-specific flash operations using WMI."""

    def __init__(self) -> None:
        """Initialize Windows flash OS adapter."""
        if not WMI_AVAILABLE:
            raise OSError("WMI library not available. Install with: pip install wmi")

        try:
            self.wmi = wmi.WMI()
        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error(
                "Failed to initialize WMI connection: %s", e, exc_info=exc_info
            )
            raise OSError(f"Failed to initialize WMI connection: {e}") from e

    def get_device_path(self, device_name: str) -> str:
        """Get the full device path for a device name on Windows.

        On Windows, this typically returns the drive letter (e.g., 'E:')
        """
        # If device_name is already a drive letter, return it
        if len(device_name) == 2 and device_name[1] == ":":
            return device_name

        # Try to find the drive letter for this device
        try:
            for disk in self.wmi.Win32_LogicalDisk(DriveType=2):  # Removable disk
                if device_name in str(disk.Caption):
                    return str(disk.Caption)
        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.warning(
                "Could not determine device path for %s: %s",
                device_name,
                e,
                exc_info=exc_info,
            )

        return device_name

    def mount_device(self, device: BlockDevice) -> list[str]:
        """Mount device on Windows.

        Windows typically auto-mounts removable devices, so we verify
        the device is accessible and return available mount points.
        """
        mount_points = []

        try:
            # Get all removable drives
            removable_drives = list(self.wmi.Win32_LogicalDisk(DriveType=2))

            for drive in removable_drives:
                drive_letter = drive.Caption

                # Check if this drive matches our device
                if self._is_matching_device(device, drive):
                    # Verify the drive is accessible
                    if self._is_drive_accessible(drive_letter):
                        mount_points.append(drive_letter + "\\")
                        logger.debug("Found accessible drive: %s", drive_letter)
                    else:
                        logger.warning("Drive %s is not accessible", drive_letter)

            if not mount_points:
                # Try to wait a moment for Windows to mount the device
                time.sleep(2)

                # Check again
                removable_drives = list(self.wmi.Win32_LogicalDisk(DriveType=2))
                for drive in removable_drives:
                    drive_letter = drive.Caption
                    if self._is_matching_device(
                        device, drive
                    ) and self._is_drive_accessible(drive_letter):
                        mount_points.append(drive_letter + "\\")
                        logger.debug(
                            "Found accessible drive after wait: %s", drive_letter
                        )

            if not mount_points:
                logger.warning(
                    "No accessible mount points found for device %s", device.name
                )

        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error(
                "Failed to mount device %s: %s", device.name, e, exc_info=exc_info
            )
            raise OSError(f"Failed to mount device {device.name}: {e}") from e

        return mount_points

    def _is_matching_device(self, device: BlockDevice, wmi_drive: object) -> bool:
        """Check if a WMI drive object matches our BlockDevice."""
        # This is a simplified matching - in a real implementation,
        # we'd want more sophisticated matching based on device properties
        if hasattr(wmi_drive, "VolumeName") and device.label:
            return bool(wmi_drive.VolumeName == device.label)

        # For now, assume any removable drive could be our target
        return True

    def _is_drive_accessible(self, drive_letter: str) -> bool:
        """Check if a drive letter is accessible."""
        try:
            drive_path = Path(drive_letter + "\\")
            return drive_path.exists() and drive_path.is_dir()
        except (OSError, PermissionError):
            return False

    def unmount_device(self, device: BlockDevice) -> bool:
        """Unmount device on Windows using safe removal."""
        try:
            # Get the drive letter(s) for this device
            drive_letters = []

            for drive in self.wmi.Win32_LogicalDisk(DriveType=2):
                if self._is_matching_device(device, drive):
                    drive_letters.append(drive.Caption)

            # Attempt to safely eject each drive
            success = True
            for drive_letter in drive_letters:
                try:
                    # Use WMI to dismount the volume
                    for volume in self.wmi.Win32_Volume():
                        if volume.DriveLetter == drive_letter:
                            result = volume.Dismount(Force=False, Permanent=False)
                            if result != 0:
                                logger.warning(
                                    "Dismount returned code %s for %s",
                                    result,
                                    drive_letter,
                                )
                                success = False
                            else:
                                logger.debug("Successfully dismounted %s", drive_letter)
                            break
                except Exception as e:
                    exc_info = logger.isEnabledFor(logging.DEBUG)
                    logger.warning(
                        "Error dismounting %s: %s", drive_letter, e, exc_info=exc_info
                    )
                    success = False

            return success

        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.warning("Error during unmount: %s", e, exc_info=exc_info)
            return False

    def copy_firmware_file(self, firmware_file: Path, mount_point: str) -> bool:
        """Copy firmware file to mounted device on Windows."""
        try:
            # Ensure mount_point ends with backslash for Windows
            if not mount_point.endswith("\\"):
                mount_point += "\\"

            dest_path = Path(mount_point) / firmware_file.name
            logger.info("Copying %s to %s", firmware_file, dest_path)

            # Use shutil.copy2 to preserve metadata
            shutil.copy2(firmware_file, mount_point)

            # Verify the file was copied successfully
            if (
                dest_path.exists()
                and dest_path.stat().st_size == firmware_file.stat().st_size
            ):
                logger.debug("File copied successfully to %s", dest_path)
                return True
            else:
                logger.error("File copy verification failed for %s", dest_path)
                return False

        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error("Failed to copy firmware file: %s", e, exc_info=exc_info)
            return False

    def sync_filesystem(self, mount_point: str) -> bool:
        """Sync filesystem on Windows."""
        try:
            # On Windows, we can use the FlushFileBuffers API via ctypes
            import ctypes
            from ctypes import wintypes

            # Get handle to the drive
            drive_letter = mount_point.rstrip("\\")
            handle = ctypes.windll.kernel32.CreateFileW(  # type: ignore[attr-defined]
                f"\\\\.\\{drive_letter}",
                0,  # No access needed for flush
                wintypes.DWORD(0x01 | 0x02),  # FILE_SHARE_READ | FILE_SHARE_WRITE
                None,
                3,  # OPEN_EXISTING
                0,
                None,
            )

            if handle == -1:
                logger.warning("Could not get handle for %s", drive_letter)
                return False

            try:
                # Flush file buffers
                result = ctypes.windll.kernel32.FlushFileBuffers(handle)  # type: ignore[attr-defined]
                if result:
                    logger.debug("Successfully flushed buffers for %s", drive_letter)
                    return True
                else:
                    logger.warning("FlushFileBuffers failed for %s", drive_letter)
                    return False
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)  # type: ignore[attr-defined]

        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.warning("Error during filesystem sync: %s", e, exc_info=exc_info)
            # Try alternative approach using sync command if available
            try:
                subprocess.run(["sync"], check=True, timeout=5)
                logger.debug("Used sync command as fallback")
                return True
            except (
                subprocess.CalledProcessError,
                subprocess.TimeoutExpired,
                FileNotFoundError,
            ):
                pass

            return False
