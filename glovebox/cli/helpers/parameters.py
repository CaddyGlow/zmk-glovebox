"""Common CLI parameter definitions for reuse across commands."""

import logging
from pathlib import Path
from typing import Annotated, Any

import typer

from glovebox.config.profile import KeyboardProfile


logger = logging.getLogger(__name__)

# Cache keys and TTL settings for completion data
PROFILE_COMPLETION_CACHE_KEY = "profile_completion_data_v1"
PROFILE_COMPLETION_TTL = 300  # 5 minutes

LAYER_NAMES_CACHE_KEY_PREFIX = "layer_names_"
LAYER_NAMES_TTL = 60  # 1 minute

STATIC_COMPLETION_CACHE_KEY = "static_completion_data_v1"
STATIC_COMPLETION_TTL = 86400  # 24 hours

FIELD_COMPLETION_CACHE_KEY = "field_completion_data_v1"
FIELD_COMPLETION_TTL = 3600  # 1 hour


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


def complete_json_paths(incomplete: str) -> list[str]:
    """Tab completion for JSON paths in --from parameter.

    Supports completion for:
    - File paths: file.json
    - JSON paths: file.json$.path.to.field
    - Shortcut syntax: file.json:layer_name or file.json:behaviors

    Args:
        incomplete: Partial --from parameter value

    Returns:
        List of completion suggestions
    """
    try:
        import json
        from pathlib import Path

        # If no special syntax detected, use regular file completion
        if "$." not in incomplete and ":" not in incomplete:
            return complete_json_files(incomplete)

        # Handle JSON path syntax: file.json$.path
        if "$." in incomplete:
            file_part, json_path = incomplete.split("$.", 1)
            file_path = Path(file_part)

            if not file_path.exists() or file_path.suffix != ".json":
                return []

            try:
                data = json.loads(file_path.read_text())
                return _get_json_path_completions(data, json_path, file_part + "$.")
            except Exception:
                return []

        # Handle shortcut syntax: file.json:shortcut
        if ":" in incomplete:
            file_part, shortcut_part = incomplete.split(":", 1)
            file_path = Path(file_part)

            if not file_path.exists() or file_path.suffix != ".json":
                return []

            try:
                data = json.loads(file_path.read_text())
                return _get_shortcut_completions(data, shortcut_part, file_part + ":")
            except Exception:
                return []

        return []
    except Exception:
        return []


def _get_json_path_completions(
    data: dict[str, Any], partial_path: str, prefix: str
) -> list[str]:
    """Get JSON path completions for a given data structure."""
    try:
        completions = []

        if not partial_path:
            # Return top-level keys
            if isinstance(data, dict):
                for key in data:
                    completions.append(f"{prefix}{key}")
                    # Add array indexing for lists
                    if isinstance(data[key], list) and data[key]:
                        for i in range(min(3, len(data[key]))):  # Show first 3 indices
                            completions.append(f"{prefix}{key}[{i}]")
            return completions

        # Navigate to the partial path
        parts = partial_path.split(".")
        current = data

        # Navigate to parent of the incomplete part
        for part in parts[:-1]:
            if "[" in part and "]" in part:
                # Handle array indexing
                key, index_part = part.split("[", 1)
                index = int(index_part.rstrip("]"))
                if isinstance(current, dict) and key in current:
                    current = current[key]
                    if isinstance(current, list) and 0 <= index < len(current):
                        current = current[index]
                    else:
                        return []
                else:
                    return []
            else:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return []

        # Generate completions for the last part
        last_part = parts[-1]
        current_prefix = f"{prefix}{'.'.join(parts[:-1])}"
        if len(parts) > 1:
            current_prefix += "."

        if isinstance(current, dict):
            for key in current:
                if key.startswith(last_part):
                    completions.append(f"{current_prefix}{key}")
                    # Add array indexing for lists
                    if isinstance(current[key], list) and current[key]:
                        for i in range(min(3, len(current[key]))):
                            completions.append(f"{current_prefix}{key}[{i}]")

        return completions
    except Exception:
        return []


def _get_shortcut_completions(
    data: dict[str, Any], partial_shortcut: str, prefix: str
) -> list[str]:
    """Get shortcut completions for --from parameter."""
    try:
        shortcuts = []

        # Add predefined shortcuts
        predefined_shortcuts = ["behaviors", "meta"]
        for shortcut in predefined_shortcuts:
            if shortcut.startswith(partial_shortcut):
                shortcuts.append(f"{prefix}{shortcut}")

        # Add layer names as shortcuts
        layer_names = data.get("layer_names", [])
        for layer_name in layer_names:
            if layer_name.lower().startswith(partial_shortcut.lower()):
                shortcuts.append(f"{prefix}{layer_name}")

        # Add common field shortcuts based on what's available in the data
        common_fields = [
            "variables",
            "holdTaps",
            "combos",
            "macros",
            "config_parameters",
        ]
        for field in common_fields:
            if field in data and field.startswith(partial_shortcut):
                shortcuts.append(f"{prefix}{field}")

        return shortcuts
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


