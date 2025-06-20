"""WSL2-specific flash adapter implementation."""

import json
import logging
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING

from glovebox.firmware.flash.models import BlockDevice

from .os_utils import windows_to_wsl_path, wsl_to_windows_path


if TYPE_CHECKING:
    from glovebox.protocols.flash_os_protocol import FlashOSProtocol

logger = logging.getLogger(__name__)


class WSL2FlashOS:
    """WSL2-specific flash operations using Windows commands via interop."""

    def __init__(self) -> None:
        """Initialize WSL2 flash OS adapter."""
        if not self._validate_wsl_interop():
            raise OSError("Windows interop not available in WSL2 environment")

    def _validate_wsl_interop(self) -> bool:
        """Verify Windows interop is available in WSL2."""
        try:
            result = subprocess.run(
                ["powershell.exe", "-Command", "echo 'test'"],
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            )
            return result.returncode == 0
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            FileNotFoundError,
        ):
            return False

    def get_device_path(self, device_name: str) -> str:
        """Get the device path for WSL2.

        If device_name is a Windows drive letter, convert to WSL2 path.
        Otherwise, return as-is.
        """
        # If device_name is a Windows drive letter, convert to WSL2 path
        if len(device_name) == 2 and device_name[1] == ":":
            try:
                return windows_to_wsl_path(device_name + "\\")
            except OSError as e:
                exc_info = logger.isEnabledFor(logging.DEBUG)
                logger.warning(
                    "Could not convert device path %s: %s",
                    device_name,
                    e,
                    exc_info=exc_info,
                )
                return device_name

        return device_name

    def mount_device(self, device: BlockDevice) -> list[str]:
        """Mount device in WSL2 using PowerShell to detect Windows drives."""
        mount_points: list[str] = []

        try:
            # Use PowerShell to get removable drives with JSON output
            ps_command = (
                "Get-WmiObject -Class Win32_LogicalDisk | "
                "Where-Object {$_.DriveType -eq 2} | "
                "Select-Object Caption, VolumeName, Size, FreeSpace | "
                "ConvertTo-Json"
            )

            result = subprocess.run(
                ["powershell.exe", "-Command", ps_command],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )

            if not result.stdout.strip():
                logger.warning("No removable drives found")
                return mount_points

            # Parse JSON response
            try:
                drives_data = json.loads(result.stdout)
                # Handle single drive case (PowerShell returns object, not array)
                if isinstance(drives_data, dict):
                    drives_data = [drives_data]

                for drive in drives_data:
                    drive_letter = drive["Caption"]

                    if self._is_matching_device(device, drive):
                        # Check if drive is accessible via PowerShell
                        if self._is_drive_accessible_ps(drive_letter):
                            # Try to convert Windows path to WSL2 path
                            try:
                                wsl_path = windows_to_wsl_path(drive_letter + "\\")
                                # Verify the WSL path is actually accessible
                                if Path(wsl_path).exists():
                                    mount_points.append(wsl_path)
                                    logger.debug(
                                        "Found accessible WSL2 drive: %s (%s)",
                                        wsl_path,
                                        drive_letter,
                                    )
                                else:
                                    logger.warning(
                                        "WSL path %s for %s does not exist",
                                        wsl_path,
                                        drive_letter,
                                    )
                            except OSError as e:
                                exc_info = logger.isEnabledFor(logging.DEBUG)
                                logger.warning(
                                    "Could not convert path for %s: %s",
                                    drive_letter,
                                    e,
                                    exc_info=exc_info,
                                )
                        else:
                            logger.debug(
                                "Drive %s is not accessible via PowerShell",
                                drive_letter,
                            )

            except json.JSONDecodeError as e:
                exc_info = logger.isEnabledFor(logging.DEBUG)
                logger.error(
                    "Failed to parse PowerShell JSON output: %s", e, exc_info=exc_info
                )
                raise OSError(f"Failed to parse drive information: {e}") from e

            if not mount_points:
                # Try waiting a moment for drive to be ready
                time.sleep(2)
                logger.debug("Retrying drive detection after wait...")

                # Try again with same command
                result = subprocess.run(
                    ["powershell.exe", "-Command", ps_command],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=True,
                )

                if result.stdout.strip():
                    drives_data = json.loads(result.stdout)
                    if isinstance(drives_data, dict):
                        drives_data = [drives_data]

                    for drive in drives_data:
                        drive_letter = drive["Caption"]
                        if self._is_matching_device(
                            device, drive
                        ) and self._is_drive_accessible_ps(drive_letter):
                            try:
                                wsl_path = windows_to_wsl_path(drive_letter + "\\")
                                mount_points.append(wsl_path)
                                logger.debug(
                                    "Found accessible WSL2 drive after wait: %s",
                                    wsl_path,
                                )
                            except OSError:
                                continue

            if not mount_points:
                logger.warning(
                    "No accessible mount points found for device %s", device.name
                )

        except subprocess.CalledProcessError as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error(
                "Failed to detect drives via PowerShell: %s", e, exc_info=exc_info
            )
            raise OSError(f"Failed to detect drives via PowerShell: {e}") from e
        except subprocess.TimeoutExpired as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error("PowerShell command timed out: %s", e, exc_info=exc_info)
            raise OSError(f"PowerShell command timed out: {e}") from e

        return mount_points

    def _is_matching_device(
        self, device: BlockDevice, drive_data: dict[str, str]
    ) -> bool:
        """Check if a PowerShell drive object matches our BlockDevice."""
        # Match by volume name if available
        if device.label and drive_data.get("VolumeName"):
            return device.label == drive_data["VolumeName"]

        # For now, assume any removable drive could be our target
        return True

    def _is_drive_accessible_ps(self, drive_letter: str) -> bool:
        """Check if a drive letter is accessible using PowerShell."""
        try:
            ps_command = f"Test-Path '{drive_letter}\\'"
            result = subprocess.run(
                ["powershell.exe", "-Command", ps_command],
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            )
            return result.stdout.strip().lower() == "true"
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return False

    def unmount_device(self, device: BlockDevice) -> bool:
        """Unmount device in WSL2 using PowerShell."""
        try:
            # Get removable drives to find matching ones
            ps_command = (
                "Get-WmiObject -Class Win32_LogicalDisk | "
                "Where-Object {$_.DriveType -eq 2} | "
                "Select-Object Caption, VolumeName | "
                "ConvertTo-Json"
            )

            result = subprocess.run(
                ["powershell.exe", "-Command", ps_command],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )

            if not result.stdout.strip():
                return True  # No drives to unmount

            drives_data = json.loads(result.stdout)
            if isinstance(drives_data, dict):
                drives_data = [drives_data]

            success = True
            for drive in drives_data:
                if self._is_matching_device(device, drive):
                    drive_letter = drive["Caption"]

                    # Use PowerShell to dismount the volume
                    dismount_command = (
                        f"$volume = Get-WmiObject -Class Win32_Volume | "
                        f"Where-Object {{$_.DriveLetter -eq '{drive_letter}'}}; "
                        f"if ($volume) {{ $volume.Dismount($false, $false) }}"
                    )

                    try:
                        subprocess.run(
                            ["powershell.exe", "-Command", dismount_command],
                            capture_output=True,
                            text=True,
                            timeout=5,
                            check=True,
                        )
                        logger.debug("Successfully dismounted %s", drive_letter)
                    except (
                        subprocess.CalledProcessError,
                        subprocess.TimeoutExpired,
                    ) as e:
                        exc_info = logger.isEnabledFor(logging.DEBUG)
                        logger.warning(
                            "Error dismounting %s: %s",
                            drive_letter,
                            e,
                            exc_info=exc_info,
                        )
                        success = False

            return success

        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            json.JSONDecodeError,
        ) as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.warning("Error during unmount: %s", e, exc_info=exc_info)
            return False

    def copy_firmware_file(self, firmware_file: Path, mount_point: str) -> bool:
        """Copy firmware file to mounted device in WSL2."""
        try:
            # Convert WSL paths to Windows paths for PowerShell copy operation
            windows_mount = wsl_to_windows_path(mount_point)
            windows_firmware = wsl_to_windows_path(str(firmware_file))

            # Ensure Windows mount point ends with backslash
            if not windows_mount.endswith("\\"):
                windows_mount += "\\"

            dest_path_windows = windows_mount + firmware_file.name
            dest_path_wsl = windows_to_wsl_path(dest_path_windows)

            logger.info(
                "Copying %s to %s (via %s)",
                firmware_file,
                dest_path_wsl,
                dest_path_windows,
            )

            # Use PowerShell Copy-Item for reliable copying
            ps_command = (
                f"Copy-Item -Path '{windows_firmware}' -Destination '{windows_mount}'"
            )

            result = subprocess.run(
                ["powershell.exe", "-Command", ps_command],
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )

            # Verify the file was copied successfully
            dest_path = Path(dest_path_wsl)
            if (
                dest_path.exists()
                and dest_path.stat().st_size == firmware_file.stat().st_size
            ):
                logger.debug("File copied successfully to %s", dest_path)
                return True
            else:
                logger.error("File copy verification failed for %s", dest_path)
                return False

        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error("Failed to copy firmware file: %s", e, exc_info=exc_info)
            return False

    def sync_filesystem(self, mount_point: str) -> bool:
        """Sync filesystem in WSL2 using Windows flush commands."""
        try:
            # Convert WSL path to Windows path
            windows_mount = wsl_to_windows_path(mount_point)
            drive_letter = windows_mount.rstrip("\\")

            # Use PowerShell to flush file system buffers
            ps_command = (
                f"$handle = [System.IO.File]::Open('{drive_letter}', "
                f"[System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, "
                f"[System.IO.FileShare]::ReadWrite); "
                f"$handle.Flush(); $handle.Close()"
            )

            result = subprocess.run(
                ["powershell.exe", "-Command", ps_command],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                logger.debug("Successfully synced filesystem for %s", mount_point)
                return True
            else:
                logger.warning("Filesystem sync returned code %s", result.returncode)
                return False

        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.warning("Error during filesystem sync: %s", e, exc_info=exc_info)
            # Try alternative approach
            try:
                subprocess.run(["sync"], check=True, timeout=5)
                logger.debug("Used Linux sync command as fallback")
                return True
            except (
                subprocess.CalledProcessError,
                subprocess.TimeoutExpired,
                FileNotFoundError,
            ):
                return False
