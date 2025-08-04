"""Helpers for CLI commands with lazy loading."""

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    # Type checking imports only
    from glovebox.cli.helpers.output import (
        print_error_message,
        print_list_item,
        print_result,
        print_success_message,
    )
    from glovebox.cli.helpers.profile import create_profile_from_option


def __getattr__(name: str) -> Any:
    """Lazy load helper functions on first access.

    This allows importing the module without loading all dependencies upfront.
    Functions are imported only when actually used.
    """
    if name == "print_success_message":
        from glovebox.cli.helpers.output import print_success_message

        return print_success_message
    elif name == "print_error_message":
        from glovebox.cli.helpers.output import print_error_message

        return print_error_message
    elif name == "print_list_item":
        from glovebox.cli.helpers.output import print_list_item

        return print_list_item
    elif name == "print_result":
        from glovebox.cli.helpers.output import print_result

        return print_result
    elif name == "create_profile_from_option":
        from glovebox.cli.helpers.profile import create_profile_from_option

        return create_profile_from_option
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "create_profile_from_option",
    "print_success_message",
    "print_error_message",
    "print_list_item",
    "print_result",
]