def complete_field_paths(ctx: typer.Context, incomplete: str) -> list[str]:
    """Tab completion for field paths in layout editing operations.

    Provides completion for LayoutData model fields including:
    - Top-level fields (title, keyboard, variables, etc.)
    - Nested fields (variables.myVar, holdTaps[0].flavor, etc.)
    - Array indexing (layers[0], combos[1].keyPositions[0], etc.)

    Args:
        ctx: Typer context for accessing command parameters
        incomplete: Partial field path being typed

    Returns:
        List of matching field paths
    """
    try:
        # Get basic LayoutData field structure
        field_completions = _get_cached_field_completions()

        # Get JSON file context for dynamic completions
        json_file = _extract_json_file_from_context(ctx)

        if json_file:
            # Add dynamic completions based on actual layout content
            dynamic_completions = _get_dynamic_field_completions(json_file, incomplete)
            field_completions.extend(dynamic_completions)

        if not incomplete:
            # Return top-level fields for empty input
            return sorted(
                [
                    comp
                    for comp in field_completions
                    if "." not in comp and "[" not in comp
                ]
            )

        # Filter completions based on incomplete input
        matching = []
        for comp in field_completions:
            if comp.startswith(incomplete):
                matching.append(comp)
            elif "." in incomplete:
                # For nested paths, also match if the completion starts with the partial path
                parts = incomplete.split(".")
                comp_parts = comp.split(".")
                if len(comp_parts) >= len(parts) and all(
                    cp.startswith(ip)
                    for cp, ip in zip(comp_parts[: len(parts)], parts, strict=False)
                ):
                    matching.append(comp)

        return sorted(set(matching))
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


def _get_cached_field_completions() -> list[str]:
    """Get cached field completion data for LayoutData model."""
    try:
        from glovebox.core.cache import create_default_cache

        cache = create_default_cache(tag="cli_completion")
        cached_data = cache.get(FIELD_COMPLETION_CACHE_KEY)

        if cached_data is not None:
            return cached_data  # type: ignore[no-any-return]

        # Build field completion data from LayoutData model
        field_completions = _build_layout_field_completions()

        # Cache with TTL
        cache.set(
            FIELD_COMPLETION_CACHE_KEY, field_completions, ttl=FIELD_COMPLETION_TTL
        )
        return field_completions
    except Exception:
        # Fallback to basic field list
        return [
            "title",
            "keyboard",
            "version",
            "creator",
            "notes",
            "date",
            "uuid",
            "parent_uuid",
            "variables",
            "layer_names",
            "layers",
            "holdTaps",
            "combos",
            "macros",
            "inputListeners",
            "config_parameters",
            "custom_defined_behaviors",
            "custom_devicetree",
            "tags",
        ]


def _build_layout_field_completions() -> list[str]:
    """Build comprehensive field completion list from LayoutData model."""
    try:
        from glovebox.layout.models import LayoutData

        completions = []

        # Get model fields from LayoutData
        model_fields = LayoutData.model_fields

        # Add top-level fields (both Python names and aliases)
        for field_name, field_info in model_fields.items():
            completions.append(field_name)

            # Add alias if it exists and is different
            if (
                hasattr(field_info, "alias")
                and field_info.alias
                and field_info.alias != field_name
            ):
                completions.append(field_info.alias)

        # Add common nested field patterns
        nested_fields = [
            # Variables - most common use case
            "variables.tapMs",
            "variables.holdMs",
            "variables.flavor",
            "variables.OPERATING_SYSTEM",
            "variables.BASE_LAYER",
            # Layer access patterns
            "layers[0]",
            "layers[1]",
            "layers[2]",
            "layer_names[0]",
            "layer_names[1]",
            "layer_names[2]",
            # HoldTap behavior fields
            "holdTaps[0].name",
            "holdTaps[0].tapping_term_ms",
            "holdTaps[0].quick_tap_ms",
            "holdTaps[0].flavor",
            "holdTaps[0].bindings",
            "holdTaps[0].hold_trigger_on_release",
            "holdTaps[0].require_prior_idle_ms",
            "holdTaps[0].hold_trigger_key_positions",
            "holdTaps[0].retro_tap",
            "holdTaps[0].tap_behavior",
            "holdTaps[0].hold_behavior",
            # Combo behavior fields
            "combos[0].name",
            "combos[0].timeout_ms",
            "combos[0].key_positions",
            "combos[0].layers",
            "combos[0].binding",
            "combos[0].behavior",
            # Macro behavior fields
            "macros[0].name",
            "macros[0].wait_ms",
            "macros[0].tap_ms",
            "macros[0].bindings",
            "macros[0].params",
            # Config parameters
            "config_parameters[0].paramName",
            "config_parameters[0].value",
            "config_parameters[0].description",
            # Input listeners
            "inputListeners[0].code",
            "inputListeners[0].inputProcessors",
            "inputListeners[0].nodes",
            # Version tracking fields
            "last_firmware_build.date",
            "last_firmware_build.profile",
            "last_firmware_build.firmware_path",
            "last_firmware_build.firmware_hash",
            "last_firmware_build.build_id",
        ]

        completions.extend(nested_fields)

        return completions
    except Exception:
        # Fallback to basic completions
        return [
            "title",
            "keyboard",
            "variables",
            "layer_names",
            "layers",
            "holdTaps",
            "combos",
            "macros",
            "custom_defined_behaviors",
        ]


