"""Shared utilities for auto-profile detection and JSON file resolution.

This module provides shared functionality for detecting keyboard profiles from JSON layout files
and resolving JSON file paths from environment variables. Used by both layout and firmware commands
to maintain consistency and reduce code duplication.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

from glovebox.core.structlog_logger import get_struct_logger


logger = get_struct_logger(__name__)


def extract_keyboard_from_json(json_file: Path) -> str | None:
    """Extract keyboard field from JSON layout file for auto-profile detection.

    Args:
        json_file: Path to the JSON layout file

    Returns:
        Keyboard name if found and valid, None otherwise
    """
    try:
        with json_file.open() as f:
            data = json.load(f)

        keyboard = data.get("keyboard")
        if keyboard and isinstance(keyboard, str):
            keyboard_stripped = str(keyboard).strip()
            if keyboard_stripped:
                return keyboard_stripped
            else:
                logger.debug("keyboard_field_empty_after_stripping")
                return None
        else:
            logger.debug("no_keyboard_field_in_json")
            return None

    except Exception as e:
        logger.warning("failed_to_extract_keyboard_from_json", error=str(e))
        return None


def get_auto_profile_from_json(json_file: Path, user_config: Any = None) -> str | None:
    """Get auto-detected profile from JSON layout file.

    Args:
        json_file: Path to the JSON layout file
        user_config: User configuration for default firmware lookup

    Returns:
        Auto-detected profile string or None if detection fails
    """
    keyboard = extract_keyboard_from_json(json_file)
    if not keyboard:
        return None

    # Try to create a keyboard-only profile first to see if the keyboard exists
    try:
        from glovebox.config.keyboard_profile import create_keyboard_profile

        # Create keyboard-only profile to validate keyboard exists
        keyboard_profile = create_keyboard_profile(keyboard, None, user_config)

        # Check if user config has a matching keyboard profile with firmware
        if user_config is not None:
            try:
                user_profile = user_config._config.profile
                if user_profile and "/" in user_profile:
                    # Split user profile into keyboard/firmware
                    user_keyboard = user_profile.split("/")[0]
                    if user_keyboard == keyboard:
                        # User has matching keyboard with firmware, use full profile
                        logger.debug(
                            "user_config_matching_keyboard_profile",
                            profile=user_profile,
                        )
                        return user_profile  # type: ignore[no-any-return]
            except AttributeError:
                # user_config doesn't have profile attribute, fall back to keyboard-only
                logger.debug("user_config_no_profile_attribute_using_keyboard_only")

        # Fall back to keyboard-only profile
        logger.debug("using_keyboard_only_profile", keyboard=keyboard)
        return keyboard

    except Exception as e:
        logger.warning(
            "failed_to_create_keyboard_profile", keyboard=keyboard, error=str(e)
        )
        return None


def resolve_json_file_path(
    json_file_arg: str | Path | None, env_var: str = "GLOVEBOX_JSON_FILE"
) -> Path | None:
    """Resolve JSON file path from argument, library reference, or environment variable.

    Args:
        json_file_arg: JSON file path or @library-reference provided as CLI argument
        env_var: Environment variable name to check for default path

    Returns:
        Resolved Path object or None if neither argument nor env var provided

    Raises:
        FileNotFoundError: If resolved path doesn't exist
        ValueError: If resolved path is not a file or library reference cannot be resolved
    """
    # Check CLI argument first
    if json_file_arg is not None:
        # Check if it's a library reference
        if isinstance(json_file_arg, str) and json_file_arg.startswith("@"):
            from glovebox.cli.helpers.library_resolver import resolve_library_reference

            try:
                resolved_path = resolve_library_reference(json_file_arg)
                logger.debug(
                    "resolved_library_reference",
                    original=json_file_arg,
                    resolved=str(resolved_path),
                )
                return resolved_path
            except Exception as e:
                raise ValueError(
                    f"Cannot resolve library reference '{json_file_arg}': {e}"
                ) from e
        else:
            resolved_path = Path(json_file_arg)
            source = "CLI argument"
    else:
        # Check environment variable
        env_value = os.environ.get(env_var)
        if env_value:
            # Check if env value is a library reference
            if env_value.startswith("@"):
                from glovebox.cli.helpers.library_resolver import (
                    resolve_library_reference,
                )

                try:
                    resolved_path = resolve_library_reference(env_value)
                    logger.debug(
                        "resolved_library_reference_from_env",
                        original=env_value,
                        resolved=str(resolved_path),
                    )
                    return resolved_path
                except Exception as e:
                    raise ValueError(
                        f"Cannot resolve library reference '{env_value}' from {env_var}: {e}"
                    ) from e
            else:
                resolved_path = Path(env_value)
                source = f"{env_var} environment variable"
        else:
            return None

    # Validate the resolved path
    try:
        resolved_path = resolved_path.resolve()

        if not resolved_path.exists():
            raise FileNotFoundError(
                f"JSON file not found (from {source}): {resolved_path}"
            )

        if not resolved_path.is_file():
            raise ValueError(f"Path is not a file (from {source}): {resolved_path}")

        return resolved_path

    except Exception as e:
        exc_info = logger.isEnabledFor(logging.DEBUG)
        logger.error(
            "invalid_json_file_path", source=source, error=str(e), exc_info=exc_info
        )
        raise


def resolve_profile_with_auto_detection(
    profile: str | None,
    json_file: Path | None,
    no_auto: bool,
    user_config: Any = None,
) -> str | None:
    """Resolve profile using auto-detection and existing precedence rules.

    Profile precedence (highest to lowest):
    1. CLI --profile flag (profile parameter)
    2. Auto-detection from JSON keyboard field (unless no_auto=True)
    3. GLOVEBOX_PROFILE environment variable (handled by UserConfig)
    4. User config file profile setting (handled by UserConfig)
    5. Hardcoded fallback (handled by UserConfig)

    Args:
        profile: Explicit profile from CLI --profile flag
        json_file: Path to JSON file for auto-detection
        no_auto: If True, disable auto-detection
        user_config: User configuration object

    Returns:
        Resolved profile string or None to use UserConfig defaults
    """
    # 1. CLI profile takes highest precedence
    if profile:
        logger.debug("using_explicit_cli_profile", profile=profile)
        return profile

    # 2. Auto-detection from JSON (unless disabled)
    if not no_auto and json_file and json_file.suffix.lower() == ".json":
        auto_profile = get_auto_profile_from_json(json_file, user_config)
        if auto_profile:
            logger.info("auto_detected_profile_from_json", profile=auto_profile)
            return auto_profile
        else:
            logger.debug("auto_profile_detection_failed_fallback_to_defaults")

    # 3-5. Let UserConfig handle environment variable, config file, and defaults
    logger.debug("using_user_config_defaults")
    return None
