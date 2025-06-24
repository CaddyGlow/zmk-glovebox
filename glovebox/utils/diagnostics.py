"""Comprehensive diagnostic data collection for Glovebox."""

import json
import logging
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from glovebox.config.user_config import UserConfig


logger = logging.getLogger(__name__)


def collect_system_diagnostics() -> dict[str, Any]:
    """Collect comprehensive system environment diagnostics.

    Returns:
        Dictionary containing system diagnostics including platform info,
        file system access, disk space, and directory permissions.
    """
    diagnostics: dict[str, Any] = {
        "environment": {
            "platform": f"{platform.system()} {platform.release()}",
            "python_version": platform.python_version(),
            "python_executable": sys.executable,
            "working_directory": str(Path.cwd()),
            "user_home": str(Path.home()),
        },
        "file_system": {},
        "disk_space": {},
    }

    # XDG directories
    try:
        xdg_env = os.getenv("XDG_CONFIG_HOME")
        if xdg_env:
            diagnostics["environment"]["xdg_config_home"] = str(Path(xdg_env))
        else:
            diagnostics["environment"]["xdg_config_home"] = str(Path.home() / ".config")
    except Exception as e:
        logger.debug("Error getting XDG config home: %s", e)
        diagnostics["environment"]["xdg_config_home"] = "error"

    # File system access checks using FileAdapter
    try:
        from glovebox.adapters.file_adapter import create_file_adapter

        file_adapter = create_file_adapter()

        temp_dir = (
            Path("/tmp")
            if platform.system() != "Windows"
            else Path(os.getenv("TEMP", "C:\\temp"))
        )

        directories_to_check = {
            "temp_directory": temp_dir,
            "config_directory": Path.home() / ".config" / "glovebox",
            "working_directory": Path.cwd(),
        }

        for dir_name, dir_path in directories_to_check.items():
            try:
                diagnostics["file_system"][f"{dir_name}_path"] = str(dir_path)
                diagnostics["file_system"][f"{dir_name}_exists"] = (
                    file_adapter.check_exists(dir_path)
                )
                diagnostics["file_system"][f"{dir_name}_writable"] = (
                    _check_directory_writable(file_adapter, dir_path)
                )
            except Exception as e:
                logger.debug("Error checking directory %s: %s", dir_path, e)
                diagnostics["file_system"][f"{dir_name}_error"] = str(e)
    except Exception as e:
        logger.debug("Error creating file adapter: %s", e)
        diagnostics["file_system"]["adapter_error"] = str(e)

    # Disk space information
    try:
        cwd_usage = shutil.disk_usage(Path.cwd())
        diagnostics["disk_space"]["available_gb"] = round(cwd_usage.free / (1024**3), 2)
        diagnostics["disk_space"]["total_gb"] = round(cwd_usage.total / (1024**3), 2)
    except Exception as e:
        logger.debug("Error getting disk usage: %s", e)
        diagnostics["disk_space"]["error"] = str(e)

    return diagnostics


