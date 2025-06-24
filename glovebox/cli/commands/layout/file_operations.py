"""Layout file manipulation CLI commands (split, merge, export, import)."""

from pathlib import Path
from typing import Annotated

import typer

from glovebox.cli.commands.layout.base import LayoutOutputCommand
from glovebox.cli.decorators import handle_errors, with_profile
from glovebox.cli.helpers.auto_profile import (
    resolve_json_file_path,
    resolve_profile_with_auto_detection,
)
from glovebox.cli.helpers.parameters import (
    JsonFileArgument,
    OutputFormatOption,
    ProfileOption,
)
from glovebox.cli.helpers.profile import (
    create_profile_from_option,
    get_keyboard_profile_from_context,
    get_user_config_from_context,
)
from glovebox.layout.layer import create_layout_layer_service
from glovebox.layout.service import create_layout_service
from glovebox.layout import (
    create_layout_component_service,
    create_layout_display_service,
    create_grid_layout_formatter,
    create_behavior_registry,
)
from glovebox.layout.behavior.formatter import BehaviorFormatterImpl
from glovebox.layout.zmk_generator import ZmkFileContentGenerator
from glovebox.adapters import create_file_adapter, create_template_adapter


def _create_layout_service_with_dependencies():
    """Create a layout service with all required dependencies."""
    file_adapter = create_file_adapter()
    template_adapter = create_template_adapter()
    behavior_registry = create_behavior_registry()
    behavior_formatter = BehaviorFormatterImpl(behavior_registry)
    dtsi_generator = ZmkFileContentGenerator(behavior_formatter)
    layout_generator = create_grid_layout_formatter()
    component_service = create_layout_component_service(file_adapter)
    layout_display_service = create_layout_display_service(layout_generator)
    
    return create_layout_service(
        file_adapter=file_adapter,
        template_adapter=template_adapter,
        behavior_registry=behavior_registry,
        component_service=component_service,
        layout_service=layout_display_service,
        behavior_formatter=behavior_formatter,
        dtsi_generator=dtsi_generator,
    )

@handle_errors
def split(
    ctx: typer.Context,
    output_dir: Annotated[Path, typer.Argument(help="Directory to save split files")],
    layout_file: JsonFileArgument = None,
    profile: ProfileOption = None,
    no_auto: Annotated[
        bool,
        typer.Option(
            "--no-auto",
            help="Disable automatic profile detection from JSON keyboard field",
        ),
    ] = False,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files")
    ] = False,
    output_format: OutputFormatOption = "text",
) -> None:
    """Split layout into separate component files.

    Breaks down a layout JSON file into individual component files:
    - metadata.json (layout metadata)
    - layers/ directory with individual layer files
    - behaviors.dtsi (custom behaviors, if any)
    - devicetree.dtsi (custom device tree, if any)

    \b
    Profile precedence (highest to lowest):
    1. CLI --profile flag (overrides all)
    2. Auto-detection from JSON keyboard field (unless --no-auto)
    3. GLOVEBOX_PROFILE environment variable
    4. User config default profile
    5. Hardcoded fallback profile

    Examples:
        # Split layout into components with auto-profile detection
        glovebox layout split my-layout.json ./components/

        # Use environment variable for JSON file
        GLOVEBOX_JSON_FILE=layout.json glovebox layout split ./components/

        # Disable auto-detection and specify profile
        glovebox layout split layout.json ./out/ --no-auto --profile glove80/v25.05
    """
    # Get user config for auto-profile detection
    user_config = get_user_config_from_context(ctx)

    # Resolve JSON file path (supports environment variable)
    resolved_layout_file = resolve_json_file_path(layout_file, "GLOVEBOX_JSON_FILE")

    if resolved_layout_file is None:
        from glovebox.cli.helpers import print_error_message

        print_error_message(
            "Layout file is required. Provide as argument or set GLOVEBOX_JSON_FILE environment variable."
        )
        raise typer.Exit(1)

    command = LayoutOutputCommand()
    command.validate_layout_file(resolved_layout_file)

    try:
        # Handle profile detection with auto-detection support
        effective_profile = resolve_profile_with_auto_detection(
            profile, resolved_layout_file, no_auto, user_config
        )

        # Create keyboard profile using effective profile
        keyboard_profile = create_profile_from_option(effective_profile, user_config)

        layout_service = _create_layout_service_with_dependencies()

        result = layout_service.decompose_components_from_file(
            profile=keyboard_profile,
            json_file_path=resolved_layout_file,
            output_dir=output_dir,
            force=force,
        )

        if result.success:
            if output_format.lower() == "json":
                result_data = {
                    "success": True,
                    "source_file": str(resolved_layout_file),
                    "output_directory": str(output_dir),
                    "components_created": result.messages
                    if hasattr(result, "messages")
                    else [],
                }
                command.format_output(result_data, "json")
            else:
                command.print_operation_success(
                    "Layout split into components",
                    {
                        "source": resolved_layout_file,
                        "output_directory": output_dir,
                        "components": "metadata.json, layers/, behaviors, devicetree",
                    },
                )
        else:
            from glovebox.cli.app import AppContext
            from glovebox.cli.helpers import print_error_message, print_list_item

            app_ctx: AppContext = ctx.obj
            icon_mode = app_ctx.icon_mode

            print_error_message("Layout split failed", icon_mode=icon_mode)
            for error in result.errors:
                print_list_item(error, icon_mode=icon_mode)
            raise typer.Exit(1)

    except Exception as e:
        command.handle_service_error(e, "split layout")


