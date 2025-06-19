"""Configuration update check commands."""

import logging
from typing import Annotated

import typer

from glovebox.cli.decorators import handle_errors
from glovebox.cli.helpers import print_success_message


logger = logging.getLogger(__name__)


@handle_errors
def check_updates(
    ctx: typer.Context,
    force: bool = typer.Option(
        False, "--force", "-f", help="Force check even if recently checked"
    ),
    include_prereleases: bool = typer.Option(
        False, "--include-prereleases", help="Include pre-release versions"
    ),
) -> None:
    """Check for ZMK firmware updates."""
    from glovebox.core.version_check import create_zmk_version_checker

    version_checker = create_zmk_version_checker()
    result = version_checker.check_for_updates(
        force=force, include_prereleases=include_prereleases
    )

    if result.check_disabled and not force:
        from glovebox.cli.app import AppContext
        from glovebox.cli.helpers.theme import Icons

        app_ctx: AppContext = ctx.obj
        use_emoji = app_ctx.use_emoji
        print(
            Icons.format_with_icon("WARNING", "Version checks are disabled", use_emoji)
        )
        print("   To enable: glovebox config edit --set disable_version_checks=false")
        return

    if result.has_update and result.latest_version:
        from glovebox.cli.app import AppContext
        from glovebox.cli.helpers.theme import Icons

        app_context: AppContext = ctx.obj
        use_emoji = app_context.use_emoji
        print(
            Icons.format_with_icon(
                "LOADING", "ZMK Firmware Update Available!", use_emoji
            )
        )
        print(f"   Current: {result.current_version or 'unknown'}")
        print(f"   Latest:  {result.latest_version}")
        if result.is_prerelease:
            print("   Type:    Pre-release")
        if result.latest_url:
            print(f"   Details: {result.latest_url}")
    else:
        from glovebox.cli.app import AppContext
        from glovebox.cli.helpers.theme import Icons

        app_ctx2: AppContext = ctx.obj
        use_emoji = app_ctx2.use_emoji
        print(
            Icons.format_with_icon("SUCCESS", "ZMK firmware is up to date", use_emoji)
        )

    if result.last_check:
        print(f"   Last checked: {result.last_check.strftime('%Y-%m-%d %H:%M:%S')}")


@handle_errors
def disable_updates(ctx: typer.Context) -> None:
    """Disable automatic ZMK version checks."""
    from glovebox.core.version_check import create_zmk_version_checker

    version_checker = create_zmk_version_checker()
    version_checker.disable_version_checks()
    print_success_message("ZMK version checks disabled")


@handle_errors
def enable_updates(ctx: typer.Context) -> None:
    """Enable automatic ZMK version checks."""
    from glovebox.core.version_check import create_zmk_version_checker

    version_checker = create_zmk_version_checker()
    version_checker.enable_version_checks()
    print_success_message("ZMK version checks enabled")
