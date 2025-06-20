"""Common CLI parameter definitions for reuse across commands."""

import logging
from typing import Annotated

import typer


logger = logging.getLogger(__name__)

# Cache key for profile completion data
PROFILE_COMPLETION_CACHE_KEY = "profile_completion_data_v1"
PROFILE_COMPLETION_TTL = 300  # 5 minutes


def _get_cached_profile_data() -> tuple[list[str], dict[str, list[str]]]:
    """Get cached profile data using persistent filesystem cache."""
    try:
        from glovebox.config import create_user_config
        from glovebox.config.keyboard_profile import (
            get_available_firmwares,
            get_available_keyboards,
        )
        from glovebox.core.cache_v2 import create_default_cache

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


# Standard output format parameter for unified output formatting
OutputFormatOption = Annotated[
    str,
    typer.Option(
        "--output-format",
        help="Output format: text|json|markdown|table (default: text)",
    ),
]


# Note: For more complex parameter variations, create new Annotated types
# following the same pattern as ProfileOption above.