def collect_docker_diagnostics() -> dict[str, Any]:
    """Collect comprehensive Docker environment diagnostics.

    Returns:
        Dictionary containing Docker availability, daemon status, version info,
        required images, and capabilities.
    """
    diagnostics: dict[str, Any] = {
        "availability": "unknown",
        "daemon_status": "unknown",
        "version_info": {},
        "images": {},
        "capabilities": {},
    }

    # Basic Docker availability using DockerAdapter
    try:
        from glovebox.adapters.docker_adapter import create_docker_adapter

        docker_adapter = create_docker_adapter()
        if docker_adapter.is_available():
            diagnostics["availability"] = "available"
            # Get version info with subprocess (DockerAdapter doesn't expose version directly)
            try:
                result = subprocess.run(
                    ["docker", "--version"],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                diagnostics["version_info"]["client"] = result.stdout.strip()
            except Exception:
                diagnostics["version_info"]["client"] = "Available (version unknown)"
        else:
            diagnostics["availability"] = "unavailable"
            diagnostics["version_info"]["client"] = "Not found"
            return diagnostics
    except Exception as e:
        logger.debug("Error creating Docker adapter: %s", e)
        diagnostics["availability"] = "unavailable"
        diagnostics["version_info"]["client"] = "Adapter error"
        diagnostics["adapter_error"] = str(e)
        return diagnostics

    # Docker daemon status
    try:
        subprocess.run(
            ["docker", "info"], check=True, capture_output=True, text=True, timeout=10
        )
        diagnostics["daemon_status"] = "running"
    except subprocess.SubprocessError:
        diagnostics["daemon_status"] = "stopped"
    except subprocess.TimeoutExpired:
        diagnostics["daemon_status"] = "timeout"
    except Exception as e:
        logger.debug("Error checking Docker daemon: %s", e)
        diagnostics["daemon_status"] = "error"

    # Docker server version (if daemon is running)
    if diagnostics["daemon_status"] == "running":
        try:
            result = subprocess.run(
                ["docker", "version", "--format", "{{.Server.Version}}"],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
            diagnostics["version_info"]["server"] = result.stdout.strip()
        except Exception as e:
            logger.debug("Error getting Docker server version: %s", e)
            diagnostics["version_info"]["server"] = "unknown"

    # Check for required images
    required_images = [
        "moergo-zmk-build:latest",
        "moergo-zmk-build:v25.05",
    ]

    for image in required_images:
        try:
            subprocess.run(
                ["docker", "image", "inspect", image],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
            diagnostics["images"][image] = "available"
        except subprocess.SubprocessError:
            diagnostics["images"][image] = "missing"
        except Exception as e:
            logger.debug("Error checking image %s: %s", image, e)
            diagnostics["images"][image] = "error"

    # Test Docker capabilities using DockerAdapter
    if diagnostics["daemon_status"] == "running":
        try:
            from glovebox.adapters.docker_adapter import create_docker_adapter

            docker_adapter = create_docker_adapter()
            diagnostics["capabilities"] = _test_docker_capabilities_with_adapter(
                docker_adapter
            )
        except Exception as e:
            logger.debug("Error testing Docker capabilities: %s", e)
            diagnostics["capabilities"] = {"error": str(e)}

    return diagnostics


def collect_usb_flash_diagnostics() -> dict[str, Any]:
    """Collect USB device detection and flash operation diagnostics.

    Returns:
        Dictionary containing USB detection capabilities, available devices,
        OS-specific tools, and flash permissions.
    """
    diagnostics: dict[str, Any] = {
        "usb_detection": {"status": "unknown"},
        "os_capabilities": {},
        "detected_devices": [],
        "permissions": {},
    }

    # Platform-specific USB detection
    system = platform.system().lower()

    if system == "linux":
        diagnostics["usb_detection"]["platform_adapter"] = "LinuxUSBMonitor"
        diagnostics["os_capabilities"] = _check_linux_flash_capabilities()
    elif system == "darwin":
        diagnostics["usb_detection"]["platform_adapter"] = "MacOSUSBMonitor"
        diagnostics["os_capabilities"] = _check_macos_flash_capabilities()
    else:
        diagnostics["usb_detection"]["platform_adapter"] = "StubUSBMonitor"
        diagnostics["os_capabilities"]["mount_tool"] = "unavailable"
        diagnostics["usb_detection"]["status"] = "unsupported_platform"
        return diagnostics

    # Test USB device detection using USBAdapter
    try:
        from glovebox.adapters.usb_adapter import create_usb_adapter
        from glovebox.firmware.flash.device_detector import create_device_detector
        from glovebox.firmware.flash.flash_operations import create_flash_operations
        from glovebox.firmware.flash.os_adapters import create_linux_flash_adapter
        from glovebox.firmware.flash.usb_monitor import (
            MountPointCache,
            create_usb_monitor,
        )

        # Create required dependencies for USB adapter
        os_adapter = create_linux_flash_adapter()
        flash_operations = create_flash_operations(os_adapter)
        mount_cache = MountPointCache()
        usb_monitor = create_usb_monitor()
        detector = create_device_detector(usb_monitor, mount_cache)

        usb_adapter = create_usb_adapter(flash_operations, detector)
        devices = usb_adapter.get_all_devices()

        diagnostics["usb_detection"]["status"] = "available"
        diagnostics["detected_devices"] = [
            {
                "name": device.name,
                "path": device.path,
                "vendor": getattr(device, "vendor", "unknown"),
                "model": getattr(device, "model", "unknown"),
                "serial": getattr(device, "serial", "unknown"),
                "vendor_id": getattr(device, "vendor_id", "unknown"),
                "product_id": getattr(device, "product_id", "unknown"),
                "size": getattr(device, "size", 0),
                "removable": getattr(device, "removable", False),
                "type": getattr(device, "type", "unknown"),
            }
            for device in devices
        ]
    except Exception as e:
        logger.debug("Error detecting USB devices: %s", e)
        diagnostics["usb_detection"]["status"] = "error"
        diagnostics["usb_detection"]["error"] = str(e)

    # Check mount permissions
    diagnostics["permissions"] = _check_mount_permissions()

    return diagnostics


def collect_config_diagnostics(
    user_config: "UserConfig",
) -> dict[str, Any]:
    """Collect configuration loading and validation diagnostics.

    Args:
        user_config: Optional user configuration instance to use for keyboard discovery

    Returns:
        Dictionary containing user config status, environment variables,
        keyboard discovery, and profile capabilities.
    """
    diagnostics: dict[str, Any] = {
        "user_config": {
            "search_paths": [],
            "found_config": None,
            "environment_vars": {},
            "validation_status": "unknown",
        },
        "keyboard_discovery": {
            "default_paths": [],
            "accessible_paths": [],
            "inaccessible_paths": [],
        },
        "profile_capabilities": {
            "keyboard_only_profiles": "supported",
            "full_profiles": "supported",
        },
    }

    # User config loading
    try:
        diagnostics["user_config"]["validation_status"] = "valid"
        diagnostics["user_config"]["found_config"] = (
            str(user_config._main_config_path)
            if user_config._main_config_path
            else "No config file"
        )
    except Exception as e:
        logger.debug("Error loading user config: %s", e)
        diagnostics["user_config"]["validation_status"] = "error"
        diagnostics["user_config"]["validation_errors"] = [str(e)]

    # Environment variables
    env_vars = {}
    for key, value in os.environ.items():
        if key.startswith("GLOVEBOX_"):
            env_vars[key] = value
    diagnostics["user_config"]["environment_vars"] = env_vars

    # Keyboard discovery paths
    try:
        from glovebox.config.keyboard_profile import get_available_keyboards

        keyboards = get_available_keyboards(user_config)
        diagnostics["keyboard_discovery"]["found_keyboards"] = len(keyboards)

        # Test loading each keyboard
        keyboard_status = []
        from glovebox.config.keyboard_profile import load_keyboard_config

        for keyboard in keyboards:
            try:
                config = load_keyboard_config(keyboard, user_config)
                keyboard_status.append(
                    {
                        "name": keyboard,
                        "status": "ok",
                        "has_firmwares": bool(getattr(config, "firmwares", {})),
                    }
                )
            except Exception as e:
                keyboard_status.append(
                    {
                        "name": keyboard,
                        "status": "error",
                        "error": str(e),
                    }
                )

        diagnostics["keyboard_discovery"]["keyboard_status"] = keyboard_status

    except Exception as e:
        logger.debug("Error in keyboard discovery: %s", e)
        diagnostics["keyboard_discovery"]["error"] = str(e)

    return diagnostics


def collect_layout_diagnostics() -> dict[str, Any]:
    """Collect layout processing and ZMK generation diagnostics.

    Returns:
        Dictionary containing layout processing capabilities, template engine
        status, behavior registry, and ZMK generation capabilities.
    """
    diagnostics: dict[str, Any] = {
        "processing": {
            "json_parser": "available",
            "template_engine": "unknown",
            "behavior_registry": "unknown",
            "component_extraction": "unknown",
        },
        "zmk_generation": {
            "keymap_generation": "unknown",
            "config_generation": "unknown",
            "dtsi_generation": "unknown",
        },
    }

    # Test JSON parsing (basic Python capability)
    try:
        json.loads('{"test": "value"}')
        diagnostics["processing"]["json_parser"] = "available"
    except Exception:
        diagnostics["processing"]["json_parser"] = "error"

    # Test template engine using TemplateAdapter
    try:
        from glovebox.adapters.template_adapter import create_template_adapter

        template_adapter = create_template_adapter()
        # Simple template test
        result = template_adapter.render_string("Hello {{ name }}", {"name": "World"})
        if "Hello World" in result:
            diagnostics["processing"]["template_engine"] = "available"
        else:
            diagnostics["processing"]["template_engine"] = "error"
    except Exception as e:
        logger.debug("Error testing template engine: %s", e)
        diagnostics["processing"]["template_engine"] = "error"
        diagnostics["processing"]["template_error"] = str(e)

    # Test layout service creation
    try:
        from glovebox.adapters import create_file_adapter, create_template_adapter
        from glovebox.layout import (
            create_behavior_registry,
            create_grid_layout_formatter,
            create_layout_component_service,
            create_layout_display_service,
            create_layout_service,
        )
        from glovebox.layout.behavior.formatter import BehaviorFormatterImpl
        from glovebox.layout.zmk_generator import ZmkFileContentGenerator

        # Create all dependencies for layout service
        file_adapter = create_file_adapter()
        template_adapter = create_template_adapter()
        behavior_registry = create_behavior_registry()
        behavior_formatter = BehaviorFormatterImpl(behavior_registry)
        dtsi_generator = ZmkFileContentGenerator(behavior_formatter)
        layout_generator = create_grid_layout_formatter()
        component_service = create_layout_component_service(file_adapter)
        layout_display_service = create_layout_display_service(layout_generator)

        layout_service = create_layout_service(
            file_adapter=file_adapter,
            template_adapter=template_adapter,
            behavior_registry=behavior_registry,
            component_service=component_service,
            layout_service=layout_display_service,
            behavior_formatter=behavior_formatter,
            dtsi_generator=dtsi_generator,
        )
        diagnostics["processing"]["component_extraction"] = "available"
        diagnostics["zmk_generation"]["keymap_generation"] = "available"
        diagnostics["zmk_generation"]["config_generation"] = "available"
        diagnostics["zmk_generation"]["dtsi_generation"] = "available"
    except Exception as e:
        logger.debug("Error creating layout service: %s", e)
        diagnostics["processing"]["component_extraction"] = "error"
        diagnostics["zmk_generation"]["keymap_generation"] = "error"
        diagnostics["zmk_generation"]["config_generation"] = "error"
        diagnostics["zmk_generation"]["dtsi_generation"] = "error"
        diagnostics["layout_service_error"] = str(e)

    return diagnostics


def collect_all_diagnostics(user_config: "UserConfig | None" = None) -> dict[str, Any]:
    """Collect all diagnostic data in a structured format.

    Args:
        user_config: Optional user configuration instance

    Returns:
        Complete diagnostic data dictionary with all subsystems.
    """
    if user_config is None:
        from glovebox.config.user_config import create_user_config

        user_config = create_user_config()

    from importlib.metadata import distribution

    diagnostics: dict[str, Any] = {
        "version": distribution("glovebox").version,
        "timestamp": None,  # Could add timestamp if needed
        "system": {},
        "docker": {},
        "usb_flash": {},
        "configuration": {},
        "layout": {},
    }

    # Collect all diagnostic data with error handling
    collectors = [
        ("system", collect_system_diagnostics),
        ("docker", collect_docker_diagnostics),
        ("usb_flash", collect_usb_flash_diagnostics),
        ("configuration", lambda: collect_config_diagnostics(user_config)),
        ("layout", collect_layout_diagnostics),
    ]

    for section_name, collector_func in collectors:
        try:
            diagnostics[section_name] = collector_func()
        except Exception as e:
            logger.error("Error collecting %s diagnostics: %s", section_name, e)
            diagnostics[section_name] = {
                "status": "collection_error",
                "error": str(e),
            }

    return diagnostics


# Helper functions


def _check_directory_writable(file_adapter: Any, directory: Path) -> bool:
    """Check if a directory is writable using file adapter."""
    try:
        if not file_adapter.check_exists(directory) or not file_adapter.is_dir(
            directory
        ):
            return False

        test_file = directory / ".glovebox_write_test"
        file_adapter.write_text(test_file, "test")
        file_adapter.remove_file(test_file)
        return True
    except Exception:
        return False


def _test_docker_capabilities() -> dict[str, str]:
    """Test Docker capabilities like volume mounts and network access (legacy function)."""
    capabilities = {
        "volume_mounts": "unknown",
        "network_access": "unknown",
        "pull_access": "unknown",
    }

    # Test volume mount capability
    try:
        temp_dir = Path("/tmp") if platform.system() != "Windows" else Path("C:\\temp")
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{temp_dir}:/test",
                "alpine:latest",
                "ls",
                "/test",
            ],
            check=True,
            capture_output=True,
            timeout=10,
        )
        capabilities["volume_mounts"] = "available"
    except Exception:
        capabilities["volume_mounts"] = "limited"

    # Test network access
    try:
        subprocess.run(
            ["docker", "run", "--rm", "alpine:latest", "ping", "-c", "1", "8.8.8.8"],
            check=True,
            capture_output=True,
            timeout=10,
        )
        capabilities["network_access"] = "available"
    except Exception:
        capabilities["network_access"] = "limited"

    return capabilities


def _test_docker_capabilities_with_adapter(docker_adapter: Any) -> dict[str, str]:
    """Test Docker capabilities using DockerAdapter."""
    capabilities = {
        "volume_mounts": "unknown",
        "network_access": "unknown",
        "basic_container_run": "unknown",
    }

    # Variables for Docker operations
    volumes: list[tuple[str, str]]
    environment: dict[str, str]
    command: list[str]

    # Test basic container run capability
    try:
        volumes = []
        environment = {}
        command = ["echo", "test"]
        result = docker_adapter.run_container(
            "alpine:latest", volumes, environment, command
        )
        if result[0] == 0:  # Exit code 0 means success
            capabilities["basic_container_run"] = "available"
        else:
            capabilities["basic_container_run"] = "limited"
    except Exception as e:
        logger.debug("Docker basic container test failed: %s", e)
        capabilities["basic_container_run"] = "limited"

    # Test volume mount capability
    try:
        temp_dir = Path("/tmp") if platform.system() != "Windows" else Path("C:\\temp")
        volumes = [(str(temp_dir), "/test")]
        environment = {}
        command = ["ls", "/test"]
        result = docker_adapter.run_container(
            "alpine:latest", volumes, environment, command
        )
        if result[0] == 0:
            capabilities["volume_mounts"] = "available"
        else:
            capabilities["volume_mounts"] = "limited"
    except Exception as e:
        logger.debug("Docker volume mount test failed: %s", e)
        capabilities["volume_mounts"] = "limited"

    # Test network access (simplified)
    try:
        volumes = []
        environment = {}
        command = ["ping", "-c", "1", "8.8.8.8"]
        result = docker_adapter.run_container(
            "alpine:latest", volumes, environment, command
        )
        if result[0] == 0:
            capabilities["network_access"] = "available"
        else:
            capabilities["network_access"] = "limited"
    except Exception as e:
        logger.debug("Docker network test failed: %s", e)
        capabilities["network_access"] = "limited"

    return capabilities


def _check_linux_flash_capabilities() -> dict[str, Any]:
    """Check Linux-specific flash capabilities."""
    capabilities = {
        "mount_tool": "unknown",
        "mount_tool_version": "unknown",
        "filesystem_sync": "unknown",
    }

    # Check udisksctl
    try:
        if not shutil.which("udisksctl"):
            raise OSError("`udisksctl` command not found. Please install udisks2.")
        capabilities["mount_tool"] = "udisksctl"
        capabilities["mount_tool_version"] = ""
    except Exception:
        capabilities["mount_tool"] = "unavailable"

    # Check sync command
    try:
        subprocess.run(["sync"], check=True, timeout=5)
        capabilities["filesystem_sync"] = "available"
    except Exception:
        capabilities["filesystem_sync"] = "unavailable"

    return capabilities


def _check_macos_flash_capabilities() -> dict[str, Any]:
    """Check macOS-specific flash capabilities."""
    capabilities = {
        "mount_tool": "unknown",
        "mount_tool_version": "unknown",
        "filesystem_sync": "unknown",
    }

    # Check diskutil
    try:
        result = subprocess.run(
            ["diskutil", "info", "/"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        capabilities["mount_tool"] = "diskutil"
        capabilities["mount_tool_version"] = "available"
    except Exception:
        capabilities["mount_tool"] = "unavailable"

    # Sync is usually available on macOS
    capabilities["filesystem_sync"] = "available"

    return capabilities


def _check_mount_permissions() -> dict[str, str]:
    """Check filesystem mount permissions."""
    permissions = {
        "device_access": "unknown",
        "mount_permissions": "unknown",
    }

    # Basic check for device access (platform-specific)
    system = platform.system().lower()

    if system == "linux":
        # Check if user is in disk/storage groups or has sudo access
        try:
            import grp

            user_groups = [
                g.gr_name for g in grp.getgrall() if os.getlogin() in g.gr_mem
            ]
            if any(
                group in user_groups
                for group in ["disk", "storage", "wheel", "sudo", "plugdev"]
            ):
                permissions["device_access"] = "elevated"
            else:
                permissions["device_access"] = "limited"
        except Exception:
            permissions["device_access"] = "unknown"
    elif system == "darwin":
        # On macOS, diskutil usually works for most users
        permissions["device_access"] = "available"

    return permissions