def _get_dynamic_field_completions(json_file: str, incomplete: str) -> list[str]:
    """Get dynamic field completions based on actual layout content."""
    try:
        import json
        from pathlib import Path

        json_path = Path(json_file)
        if not json_path.exists():
            return []

        data = json.loads(json_path.read_text())
        dynamic_completions = []

        # Add specific variable names if variables exist
        if "variables" in data and isinstance(data["variables"], dict):
            for var_name in data["variables"]:
                dynamic_completions.append(f"variables.{var_name}")

        # Add layer-specific completions if we have layer names
        layer_names = data.get("layer_names", [])
        if layer_names and incomplete.startswith("layers["):
            # Add specific layer indices based on actual layer count
            for i in range(len(layer_names)):
                dynamic_completions.append(f"layers[{i}]")

        # Add behavior-specific completions based on actual behaviors
        for behavior_type in ["holdTaps", "combos", "macros", "inputListeners"]:
            if behavior_type in data and isinstance(data[behavior_type], list):
                for i in range(len(data[behavior_type])):
                    dynamic_completions.append(f"{behavior_type}[{i}]")
                    # Add specific field completions for this behavior
                    if incomplete.startswith(f"{behavior_type}[{i}]."):
                        behavior_data = data[behavior_type][i]
                        if isinstance(behavior_data, dict):
                            for field_name in behavior_data:
                                dynamic_completions.append(
                                    f"{behavior_type}[{i}].{field_name}"
                                )

        # Add config parameter completions
        if "config_parameters" in data and isinstance(data["config_parameters"], list):
            for i in range(len(data["config_parameters"])):
                dynamic_completions.append(f"config_parameters[{i}]")
                dynamic_completions.append(f"config_parameters[{i}].paramName")
                dynamic_completions.append(f"config_parameters[{i}].value")

        return dynamic_completions
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
) -> KeyboardProfile:
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


# Field path parameter with smart completion based on LayoutData model
FieldPathOption = Annotated[
    str | None,
    typer.Option(
        "--field",
        help="Field path using dot notation (e.g., 'variables.tapMs', 'holdTaps[0].flavor'). Use tab completion for available fields.",
        autocompletion=complete_field_paths,
    ),
]


# Field path parameter for get operations (can be used multiple times)
GetFieldOption = Annotated[
    list[str] | None,
    typer.Option(
        "--get",
        help="Get field value(s) using JSON path notation. Use tab completion for available fields.",
        autocompletion=complete_field_paths,
    ),
]


# Field path parameter for set operations
SetFieldOption = Annotated[
    list[str] | None,
    typer.Option(
        "--set",
        help="Set field value using key=value format. Use tab completion for available fields.",
        autocompletion=complete_field_paths,
    ),
]


# Field path parameter for merge operations
MergeFieldOption = Annotated[
    list[str] | None,
    typer.Option(
        "--merge",
        help="Merge values into field using key=--from syntax. Use tab completion for available fields.",
        autocompletion=complete_field_paths,
    ),
]


# Field path parameter for append operations
AppendFieldOption = Annotated[
    list[str] | None,
    typer.Option(
        "--append",
        help="Append values to array field using key=--from syntax. Use tab completion for available fields.",
        autocompletion=complete_field_paths,
    ),
]


# Field path parameter for unset operations
UnsetFieldOption = Annotated[
    list[str] | None,
    typer.Option(
        "--unset",
        help="Remove field or dictionary key (e.g., 'variables.myVar'). Use tab completion for available fields.",
        autocompletion=complete_field_paths,
    ),
]


# Note: For more complex parameter variations, create new Annotated types
# following the same pattern as ProfileOption above.
