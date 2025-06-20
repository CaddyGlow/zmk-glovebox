"""OS-specific implementations for flash operations."""

import json
import logging
import os
import platform
import re
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
    from glovebox.protocols.flash_os_protocol import FlashOSProtocol

from glovebox.firmware.flash.models import BlockDevice


logger = logging.getLogger(__name__)


def is_wsl2() -> bool:
    """Detect if running in WSL2 environment."""
    try:
        with Path("/proc/version").open() as f:
            version = f.read().lower()
        return "microsoft" in version
    except (OSError, FileNotFoundError):
        return False


def windows_to_wsl_path(windows_path: str) -> str:
    """Convert Windows path to WSL path using wslpath.

    Args:
        windows_path: Windows path (e.g., 'E:\\')

    Returns:
        WSL path (e.g., '/mnt/e/')

    Raises:
        OSError: If wslpath command fails and fallback fails
    """
    try:
        result = subprocess.run(
            ["wslpath", "-u", windows_path],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        # Try fallback conversion for drive letters
        if len(windows_path) >= 2 and windows_path[1] == ":":
            drive_letter = windows_path[0].lower()
            fallback_path = f"/mnt/{drive_letter}/"
            logger.debug(
                "wslpath failed for %s, trying fallback: %s",
                windows_path,
                fallback_path,
            )

            # Test if the fallback path exists
            if Path(fallback_path).exists():
                logger.debug("Fallback path %s exists, using it", fallback_path)
                return fallback_path
            else:
                logger.debug("Fallback path %s does not exist", fallback_path)

        exc_info = logger.isEnabledFor(logging.DEBUG)
        logger.error(
            "Failed to convert Windows path %s: %s", windows_path, e, exc_info=exc_info
        )
        raise OSError(f"Failed to convert Windows path {windows_path}: {e}") from e


def wsl_to_windows_path(wsl_path: str) -> str:
    """Convert WSL path to Windows path using wslpath.

    Args:
        wsl_path: WSL path (e.g., '/mnt/e/')

    Returns:
        Windows path (e.g., 'E:\\')

    Raises:
        OSError: If wslpath command fails
    """
    try:
        result = subprocess.run(
            ["wslpath", "-w", wsl_path],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        raise OSError(f"Failed to convert WSL path {wsl_path}: {e}") from e


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
                logger.warning(f"Could not convert device path {device_name}: {e}")
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
                                        f"Found accessible WSL2 drive: {wsl_path} ({drive_letter})"
                                    )
                                else:
                                    logger.warning(
                                        f"WSL path {wsl_path} for {drive_letter} does not exist"
                                    )
                            except OSError as e:
                                logger.warning(
                                    f"Could not convert path for {drive_letter}: {e}"
                                )
                        else:
                            logger.debug(
                                f"Drive {drive_letter} is not accessible via PowerShell"
                            )

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse PowerShell JSON output: {e}")
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
                                    f"Found accessible WSL2 drive after wait: {wsl_path}"
                                )
                            except OSError:
                                continue

            if not mount_points:
                logger.warning(
                    f"No accessible mount points found for device {device.name}"
                )

        except subprocess.CalledProcessError as e:
            raise OSError(f"Failed to detect drives via PowerShell: {e}") from e
        except subprocess.TimeoutExpired as e:
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
                        logger.debug(f"Successfully dismounted {drive_letter}")
                    except (
                        subprocess.CalledProcessError,
                        subprocess.TimeoutExpired,
                    ) as e:
                        logger.warning(f"Error dismounting {drive_letter}: {e}")
                        success = False

            return success

        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            json.JSONDecodeError,
        ) as e:
            logger.warning(f"Error during unmount: {e}")
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
                f"Copying {firmware_file} to {dest_path_wsl} (via {dest_path_windows})"
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
                logger.debug(f"File copied successfully to {dest_path}")
                return True
            else:
                logger.error(f"File copy verification failed for {dest_path}")
                return False

        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.error(f"Failed to copy firmware file: {e}")
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
                logger.debug(f"Successfully synced filesystem for {mount_point}")
                return True
            else:
                logger.warning(f"Filesystem sync returned code {result.returncode}")
                return False

        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.warning(f"Error during filesystem sync: {e}")
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


