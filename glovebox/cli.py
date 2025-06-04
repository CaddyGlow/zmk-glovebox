"""Command-line interface for Glovebox using Typer."""

import json
import logging
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, Optional

import typer

from glovebox import __version__

# Import CLI modules
from glovebox.cli_config import config_app
from glovebox.core.errors import BuildError, ConfigError, FlashError, KeymapError
from glovebox.core.logging import setup_logging
from glovebox.services import (
    create_build_service,
    create_flash_service,
    create_keymap_service,
)


logger = logging.getLogger(__name__)


# Context object for sharing state
class AppContext:
    def __init__(self, verbose: int = 0, log_file: str | None = None):
        self.verbose = verbose
        self.log_file = log_file


# Main app
app = typer.Typer(
    name="glovebox",
    help=f"Glovebox ZMK Keyboard Management Tool v{__version__}",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)

# Subcommands
keymap_app = typer.Typer(
    name="keymap",
    help="Keymap management commands",
    no_args_is_help=True,
)

firmware_app = typer.Typer(
    name="firmware",
    help="Firmware management commands",
    no_args_is_help=True,
)

# Register subcommands
app.add_typer(keymap_app, name="keymap")
app.add_typer(firmware_app, name="firmware")
app.add_typer(config_app, name="config")


# Global callback
@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    verbose: Annotated[
        int,
        typer.Option(
            "-v", "--verbose", count=True, help="Increase verbosity (use -v, -vv)"
        ),
    ] = 0,
    log_file: Annotated[
        str | None, typer.Option("--log-file", help="Log to file")
    ] = None,
    version: Annotated[
        bool, typer.Option("--version", help="Show version and exit")
    ] = False,
) -> None:
    """Glovebox ZMK Keyboard Management Tool."""
    if version:
        print(f"Glovebox v{__version__}")
        raise typer.Exit()

    # If no subcommand was invoked and version wasn't requested, show help
    if ctx.invoked_subcommand is None and not version:
        print(ctx.get_help())
        raise typer.Exit()

    # Store context
    ctx.ensure_object(AppContext)
    ctx.obj.verbose = verbose
    ctx.obj.log_file = log_file

    # Set log level based on verbosity
    log_level = logging.WARNING
    if verbose == 1:
        log_level = logging.INFO
    elif verbose >= 2:
        log_level = logging.DEBUG

    setup_logging(level=log_level, log_file=log_file)


