"""Helper functions for extracting data for filename generation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile
    from glovebox.layout.models import LayoutData


def extract_layout_data(layout: LayoutData) -> dict[str, Any]:
    """Extract filename template data from a LayoutData object.

    Args:
        layout: Layout data object

    Returns:
        Dictionary with layout data for template variables
    """
    return {
        "title": getattr(layout, "title", ""),
        "keyboard": getattr(layout, "keyboard", ""),
        "version": getattr(layout, "version", ""),
        "creator": getattr(layout, "creator", ""),
        "date": getattr(layout, "date", None),
        "uuid": getattr(layout, "uuid", ""),
    }


def extract_profile_data(profile: KeyboardProfile) -> dict[str, Any]:
    """Extract filename template data from a KeyboardProfile object.

    Args:
        profile: Keyboard profile object

    Returns:
        Dictionary with profile data for template variables
    """
    return {
        "keyboard_name": profile.keyboard_name,
        "firmware_version": profile.firmware_version or "",
    }


def extract_layout_dict_data(layout_dict: dict[str, Any]) -> dict[str, Any]:
    """Extract filename template data from a layout dictionary.

    Args:
        layout_dict: Layout data as dictionary

    Returns:
        Dictionary with layout data for template variables
    """
    return {
        "title": layout_dict.get("title", ""),
        "keyboard": layout_dict.get("keyboard", ""),
        "version": layout_dict.get("version", ""),
        "creator": layout_dict.get("creator", ""),
        "date": layout_dict.get("date"),
        "uuid": layout_dict.get("uuid", ""),
    }


def extract_bookmark_data(bookmark_name: str, layout_title: str = "") -> dict[str, Any]:
    """Extract filename template data from bookmark information.

    Args:
        bookmark_name: Name of the bookmark
        layout_title: Title of the layout (if available)

    Returns:
        Dictionary with bookmark data for template variables
    """
    return {
        "title": layout_title or bookmark_name,
        "bookmark_name": bookmark_name,
    }


def extract_firmware_data(
    uf2_files: list[str] | None = None, build_id: str = ""
) -> dict[str, Any]:
    """Extract filename template data from firmware build information.

    Args:
        uf2_files: List of UF2 filenames
        build_id: Build identifier

    Returns:
        Dictionary with firmware data for template variables
    """
    board = ""
    if uf2_files:
        # Try to extract board name from first UF2 file
        # Common patterns: "keyboard_board.uf2" or "keyboard-board.uf2"
        first_file = uf2_files[0]
        if "_" in first_file:
            parts = first_file.replace(".uf2", "").split("_")
            if len(parts) > 1:
                board = parts[-1]  # Last part is usually the board
        elif "-" in first_file:
            parts = first_file.replace(".uf2", "").split("-")
            if len(parts) > 1:
                board = parts[-1]  # Last part is usually the board

    return {
        "build_id": build_id,
        "board": board,
    }
