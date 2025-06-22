"""Context extractors for automatic metrics collection from function arguments."""

import inspect
from collections.abc import Callable
from pathlib import Path
from typing import Any

import typer


def extract_cli_context(
    func: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]
) -> dict[str, Any]:
    """Extract context information from CLI command function arguments.

    This extractor is designed to work with typer-based CLI commands and
    extracts common information like profile names, file paths, and options.

    Args:
        func: The CLI command function being called
        args: Positional arguments passed to the function
        kwargs: Keyword arguments passed to the function

    Returns:
        Dictionary of extracted context information

    Example context:
        {
            "profile_name": "glove80/v25.05",
            "input_file": "/path/to/layout.json",
            "output_directory": "/path/to/output",
            "force": True,
            "output_format": "json"
        }
    """
    context: dict[str, Any] = {}

    try:
        # Extract profile information
        if "profile" in kwargs and kwargs["profile"]:
            context["profile_name"] = str(kwargs["profile"])

        # Extract typer context if available
        if "ctx" in kwargs and isinstance(kwargs["ctx"], typer.Context):
            typer_ctx = kwargs["ctx"]
            if (
                hasattr(typer_ctx, "params")
                and "profile_name" not in context
                and "profile" in typer_ctx.params
            ):
                # Extract profile from context params if not in kwargs
                profile = typer_ctx.params["profile"]
                if profile:
                    context["profile_name"] = str(profile)

        # Extract file paths
        common_file_params = [
            "json_file",
            "layout_file",
            "input_file",
            "keymap_file",
            "config_file",
            "firmware_file",
        ]

        for param in common_file_params:
            if param in kwargs and kwargs[param]:
                file_path = kwargs[param]
                if isinstance(file_path, str | Path):
                    # Convert to string and store with descriptive key
                    if param == "json_file" or param in ["layout_file", "input_file"]:
                        context["input_file"] = str(file_path)
                    elif param in ["keymap_file", "config_file"]:
                        context[param] = str(file_path)
                    elif param == "firmware_file":
                        context["firmware_file"] = str(file_path)

        # Extract output directories/files
        output_params = [
            "output_dir",
            "output_directory",
            "output_file_prefix",
            "output_file",
            "output",
        ]

        for param in output_params:
            if param in kwargs and kwargs[param]:
                output_path = kwargs[param]
                if isinstance(output_path, str | Path):
                    context["output_directory"] = str(output_path)

        # Extract common boolean flags
        boolean_flags = ["force", "verbose", "dry_run", "no_cache"]
        for flag in boolean_flags:
            if flag in kwargs and kwargs[flag] is not None:
                context[flag] = bool(kwargs[flag])

        # Extract format options
        if "output_format" in kwargs and kwargs["output_format"]:
            context["output_format"] = str(kwargs["output_format"])

        # Extract limit/count parameters
        numeric_params = ["limit", "count", "timeout"]
        for param in numeric_params:
            if param in kwargs and kwargs[param] is not None:
                context[param] = int(kwargs[param])

        # Try to extract from positional arguments if function signature is available
        try:
            sig = inspect.signature(func)
            param_names = list(sig.parameters.keys())

            # Map positional args to parameter names
            for i, arg in enumerate(args):
                if i < len(param_names):
                    param_name = param_names[i]
                    # Skip context parameter
                    if param_name == "ctx":
                        continue

                    # Handle file-like positional arguments
                    if isinstance(arg, str | Path) and str(arg) != "-":
                        if param_name in ["json_file", "layout_file", "input_file"]:
                            context["input_file"] = str(arg)
                        elif param_name in [
                            "output_dir",
                            "output_file_prefix",
                            "output",
                        ]:
                            context["output_directory"] = str(arg)

        except Exception:
            # Signature inspection failed, continue with what we have
            pass

    except Exception:
        # If context extraction fails, return empty dict
        # This ensures the decorator doesn't break the function
        pass

    return context


def extract_service_context(
    func: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]
) -> dict[str, Any]:
    """Extract context information from service method arguments.

    This extractor works with service classes and extracts common service
    operation context like profile information, file paths, and options.

    Args:
        func: The service method being called
        args: Positional arguments passed to the method
        kwargs: Keyword arguments passed to the method

    Returns:
        Dictionary of extracted context information

    Example context:
        {
            "profile_name": "glove80/v25.05",
            "keyboard_name": "glove80",
            "firmware_version": "v25.05",
            "input_file": "/path/to/layout.json",
            "output_directory": "/path/to/output"
        }
    """
    context: dict[str, Any] = {}

    try:
        # Extract profile information
        if "profile" in kwargs:
            profile = kwargs["profile"]
            if profile and hasattr(profile, "keyboard_name"):
                context["keyboard_name"] = profile.keyboard_name
                context["profile_name"] = profile.keyboard_name
                if hasattr(profile, "firmware_version") and profile.firmware_version:
                    context["firmware_version"] = profile.firmware_version
                    context["profile_name"] = (
                        f"{profile.keyboard_name}/{profile.firmware_version}"
                    )

        # Extract keyboard profile from positional args (common pattern)
        if args and len(args) > 1:
            # Check second argument (profile) - skip first (self)
            profile_arg = args[1]
            if hasattr(profile_arg, "keyboard_name"):
                context["keyboard_name"] = profile_arg.keyboard_name
                context["profile_name"] = profile_arg.keyboard_name
                if (
                    hasattr(profile_arg, "firmware_version")
                    and profile_arg.firmware_version
                ):
                    context["firmware_version"] = profile_arg.firmware_version
                    context["profile_name"] = (
                        f"{profile_arg.keyboard_name}/{profile_arg.firmware_version}"
                    )

        # Extract file paths from common service parameters
        file_params = [
            "json_file_path",
            "layout_file",
            "keymap_file",
            "config_file",
            "firmware_file",
            "input_file",
        ]

        for param in file_params:
            if param in kwargs and kwargs[param]:
                file_path = kwargs[param]
                if isinstance(file_path, str | Path):
                    if param in ["json_file_path", "layout_file", "input_file"]:
                        context["input_file"] = str(file_path)
                    else:
                        context[param] = str(file_path)

        # Extract output information
        output_params = [
            "output_dir",
            "output_directory",
            "output_file_prefix",
            "output_path",
        ]

        for param in output_params:
            if param in kwargs and kwargs[param]:
                output_path = kwargs[param]
                if isinstance(output_path, str | Path):
                    context["output_directory"] = str(output_path)

        # Extract service-specific flags
        if "force" in kwargs and kwargs["force"] is not None:
            context["force"] = bool(kwargs["force"])

        # Extract configuration information
        if "config" in kwargs and kwargs["config"]:
            config = kwargs["config"]
            if hasattr(config, "build_matrix") and hasattr(
                config.build_matrix, "board"
            ):
                context["board_targets"] = config.build_matrix.board

    except Exception:
        # If context extraction fails, return empty dict
        pass

    return context


