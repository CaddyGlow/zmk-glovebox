"""ZMK Layout info command - Show zmk-layout integration status and capabilities."""

import json
from typing import Annotated

import typer
from rich.panel import Panel
from rich.table import Table

from glovebox.cli.decorators import handle_errors, with_metrics, with_profile
from glovebox.cli.helpers.theme import get_themed_console
from glovebox.core.structlog_logger import get_struct_logger
from glovebox.layout.zmk_layout_service import create_zmk_layout_service


logger = get_struct_logger(__name__)
console = get_themed_console()


@with_metrics("zmk_layout.info")
@with_profile()
@handle_errors
def info_layout(
    ctx: typer.Context,
    profile: Annotated[
        str | None,
        typer.Option(
            "-p",
            "--profile",
            help="Keyboard profile to get specific information",
        ),
    ] = None,
    format: Annotated[
        str,
        typer.Option(
            "-f",
            "--format",
            help="Output format: table, json",
        ),
    ] = "table",
    show_capabilities: Annotated[
        bool,
        typer.Option(
            "--capabilities",
            help="Show detailed capability information",
        ),
    ] = True,
    show_keyboards: Annotated[
        bool,
        typer.Option(
            "--keyboards",
            help="Show supported keyboards",
        ),
    ] = True,
    show_providers: Annotated[
        bool,
        typer.Option(
            "--providers",
            help="Show provider information",
        ),
    ] = False,
) -> None:
    """Show zmk-layout integration status and capabilities.

    This command displays comprehensive information about the zmk-layout
    library integration, including version, capabilities, supported
    keyboards, and provider status.

    **Examples:**

    \b
    # Show basic information
    glovebox zmk-layout info

    \b
    # Show detailed information with providers
    glovebox zmk-layout info --providers --capabilities

    \b
    # JSON output for automation
    glovebox zmk-layout info -f json

    \b
    # Information for specific profile
    glovebox zmk-layout info -p glove80
    """
    try:
        # Get keyboard profile
        app_context = ctx.obj
        keyboard_profile = app_context.keyboard_profile

        # Create zmk-layout service
        zmk_service = create_zmk_layout_service(
            keyboard_id=keyboard_profile.keyboard_name if keyboard_profile else None
        )

        # Get compiler information
        info = zmk_service.get_compiler_info()

        # Get supported keyboards if requested
        supported_keyboards = []
        if show_keyboards:
            try:
                supported_keyboards = zmk_service.get_supported_keyboards()
            except Exception as e:
                logger.debug("failed_to_get_supported_keyboards", error=str(e))

        if format == "json":
            # JSON output for automation
            output = {
                "zmk_layout_info": info,
                "keyboard_profile": {
                    "current": keyboard_profile.keyboard_name
                    if keyboard_profile
                    else None,
                    "profile_name": profile,
                },
                "supported_keyboards": supported_keyboards,
                "integration_status": "active" if "error" not in info else "error",
            }
            console.console.print(json.dumps(output, indent=2), highlight=False)

        else:
            # Rich table output
            console.console.print(
                Panel(
                    "[bold blue]ZMK Layout Library Integration[/bold blue]",
                    expand=False,
                )
            )

            # Main info table
            main_table = Table(show_header=False, box=None, padding=(0, 1))
            main_table.add_column("Property", style="cyan", width=20)
            main_table.add_column("Value", style="white")

            # Add basic information
            main_table.add_row("Library", info.get("library", "unknown"))
            main_table.add_row("Version", info.get("version", "unknown"))
            main_table.add_row(
                "Status",
                "[green]Active[/green]" if "error" not in info else "[red]Error[/red]",
            )

            if keyboard_profile:
                main_table.add_row("Current Keyboard", keyboard_profile.keyboard_name)

            if profile:
                main_table.add_row("Profile", profile)

            main_table.add_row("Keyboard ID", info.get("keyboard_id") or "auto-detect")

            console.console.print(main_table)

            # Capabilities table
            if show_capabilities and "capabilities" in info:
                console.console.print("\n[bold blue]Capabilities[/bold blue]")

                cap_table = Table(show_header=False, box=None, padding=(0, 1))
                cap_table.add_column("", style="green", width=2)
                cap_table.add_column("Capability", style="white")

                for capability in info["capabilities"]:
                    cap_table.add_row("✓", capability.replace("_", " ").title())

                console.console.print(cap_table)

            # Supported keyboards
            if show_keyboards and supported_keyboards:
                console.console.print("\n[bold blue]Supported Keyboards[/bold blue]")

                # Display keyboards in columns
                keyboard_chunks = [
                    supported_keyboards[i : i + 3]
                    for i in range(0, len(supported_keyboards), 3)
                ]
                for chunk in keyboard_chunks:
                    keyboard_row = "  ".join(f"[cyan]{kb}[/cyan]" for kb in chunk)
                    console.console.print(f"  {keyboard_row}")

            # Provider information
            if show_providers and "providers" in info:
                console.console.print("\n[bold blue]Providers[/bold blue]")

                provider_table = Table(show_header=True, header_style="bold blue")
                provider_table.add_column("Provider", style="cyan")
                provider_table.add_column("Implementation", style="white")

                for provider_type, provider_class in info["providers"].items():
                    provider_table.add_row(
                        provider_type.replace("_", " ").title(), provider_class
                    )

                console.console.print(provider_table)

            # Error information if present
            if "error" in info:
                console.console.print(
                    f"\n[red]Error:[/red] {info['error']}", style="error"
                )

        # Log info request
        logger.info(
            "zmk_layout_info_requested",
            keyboard_profile=keyboard_profile.keyboard_name
            if keyboard_profile
            else None,
            format=format,
            show_capabilities=show_capabilities,
            show_keyboards=show_keyboards,
            show_providers=show_providers,
        )

    except Exception as e:
        logger.error("zmk_layout_info_failed", error=str(e), exc_info=True)
        console.console.print(f"[red]Error:[/red] {e}", style="error")
        ctx.exit(1)
