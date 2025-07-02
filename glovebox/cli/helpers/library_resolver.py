"""Library reference resolution for CLI parameters.

This module provides functionality to resolve library references using the @ prefix
(e.g., @my-layout or @uuid) to actual file paths in the library.
"""

import logging
import re
from pathlib import Path
from typing import Any
from uuid import UUID

from glovebox.config import create_user_config
from glovebox.library import create_library_service
from glovebox.library.models import LibraryEntry
from glovebox.moergo.client import create_moergo_client


logger = logging.getLogger(__name__)

# Regex pattern to validate UUID format
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


def is_library_reference(value: str | None) -> bool:
    """Check if a value is a library reference (starts with @).

    Args:
        value: The parameter value to check

    Returns:
        True if value starts with @, False otherwise
    """
    return value.startswith("@") if value else False


def is_valid_uuid(value: str) -> bool:
    """Check if a value is a valid UUID format.

    Args:
        value: The string to check

    Returns:
        True if value matches UUID format, False otherwise
    """
    try:
        # Try parsing as UUID to be extra sure
        UUID(value)
        return True
    except (ValueError, AttributeError):
        # Also accept the regex pattern for flexibility
        return bool(UUID_PATTERN.match(value))


def resolve_library_reference(value: str, fetch_from_moergo: bool = True) -> Path:
    """Resolve a library reference to an actual file path.

    This function handles:
    - @name references: Looks up by layout name in library
    - @uuid references: Looks up by UUID in library
    - MoErgo fallback: If UUID not found locally and user is authenticated,
      fetches from MoErgo API

    Args:
        value: The library reference (e.g., "@my-layout" or "@uuid")
        fetch_from_moergo: Whether to try fetching from MoErgo if not found locally

    Returns:
        Path to the resolved layout file

    Raises:
        ValueError: If reference cannot be resolved
    """
    if not is_library_reference(value):
        raise ValueError(f"Not a library reference: {value}")

    # Remove @ prefix
    reference = value[1:]

    if not reference:
        raise ValueError("Empty library reference after @")

    # Create services
    user_config = create_user_config()
    library_service = create_library_service(user_config._config)

    # Try to resolve the reference
    entry: LibraryEntry | None = None

    # Check if it's a UUID
    if is_valid_uuid(reference):
        logger.debug("Attempting to resolve UUID reference: %s", reference)
        entry = library_service.get_layout_entry(reference)

        # If not found locally and MoErgo fetch is enabled, try MoErgo
        if entry is None and fetch_from_moergo:
            logger.debug("UUID not found locally, checking MoErgo API")
            entry = _fetch_from_moergo(reference, library_service, user_config._config)
    else:
        # Try by name
        logger.debug("Attempting to resolve name reference: %s", reference)
        entry = library_service.get_layout_entry_by_name(reference)

    if entry is None:
        raise ValueError(
            f"Could not resolve library reference '{value}'. "
            f"Layout not found in library."
        )

    # Verify the file exists
    if not entry.file_path.exists():
        raise ValueError(
            f"Layout file for '{value}' not found at expected path: {entry.file_path}"
        )

    logger.info("Resolved library reference '%s' to file: %s", value, entry.file_path)
    return entry.file_path


def _fetch_from_moergo(
    uuid: str, library_service: Any, user_config: Any
) -> LibraryEntry | None:
    """Try to fetch a layout from MoErgo API by UUID.

    Args:
        uuid: The UUID to fetch
        library_service: Library service instance
        user_config: User configuration

    Returns:
        LibraryEntry if successfully fetched, None otherwise
    """
    try:
        # Check if we have MoErgo credentials
        if not user_config.moergo_api_key:
            logger.debug("No MoErgo API key configured, skipping MoErgo fetch")
            return None

        # Create MoErgo client
        moergo_client = create_moergo_client(user_config=user_config)

        # Check if layout exists on MoErgo
        try:
            # First check if we can access the layout metadata
            meta_response = moergo_client.get_layout_meta(uuid, use_cache=False)
            if not meta_response or "layout_meta" not in meta_response:
                logger.debug("Layout %s not found on MoErgo", uuid)
                return None

            logger.info("Found layout %s on MoErgo, fetching...", uuid)

            # Use library service to fetch from MoErgo
            from glovebox.library.models import FetchRequest

            fetch_request = FetchRequest(
                source=f"moergo:{uuid}",
                name=None,  # Will use title from MoErgo
                force_overwrite=False,
            )

            result = library_service.fetch_layout(fetch_request)

            if result.success and result.entry:
                logger.info("Successfully fetched layout %s from MoErgo", uuid)
                return result.entry  # type: ignore[no-any-return]
            else:
                logger.warning(
                    "Failed to fetch layout %s from MoErgo: %s",
                    uuid,
                    result.errors,
                )
                return None

        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.debug(
                "Error checking/fetching layout %s from MoErgo: %s",
                uuid,
                e,
                exc_info=exc_info,
            )
            return None

    except Exception as e:
        exc_info = logger.isEnabledFor(logging.DEBUG)
        logger.error("Unexpected error during MoErgo fetch: %s", e, exc_info=exc_info)
        return None


def resolve_parameter_value(value: str | None) -> str | Path | None:
    """Resolve a parameter value that might be a library reference.

    This is a convenience function that handles both regular paths and
    library references transparently.

    Args:
        value: The parameter value (could be path or @reference)

    Returns:
        Original value if not a library reference, resolved Path if it is,
        or None if value is None
    """
    if value is None:
        return None

    if is_library_reference(value):
        return resolve_library_reference(value)

    return value


def get_library_entries_for_completion() -> list[tuple[str, str]]:
    """Get library entries for tab completion.

    Returns:
        List of tuples (reference, description) for completion
    """
    try:
        user_config = create_user_config()
        library_service = create_library_service(user_config._config)

        entries = []
        local_layouts = library_service.list_local_layouts()

        for entry in local_layouts:
            # Add name-based reference
            name_ref = f"@{entry.name}"
            name_desc = f"{entry.title or entry.name} (by {entry.creator or 'unknown'})"
            entries.append((name_ref, name_desc))

            # Add UUID-based reference
            uuid_ref = f"@{entry.uuid}"
            uuid_desc = f"{entry.title or entry.name} (UUID)"
            entries.append((uuid_ref, uuid_desc))

        return entries[:50]  # Limit for performance

    except Exception as e:
        logger.debug("Error getting library entries for completion: %s", e)
        return []