def extract_compilation_context(
    func: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]
) -> dict[str, Any]:
    """Extract context information from compilation service arguments.

    This extractor is specialized for compilation operations and extracts
    build-specific context like board targets, Docker images, and workspace paths.

    Args:
        func: The compilation function being called
        args: Positional arguments passed to the function
        kwargs: Keyword arguments passed to the function

    Returns:
        Dictionary of extracted context information

    Example context:
        {
            "compilation_strategy": "zmk_config",
            "board_targets": ["nice_nano_v2"],
            "docker_image": "zmkfirmware/zmk-build-arm:stable",
            "workspace_path": "/tmp/zmk_workspace"
        }
    """
    context: dict[str, Any] = {}

    try:
        # Extract compilation configuration
        if "config" in kwargs and kwargs["config"]:
            config = kwargs["config"]

            # Extract compilation strategy
            if hasattr(config, "type"):
                context["compilation_strategy"] = config.type
            elif hasattr(config, "__class__"):
                # Infer strategy from class name
                class_name = config.__class__.__name__.lower()
                if "zmk" in class_name:
                    context["compilation_strategy"] = "zmk_config"
                elif "moergo" in class_name:
                    context["compilation_strategy"] = "moergo"

            # Extract build targets
            if hasattr(config, "build_matrix"):
                build_matrix = config.build_matrix
                if hasattr(build_matrix, "board"):
                    context["board_targets"] = build_matrix.board

            # Extract Docker image
            if hasattr(config, "image"):
                context["docker_image"] = config.image

            # Extract repository information
            if hasattr(config, "repository"):
                context["repository"] = config.repository
            if hasattr(config, "branch"):
                context["branch"] = config.branch

        # Extract workspace path
        if "workspace_path" in kwargs and kwargs["workspace_path"]:
            workspace_path = kwargs["workspace_path"]
            if isinstance(workspace_path, str | Path):
                context["workspace_path"] = str(workspace_path)

        # Extract file paths
        file_params = ["keymap_file", "config_file", "json_file"]
        for param in file_params:
            if param in kwargs and kwargs[param]:
                file_path = kwargs[param]
                if isinstance(file_path, str | Path):
                    context[param] = str(file_path)

        # Extract output directory
        if "output_dir" in kwargs and kwargs["output_dir"]:
            output_dir = kwargs["output_dir"]
            if isinstance(output_dir, str | Path):
                context["output_directory"] = str(output_dir)

    except Exception:
        # If context extraction fails, return empty dict
        pass

    return context


def extract_flash_context(
    func: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]
) -> dict[str, Any]:
    """Extract context information from firmware flashing operations.

    This extractor is specialized for firmware flashing and extracts
    device and firmware information.

    Args:
        func: The flash function being called
        args: Positional arguments passed to the function
        kwargs: Keyword arguments passed to the function

    Returns:
        Dictionary of extracted context information

    Example context:
        {
            "firmware_file": "/path/to/firmware.uf2",
            "device_path": "/dev/sdb1",
            "device_vendor_id": "2e8a",
            "device_product_id": "0003"
        }
    """
    context: dict[str, Any] = {}

    try:
        # Extract firmware file
        if "firmware_file" in kwargs and kwargs["firmware_file"]:
            firmware_file = kwargs["firmware_file"]
            if isinstance(firmware_file, str | Path):
                context["firmware_file"] = str(firmware_file)
                # Extract file size if file exists
                try:
                    file_path = Path(firmware_file)
                    if file_path.exists():
                        context["firmware_size_bytes"] = file_path.stat().st_size
                except Exception:
                    pass

        # Extract device information
        device_params = ["device_path", "device", "mount_point"]
        for param in device_params:
            if param in kwargs and kwargs[param]:
                context["device_path"] = str(kwargs[param])

        # Extract USB device information
        usb_params = [
            "vendor_id",
            "product_id",
            "device_vendor_id",
            "device_product_id",
        ]
        for param in usb_params:
            if param in kwargs and kwargs[param]:
                if "vendor" in param:
                    context["device_vendor_id"] = str(kwargs[param])
                elif "product" in param:
                    context["device_product_id"] = str(kwargs[param])

        # Extract profile information for device detection
        if "profile" in kwargs:
            profile = kwargs["profile"]
            if profile and hasattr(profile, "keyboard_name"):
                context["keyboard_name"] = profile.keyboard_name

    except Exception:
        # If context extraction fails, return empty dict
        pass

    return context
