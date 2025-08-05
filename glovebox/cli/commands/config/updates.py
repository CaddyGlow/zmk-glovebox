"""Configuration update check commands."""

import typer

from glovebox.cli.decorators import handle_errors
from glovebox.core.structlog_logger import get_struct_logger


logger = get_struct_logger(__name__)


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
    from glovebox.cli.helpers.profile import get_user_config_from_context
    from glovebox.core.version_check import create_zmk_version_checker

    user_config = get_user_config_from_context(ctx)
    version_checker = create_zmk_version_checker(user_config)
    result = version_checker.check_for_updates(
        force=force, include_prereleases=include_prereleases
    )

    if result.check_disabled and not force:
        from glovebox.cli.app import AppContext
        from glovebox.cli.helpers.theme import Icons, get_icon_mode_from_context

        icon_mode = get_icon_mode_from_context(ctx)
        print(
            Icons.format_with_icon("WARNING", "Version checks are disabled", icon_mode)
        )
        print("   To enable: glovebox config edit --set disable_version_checks=false")
        return

    if result.has_update and result.latest_version:
        from glovebox.cli.app import AppContext
        from glovebox.cli.helpers.theme import Icons, get_icon_mode_from_context

        app_context: AppContext = ctx.obj
        icon_mode = get_icon_mode_from_context(ctx)
        print(
            Icons.format_with_icon(
                "LOADING", "ZMK Firmware Update Available!", icon_mode
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
        from glovebox.cli.helpers.theme import Icons, get_icon_mode_from_context

        app_ctx2: AppContext = ctx.obj
        icon_mode = get_icon_mode_from_context(ctx)
        print(
            Icons.format_with_icon("SUCCESS", "ZMK firmware is up to date", icon_mode)
        )

    if result.last_check:
        print(f"   Last checked: {result.last_check.strftime('%Y-%m-%d %H:%M:%S')}")