class WindowsFlashOS:
    """Windows-specific flash operations using WMI."""

    def __init__(self) -> None:
        """Initialize Windows flash OS adapter."""
        if not WMI_AVAILABLE:
            raise OSError("WMI library not available. Install with: pip install wmi")

        try:
            self.wmi = wmi.WMI()
        except Exception as e:
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
            logger.warning(f"Could not determine device path for {device_name}: {e}")

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
                        logger.debug(f"Found accessible drive: {drive_letter}")
                    else:
                        logger.warning(f"Drive {drive_letter} is not accessible")

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
                            f"Found accessible drive after wait: {drive_letter}"
                        )

            if not mount_points:
                logger.warning(
                    f"No accessible mount points found for device {device.name}"
                )

        except Exception as e:
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
                                    f"Dismount returned code {result} for {drive_letter}"
                                )
                                success = False
                            else:
                                logger.debug(f"Successfully dismounted {drive_letter}")
                            break
                except Exception as e:
                    logger.warning(f"Error dismounting {drive_letter}: {e}")
                    success = False

            return success

        except Exception as e:
            logger.warning(f"Error during unmount: {e}")
            return False

    def copy_firmware_file(self, firmware_file: Path, mount_point: str) -> bool:
        """Copy firmware file to mounted device on Windows."""
        try:
            # Ensure mount_point ends with backslash for Windows
            if not mount_point.endswith("\\"):
                mount_point += "\\"

            dest_path = Path(mount_point) / firmware_file.name
            logger.info(f"Copying {firmware_file} to {dest_path}")

            # Use shutil.copy2 to preserve metadata
            shutil.copy2(firmware_file, mount_point)

            # Verify the file was copied successfully
            if (
                dest_path.exists()
                and dest_path.stat().st_size == firmware_file.stat().st_size
            ):
                logger.debug(f"File copied successfully to {dest_path}")
                return True
            else:
                logger.error(f"File copy verification failed for {dest_path}")
                return False

        except Exception as e:
            logger.error(f"Failed to copy firmware file: {e}")
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
                logger.warning(f"Could not get handle for {drive_letter}")
                return False

            try:
                # Flush file buffers
                result = ctypes.windll.kernel32.FlushFileBuffers(handle)  # type: ignore[attr-defined]
                if result:
                    logger.debug(f"Successfully flushed buffers for {drive_letter}")
                    return True
                else:
                    logger.warning(f"FlushFileBuffers failed for {drive_letter}")
                    return False
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)  # type: ignore[attr-defined]

        except Exception as e:
            logger.warning(f"Error during filesystem sync: {e}")
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
        # Check if running in WSL2
        if is_wsl2():
            logger.debug("Creating WSL2 flash OS adapter")
            try:
                return WSL2FlashOS()
            except OSError as e:
                logger.error(f"Failed to create WSL2 flash adapter: {e}")
                logger.warning("Falling back to Linux adapter")
                return LinuxFlashOS()
        else:
            logger.debug("Creating Linux flash OS adapter")
            return LinuxFlashOS()
    elif system == "Darwin":
        logger.debug("Creating macOS flash OS adapter")
        return MacOSFlashOS()
    elif system == "Windows":
        logger.debug("Creating Windows flash OS adapter")
        try:
            return WindowsFlashOS()
        except OSError as e:
            logger.error(f"Failed to create Windows flash adapter: {e}")
            logger.warning("Falling back to stub adapter")
            return StubFlashOS()
    else:
        logger.warning(f"Unsupported platform: {system}, using stub adapter")
        return StubFlashOS()
