"""Transform command for AST-based layout transformations."""

import json
import tempfile
from pathlib import Path
from typing import Any

import click

from glovebox.cli.decorators import handle_errors, with_metrics, with_profile
from glovebox.cli.helpers.theme import get_themed_console
from glovebox.core.structlog_logger import get_struct_logger
from glovebox.layout.models import LayoutData
from glovebox.layout.zmk_layout_service_enhanced import (
    create_enhanced_zmk_layout_service,
)


logger = get_struct_logger(__name__)


@click.group(name="transform")
@click.pass_context
def transform_group(ctx: click.Context) -> None:
    """AST-based layout transformation commands."""
    console = get_themed_console()
    console.console.print("[bold blue]ZMK Layout AST Transform Commands[/bold blue]")


@transform_group.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output", "-o", type=click.Path(path_type=Path), help="Output file path"
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be transformed without applying changes",
)
@click.option(
    "--remap", multiple=True, help="Key remapping in format 'old_key:new_key'"
)
@click.option("--merge-layers", help="Layer merge config as JSON")
@click.option(
    "--modify-behavior",
    multiple=True,
    help="Behavior modifications in format 'behavior:param=value'",
)
@click.option("--expand-macros", is_flag=True, help="Expand macro definitions")
@click.option("--generate-combos", help="Combo generation patterns as JSON")
@with_profile()
@with_metrics("zmk_layout.transform.apply")
@handle_errors
def apply(
    input_file: Path,
    output: Path | None,
    dry_run: bool,
    remap: tuple[str, ...],
    merge_layers: str | None,
    modify_behavior: tuple[str, ...],
    expand_macros: bool,
    generate_combos: str | None,
    app_context: Any,
) -> None:
    """Apply AST transformations to a layout file."""
    console = get_themed_console()

    try:
        # Read input layout
        with input_file.open() as f:
            layout_data_dict = json.load(f)

        layout_data = LayoutData.model_validate(layout_data_dict)
        keyboard_profile = app_context.keyboard_profile

        # Create enhanced zmk-layout service
        service = create_enhanced_zmk_layout_service(
            keyboard_id=keyboard_profile.keyboard_name if keyboard_profile else None
        )

        console.console.print(f"[green]Processing layout:[/green] {input_file}")
        console.console.print(f"[blue]Keyboard:[/blue] {layout_data.keyboard}")
        console.console.print(f"[blue]Layers:[/blue] {len(layout_data.layers)}")

        # Configure transformations
        transformations_applied = []

        # Configure key remapping
        if remap:
            key_mappings = {}
            for mapping in remap:
                if ":" in mapping:
                    old_key, new_key = mapping.split(":", 1)
                    key_mappings[old_key.strip()] = new_key.strip()

            if key_mappings:
                service.configure_key_remapping(key_mappings)
                transformations_applied.append("KeyRemap")
                console.console.print(
                    f"[yellow]Configured key remapping:[/yellow] {key_mappings}"
                )

        # Configure layer merging
        if merge_layers:
            try:
                merge_config = json.loads(merge_layers)
                service.configure_layer_merging(merge_config)
                transformations_applied.append("LayerMerge")
                console.console.print(
                    f"[yellow]Configured layer merging:[/yellow] {merge_config}"
                )
            except json.JSONDecodeError as e:
                console.console.print(f"[red]Invalid layer merge JSON:[/red] {e}")
                return

        # Configure behavior modifications
        if modify_behavior:
            behavior_mods: dict[str, dict[str, str]] = {}
            for mod in modify_behavior:
                if ":" in mod and "=" in mod:
                    behavior_part, param_part = mod.split(":", 1)
                    if "=" in param_part:
                        param, value = param_part.split("=", 1)
                        behavior_name = behavior_part.strip()
                        if behavior_name not in behavior_mods:
                            behavior_mods[behavior_name] = {}
                        behavior_mods[behavior_name][param.strip()] = value.strip()

            if behavior_mods:
                service.configure_behavior_modifications(behavior_mods)
                transformations_applied.append("BehaviorTransform")
                console.console.print(
                    f"[yellow]Configured behavior modifications:[/yellow] {behavior_mods}"
                )

        # Configure macro processing
        if expand_macros:
            # For demo purposes, use some common macros
            macro_definitions = {
                "COPY": ["&kp LC(C)"],
                "PASTE": ["&kp LC(V)"],
                "CUT": ["&kp LC(X)"],
            }
            service.configure_macro_processing(macro_definitions, expand=True)
            transformations_applied.append("MacroTransform")
            console.console.print("[yellow]Configured macro expansion[/yellow]")

        # Configure combo generation
        if generate_combos:
            try:
                combo_patterns = json.loads(generate_combos)
                service.configure_combo_generation(combo_patterns)
                transformations_applied.append("ComboTransform")
                console.console.print(
                    f"[yellow]Configured combo generation:[/yellow] {combo_patterns}"
                )
            except json.JSONDecodeError as e:
                console.console.print(f"[red]Invalid combo patterns JSON:[/red] {e}")
                return

        # Set dry run mode if requested
        if dry_run:
            service.set_dry_run_mode(True)
            console.console.print("[yellow]Dry run mode enabled[/yellow]")

        # Apply transformations
        if transformations_applied:
            console.console.print(
                f"\\n[bold]Applying transformations:[/bold] {', '.join(transformations_applied)}"
            )

            # Apply transformations using the enhanced service
            transformation_result = service.apply_transformations(
                layout_data_dict, transformations_applied
            )

            # Display results
            if transformation_result.success:
                console.console.print(
                    "[green]✓ Transformations applied successfully[/green]"
                )

                if transformation_result.transformation_log:
                    console.console.print("\\n[bold]Transformation Log:[/bold]")
                    for log_entry in transformation_result.transformation_log:
                        console.console.print(f"  • {log_entry}")

                if transformation_result.warnings:
                    console.console.print("\\n[bold yellow]Warnings:[/bold yellow]")
                    for warning in transformation_result.warnings:
                        console.console.print(f"  ⚠️  {warning}")

                # Compile the transformed layout if not in dry run mode
                if not dry_run:
                    compile_result = service.compile_layout(
                        layout_data, transformations=transformations_applied
                    )

                    if compile_result.success:
                        if output:
                            # Write to output file
                            keymap_content = compile_result.keymap_content or ""
                            output.write_text(keymap_content)
                            console.console.print(
                                f"[green]✓ Transformed layout written to:[/green] {output}"
                            )
                        else:
                            # Display to console
                            console.console.print("\\n[bold]Transformed Keymap:[/bold]")
                            console.console.print(compile_result.keymap_content)
                    else:
                        console.console.print(
                            "[red]✗ Compilation failed after transformation[/red]"
                        )
                        for error in compile_result.errors:
                            console.console.print(f"  • {error}")
            else:
                console.console.print("[red]✗ Transformations failed[/red]")
                for error_msg in transformation_result.errors:
                    console.console.print(f"  • {error_msg}")
        else:
            console.console.print("[yellow]No transformations configured[/yellow]")
            console.console.print(
                "Use options like --remap, --merge-layers, --modify-behavior to configure transformations"
            )

    except Exception as e:
        logger.error("transformation_failed", error=str(e), exc_info=True)
        console.console.print(f"[red]Error applying transformations:[/red] {e}")