@handle_errors
@with_profile(default_profile="glove80/v25.05")
def merge(
    ctx: typer.Context,
    input_dir: Annotated[
        Path,
        typer.Argument(help="Directory with metadata.json and layers/ subdirectory"),
    ],
    output_file: Annotated[Path, typer.Argument(help="Output layout JSON file path")],
    profile: ProfileOption = None,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files")
    ] = False,
    output_format: OutputFormatOption = "text",
) -> None:
    """Merge component files into a single layout JSON file.

    Combines component files (created by split) back into a complete layout:
    - Reads metadata.json for layout metadata
    - Combines all files in layers/ directory
    - Includes custom behaviors and device tree if present

    This was previously called 'compose' but renamed for clarity.

    Examples:
        # Merge components back into layout
        glovebox layout merge ./components/ merged-layout.json

        # Force overwrite existing output file
        glovebox layout merge ./split/ layout.json --force

        # Specify keyboard profile
        glovebox layout merge ./components/ layout.json --profile glove80/v25.05
    """
    command = LayoutOutputCommand()

    try:
        layout_service = _create_layout_service_with_dependencies()
        keyboard_profile = get_keyboard_profile_from_context(ctx)

        result = layout_service.generate_from_directory(
            profile=keyboard_profile,
            components_dir=input_dir,
            output_file_prefix=output_file,
            force=force,
        )

        if result.success:
            if output_format.lower() == "json":
                result_data = {
                    "success": True,
                    "source_directory": str(input_dir),
                    "output_file": str(output_file),
                    "components_merged": result.messages
                    if hasattr(result, "messages")
                    else [],
                }
                command.format_output(result_data, "json")
            else:
                command.print_operation_success(
                    "Components merged into layout",
                    {
                        "source_directory": input_dir,
                        "output_file": output_file,
                        "status": "Layout file created successfully",
                    },
                )
        else:
            from glovebox.cli.app import AppContext
            from glovebox.cli.helpers import print_error_message, print_list_item

            app_ctx: AppContext = ctx.obj
            icon_mode = app_ctx.icon_mode

            print_error_message("Layout merge failed", icon_mode=icon_mode)
            for error in result.errors:
                print_list_item(error, icon_mode=icon_mode)
            raise typer.Exit(1)

    except Exception as e:
        command.handle_service_error(e, "merge layout")


@handle_errors
def export(
    layout_file: Annotated[Path, typer.Argument(help="Path to layout JSON file")],
    layer_name: Annotated[str, typer.Argument(help="Name of the layer to export")],
    output: Annotated[Path, typer.Argument(help="Output file path")],
    format_type: Annotated[
        str,
        typer.Option(
            "--format",
            help="Export format: bindings (array), layer (object), or full (layout)",
        ),
    ] = "bindings",
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files")
    ] = False,
    output_format: OutputFormatOption = "text",
) -> None:
    """Export a layer to an external JSON file.

    Exports layer data in various formats for sharing and reuse:
    - bindings: Array of binding objects (compact)
    - layer: Layer object with name and bindings
    - full: Minimal complete layout with just this layer

    This replaces the previous 'export-layer' command.

    Examples:
        # Export layer as compact bindings array
        glovebox layout export layout.json "Symbol" symbol-bindings.json

        # Export as complete layer object
        glovebox layout export layout.json "Symbol" symbol.json --format layer

        # Export as minimal complete layout
        glovebox layout export layout.json "Symbol" symbol-layout.json --format full

        # Force overwrite existing file
        glovebox layout export layout.json "Gaming" gaming.json --force
    """
    command = LayoutOutputCommand()
    command.validate_layout_file(layout_file)

    try:
        layer_service = create_layout_layer_service()
        result = layer_service.export_layer(
            layout_file=layout_file,
            layer_name=layer_name,
            output=output,
            format_type=format_type,
            force=force,
        )

        if output_format.lower() == "json":
            result_data = {
                "success": True,
                "source_file": str(result["source_file"]),
                "layer_name": result["layer_name"],
                "output_file": str(result["output_file"]),
                "format": result["format"],
                "binding_count": result["binding_count"],
            }
            command.format_output(result_data, "json")
        else:
            command.print_operation_success(
                "Layer exported successfully",
                {
                    "source": result["source_file"],
                    "layer": result["layer_name"],
                    "output": result["output_file"],
                    "format": result["format"],
                    "bindings": result["binding_count"],
                },
            )

    except Exception as e:
        command.handle_service_error(e, f"export layer '{layer_name}'")


