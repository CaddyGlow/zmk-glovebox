"""Common CLI parameter definitions for reuse across commands."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile


logger = logging.getLogger(__name__)

# Cache keys and TTL settings for completion data
PROFILE_COMPLETION_CACHE_KEY = "profile_completion_data_v1"
PROFILE_COMPLETION_TTL = 300  # 5 minutes

LAYER_NAMES_CACHE_KEY_PREFIX = "layer_names_"
LAYER_NAMES_TTL = 60  # 1 minute

STATIC_COMPLETION_CACHE_KEY = "static_completion_data_v1"
STATIC_COMPLETION_TTL = 86400  # 24 hours


def _get_cached_profile_data() -> tuple[list[str], dict[str, list[str]]]:
    """Get cached profile data using persistent filesystem cache."""
    try:
        from glovebox.config import create_user_config
        from glovebox.config.keyboard_profile import (
            get_available_firmwares,
            get_available_keyboards,
        )
        from glovebox.core.cache import create_default_cache

        # Get user config and create appropriate cache
        user_config = create_user_config()

        # Create cache using default settings for profile completion performance
        # Tab completion always uses cache for performance, even if general caching is disabled
        cache = create_default_cache(tag="cli_completion")

        # Try to get cached data first
        cached_data = cache.get(PROFILE_COMPLETION_CACHE_KEY)
        if cached_data is not None:
            logger.debug("Profile completion cache hit")
            return cached_data["keyboards"], cached_data["keyboards_with_firmwares"]

        # Cache miss - need to build the data
        logger.debug("Profile completion cache miss - building data")
        keyboards = get_available_keyboards(user_config)

        # Pre-build keyboard/firmware combinations with optimized error handling
        keyboards_with_firmwares = {}
        for keyboard in keyboards:
            try:
                firmwares = get_available_firmwares(keyboard, user_config)
                # Convert to list once to avoid repeated conversions
                keyboards_with_firmwares[keyboard] = (
                    list(firmwares) if firmwares else []
                )
            except Exception as e:
                # On error, provide empty list instead of failing completely
                logger.debug("Failed to get firmwares for %s: %s", keyboard, e)
                keyboards_with_firmwares[keyboard] = []

        # Cache the data with TTL
        cache_data = {
            "keyboards": keyboards,
            "keyboards_with_firmwares": keyboards_with_firmwares,
        }
        cache.set(PROFILE_COMPLETION_CACHE_KEY, cache_data, ttl=PROFILE_COMPLETION_TTL)
        logger.debug(
            "Profile completion data cached for %d seconds", PROFILE_COMPLETION_TTL
        )

        return keyboards, keyboards_with_firmwares
    except Exception as e:
        # If cache operations fail, return empty data but don't crash
        logger.debug("Profile completion cache failed: %s", e)
        return [], {}


def complete_profile_names(incomplete: str) -> list[str]:
    """Fast tab completion for profile names (keyboard/firmware format).

    Uses caching to avoid repeated expensive config loading and firmware lookups.
    Cache expires after 30 seconds to balance performance and freshness.

    Args:
        incomplete: Partial profile string being typed

    Returns:
        List of matching profile strings
    """
    try:
        keyboards, keyboards_with_firmwares = _get_cached_profile_data()

        if not keyboards:
            return []

        # If incomplete contains "/", complete firmware part only
        if "/" in incomplete:
            keyboard_part, firmware_part = incomplete.split("/", 1)
            if keyboard_part in keyboards_with_firmwares:
                firmwares = keyboards_with_firmwares[keyboard_part]
                return [
                    f"{keyboard_part}/{firmware}"
                    for firmware in firmwares
                    if firmware.startswith(firmware_part)
                ]
            return []

        # For keyboard completion, use early exit optimization
        if not incomplete:
            # Return all available profiles for empty string
            profiles = list(keyboards)
            for keyboard, firmwares in keyboards_with_firmwares.items():
                profiles.extend([f"{keyboard}/{firmware}" for firmware in firmwares])
            return sorted(set(profiles))

        # Filter keyboards first, then add firmware combinations only for matches
        matching_keyboards = []
        profiles = []

        for keyboard in keyboards:
            if keyboard.startswith(incomplete):
                matching_keyboards.append(keyboard)
                profiles.append(keyboard)
                # Add firmware combinations for this keyboard
                firmwares = keyboards_with_firmwares.get(keyboard, [])
                profiles.extend([f"{keyboard}/{firmware}" for firmware in firmwares])

        return sorted(set(profiles)) if profiles else []
    except Exception:
        # If completion fails, return empty list
        return []


def _get_cached_static_completion_data() -> dict[str, list[str]]:
    """Get cached static completion data (view modes, output formats)."""
    try:
        from glovebox.core.cache import create_default_cache

        cache = create_default_cache(tag="cli_completion")
        cached_data = cache.get(STATIC_COMPLETION_CACHE_KEY)

        if cached_data is not None:
            return cached_data  # type: ignore[no-any-return]

        # Build static completion data
        static_data = {
            "view_modes": ["normal", "compact", "split", "flat"],
            "output_formats": [
                "text",
                "json",
                "markdown",
                "table",
                "yaml",
                "rich-table",
                "rich-panel",
                "rich-grid",
            ],
        }

        cache.set(STATIC_COMPLETION_CACHE_KEY, static_data, ttl=STATIC_COMPLETION_TTL)
        return static_data
    except Exception:
        return {
            "view_modes": ["normal", "compact", "split", "flat"],
            "output_formats": [
                "text",
                "json",
                "table",
                "rich-table",
                "rich-panel",
                "rich-grid",
            ],
        }


def complete_view_modes(incomplete: str) -> list[str]:
    """Tab completion for view modes."""
    try:
        static_data = _get_cached_static_completion_data()
        view_modes = static_data.get("view_modes", [])

        if not incomplete:
            return view_modes

        return [mode for mode in view_modes if mode.startswith(incomplete)]
    except Exception:
        return []


def complete_output_formats(incomplete: str) -> list[str]:
    """Tab completion for output formats."""
    try:
        static_data = _get_cached_static_completion_data()
        formats = static_data.get("output_formats", [])

        if not incomplete:
            return formats

        return [fmt for fmt in formats if fmt.startswith(incomplete)]
    except Exception:
        return []


def complete_json_files(incomplete: str) -> list[str]:
    """Tab completion for JSON files with path completion."""
    try:
        from pathlib import Path

        if not incomplete:
            return ["examples/layouts/", "./", "../"]

        path = Path(incomplete)

        if incomplete.endswith("/") and path.is_dir():
            return [
                str(item) + ("/" if item.is_dir() else "")
                for item in path.iterdir()
                if item.is_dir() or item.suffix == ".json"
            ]

        if "/" in incomplete:
            parent = path.parent
            name_prefix = path.name
        else:
            parent = Path()
            name_prefix = incomplete

        if parent.exists():
            matches = []
            for item in parent.iterdir():
                if item.name.startswith(name_prefix):
                    if item.is_dir():
                        matches.append(str(item) + "/")
                    elif item.suffix == ".json":
                        matches.append(str(item))
            return sorted(matches)

        return []
    except Exception:
        return []


def complete_layer_names(ctx: typer.Context, incomplete: str) -> list[str]:
    """Tab completion for layer names based on JSON file context."""
    try:
        json_file = _extract_json_file_from_context(ctx)

        if not json_file:
            return []

        layer_names = _get_cached_layer_names(json_file)

        if not layer_names:
            return []

        completions = []

        # Add both indices and names
        for i, name in enumerate(layer_names):
            completions.append(str(i))  # Numeric index
            completions.append(name.lower())  # Lowercase name
            if name != name.lower():
                completions.append(name)  # Original case name

        if not incomplete:
            return sorted(set(completions))

        incomplete_lower = incomplete.lower()
        return [
            comp
            for comp in completions
            if comp.startswith(incomplete) or comp.startswith(incomplete_lower)
        ]
    except Exception:
        return []


def _extract_json_file_from_context(ctx: typer.Context) -> str | None:
    """Extract JSON file path from command context or environment."""
    import os
    from pathlib import Path

    try:
        # Check already parsed context parameters
        if hasattr(ctx, "params") and ctx.params:
            for param_name in ["json_file", "file1", "file2", "layout_file"]:
                if param_name in ctx.params and ctx.params[param_name]:
                    json_path = str(ctx.params[param_name])
                    if Path(json_path).exists():
                        return json_path

        # Check environment variable
        env_file = os.environ.get("GLOVEBOX_JSON_FILE")
        if env_file and Path(env_file).exists():
            return env_file

        return None
    except Exception:
        return None


def _get_cached_layer_names(json_file: str) -> list[str]:
    """Get cached layer names for a JSON file."""
    try:
        import json
        from pathlib import Path

        from glovebox.core.cache import create_default_cache

        json_path = Path(json_file)
        if not json_path.exists():
            return []

        # Create cache key based on file path and modification time
        mtime = json_path.stat().st_mtime
        cache_key = f"{LAYER_NAMES_CACHE_KEY_PREFIX}{json_path}_{mtime}"

        cache = create_default_cache(tag="cli_completion")
        cached_names = cache.get(cache_key)

        if cached_names is not None:
            return cached_names  # type: ignore[no-any-return]

        # Load layer names from file
        data = json.loads(json_path.read_text())
        layer_names = data.get("layer_names", [])

        # Filter out empty names
        layer_names = [name for name in layer_names if name and name.strip()]

        # Cache with TTL
        cache.set(cache_key, layer_names, ttl=LAYER_NAMES_TTL)
        return layer_names
    except Exception:
        return []


# Standard profile parameter that can be reused across all commands
ProfileOption = Annotated[
    str | None,
    typer.Option(
        "--profile",
        "-p",
        help="Profile to use (e.g., 'glove80/v25.05'). Uses user config default if not specified.",
        autocompletion=complete_profile_names,
    ),
]



def create_profile_from_param_unified(
    ctx: typer.Context,
    profile: str | None,
    default_profile: str | None = None,
    json_file: Path | None = None,
    no_auto: bool = False,
) -> "KeyboardProfile":
    """Unified function to create profile from CLI parameters.

    This consolidates the profile creation logic for commands that use
    ProfileOption parameters instead of the @with_profile decorator.

    Args:
        ctx: Typer context
        profile: Profile parameter value from CLI
        default_profile: Default profile to use if none provided
        json_file: JSON file for auto-detection
        no_auto: Disable auto-detection

    Returns:
        KeyboardProfile instance
    """
    from glovebox.cli.helpers.profile import resolve_and_create_profile_unified

    return resolve_and_create_profile_unified(
        ctx=ctx,
        profile_option=profile,
        default_profile=default_profile,
        json_file_path=json_file,
        no_auto=no_auto,
    )


# Standard output format parameter for unified output formatting
OutputFormatOption = Annotated[
    str,
    typer.Option(
        "--output-format",
        help="Output format: text|json|markdown|table|rich-table|rich-panel|rich-grid (default: text)",
        autocompletion=complete_output_formats,
    ),
]


# View mode parameter with completion
ViewModeOption = Annotated[
    str | None,
    typer.Option(
        "--view-mode",
        "-m",
        help="View mode (normal, compact, split, flat)",
        autocompletion=complete_view_modes,
    ),
]


# JSON file argument with path completion
JsonFileArgument = Annotated[
    str | None,
    typer.Argument(
        help="Path to keyboard layout JSON file. Used for layer name completion in --layer option.",
        autocompletion=complete_json_files,
    ),
]


# Layer parameter with dynamic completion based on JSON file context
LayerOption = Annotated[
    str | None,
    typer.Option(
        "--layer",
        help="Show only specific layer (index or name). For tab completion: export GLOVEBOX_JSON_FILE=path/to/file.json",
        autocompletion=complete_layer_names,
    ),
]


# Width parameter for key display (commonly used)
KeyWidthOption = Annotated[
    int,
    typer.Option(
        "--key-width",
        "-w",
        help="Width for displaying each key",
    ),
]


# Note: For more complex parameter variations, create new Annotated types
# following the same pattern as ProfileOption above.