@transform_group.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@with_profile()
@with_metrics("zmk_layout.transform.info")
@handle_errors
def info(input_file: Path, app_context: Any) -> None:
    """Show transformation capabilities and AST information for a layout."""
    console = get_themed_console()

    try:
        # Read input layout
        with input_file.open() as f:
            layout_data_dict = json.load(f)

        layout_data = LayoutData.model_validate(layout_data_dict)
        keyboard_profile = app_context.keyboard_profile

        # Create enhanced zmk-layout service
        service = create_enhanced_zmk_layout_service(
            keyboard_id=keyboard_profile.keyboard_name if keyboard_profile else None
        )

        console.console.print(f"[green]Layout File:[/green] {input_file}")
        console.console.print(f"[blue]Keyboard:[/blue] {layout_data.keyboard}")
        console.console.print(f"[blue]Layers:[/blue] {len(layout_data.layers)}")

        # Get compiler info including AST processing capabilities
        compiler_info = service.get_compiler_info()

        console.console.print("\\n[bold]Enhanced Compiler Capabilities:[/bold]")
        for capability in compiler_info.get("capabilities", []):
            console.console.print(f"  ✓ {capability.replace('_', ' ').title()}")

        if "ast_processing" in compiler_info:
            ast_info = compiler_info["ast_processing"]
            console.console.print("\\n[bold]AST Processing:[/bold]")
            console.console.print(
                f"  • Total Transformers: {ast_info.get('transformers_count', 0)}"
            )
            console.console.print(
                f"  • Dry Run Mode: {'Enabled' if ast_info.get('dry_run_mode') else 'Disabled'}"
            )
            console.console.print(
                f"  • Rollback Support: {'Enabled' if ast_info.get('rollback_enabled') else 'Disabled'}"
            )

            enabled_transformers = ast_info.get("enabled_transformers", [])
            if enabled_transformers:
                console.console.print(
                    f"  • Enabled Transformers: {', '.join(enabled_transformers)}"
                )
            else:
                console.console.print("  • No transformers currently enabled")

        console.console.print("\\n[bold]Available Transformations:[/bold]")
        console.console.print("  • Key Remapping: --remap 'old_key:new_key'")
        console.console.print(
            '  • Layer Merging: --merge-layers \'{"new_layer": ["layer1", "layer2"]}\''
        )
        console.console.print(
            "  • Behavior Modifications: --modify-behavior 'behavior:param=value'"
        )
        console.console.print("  • Macro Expansion: --expand-macros")
        console.console.print(
            '  • Combo Generation: --generate-combos \'{"pattern": {"config": "value"}}\''
        )

        # Show layer structure for transformation planning
        console.console.print("\\n[bold]Layer Structure:[/bold]")
        for i, layer in enumerate(layout_data.layers):
            layer_name = getattr(layer, "name", f"layer_{i}")
            layer_bindings = (
                getattr(layer, "bindings", layer)
                if hasattr(layer, "bindings")
                else layer
            )
            binding_count = (
                len(layer_bindings) if isinstance(layer_bindings, list | tuple) else 0
            )
            console.console.print(f"  [{i}] {layer_name}: {binding_count} bindings")

    except Exception as e:
        logger.error("transformation_info_failed", error=str(e), exc_info=True)
        console.console.print(f"[red]Error getting transformation info:[/red] {e}")