# Error handler decorator
def handle_errors(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to handle common exceptions."""
    from functools import wraps

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except KeymapError as e:
            logger.error(f"Keymap error: {e}")
            raise typer.Exit(1) from e
        except ConfigError as e:
            logger.error(f"Configuration error: {e}")
            raise typer.Exit(1) from e
        except BuildError as e:
            logger.error(f"Build error: {e}")
            raise typer.Exit(1) from e
        except FlashError as e:
            logger.error(f"Flash error: {e}")
            raise typer.Exit(1) from e
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            raise typer.Exit(1) from e
        except FileNotFoundError as e:
            logger.error(f"File not found: {e}")
            raise typer.Exit(1) from e
        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
            raise typer.Exit(1) from e

    return wrapper


# KEYMAP COMMANDS
@keymap_app.command(name="compile")
@handle_errors
def keymap_compile(
    target_prefix: Annotated[
        str,
        typer.Argument(
            help="Target directory and base filename (e.g., 'config/my_glove80')"
        ),
    ],
    profile: Annotated[
        str,
        typer.Option(
            "--profile",
            "-p",
            help="Profile to use (e.g., 'v25.05', 'glove80/mybranch')",
        ),
    ],
    json_file: Annotated[
        str,
        typer.Argument(help="Path to keymap JSON file"),
    ],
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files")
    ] = False,
) -> None:
    """Compile a keymap JSON file into ZMK keymap and config files."""
    # Load JSON data
    json_file_path = Path(json_file)
    if not json_file_path.exists():
        raise typer.BadParameter(f"Input file not found: {json_file_path}")

    logger.info(f"Reading keymap JSON from {json_file_path}...")
    json_data = json.loads(json_file_path.read_text())

    # Load keyboard configuration
    from glovebox.config.keyboard_config import (
        create_keyboard_profile,
        get_available_firmwares,
        get_available_keyboards,
    )

    # Parse profile to get keyboard name and firmware version
    # Format can be either "keyboard" or "keyboard/firmware"
    if "/" in profile:
        keyboard_name, firmware_name = profile.split("/", 1)
    else:
        keyboard_name = profile
        firmware_name = "default"

    logger.debug(f"Using keyboard: {keyboard_name}, firmware: {firmware_name}")

    # Create KeyboardProfile
    try:
        # Create keyboard profile for the specified keyboard and firmware
        keyboard_profile = create_keyboard_profile(keyboard_name, firmware_name)
        logger.debug(f"Created keyboard profile for {keyboard_name}/{firmware_name}")
    except Exception as e:
        # Handle profile creation errors with helpful feedback
        if "not found for keyboard" in str(e):
            # Show available firmwares if the firmware wasn't found
            print(
                f"Error: Firmware '{firmware_name}' not found for keyboard: {keyboard_name}"
            )
            try:
                firmwares = get_available_firmwares(keyboard_name)
                if firmwares:
                    print("Available firmwares:")
                    for fw_name in firmwares:
                        print(f"  • {fw_name}")
            except Exception:
                pass
        else:
            # General configuration error
            print(f"Error: Failed to load keyboard configuration: {e}")
            keyboards = get_available_keyboards()
            print("Available keyboards:")
            for kb in keyboards:
                print(f"  • {kb}")
        raise typer.Exit(1) from e

    # Compile keymap using the KeyboardProfile
    keymap_service = create_keymap_service()
    result = keymap_service.compile(keyboard_profile, json_data, target_prefix)

    if result.success:
        print("✓ Keymap compiled successfully")
        output_files = result.get_output_files()
        for file_type, file_path in output_files.items():
            print(f"  • {file_type}: {file_path}")
    else:
        print("✗ Keymap compilation failed")
        for error in result.errors:
            print(f"  • {error}")
        raise typer.Exit(1) from None


@keymap_app.command()
@handle_errors
def split(
    keymap_file: Annotated[Path, typer.Argument(help="Path to keymap JSON file")],
    output_dir: Annotated[
        Path, typer.Argument(help="Directory to save extracted files")
    ],
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files")
    ] = False,
) -> None:
    """Split a keymap file into individual layer files."""
    if not keymap_file.exists():
        raise typer.BadParameter(f"Keymap file not found: {keymap_file}")

    keymap_service = create_keymap_service()
    result = keymap_service.split(keymap_file=keymap_file, output_dir=output_dir)

    if result.success:
        print(f"✓ Keymap split into layers at {output_dir}")
    else:
        print("✗ Keymap split failed")
        for error in result.errors:
            print(f"  • {error}")
        raise typer.Exit(1) from None


@keymap_app.command()
@handle_errors
def merge(
    input_dir: Annotated[
        Path, typer.Argument(help="Directory with base.json and layers/ subdirectory")
    ],
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Output keymap JSON file path")
    ],
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files")
    ] = False,
) -> None:
    """Merge layer files into a single keymap file."""
    if not input_dir.exists():
        raise typer.BadParameter(f"Input directory not found: {input_dir}")

    keymap_service = create_keymap_service()
    result = keymap_service.merge(input_dir=input_dir, output_file=output)

    if result.success:
        print(f"✓ Keymap merged and saved to {output}")
    else:
        print("✗ Keymap merge failed")
        for error in result.errors:
            print(f"  • {error}")
        raise typer.Exit(1) from None


@keymap_app.command()
@handle_errors
def show(
    json_file: Annotated[
        Path, typer.Argument(help="Path to keyboard layout JSON file")
    ],
    key_width: Annotated[
        int, typer.Option("--key-width", "-w", help="Width for displaying each key")
    ] = 10,
    view_mode: Annotated[
        str | None,
        typer.Option(
            "--view-mode", "-m", help="View mode (normal, compact, split, flat)"
        ),
    ] = None,
    layout: Annotated[
        str | None,
        typer.Option("--layout", "-l", help="Layout name to use for display"),
    ] = None,
    layer: Annotated[
        int | None, typer.Option("--layer", help="Show only specific layer index")
    ] = None,
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            "-p",
            help="Profile to use (e.g., 'glove80', 'glove80/v25.05')",
        ),
    ] = None,
) -> None:
    """Display keymap layout in terminal."""
    if not json_file.exists():
        raise typer.BadParameter(f"JSON file not found: {json_file}")

    json_data = json.loads(json_file.read_text())

    # Create KeyboardProfile if profile is specified
    keyboard_profile = None
    if profile:
        from glovebox.config.keyboard_config import (
            create_keyboard_profile,
            get_available_firmwares,
            get_available_keyboards,
        )

        # Parse profile to get keyboard name and firmware version
        if "/" in profile:
            keyboard_name, firmware_name = profile.split("/", 1)
        else:
            keyboard_name = profile
            # Try to get the default firmware version
            try:
                from glovebox.config.keyboard_config import get_default_firmware

                firmware_name = get_default_firmware(keyboard_name)
            except Exception as e:
                logger.warning(
                    f"Could not determine default firmware for {keyboard_name}: {e}"
                )
                firmware_name = "default"

        try:
            # Create keyboard profile for the specified keyboard and firmware
            keyboard_profile = create_keyboard_profile(keyboard_name, firmware_name)
            logger.debug(
                f"Created keyboard profile for {keyboard_name}/{firmware_name}"
            )
        except Exception as e:
            logger.warning(f"Failed to create keyboard profile: {e}")
            # Don't exit - we can fall back to keyboard_type

    # If a layout is specified or we have a profile, use the enhanced display
    if layout or view_mode or keyboard_profile:
        from glovebox.services.display_service import create_display_service

        display_service = create_display_service()

        # Use the enhanced layout-based display
        result = display_service.display_keymap_with_layout(
            keymap_data=json_data,
            profile=keyboard_profile,
            layout_name=layout,
            keyboard_type=json_data.get("keyboard"),
            view_mode=view_mode,
            layer_index=layer,
        )

        # Print the result
        print(result)
    else:
        # Use the traditional display
        try:
            keymap_service = create_keymap_service()
            result = keymap_service.show(keymap_data=json_data, key_width=key_width)

            # Display the result
            if isinstance(result, list):
                for line in result:
                    print(line)
            else:
                print(result)
        except NotImplementedError as e:
            print(f"Error: {e}")
            print("Please use the --profile option to use the enhanced display service instead.")
            raise typer.Exit(1) from e


@keymap_app.command()
@handle_errors
def validate(
    json_file: Annotated[Path, typer.Argument(help="Path to keymap JSON file")],
) -> None:
    """Validate keymap syntax and structure."""
    if not json_file.exists():
        raise typer.BadParameter(f"JSON file not found: {json_file}")

    json_data = json.loads(json_file.read_text())

    keymap_service = create_keymap_service()
    if keymap_service.validate(json_data):
        print(f"✓ Keymap file {json_file} is valid")
    else:
        print(f"✗ Keymap file {json_file} is invalid")
        raise typer.Exit(1) from None


# FIRMWARE COMMANDS
@firmware_app.command(name="compile")
@handle_errors
def firmware_compile(
    keymap_file: Annotated[Path, typer.Argument(help="Path to keymap (.keymap) file")],
    kconfig_file: Annotated[Path, typer.Argument(help="Path to kconfig (.conf) file")],
    output_dir: Annotated[
        Path, typer.Option("--output-dir", "-o", help="Build output directory")
    ] = Path("build"),
    keyboard: Annotated[
        str, typer.Option("--keyboard", "-k", help="Target keyboard")
    ] = "glove80",
    firmware: Annotated[
        str | None, typer.Option("--firmware", "-f", help="Firmware version to use")
    ] = None,
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            "-p",
            help="Profile to use (e.g., 'glove80', 'glove80/v25.05')",
        ),
    ] = None,
    branch: Annotated[str, typer.Option("--branch", help="Git branch to use")] = "main",
    repo: Annotated[
        str, typer.Option("--repo", help="Git repository")
    ] = "moergo-sc/zmk",
    jobs: Annotated[
        int | None, typer.Option("--jobs", "-j", help="Number of parallel jobs")
    ] = None,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Enable verbose build output")
    ] = False,
) -> None:
    """Compile firmware from keymap and config files."""
    # Validate input files
    if not keymap_file.exists():
        raise typer.BadParameter(f"Keymap file not found: {keymap_file}")
    if not kconfig_file.exists():
        raise typer.BadParameter(f"Kconfig file not found: {kconfig_file}")

    # Initialize build configuration
    build_config = {
        "keymap_path": str(keymap_file),
        "kconfig_path": str(kconfig_file),
        "output_dir": str(output_dir),
        "branch": branch,
        "repo": repo,
        "jobs": jobs,
        "verbose": verbose,
    }

    # Optional: add keyboard to build_config for backward compatibility
    if keyboard:
        build_config["keyboard"] = keyboard

    # Create KeyboardProfile if profile is specified
    keyboard_profile = None

    # Handle the profile parameter (which has priority)
    if profile:
        from glovebox.config.keyboard_config import (
            create_keyboard_profile,
            get_available_firmwares,
            get_available_keyboards,
        )

        # Parse profile to get keyboard name and firmware version
        if "/" in profile:
            keyboard_name, firmware_version = profile.split("/", 1)
        else:
            keyboard_name = profile
            if firmware:
                # Use explicitly provided firmware version
                firmware_version = firmware
            else:
                # Try to get the default firmware version
                try:
                    from glovebox.config.keyboard_config import get_default_firmware

                    firmware_version = get_default_firmware(keyboard_name)
                except Exception as e:
                    logger.warning(
                        f"Could not determine default firmware for {keyboard_name}: {e}"
                    )
                    firmware_version = "default"

        try:
            # Create keyboard profile for the specified keyboard and firmware
            keyboard_profile = create_keyboard_profile(keyboard_name, firmware_version)
            logger.debug(
                f"Created keyboard profile for {keyboard_name}/{firmware_version}"
            )
        except Exception as e:
            # Handle profile creation errors with helpful feedback
            if "not found for keyboard" in str(e):
                # Show available firmwares if the firmware wasn't found
                print(
                    f"Error: Firmware '{firmware_version}' not found for keyboard: {keyboard_name}"
                )
                try:
                    firmwares = get_available_firmwares(keyboard_name)
                    if firmwares:
                        print("Available firmwares:")
                        for fw_name in firmwares:
                            print(f"  • {fw_name}")
                except Exception:
                    pass
            else:
                # General configuration error
                print(f"Error: Failed to load keyboard configuration: {e}")
                keyboards = get_available_keyboards()
                print("Available keyboards:")
                for kb in keyboards:
                    print(f"  • {kb}")
            raise typer.Exit(1) from e
    # Handle keyboard + firmware parameters (if profile not specified)
    elif keyboard and firmware:
        from glovebox.config.keyboard_config import create_keyboard_profile

        try:
            keyboard_profile = create_keyboard_profile(keyboard, firmware)
            logger.debug(f"Created keyboard profile for {keyboard}/{firmware}")
        except Exception as e:
            logger.warning(
                f"Failed to create keyboard profile from keyboard and firmware: {e}"
            )
            # Continue without a profile, will use the build_config

    # Compile firmware using the build service with profile if available
    build_service = create_build_service()
    result = build_service.compile(build_config, profile=keyboard_profile)

    if result.success:
        print("✓ Firmware compiled successfully")
        for message in result.messages:
            print(f"  • {message}")
    else:
        print("✗ Firmware compilation failed")
        for error in result.errors:
            print(f"  • {error}")
        raise typer.Exit(1) from None


@firmware_app.command()
@handle_errors
def flash(
    firmware_file: Annotated[Path, typer.Argument(help="Path to firmware (.uf2) file")],
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            "-p",
            help="Profile to use (e.g., 'glove80', 'glove80/v25.05')",
        ),
    ] = None,
    query: Annotated[
        str, typer.Option("--query", "-q", help="Device query string")
    ] = "vendor=Adafruit and serial~=GLV80-.* and removable=true",
    timeout: Annotated[int, typer.Option("--timeout", help="Timeout in seconds")] = 60,
    count: Annotated[
        int,
        typer.Option(
            "--count", "-n", help="Number of devices to flash (0 for infinite)"
        ),
    ] = 2,
    no_track: Annotated[
        bool, typer.Option("--no-track", help="Disable device tracking")
    ] = False,
) -> None:
    """Flash firmware to keyboard(s)."""
    if not firmware_file.exists():
        raise typer.BadParameter(f"Firmware file not found: {firmware_file}")

    # Create KeyboardProfile if profile is specified
    keyboard_profile = None
    if profile:
        from glovebox.config.keyboard_config import (
            create_keyboard_profile,
            get_available_firmwares,
            get_available_keyboards,
        )

        # Parse profile to get keyboard name and firmware version
        if "/" in profile:
            keyboard_name, firmware_version = profile.split("/", 1)
        else:
            keyboard_name = profile
            # Try to get the default firmware version
            try:
                from glovebox.config.keyboard_config import get_default_firmware

                firmware_version = get_default_firmware(keyboard_name)
            except Exception as e:
                logger.warning(
                    f"Could not determine default firmware for {keyboard_name}: {e}"
                )
                firmware_version = "default"

        try:
            # Create keyboard profile for the specified keyboard and firmware
            keyboard_profile = create_keyboard_profile(keyboard_name, firmware_version)
            logger.debug(
                f"Created keyboard profile for {keyboard_name}/{firmware_version}"
            )
        except Exception as e:
            # Handle profile creation errors with helpful feedback
            if "not found for keyboard" in str(e):
                # Show available firmwares if the firmware wasn't found
                print(
                    f"Error: Firmware '{firmware_version}' not found for keyboard: {keyboard_name}"
                )
                try:
                    firmwares = get_available_firmwares(keyboard_name)
                    if firmwares:
                        print("Available firmwares:")
                        for fw_name in firmwares:
                            print(f"  • {fw_name}")
                except Exception:
                    pass
            else:
                # General configuration error
                print(f"Error: Failed to load keyboard configuration: {e}")
                keyboards = get_available_keyboards()
                print("Available keyboards:")
                for kb in keyboards:
                    print(f"  • {kb}")
            raise typer.Exit(1) from e

    flash_service = create_flash_service()
    result = flash_service.flash(
        firmware_file=firmware_file,
        profile=keyboard_profile,
        query=query,  # query parameter will override profile's query if provided
        timeout=timeout,
        count=count,
        track_flashed=not no_track,
    )

    if result.success:
        print(f"✓ Successfully flashed {result.devices_flashed} device(s)")
        if result.device_details:
            for device in result.device_details:
                if device["status"] == "success":
                    print(f"  • {device['name']}: SUCCESS")
    else:
        print(f"✗ Flash completed with {result.devices_failed} failure(s)")
        if result.device_details:
            for device in result.device_details:
                if device["status"] == "failed":
                    error_msg = device.get("error", "Unknown error")
                    print(f"  • {device['name']}: FAILED - {error_msg}")
        raise typer.Exit(1) from None


@app.command()
def status() -> None:
    """Show system status and diagnostics."""
    print(f"Glovebox v{__version__}\n")

    # Check dependencies
    dependencies = {
        "Docker": "docker --version",
    }

    print("System Dependencies:")
    print("-" * 50)
    print("Tool\tStatus\tVersion")

    for name, cmd in dependencies.items():
        try:
            result = subprocess.run(
                cmd.split(), check=True, capture_output=True, text=True, timeout=5
            )
            print(f"{name}\tAvailable\t{result.stdout.strip()}")
        except (
            subprocess.SubprocessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ):
            print(f"{name}\tMissing\tNot found")

    # Show keyboards and firmwares using the new keyboard config
    from glovebox.config.keyboard_config import (
        get_available_firmwares,
        get_available_keyboards,
        load_keyboard_config_raw,
    )

    # Get keyboards
    keyboards = get_available_keyboards()
    print(f"\nAvailable Keyboards: {len(keyboards)}")
    for keyboard in keyboards:
        print(f"  • {keyboard}")

        try:
            # Load keyboard config to get available firmwares
            config = load_keyboard_config_raw(keyboard)
            firmwares = config.get("firmwares", {})
            if firmwares:
                print(f"    Firmwares: {len(firmwares)}")
                for firmware in firmwares:
                    print(f"      ‣ {firmware}")
        except Exception as e:
            print(f"    Error loading keyboard config: {e}")

    # Environment info
    import platform
    from pathlib import Path

    print("\nEnvironment:")
    print("-" * 50)
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Python: {platform.python_version()}")
    print(f"Working Directory: {Path.cwd().as_posix()}")


def main() -> int:
    """Main CLI entry point."""
    try:
        app()
        return 0
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