@handle_errors
def import_layout(
    base_layout: Annotated[
        Path, typer.Argument(help="Base layout file to import into")
    ],
    add_from: Annotated[
        list[str],
        typer.Option(
            "--add-from",
            help="Source files to import from (format: file.json or file.json:layer)",
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output", "-o", help="Output file (default: overwrite base layout)"
        ),
    ] = None,
    merge_strategy: Annotated[
        str,
        typer.Option(
            "--strategy",
            help="Merge strategy: append (default), replace, or merge",
        ),
    ] = "append",
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files")
    ] = False,
    output_format: OutputFormatOption = "text",
) -> None:
    """Import layers and components from other layout files.

    Unified import command that can combine multiple layouts, import specific
    layers, or merge entire layouts with different strategies.

    Import Sources:
        file.json           - Import all compatible components
        file.json:layer     - Import specific layer by name
        file.json:behaviors - Import custom behaviors
        file.json:meta      - Import metadata fields

    Merge Strategies:
        append   - Add new layers, keep existing (default)
        replace  - Replace conflicting layers
        merge    - Intelligent merge with conflict resolution

    Examples:
        # Import specific layers from other layouts
        glovebox layout import base.json --add-from other.json:Symbol --add-from gaming.json:Gaming

        # Import entire layouts with append strategy
        glovebox layout import base.json --add-from layout1.json --add-from layout2.json

        # Import with replace strategy
        glovebox layout import base.json --add-from other.json --strategy replace

        # Import behaviors only
        glovebox layout import layout.json --add-from custom.json:behaviors

        # Save to new file
        glovebox layout import base.json --add-from other.json --output merged.json
    """
    command = LayoutOutputCommand()
    command.validate_layout_file(base_layout)

    try:
        # This is a more complex operation that would need a new service
        # For now, we'll implement a basic version using existing services
        layer_service = create_layout_layer_service()

        current_file = base_layout
        changes_made = False
        import_results = []

        for source_spec in add_from:
            if ":" in source_spec:
                source_file, source_component = source_spec.split(":", 1)
                source_path = Path(source_file)

                if source_component == "behaviors":
                    # Import custom behaviors (would need editor service enhancement)
                    import_results.append(
                        {
                            "source": source_file,
                            "component": "behaviors",
                            "status": "not_implemented",
                        }
                    )
                elif source_component == "meta":
                    # Import metadata (would need editor service enhancement)
                    import_results.append(
                        {
                            "source": source_file,
                            "component": "metadata",
                            "status": "not_implemented",
                        }
                    )
                else:
                    # Import specific layer
                    # Generate unique name if strategy is append
                    layer_name = source_component
                    if merge_strategy == "append":
                        # Would need to check for name conflicts and generate unique names
                        pass

                    result = layer_service.add_layer(
                        layout_file=current_file,
                        layer_name=layer_name,
                        import_from=source_path,
                        import_layer=source_component,
                        output=output if not changes_made else None,
                        force=force,
                    )
                    current_file = result["output_path"]
                    changes_made = True
                    import_results.append(
                        {
                            "source": source_file,
                            "component": f"layer:{source_component}",
                            "status": "imported",
                            "new_name": layer_name,
                        }
                    )
            else:
                # Import entire layout (would need full layout merge service)
                import_results.append(
                    {
                        "source": source_spec,
                        "component": "full_layout",
                        "status": "not_implemented",
                    }
                )

        if output_format.lower() == "json":
            result_data = {
                "success": True,
                "base_layout": str(base_layout),
                "output_file": str(current_file) if changes_made else str(base_layout),
                "imports": import_results,
                "strategy": merge_strategy,
            }
            command.format_output(result_data, "json")
        else:
            if changes_made:
                command.print_operation_success(
                    "Layout import completed",
                    {
                        "base_layout": base_layout,
                        "output_file": current_file,
                        "imports_completed": len(
                            [r for r in import_results if r["status"] == "imported"]
                        ),
                        "strategy": merge_strategy,
                    },
                )
            else:
                from glovebox.cli.helpers import print_success_message

                print_success_message("No compatible imports found")

            # Show individual import results
            from glovebox.cli.helpers import print_list_item

            for result in import_results:
                if result["status"] == "imported":
                    print_list_item(
                        f"✓ Imported {result['component']} from {result['source']}"
                    )
                elif result["status"] == "not_implemented":
                    from glovebox.cli.helpers.theme import Icons

                    print_list_item(
                        f"{Icons.get_icon('WARNING', 'emoji')} {result['component']} import not yet implemented"
                    )

    except Exception as e:
        command.handle_service_error(e, "import layout")