@transform_group.command()
@with_profile()
@with_metrics("zmk_layout.transform.examples")
@handle_errors
def examples(app_context: Any) -> None:
    """Show examples of AST transformation commands."""
    console = get_themed_console()

    console.console.print("[bold blue]AST Transformation Examples[/bold blue]\\n")

    console.console.print("[bold]1. Key Remapping:[/bold]")
    console.console.print(
        "   glovebox zmk-layout transform apply layout.json --remap 'A:B' --remap 'B:A'"
    )
    console.console.print("   [dim]Swaps A and B keys across all layers[/dim]\\n")

    console.console.print("[bold]2. Layer Merging:[/bold]")
    console.console.print(
        '   glovebox zmk-layout transform apply layout.json --merge-layers \'{"combined": ["base", "nav"]}\''
    )
    console.console.print(
        "   [dim]Merges base and nav layers into a new combined layer[/dim]\\n"
    )

    console.console.print("[bold]3. Behavior Modifications:[/bold]")
    console.console.print(
        "   glovebox zmk-layout transform apply layout.json --modify-behavior 'hold_tap:tapping_term_ms=200'"
    )
    console.console.print(
        "   [dim]Changes tapping term for hold-tap behaviors[/dim]\\n"
    )

    console.console.print("[bold]4. Macro Expansion:[/bold]")
    console.console.print(
        "   glovebox zmk-layout transform apply layout.json --expand-macros"
    )
    console.console.print(
        "   [dim]Expands common macros like COPY, PASTE, CUT[/dim]\\n"
    )

    console.console.print("[bold]5. Combo Generation:[/bold]")
    console.console.print(
        '   glovebox zmk-layout transform apply layout.json --generate-combos \'{"copy": {"keys": [1, 2], "binding": "&kp LC(C)"}}\''
    )
    console.console.print("   [dim]Generates combos based on patterns[/dim]\\n")

    console.console.print("[bold]6. Dry Run Mode:[/bold]")
    console.console.print(
        "   glovebox zmk-layout transform apply layout.json --dry-run --remap 'A:B'"
    )
    console.console.print(
        "   [dim]Shows what would be transformed without applying changes[/dim]\\n"
    )

    console.console.print("[bold]7. Complex Transformation:[/bold]")
    console.console.print("   glovebox zmk-layout transform apply layout.json \\\\")
    console.console.print("     --remap 'A:B' --remap 'B:A' \\\\")
    console.console.print("     --expand-macros \\\\")
    console.console.print("     --modify-behavior 'hold_tap:tapping_term_ms=150' \\\\")
    console.console.print("     --output transformed_layout.dtsi")
    console.console.print(
        "   [dim]Applies multiple transformations and saves to file[/dim]\\n"
    )

    console.console.print("[bold yellow]Tips:[/bold yellow]")
    console.console.print("• Use --dry-run to preview changes before applying")
    console.console.print("• Use transform info to analyze layout structure first")
    console.console.print("• Transformations are applied in priority order")
    console.console.print(
        "• Rollback support allows reverting changes during development"
    )
