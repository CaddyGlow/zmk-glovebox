"""Layout-related CLI commands."""

import json
import logging
from pathlib import Path
from typing import Annotated

import typer

from glovebox.cli.decorators import handle_errors, with_profile
from glovebox.cli.helpers import (
    print_error_message,
    print_list_item,
    print_success_message,
)
from glovebox.cli.helpers.parameters import OutputFormatOption, ProfileOption
from glovebox.cli.helpers.profile import get_keyboard_profile_from_context
from glovebox.layout.service import create_layout_service
from glovebox.layout.version_manager import create_version_manager


logger = logging.getLogger(__name__)

# Create a typer app for layout commands
layout_app = typer.Typer(
    name="layout",
    help="""Layout management commands.

Convert JSON layouts to ZMK files, extract/merge layers, validate layouts,
and display visual representations of keyboard layouts.""",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@layout_app.command(name="compile")
@handle_errors
@with_profile()
def layout_compile(
    ctx: typer.Context,
    output_file_prefix: Annotated[
        str,
        typer.Argument(
            help="Output directory and base filename (e.g., 'config/my_glove80')"
        ),
    ],
    json_file: Annotated[
        str,
        typer.Argument(help="Path to keymap JSON file"),
    ],
    profile: ProfileOption = None,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files")
    ] = False,
    output_format: OutputFormatOption = "text",
) -> None:
    """Compile ZMK keymap and config files from a JSON keymap file.

    Takes a JSON layout file (exported from Layout Editor) and generates
    ZMK .keymap and .conf files ready for firmware compilation.

    ---

    Examples:

    * glovebox layout compile layout.json output/glove80 --profile glove80/v25.05

    * cat layout.json | glovebox layout compile - output/glove80 --profile glove80/v25.05
    """

    # Generate keymap using the file-based service method
    keymap_service = create_layout_service()

    # The @with_profile decorator injects keyboard_profile parameter
    keyboard_profile = get_keyboard_profile_from_context(ctx)

    try:
        result = keymap_service.generate_from_file(
            profile=keyboard_profile,
            json_file_path=Path(json_file),
            output_file_prefix=output_file_prefix,
            force=force,
        )

        if result.success:
            if output_format.lower() == "json":
                # JSON output for automation
                output_files = result.get_output_files()
                result_data = {
                    "success": True,
                    "message": "Layout generated successfully",
                    "output_files": output_files,
                    "messages": result.messages if hasattr(result, "messages") else [],
                }
                from glovebox.cli.helpers.output_formatter import OutputFormatter

                formatter = OutputFormatter()
                print(formatter.format(result_data, "json"))
            else:
                # Rich text output (default)
                print_success_message("Layout generated successfully")
                output_files = result.get_output_files()

                if output_format.lower() == "table":
                    # Table format for file listing
                    file_data = [
                        {"Type": file_type, "Path": str(file_path)}
                        for file_type, file_path in output_files.items()
                    ]
                    from glovebox.cli.helpers.output_formatter import OutputFormatter

                    formatter = OutputFormatter()
                    formatter.print_formatted(file_data, "table")
                else:
                    # Text format (default)
                    for file_type, file_path in output_files.items():
                        print_list_item(f"{file_type}: {file_path}")
        else:
            print_error_message("Layout generation failed")
            for error in result.errors:
                print_list_item(error)
            raise typer.Exit(1)

    except Exception as e:
        print_error_message(f"Layout generation failed: {str(e)}")
        raise typer.Exit(1) from None


@layout_app.command()
@handle_errors
@with_profile()
def decompose(
    ctx: typer.Context,
    keymap_file: Annotated[Path, typer.Argument(help="Path to keymap JSON file")],
    output_dir: Annotated[
        Path, typer.Argument(help="Directory to save extracted files")
    ],
    profile: ProfileOption = None,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files")
    ] = False,
    output_format: OutputFormatOption = "text",
) -> None:
    """Decompose layers from a keymap file into individual layer files."""

    # Use the file-based service method
    keymap_service = create_layout_service()

    # The @with_profile decorator injects keyboard_profile via context
    keyboard_profile = get_keyboard_profile_from_context(ctx)

    try:
        result = keymap_service.decompose_components_from_file(
            profile=keyboard_profile,
            json_file_path=keymap_file,
            output_dir=output_dir,
            force=force,
        )

        if result.success:
            print_success_message(f"Layout layers decomposed to {output_dir}")
        else:
            print_error_message("Layout component decomposition failed")
            for error in result.errors:
                print_list_item(error)
            raise typer.Exit(1)
    except Exception as e:
        print_error_message(f"Layout component extraction failed: {str(e)}")
        raise typer.Exit(1) from None


@layout_app.command()
@handle_errors
@with_profile(default_profile="glove80/v25.05")
def compose(
    ctx: typer.Context,
    input_dir: Annotated[
        Path,
        typer.Argument(help="Directory with metadata.json and layers/ subdirectory"),
    ],
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Output keymap JSON file path")
    ],
    profile: ProfileOption = None,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files")
    ] = False,
    output_format: OutputFormatOption = "text",
) -> None:
    """Compose layer files into a single keymap file."""

    # Use the file-based service method
    keymap_service = create_layout_service()

    # The @with_profile decorator injects keyboard_profile via context
    keyboard_profile = get_keyboard_profile_from_context(ctx)

    try:
        result = keymap_service.generate_from_directory(
            profile=keyboard_profile,
            components_dir=input_dir,
            output_file_prefix=output,
            force=force,
        )

        if result.success:
            print_success_message(f"Layout composed and saved to {output}")
        else:
            print_error_message("Layout composition failed")
            for error in result.errors:
                print_list_item(error)
            raise typer.Exit(1)
    except Exception as e:
        print_error_message(f"Layout composition failed: {str(e)}")
        raise typer.Exit(1) from None


@layout_app.command()
@handle_errors
@with_profile(default_profile="glove80/v25.05")
def validate(
    ctx: typer.Context,
    json_file: Annotated[Path, typer.Argument(help="Path to keymap JSON file")],
    profile: ProfileOption = None,
    output_format: OutputFormatOption = "text",
) -> None:
    """Validate keymap syntax and structure."""

    # Validate using the file-based service method
    keymap_service = create_layout_service()

    # The @with_profile decorator injects keyboard_profile via context
    keyboard_profile = get_keyboard_profile_from_context(ctx)

    try:
        if keymap_service.validate_from_file(
            profile=keyboard_profile, json_file_path=json_file
        ):
            print_success_message(f"Layout file {json_file} is valid")
        else:
            print_error_message(f"Layout file {json_file} is invalid")
            raise typer.Exit(1)
    except Exception as e:
        print_error_message(f"Layout validation failed: {str(e)}")
        raise typer.Exit(1) from None


@layout_app.command()
@handle_errors
@with_profile(default_profile="glove80/v25.05")
def show(
    ctx: typer.Context,
    json_file: Annotated[
        Path, typer.Argument(help="Path to keyboard layout JSON file")
    ],
    key_width: Annotated[
        int, typer.Option("--key-width", "-w", help="Width for displaying each key")
    ] = 10,
    view_mode: Annotated[
        str | None,
        typer.Option(
            "--view-mode", "-m", help="View mode (normal, compact, split, flat)"
        ),
    ] = None,
    layout: Annotated[
        str | None,
        typer.Option("--layout", "-l", help="Layout name to use for display"),
    ] = None,
    layer: Annotated[
        int | None, typer.Option("--layer", help="Show only specific layer index")
    ] = None,
    profile: ProfileOption = None,
    output_format: OutputFormatOption = "text",
) -> None:
    """Display keymap layout in terminal."""

    # Call the service
    keymap_service = create_layout_service()

    # The @with_profile decorator injects keyboard_profile via context
    keyboard_profile = get_keyboard_profile_from_context(ctx)

    try:
        # Get layout data first for formatting
        if output_format.lower() != "text":
            # For non-text formats, load and format the JSON data
            layout_data = json.loads(json_file.read_text())

            from glovebox.cli.helpers.output_formatter import LayoutDisplayFormatter

            formatter = LayoutDisplayFormatter()
            formatter.print_formatted(layout_data, output_format)
        else:
            # For text format, use the existing show method
            result = keymap_service.show_from_file(
                json_file_path=json_file,
                profile=keyboard_profile,
                key_width=key_width,
            )
            # The show method returns a string
            typer.echo(result)
    except NotImplementedError as e:
        print_error_message(str(e))
        raise typer.Exit(1) from e


@layout_app.command(name="import-master")
@handle_errors
def import_master(
    json_file: Annotated[Path, typer.Argument(help="Path to master layout JSON file")],
    name: Annotated[str, typer.Argument(help="Version name (e.g., 'v42-pre')")],
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing version")
    ] = False,
    output_format: OutputFormatOption = "text",
) -> None:
    """Import a master layout version for future upgrades.

    Downloads a new master version (e.g., from Layout Editor) and stores it
    locally for upgrading custom layouts. Master versions are stored in
    ~/.glovebox/masters/{keyboard}/ for reuse.

    Examples:
        # Import downloaded master version
        glovebox layout import-master ~/Downloads/glorious-v42-pre.json v42-pre

        # Overwrite existing version
        glovebox layout import-master glorious-v42.json v42-pre --force
    """
    version_manager = create_version_manager()

    try:
        result = version_manager.import_master(json_file, name, force)

        if output_format.lower() == "json":
            from glovebox.cli.helpers.output_formatter import OutputFormatter

            formatter = OutputFormatter()
            print(formatter.format(result, "json"))
        else:
            print_success_message(
                f"Imported master version '{name}' for {result['keyboard']}"
            )
            print_list_item(f"Title: {result['title']}")
            print_list_item(f"Stored: {result['path']}")

    except Exception as e:
        print_error_message(f"Failed to import master: {str(e)}")
        raise typer.Exit(1) from None


@layout_app.command()
@handle_errors
def upgrade(
    custom_layout: Annotated[
        Path, typer.Argument(help="Path to custom layout to upgrade")
    ],
    to_master: Annotated[
        str, typer.Option("--to-master", help="Target master version name")
    ],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output path (default: auto-generated)"),
    ] = None,
    from_master: Annotated[
        str | None,
        typer.Option(
            "--from-master",
            help="Source master version (auto-detected if not specified)",
        ),
    ] = None,
    strategy: Annotated[
        str, typer.Option("--strategy", help="Upgrade strategy")
    ] = "preserve-custom",
    output_format: OutputFormatOption = "text",
) -> None:
    """Upgrade custom layout to new master version preserving customizations.

    Merges your customizations with a new master version, preserving your
    custom layers, behaviors, and configurations while updating base layers.

    Examples:
        # Upgrade to new master version (auto-detects source version)
        glovebox layout upgrade my-custom-v41.json --to-master v42-pre

        # Manually specify source version for layouts without metadata
        glovebox layout upgrade my-layout.json --from-master v41 --to-master v42-pre

        # Specify output location
        glovebox layout upgrade my-layout.json --to-master v42-pre --output my-layout-v42.json
    """
    version_manager = create_version_manager()

    try:
        result = version_manager.upgrade_layout(
            custom_layout, to_master, output, strategy, from_master
        )

        if output_format.lower() == "json":
            from glovebox.cli.helpers.output_formatter import OutputFormatter

            formatter = OutputFormatter()
            print(formatter.format(result, "json"))
        else:
            print_success_message(
                f"Upgraded layout from {result['from_version']} to {result['to_version']}"
            )
            print_list_item(f"Output: {result['output_path']}")

            preserved = result["preserved_customizations"]
            if preserved["custom_layers"]:
                print_list_item(
                    f"Preserved custom layers: {', '.join(preserved['custom_layers'])}"
                )
            if preserved["custom_behaviors"]:
                print_list_item(
                    f"Preserved behaviors: {', '.join(preserved['custom_behaviors'])}"
                )
            if preserved["custom_config"]:
                print_list_item(
                    f"Preserved config: {', '.join(preserved['custom_config'])}"
                )

    except Exception as e:
        print_error_message(f"Failed to upgrade layout: {str(e)}")
        raise typer.Exit(1) from None


@layout_app.command(name="list-masters")
@handle_errors
def list_masters(
    keyboard: Annotated[str, typer.Argument(help="Keyboard name (e.g., 'glove80')")],
    output_format: OutputFormatOption = "text",
) -> None:
    """List available master versions for a keyboard.

    Shows all imported master versions that can be used for upgrades.

    Examples:
        # List master versions for Glove80
        glovebox layout list-masters glove80
    """
    version_manager = create_version_manager()

    try:
        masters = version_manager.list_masters(keyboard)

        if not masters:
            print_error_message(f"No master versions found for keyboard '{keyboard}'")
            print_list_item(
                "Import a master version with: glovebox layout import-master"
            )
            return

        if output_format.lower() == "json":
            from glovebox.cli.helpers.output_formatter import OutputFormatter

            formatter = OutputFormatter()
            result_data = {"keyboard": keyboard, "masters": masters}
            print(formatter.format(result_data, "json"))
        elif output_format.lower() == "table":
            from glovebox.cli.helpers.output_formatter import OutputFormatter

            formatter = OutputFormatter()
            formatter.print_formatted(masters, "table")
        else:
            print_success_message(f"Master versions for {keyboard}:")
            for master in masters:
                date_str = master["date"][:10] if master["date"] else "Unknown"
                print_list_item(f"{master['name']} - {master['title']} ({date_str})")

    except Exception as e:
        print_error_message(f"Failed to list masters: {str(e)}")
        raise typer.Exit(1) from None


@layout_app.command()
@handle_errors
def patch(
    source_layout: Annotated[Path, typer.Argument(help="Source layout file to patch")],
    patch_file: Annotated[
        Path,
        typer.Argument(
            help="JSON diff file from 'glovebox layout diff --output-format json'"
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output path (default: source_layout with -patched suffix)",
        ),
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files")
    ] = False,
) -> None:
    """Apply a JSON diff patch to transform a layout.

    Takes a source layout and applies changes from a JSON diff file
    (generated by 'glovebox layout diff --output-format json') to create
    a new transformed layout.

    Examples:
        # Generate a diff
        glovebox layout diff old.json new.json --output-format json > changes.json

        # Apply the diff to transform another layout
        glovebox layout patch my-layout.json changes.json --output patched-layout.json

        # Apply diff with auto-generated output name
        glovebox layout patch my-layout.json changes.json
    """
    import json

    from glovebox.layout.version_manager import create_version_manager

    try:
        # Load the source layout
        version_manager = create_version_manager()
        source_data = version_manager._load_layout(source_layout)

        # Load the patch data
        if not patch_file.exists():
            print_error_message(f"Patch file not found: {patch_file}")
            raise typer.Exit(1)

        patch_content = patch_file.read_text()
        patch_data = json.loads(patch_content)

        # Validate patch format
        if not isinstance(patch_data, dict) or "layers" not in patch_data:
            print_error_message(
                "Invalid patch file format. Must be JSON diff output from 'glovebox layout diff'"
            )
            raise typer.Exit(1)

        # Determine output path
        if output is None:
            output = source_layout.parent / f"{source_layout.stem}-patched.json"

        if output.exists() and not force:
            print_error_message(
                f"Output file already exists: {output}. Use --force to overwrite."
            )
            raise typer.Exit(1)

        # Apply the patch
        patched_data = source_data.model_copy(deep=True)

        # Apply metadata changes
        if "metadata" in patch_data and patch_data["metadata"]:
            for field, change in patch_data["metadata"].items():
                if isinstance(change, dict) and "to" in change:
                    setattr(patched_data, field, change["to"])

        # Apply layer structure changes
        layers_patch = patch_data.get("layers", {})

        # Remove layers
        removed_layers = layers_patch.get("removed", [])
        for layer_name in removed_layers:
            if layer_name in patched_data.layer_names:
                idx = patched_data.layer_names.index(layer_name)
                patched_data.layer_names.pop(idx)
                if idx < len(patched_data.layers):
                    patched_data.layers.pop(idx)

        # Add layers (this is complex without the source data, so we'll note it)
        added_layers = layers_patch.get("added", [])
        if added_layers:
            print_error_message(
                f"Warning: Cannot add new layers {added_layers} - patch only supports modifying existing layers"
            )

        # Apply key changes to existing layers
        changed_layers = layers_patch.get("changed", {})
        for layer_name, layer_changes in changed_layers.items():
            if layer_name not in patched_data.layer_names:
                continue

            layer_idx = patched_data.layer_names.index(layer_name)
            if layer_idx >= len(patched_data.layers):
                continue

            # Apply individual key changes
            key_changes = layer_changes.get("key_changes", [])
            for key_change in key_changes:
                key_idx = key_change.get("key_index")
                new_value = key_change.get("to")

                if (
                    key_idx is not None
                    and new_value is not None
                    and key_idx < len(patched_data.layers[layer_idx])
                ):
                    # Convert DTSI string back to LayoutBinding object
                    from glovebox.layout.models import LayoutBinding, LayoutParam

                    if new_value == "None" or new_value is None:
                        # Handle null/none values
                        patched_data.layers[layer_idx][key_idx] = LayoutBinding(
                            value="&none", params=[]
                        )
                    else:
                        # Parse DTSI string
                        parts = new_value.split()
                        value = parts[0] if parts else "&none"
                        params = []

                        for param in parts[1:]:
                            params.append(LayoutParam(value=param, params=[]))

                        patched_data.layers[layer_idx][key_idx] = LayoutBinding(
                            value=value, params=params
                        )

        # Save the patched layout
        version_manager._save_layout(patched_data, output)

        print_success_message("Applied patch successfully")
        print_list_item(f"Source: {source_layout}")
        print_list_item(f"Patch: {patch_file}")
        print_list_item(f"Output: {output}")

        # Show summary of changes applied
        total_changes = 0
        if "metadata" in patch_data:
            total_changes += len(patch_data["metadata"])
        if "layers" in patch_data:
            total_changes += len(patch_data["layers"].get("removed", []))
            for layer_changes in patch_data["layers"].get("changed", {}).values():
                total_changes += len(layer_changes.get("key_changes", []))

        print_list_item(f"Applied {total_changes} changes")

    except json.JSONDecodeError as e:
        print_error_message(f"Invalid JSON in patch file: {e}")
        raise typer.Exit(1) from None
    except Exception as e:
        print_error_message(f"Failed to apply patch: {e}")
        raise typer.Exit(1) from None


@layout_app.command(name="create-patch")
@handle_errors
def create_patch(
    layout1: Annotated[Path, typer.Argument(help="Original layout file")],
    layout2: Annotated[Path, typer.Argument(help="Modified layout file")],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output", "-o", help="Output patch file (default: auto-generated)"
        ),
    ] = None,
    section: Annotated[
        str,
        typer.Option(
            "--section", help="DTSI section to patch: behaviors, devicetree, or both"
        ),
    ] = "both",
) -> None:
    """Create a unified diff patch file for custom DTSI sections.

    Generates standard unified diff patches that can be used with merge tools
    like git apply, patch command, or merge tools.

    The patch focuses on custom_defined_behaviors and custom_devicetree
    sections only, providing merge-tool compatible output.

    Examples:
        # Create patch for both DTSI sections
        glovebox layout create-patch old.json new.json --output changes.patch

        # Create patch for behaviors only
        glovebox layout create-patch old.json new.json --section behaviors

        # Create patch for devicetree only
        glovebox layout create-patch old.json new.json --section devicetree

        # Auto-generate patch filename
        glovebox layout create-patch old.json new.json
    """
    import difflib

    from glovebox.layout.version_manager import create_version_manager

    try:
        version_manager = create_version_manager()

        # Load both layouts
        layout1_data = version_manager._load_layout(layout1)
        layout2_data = version_manager._load_layout(layout2)

        # Determine output path
        if output is None:
            output = Path(f"{layout1.stem}-to-{layout2.stem}.patch")

        # Collect patches
        patch_sections = []

        def create_section_patch(
            content1: str, content2: str, section_name: str
        ) -> list[str]:
            """Create unified diff for a DTSI section."""
            content1_lines = content1.splitlines(keepends=True) if content1 else []
            content2_lines = content2.splitlines(keepends=True) if content2 else []

            return list(
                difflib.unified_diff(
                    content1_lines,
                    content2_lines,
                    fromfile=f"a/{section_name}",
                    tofile=f"b/{section_name}",
                    lineterm="",
                )
            )

        # Generate patches based on section parameter
        if section in ["behaviors", "both"]:
            behaviors1 = layout1_data.custom_defined_behaviors or ""
            behaviors2 = layout2_data.custom_defined_behaviors or ""

            if behaviors1 != behaviors2:
                behaviors_patch = create_section_patch(
                    behaviors1, behaviors2, "custom_defined_behaviors"
                )
                if behaviors_patch:
                    patch_sections.extend(behaviors_patch)
                    patch_sections.append("")  # Add separator

        if section in ["devicetree", "both"]:
            devicetree1 = layout1_data.custom_devicetree or ""
            devicetree2 = layout2_data.custom_devicetree or ""

            if devicetree1 != devicetree2:
                devicetree_patch = create_section_patch(
                    devicetree1, devicetree2, "custom_devicetree"
                )
                if devicetree_patch:
                    patch_sections.extend(devicetree_patch)

        if not patch_sections:
            print_success_message("No differences found in specified DTSI sections")
            return

        # Write patch file
        patch_content = "\n".join(patch_sections)
        output.write_text(patch_content)

        print_success_message("Created patch file successfully")
        print_list_item(f"Source: {layout1}")
        print_list_item(f"Target: {layout2}")
        print_list_item(f"Output: {output}")
        print_list_item(f"Sections: {section}")
        print_list_item(f"Patch size: {len(patch_sections)} lines")

        # Show usage instructions
        print_success_message("Usage instructions:")
        print_list_item(f"Apply with git: git apply {output}")
        print_list_item(f"Apply with patch: patch -p1 < {output}")
        print_list_item(f"View with diff tool: your-merge-tool {output}")

    except Exception as e:
        print_error_message(f"Failed to create patch: {e}")
        raise typer.Exit(1) from None


@layout_app.command()
@handle_errors
@with_profile(default_profile="glove80/v25.05")
def diff(
    ctx: typer.Context,
    layout1: Annotated[Path, typer.Argument(help="First layout file to compare")],
    layout2: Annotated[Path, typer.Argument(help="Second layout file to compare")],
    output_format: Annotated[
        str,
        typer.Option(
            "--output-format",
            help="Output format: summary (default), detailed, dtsi, or json",
        ),
    ] = "summary",
    profile: ProfileOption = None,
    compare_dtsi: Annotated[
        bool,
        typer.Option(
            "--compare-dtsi", help="Include detailed custom DTSI code comparison"
        ),
    ] = False,
) -> None:
    """Compare two layouts showing differences.

    Shows differences between two layout files, focusing on layers,
    behaviors, custom DTSI code, and configuration changes.

    Output Formats:
        summary  - Basic difference counts (default)
        detailed - Individual key differences within layers
        dtsi     - Detailed DTSI code differences with unified diff
        json     - Structured data with exact key changes for automation

    The --compare-dtsi flag enables detailed custom DTSI code comparison
    for any output format.

    Examples:
        # Basic comparison showing layer and config changes
        glovebox layout diff my-layout-v41.json my-layout-v42.json

        # Detailed view with individual key differences
        glovebox layout diff layout1.json layout2.json --output-format detailed

        # Include custom DTSI code differences
        glovebox layout diff layout1.json layout2.json --compare-dtsi

        # DTSI-focused output with unified diff format
        glovebox layout diff layout1.json layout2.json --output-format dtsi

        # JSON output with structured key change data
        glovebox layout diff layout1.json layout2.json --output-format json

        # JSON with DTSI differences for complete automation
        glovebox layout diff layout1.json layout2.json --output-format json --compare-dtsi

        # Extract single-line patch string for merge tools
        glovebox layout diff layout1.json layout2.json --output-format json --compare-dtsi | jq -r '.custom_dtsi.custom_defined_behaviors.patch_string'

        # Compare your custom layout with a master version
        glovebox layout diff ~/.glovebox/masters/glove80/v42-rc3.json my-custom.json --output-format detailed

        # Process JSON output with jq to extract specific changes
        glovebox layout diff layout1.json layout2.json --output-format json | jq '.layers.changed.Cursor.key_changes'
    """
    from glovebox.layout.version_manager import create_version_manager

    try:
        version_manager = create_version_manager()

        # Load both layouts
        layout1_data = version_manager._load_layout(layout1)
        layout2_data = version_manager._load_layout(layout2)

        # Simple diff implementation
        differences = []

        # Compare metadata
        if layout1_data.title != layout2_data.title:
            differences.append(
                f"Title: '{layout1_data.title}' → '{layout2_data.title}'"
            )
        if layout1_data.version != layout2_data.version:
            differences.append(
                f"Version: '{layout1_data.version}' → '{layout2_data.version}'"
            )

        # Compare layers
        layout1_layers = set(layout1_data.layer_names)
        layout2_layers = set(layout2_data.layer_names)

        added_layers = layout2_layers - layout1_layers
        removed_layers = layout1_layers - layout2_layers

        if added_layers:
            differences.append(f"Added layers: {', '.join(sorted(added_layers))}")
        if removed_layers:
            differences.append(f"Removed layers: {', '.join(sorted(removed_layers))}")

        # Compare behaviors
        layout1_behaviors = (
            len(layout1_data.hold_taps)
            + len(layout1_data.combos)
            + len(layout1_data.macros)
        )
        layout2_behaviors = (
            len(layout2_data.hold_taps)
            + len(layout2_data.combos)
            + len(layout2_data.macros)
        )

        if layout1_behaviors != layout2_behaviors:
            differences.append(f"Behaviors: {layout1_behaviors} → {layout2_behaviors}")

        # Compare config parameters
        layout1_config = len(layout1_data.config_parameters)
        layout2_config = len(layout2_data.config_parameters)

        if layout1_config != layout2_config:
            differences.append(
                f"Config parameters: {layout1_config} → {layout2_config}"
            )

        # Compare custom DTSI code sections
        def normalize_dtsi_content(content: str) -> list[str]:
            """Normalize DTSI content by removing empty lines and normalizing whitespace."""
            if not content:
                return []
            lines = []
            for line in content.splitlines():
                # Strip whitespace and skip empty lines
                normalized = line.strip()
                if normalized:
                    lines.append(normalized)
            return lines

        def get_dtsi_diff(content1: str, content2: str, section_name: str) -> list[str]:
            """Get unified diff for DTSI content."""
            import difflib

            lines1 = normalize_dtsi_content(content1)
            lines2 = normalize_dtsi_content(content2)

            if lines1 == lines2:
                return []

            # Generate unified diff
            diff_lines = list(
                difflib.unified_diff(
                    lines1,
                    lines2,
                    fromfile=f"layout1/{section_name}",
                    tofile=f"layout2/{section_name}",
                    lineterm="",
                    n=3,  # Context lines
                )
            )

            # Filter out the header lines and format for display
            meaningful_diffs = []
            change_count = 0

            for line in diff_lines[2:]:  # Skip file headers
                if line.startswith("@@"):
                    if meaningful_diffs:  # Add separator between chunks
                        meaningful_diffs.append("")
                    continue
                elif line.startswith("-") and not line.startswith("---"):
                    change_count += 1
                    if change_count <= 15:  # Limit output
                        line_preview = (
                            line[1:61] + "..." if len(line) > 61 else line[1:]
                        )
                        meaningful_diffs.append(f"  - {line_preview}")
                elif line.startswith("+") and not line.startswith("+++"):
                    if change_count <= 15:  # Limit output
                        line_preview = (
                            line[1:61] + "..." if len(line) > 61 else line[1:]
                        )
                        meaningful_diffs.append(f"  + {line_preview}")
                elif line.startswith(" ") and change_count <= 15:
                    # Context line
                    line_preview = line[1:61] + "..." if len(line) > 61 else line[1:]
                    meaningful_diffs.append(f"    {line_preview}")

            if change_count > 15:
                meaningful_diffs.append(f"  ... and {change_count - 15} more changes")

            # Add header with change count
            if meaningful_diffs:
                meaningful_diffs.insert(0, f"{section_name}: {change_count} changes")

            return meaningful_diffs

        # Check custom_defined_behaviors and custom_devicetree
        behaviors1 = layout1_data.custom_defined_behaviors or ""
        behaviors2 = layout2_data.custom_defined_behaviors or ""
        devicetree1 = layout1_data.custom_devicetree or ""
        devicetree2 = layout2_data.custom_devicetree or ""

        # Compare custom DTSI code if flag is set or detailed format requested
        if compare_dtsi or output_format.lower() in ["detailed", "dtsi"]:
            if normalize_dtsi_content(behaviors1) != normalize_dtsi_content(behaviors2):
                behavior_diffs = get_dtsi_diff(
                    behaviors1, behaviors2, "custom_defined_behaviors"
                )
                differences.extend(behavior_diffs)

            if normalize_dtsi_content(devicetree1) != normalize_dtsi_content(
                devicetree2
            ):
                devicetree_diffs = get_dtsi_diff(
                    devicetree1, devicetree2, "custom_devicetree"
                )
                differences.extend(devicetree_diffs)
        else:
            # Simple summary for custom DTSI content
            if normalize_dtsi_content(behaviors1) != normalize_dtsi_content(behaviors2):
                differences.append("custom_defined_behaviors: Content differs")
            if normalize_dtsi_content(devicetree1) != normalize_dtsi_content(
                devicetree2
            ):
                differences.append("custom_devicetree: Content differs")

        # Helper function to convert key objects to DTSI format
        def key_to_dtsi(key_obj):
            if key_obj is None:
                return None
            if hasattr(key_obj, "value"):
                # LayoutBinding object
                if hasattr(key_obj, "params") and key_obj.params:
                    params_str = " ".join(
                        str(p.value) if hasattr(p, "value") else str(p)
                        for p in key_obj.params
                    )
                    return f"{key_obj.value} {params_str}"
                else:
                    return key_obj.value
            elif isinstance(key_obj, dict):
                # Dictionary format
                value = key_obj.get("value", "")
                params = key_obj.get("params", [])
                if params:
                    params_str = " ".join(
                        str(p.get("value", p)) if isinstance(p, dict) else str(p)
                        for p in params
                    )
                    return f"{value} {params_str}"
                else:
                    return value
            else:
                return str(key_obj)

        # Compare DTSI layer content for common layers
        common_layers = layout1_layers & layout2_layers
        layer_differences = []

        for layer_name in sorted(common_layers):
            try:
                # Find layer indices
                layout1_idx = layout1_data.layer_names.index(layer_name)
                layout2_idx = layout2_data.layer_names.index(layer_name)

                if layout1_idx < len(layout1_data.layers) and layout2_idx < len(
                    layout2_data.layers
                ):
                    layer1 = (
                        layout1_data.layers[layout1_idx]
                        if isinstance(layout1_data.layers[layout1_idx], list)
                        else []
                    )
                    layer2 = (
                        layout2_data.layers[layout2_idx]
                        if isinstance(layout2_data.layers[layout2_idx], list)
                        else []
                    )

                    if layer1 != layer2:
                        # Count key differences
                        key_diffs = 0
                        max_keys = max(len(layer1), len(layer2))

                        for i in range(max_keys):
                            key1 = layer1[i] if i < len(layer1) else None
                            key2 = layer2[i] if i < len(layer2) else None
                            if key1 != key2:
                                key_diffs += 1

                        layer_differences.append(
                            f"Layer '{layer_name}': {key_diffs} key differences"
                        )

                        # Show detailed differences with DTSI format
                        if output_format.lower() == "detailed":
                            for i in range(max_keys):
                                key1 = layer1[i] if i < len(layer1) else None
                                key2 = layer2[i] if i < len(layer2) else None
                                if key1 != key2:
                                    key1_dtsi = key_to_dtsi(key1) or "None"
                                    key2_dtsi = key_to_dtsi(key2) or "None"
                                    # Truncate long DTSI strings for readability
                                    key1_str = (
                                        key1_dtsi[:40] + "..."
                                        if len(key1_dtsi) > 40
                                        else key1_dtsi
                                    )
                                    key2_str = (
                                        key2_dtsi[:40] + "..."
                                        if len(key2_dtsi) > 40
                                        else key2_dtsi
                                    )
                                    layer_differences.append(
                                        f"  Key {i:2d}: '{key1_str}' → '{key2_str}'"
                                    )

            except (ValueError, IndexError) as e:
                layer_differences.append(f"Layer '{layer_name}': Error comparing - {e}")

        if layer_differences:
            differences.extend(layer_differences)

        # Display results
        if output_format.lower() == "json":
            # JSON output for automation - rebuild with structured data
            json_result = {
                "success": True,
                "layout1": str(layout1),
                "layout2": str(layout2),
                "total_differences": 0,
                "metadata": {},
                "layers": {
                    "added": list(added_layers),
                    "removed": list(removed_layers),
                    "changed": {},
                },
                "behaviors": {
                    "layout1_count": layout1_behaviors,
                    "layout2_count": layout2_behaviors,
                    "changed": layout1_behaviors != layout2_behaviors,
                },
                "config": {
                    "layout1_count": layout1_config,
                    "layout2_count": layout2_config,
                    "changed": layout1_config != layout2_config,
                },
                "custom_dtsi": {
                    "custom_defined_behaviors": {
                        "changed": normalize_dtsi_content(behaviors1)
                        != normalize_dtsi_content(behaviors2),
                        "differences": [],
                    },
                    "custom_devicetree": {
                        "changed": normalize_dtsi_content(devicetree1)
                        != normalize_dtsi_content(devicetree2),
                        "differences": [],
                    },
                },
            }

            # Add metadata changes
            if layout1_data.title != layout2_data.title:
                json_result["metadata"]["title"] = {
                    "from": layout1_data.title,
                    "to": layout2_data.title,
                }
            if layout1_data.version != layout2_data.version:
                json_result["metadata"]["version"] = {
                    "from": layout1_data.version,
                    "to": layout2_data.version,
                }
            if layout1_data.creator != layout2_data.creator:
                json_result["metadata"]["creator"] = {
                    "from": layout1_data.creator,
                    "to": layout2_data.creator,
                }

            # Add layer key changes
            for layer_name in sorted(common_layers):
                try:
                    layout1_idx = layout1_data.layer_names.index(layer_name)
                    layout2_idx = layout2_data.layer_names.index(layer_name)

                    if layout1_idx < len(layout1_data.layers) and layout2_idx < len(
                        layout2_data.layers
                    ):
                        layer1 = (
                            layout1_data.layers[layout1_idx]
                            if isinstance(layout1_data.layers[layout1_idx], list)
                            else []
                        )
                        layer2 = (
                            layout2_data.layers[layout2_idx]
                            if isinstance(layout2_data.layers[layout2_idx], list)
                            else []
                        )

                        if layer1 != layer2:
                            key_changes = []
                            max_keys = max(len(layer1), len(layer2))

                            for i in range(max_keys):
                                key1 = layer1[i] if i < len(layer1) else None
                                key2 = layer2[i] if i < len(layer2) else None

                                if key1 != key2:
                                    key_changes.append(
                                        {
                                            "key_index": i,
                                            "from": key_to_dtsi(key1),
                                            "to": key_to_dtsi(key2),
                                        }
                                    )

                            if key_changes:
                                json_result["layers"]["changed"][layer_name] = {
                                    "total_key_differences": len(key_changes),
                                    "key_changes": key_changes,  # No truncation for JSON output
                                }

                except (ValueError, IndexError):
                    continue

            # Add DTSI differences with complete content (no truncation for JSON)
            if compare_dtsi or output_format.lower() in ["detailed", "dtsi"]:
                import difflib

                # For custom_defined_behaviors
                if normalize_dtsi_content(behaviors1) != normalize_dtsi_content(
                    behaviors2
                ):
                    # Get unified diff lines for merge tool compatibility
                    behaviors1_lines = (
                        behaviors1.splitlines(keepends=True) if behaviors1 else []
                    )
                    behaviors2_lines = (
                        behaviors2.splitlines(keepends=True) if behaviors2 else []
                    )

                    unified_diff = list(
                        difflib.unified_diff(
                            behaviors1_lines,
                            behaviors2_lines,
                            fromfile=f"{layout1.name}/custom_defined_behaviors",
                            tofile=f"{layout2.name}/custom_defined_behaviors",
                            lineterm="",
                        )
                    )

                    # Create single-line patch format for merge tools
                    patch_string = "\\n".join(unified_diff) if unified_diff else ""

                    json_result["custom_dtsi"]["custom_defined_behaviors"].update(
                        {
                            "from_content": behaviors1,
                            "to_content": behaviors2,
                            "unified_diff": unified_diff,
                            "patch_string": patch_string,
                            "patch_ready": True,
                        }
                    )

                # For custom_devicetree
                if normalize_dtsi_content(devicetree1) != normalize_dtsi_content(
                    devicetree2
                ):
                    # Get unified diff lines for merge tool compatibility
                    devicetree1_lines = (
                        devicetree1.splitlines(keepends=True) if devicetree1 else []
                    )
                    devicetree2_lines = (
                        devicetree2.splitlines(keepends=True) if devicetree2 else []
                    )

                    unified_diff = list(
                        difflib.unified_diff(
                            devicetree1_lines,
                            devicetree2_lines,
                            fromfile=f"{layout1.name}/custom_devicetree",
                            tofile=f"{layout2.name}/custom_devicetree",
                            lineterm="",
                        )
                    )

                    # Create single-line patch format for merge tools
                    patch_string = "\\n".join(unified_diff) if unified_diff else ""

                    json_result["custom_dtsi"]["custom_devicetree"].update(
                        {
                            "from_content": devicetree1,
                            "to_content": devicetree2,
                            "unified_diff": unified_diff,
                            "patch_string": patch_string,
                            "patch_ready": True,
                        }
                    )

            # Calculate total differences
            json_result["total_differences"] = (
                len(json_result["metadata"])
                + len(json_result["layers"]["added"])
                + len(json_result["layers"]["removed"])
                + len(json_result["layers"]["changed"])
                + (1 if json_result["behaviors"]["changed"] else 0)
                + (1 if json_result["config"]["changed"] else 0)
                + (
                    1
                    if json_result["custom_dtsi"]["custom_defined_behaviors"]["changed"]
                    else 0
                )
                + (
                    1
                    if json_result["custom_dtsi"]["custom_devicetree"]["changed"]
                    else 0
                )
            )

            from glovebox.cli.helpers.output_formatter import OutputFormatter

            formatter = OutputFormatter()
            print(formatter.format(json_result, "json"))
        else:
            # Text output (default)
            if not differences:
                print_success_message("No significant differences found")
            else:
                print_success_message(f"Found {len(differences)} difference(s):")
                for diff in differences:
                    print_list_item(diff)

    except Exception as e:
        print_error_message(f"Failed to compare layouts: {str(e)}")
        raise typer.Exit(1) from None


@layout_app.command(name="get-field")
@handle_errors
def get_field(
    layout_file: Annotated[Path, typer.Argument(help="Path to layout JSON file")],
    field_path: Annotated[
        str,
        typer.Argument(
            help="Field path (e.g., 'title', 'layer_names[0]', 'custom_defined_behaviors')"
        ),
    ],
    output_format: Annotated[
        str,
        typer.Option(
            "--output-format", help="Output format: text (default), json, or raw"
        ),
    ] = "text",
) -> None:
    """Get a specific field value from a layout JSON file.

    Supports dot notation and array indexing for nested field access.
    Use bracket notation for array indices and special characters.

    Examples:
        # Get basic fields
        glovebox layout get-field layout.json title
        glovebox layout get-field layout.json version
        glovebox layout get-field layout.json keyboard

        # Get array elements
        glovebox layout get-field layout.json layer_names[0]
        glovebox layout get-field layout.json layer_names[-1]  # Last element

        # Get nested fields
        glovebox layout get-field layout.json config_parameters[0].paramName

        # Get large text fields
        glovebox layout get-field layout.json custom_defined_behaviors --output-format raw
        glovebox layout get-field layout.json custom_devicetree --output-format raw

        # JSON output for automation
        glovebox layout get-field layout.json layer_names --output-format json
    """
    import json

    from glovebox.layout.version_manager import create_version_manager

    try:
        version_manager = create_version_manager()
        layout_data = version_manager._load_layout(layout_file)

        # Parse field path and extract value directly from the Pydantic model
        value = _extract_field_value_from_model(layout_data, field_path)

        # Format output based on requested format
        if output_format.lower() == "json":
            from glovebox.cli.helpers.output_formatter import OutputFormatter

            formatter = OutputFormatter()
            print(formatter.format(value, "json"))
        elif output_format.lower() == "raw":
            # Raw output with no formatting
            print(str(value))
        else:
            # Text format with basic formatting
            if isinstance(value, dict | list):
                from glovebox.cli.helpers.output_formatter import OutputFormatter

                formatter = OutputFormatter()
                print(formatter.format(value, "json"))
            else:
                print(str(value))

    except Exception as e:
        print_error_message(f"Failed to get field '{field_path}': {e}")
        raise typer.Exit(1) from None


@layout_app.command(name="set-field")
@handle_errors
def set_field(
    layout_file: Annotated[Path, typer.Argument(help="Path to layout JSON file")],
    field_path: Annotated[
        str,
        typer.Argument(
            help="Field path (e.g., 'title', 'layer_names[0]', 'custom_defined_behaviors')"
        ),
    ],
    value: Annotated[str, typer.Argument(help="New value for the field")],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output", "-o", help="Output file (default: overwrite original)"
        ),
    ] = None,
    value_type: Annotated[
        str,
        typer.Option(
            "--type", help="Value type: auto (default), string, number, boolean, json"
        ),
    ] = "auto",
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files")
    ] = False,
) -> None:
    """Set a specific field value in a layout JSON file.

    Supports dot notation and array indexing for nested field access.
    Values are automatically parsed based on type or can be explicitly typed.

    Examples:
        # Set basic string fields
        glovebox layout set-field layout.json title "My Custom Layout"
        glovebox layout set-field layout.json creator "username"

        # Set with explicit types
        glovebox layout set-field layout.json version "2.0.0" --type string

        # Set array elements
        glovebox layout set-field layout.json layer_names[0] "Base" --type string

        # Set large text fields from files
        glovebox layout set-field layout.json custom_defined_behaviors "$(cat behaviors.dtsi)" --type string

        # Set configuration values
        glovebox layout set-field layout.json config_parameters[0].value "true" --type string

        # Set with JSON values
        glovebox layout set-field layout.json tags '["custom", "modified"]' --type json

        # Output to different file
        glovebox layout set-field layout.json title "New Title" --output modified_layout.json
    """
    import json

    from glovebox.layout.version_manager import create_version_manager

    try:
        version_manager = create_version_manager()
        layout_data = version_manager._load_layout(layout_file)

        # Parse and convert the value based on type
        parsed_value = _parse_field_value(value, value_type)

        # Set the field value directly on the Pydantic model for validation
        _set_field_value_on_model(layout_data, field_path, parsed_value)

        # Determine output path
        if output is None:
            output = layout_file

        if output.exists() and output != layout_file and not force:
            print_error_message(
                f"Output file already exists: {output}. Use --force to overwrite."
            )
            raise typer.Exit(1)

        # Save the modified layout using Pydantic's JSON serialization
        output_content = json.dumps(
            layout_data.model_dump(by_alias=True, exclude_unset=True, mode="json"),
            indent=2,
            ensure_ascii=False,
        )
        output.write_text(output_content, encoding="utf-8")

        print_success_message("Field updated successfully")
        print_list_item(f"File: {output}")
        print_list_item(f"Field: {field_path}")
        print_list_item(
            f"Value: {str(parsed_value)[:100]}{'...' if len(str(parsed_value)) > 100 else ''}"
        )

    except Exception as e:
        print_error_message(f"Failed to set field '{field_path}': {e}")
        raise typer.Exit(1) from None


def _extract_field_value(data: dict, field_path: str):
    """Extract a field value using dot notation and array indexing."""
    import re

    # Split field path into parts, handling array indices
    parts = []
    current_part = ""
    i = 0

    while i < len(field_path):
        char = field_path[i]
        if char == "[":
            # Find matching closing bracket
            if current_part:
                parts.append(current_part)
                current_part = ""
            bracket_count = 1
            index_start = i + 1
            i += 1
            while i < len(field_path) and bracket_count > 0:
                if field_path[i] == "[":
                    bracket_count += 1
                elif field_path[i] == "]":
                    bracket_count -= 1
                i += 1
            index_str = field_path[index_start : i - 1]
            parts.append(f"[{index_str}]")
        elif char == ".":
            if current_part:
                parts.append(current_part)
                current_part = ""
            i += 1
        else:
            current_part += char
            i += 1

    if current_part:
        parts.append(current_part)

    # Navigate through the data structure
    current = data
    for part in parts:
        if part.startswith("[") and part.endswith("]"):
            # Array index access
            index_str = part[1:-1]
            try:
                index = int(index_str)
                if isinstance(current, list):
                    current = current[index]
                else:
                    raise ValueError(f"Cannot index non-list value with [{index_str}]")
            except ValueError as e:
                raise ValueError(f"Invalid array index: {index_str}") from e
        else:
            # Dictionary key access
            if isinstance(current, dict):
                if part in current:
                    current = current[part]
                else:
                    raise KeyError(f"Field '{part}' not found")
            else:
                raise ValueError(f"Cannot access field '{part}' on non-dict value")

    return current


def _set_field_value(data: dict, field_path: str, value):
    """Set a field value using dot notation and array indexing."""
    # Split field path into parts, handling array indices
    parts = []
    current_part = ""
    i = 0

    while i < len(field_path):
        char = field_path[i]
        if char == "[":
            # Find matching closing bracket
            if current_part:
                parts.append(current_part)
                current_part = ""
            bracket_count = 1
            index_start = i + 1
            i += 1
            while i < len(field_path) and bracket_count > 0:
                if field_path[i] == "[":
                    bracket_count += 1
                elif field_path[i] == "]":
                    bracket_count -= 1
                i += 1
            index_str = field_path[index_start : i - 1]
            parts.append(f"[{index_str}]")
        elif char == ".":
            if current_part:
                parts.append(current_part)
                current_part = ""
            i += 1
        else:
            current_part += char
            i += 1

    if current_part:
        parts.append(current_part)

    # Navigate to the parent and set the final field
    current = data
    for _i, part in enumerate(parts[:-1]):
        if part.startswith("[") and part.endswith("]"):
            # Array index access
            index_str = part[1:-1]
            try:
                index = int(index_str)
                if isinstance(current, list):
                    current = current[index]
                else:
                    raise ValueError(f"Cannot index non-list value with [{index_str}]")
            except ValueError as e:
                raise ValueError(f"Invalid array index: {index_str}") from e
        else:
            # Dictionary key access
            if isinstance(current, dict):
                if part in current:
                    current = current[part]
                else:
                    raise KeyError(f"Field '{part}' not found")
            else:
                raise ValueError(f"Cannot access field '{part}' on non-dict value")

    # Set the final field
    final_part = parts[-1]
    if final_part.startswith("[") and final_part.endswith("]"):
        # Array index access
        index_str = final_part[1:-1]
        try:
            index = int(index_str)
            if isinstance(current, list):
                current[index] = value
            else:
                raise ValueError(f"Cannot index non-list value with [{index_str}]")
        except ValueError as e:
            raise ValueError(f"Invalid array index: {index_str}") from e
    else:
        # Dictionary key access
        if isinstance(current, dict):
            current[final_part] = value
        else:
            raise ValueError(f"Cannot set field '{final_part}' on non-dict value")


def _parse_field_value(value_str: str, value_type: str):
    """Parse a string value based on the specified type."""
    import json

    if value_type == "string":
        return value_str
    elif value_type == "number":
        try:
            # Try integer first
            if "." not in value_str:
                return int(value_str)
            else:
                return float(value_str)
        except ValueError as e:
            raise ValueError(f"Cannot parse '{value_str}' as number") from e
    elif value_type == "boolean":
        if value_str.lower() in ("true", "1", "yes", "on"):
            return True
        elif value_str.lower() in ("false", "0", "no", "off"):
            return False
        else:
            raise ValueError(f"Cannot parse '{value_str}' as boolean")
    elif value_type == "json":
        try:
            return json.loads(value_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Cannot parse '{value_str}' as JSON: {e}") from e
    else:  # auto
        # Try to automatically determine the type
        if value_str.lower() in ("true", "false"):
            return value_str.lower() == "true"

        # Try number
        try:
            if "." in value_str:
                return float(value_str)
            else:
                return int(value_str)
        except ValueError:
            pass

        # Try JSON for complex types
        if value_str.startswith(("{", "[")):
            try:
                return json.loads(value_str)
            except json.JSONDecodeError:
                pass

        # Default to string
        return value_str


def _parse_field_path(field_path: str):
    """Parse field path into parts, handling array indices."""
    parts = []
    current_part = ""
    i = 0

    while i < len(field_path):
        char = field_path[i]
        if char == "[":
            # Find matching closing bracket
            if current_part:
                parts.append(current_part)
                current_part = ""
            bracket_count = 1
            index_start = i + 1
            i += 1
            while i < len(field_path) and bracket_count > 0:
                if field_path[i] == "[":
                    bracket_count += 1
                elif field_path[i] == "]":
                    bracket_count -= 1
                i += 1
            index_str = field_path[index_start : i - 1]
            parts.append(f"[{index_str}]")
        elif char == ".":
            if current_part:
                parts.append(current_part)
                current_part = ""
            i += 1
        else:
            current_part += char
            i += 1

    if current_part:
        parts.append(current_part)

    return parts


def _extract_field_value_from_model(model, field_path: str):
    """Extract a field value directly from a Pydantic model."""
    parts = _parse_field_path(field_path)
    current = model

    for part in parts:
        if part.startswith("[") and part.endswith("]"):
            # Array index access
            index_str = part[1:-1]
            try:
                index = int(index_str)
                if hasattr(current, "__getitem__"):
                    current = current[index]
                else:
                    raise ValueError(
                        f"Cannot index non-indexable value with [{index_str}]"
                    )
            except (ValueError, IndexError) as e:
                raise ValueError(f"Invalid array index: {index_str}") from e
        else:
            # Attribute access
            if hasattr(current, part):
                current = getattr(current, part)
            else:
                raise KeyError(f"Field '{part}' not found")

    return current


def _set_field_value_on_model(model, field_path: str, value):
    """Set a field value directly on a Pydantic model."""
    parts = _parse_field_path(field_path)
    current = model

    # Navigate to the parent
    for part in parts[:-1]:
        if part.startswith("[") and part.endswith("]"):
            # Array index access
            index_str = part[1:-1]
            try:
                index = int(index_str)
                if hasattr(current, "__getitem__"):
                    current = current[index]
                else:
                    raise ValueError(
                        f"Cannot index non-indexable value with [{index_str}]"
                    )
            except (ValueError, IndexError) as e:
                raise ValueError(f"Invalid array index: {index_str}") from e
        else:
            # Attribute access
            if hasattr(current, part):
                current = getattr(current, part)
            else:
                raise KeyError(f"Field '{part}' not found")

    # Set the final field
    final_part = parts[-1]
    if final_part.startswith("[") and final_part.endswith("]"):
        # Array index access
        index_str = final_part[1:-1]
        try:
            index = int(index_str)
            if hasattr(current, "__setitem__"):
                current[index] = value
            else:
                raise ValueError(
                    f"Cannot set index on non-indexable value with [{index_str}]"
                )
        except (ValueError, IndexError) as e:
            raise ValueError(f"Invalid array index: {index_str}") from e
    else:
        # Attribute access - use setattr for Pydantic model field setting
        if hasattr(current, final_part):
            setattr(current, final_part, value)
        else:
            raise KeyError(f"Field '{final_part}' not found")


@layout_app.command(name="add-layer")
@handle_errors
def add_layer(
    layout_file: Annotated[Path, typer.Argument(help="Path to layout JSON file")],
    layer_name: Annotated[str, typer.Argument(help="Name of the new layer")],
    position: Annotated[
        int | None,
        typer.Option(
            "--position",
            "-p",
            help="Position to insert (0-based index, default: append)",
        ),
    ] = None,
    copy_from: Annotated[
        str | None,
        typer.Option("--copy-from", help="Copy bindings from existing layer name"),
    ] = None,
    import_from: Annotated[
        Path | None,
        typer.Option(
            "--import-from",
            help="Import layer from external JSON file (layer.json or full layout.json)",
        ),
    ] = None,
    import_layer: Annotated[
        str | None,
        typer.Option(
            "--import-layer",
            help="Specific layer name to import (when importing from full layout)",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output", "-o", help="Output file (default: overwrite original)"
        ),
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files")
    ] = False,
) -> None:
    """Add a new layer to the layout.

    Creates a new layer with empty bindings, copies from an existing layer,
    or imports from an external JSON file. The layer can be inserted at a
    specific position or appended to the end.

    Examples:
        # Add empty layer at the end
        glovebox layout add-layer layout.json "MyNewLayer"

        # Insert layer at specific position
        glovebox layout add-layer layout.json "MyNewLayer" --position 5

        # Copy layer from existing layer
        glovebox layout add-layer layout.json "CopiedLayer" --copy-from "Symbol"

        # Import layer from single layer JSON file
        glovebox layout add-layer layout.json "ImportedLayer" --import-from exported_layer.json

        # Import specific layer from full layout JSON
        glovebox layout add-layer layout.json "ImportedSymbol" --import-from other_layout.json --import-layer "Symbol"

        # Import and insert at specific position
        glovebox layout add-layer layout.json "ImportedLayer" --import-from layer.json --position 2

        # Output to different file
        glovebox layout add-layer layout.json "NewLayer" --output modified_layout.json
    """
    import json

    from glovebox.layout.models import LayoutBinding
    from glovebox.layout.version_manager import create_version_manager

    try:
        version_manager = create_version_manager()
        layout_data = version_manager._load_layout(layout_file)

        # Validate mutually exclusive options
        source_count = sum(bool(x) for x in [copy_from, import_from])
        if source_count > 1:
            print_error_message("Cannot use --copy-from and --import-from together")
            raise typer.Exit(1)

        if import_layer and not import_from:
            print_error_message("--import-layer requires --import-from")
            raise typer.Exit(1)

        # Check if layer already exists
        if layer_name in layout_data.layer_names:
            print_error_message(f"Layer '{layer_name}' already exists")
            raise typer.Exit(1)

        # Determine position
        if position is None:
            position = len(layout_data.layer_names)
        elif position < 0:
            position = max(0, len(layout_data.layer_names) + position + 1)
        elif position > len(layout_data.layer_names):
            position = len(layout_data.layer_names)

        # Create layer bindings
        if import_from:
            # Import from external JSON file
            if not import_from.exists():
                print_error_message(f"Import file not found: {import_from}")
                raise typer.Exit(1)

            try:
                import_content = import_from.read_text(encoding="utf-8")
                import_data = json.loads(import_content)

                # Detect if this is a single layer JSON or full layout JSON
                if isinstance(import_data, list):
                    # Single layer format: array of bindings
                    new_bindings = [
                        LayoutBinding.model_validate(binding)
                        if isinstance(binding, dict)
                        else LayoutBinding(value=str(binding), params=[])
                        for binding in import_data
                    ]
                    print_list_item(
                        f"Imported {len(new_bindings)} bindings from single layer file"
                    )
                elif isinstance(import_data, dict):
                    # Full layout format: check for layer structure
                    if import_layer:
                        # Import specific layer from full layout
                        if (
                            "layer_names" not in import_data
                            or "layers" not in import_data
                        ):
                            print_error_message(
                                "Import file is not a valid layout JSON"
                            )
                            raise typer.Exit(1)

                        if import_layer not in import_data["layer_names"]:
                            available_layers = ", ".join(import_data["layer_names"])
                            print_error_message(
                                f"Layer '{import_layer}' not found in import file. Available layers: {available_layers}"
                            )
                            raise typer.Exit(1)

                        layer_idx = import_data["layer_names"].index(import_layer)
                        if layer_idx >= len(import_data["layers"]):
                            print_error_message(
                                f"Layer '{import_layer}' has no binding data in import file"
                            )
                            raise typer.Exit(1)

                        imported_bindings = import_data["layers"][layer_idx]
                        new_bindings = [
                            LayoutBinding.model_validate(binding)
                            if isinstance(binding, dict)
                            else LayoutBinding(value=str(binding), params=[])
                            for binding in imported_bindings
                        ]
                        print_list_item(
                            f"Imported layer '{import_layer}' with {len(new_bindings)} bindings"
                        )
                    else:
                        # Try to import as single layer if it has 'bindings' field
                        if "bindings" in import_data:
                            new_bindings = [
                                LayoutBinding.model_validate(binding)
                                if isinstance(binding, dict)
                                else LayoutBinding(value=str(binding), params=[])
                                for binding in import_data["bindings"]
                            ]
                            print_list_item(
                                f"Imported {len(new_bindings)} bindings from layer object"
                            )
                        else:
                            print_error_message(
                                "Import file appears to be a full layout. Use --import-layer to specify which layer to import"
                            )
                            raise typer.Exit(1)
                else:
                    print_error_message(
                        "Invalid import file format. Expected array of bindings or layout object"
                    )
                    raise typer.Exit(1)

            except json.JSONDecodeError as e:
                print_error_message(f"Invalid JSON in import file: {e}")
                raise typer.Exit(1) from e
            except Exception as e:
                print_error_message(f"Failed to import layer: {e}")
                raise typer.Exit(1) from e

        elif copy_from:
            if copy_from not in layout_data.layer_names:
                print_error_message(f"Source layer '{copy_from}' not found")
                raise typer.Exit(1)

            source_idx = layout_data.layer_names.index(copy_from)
            if source_idx < len(layout_data.layers):
                # Deep copy the bindings
                source_bindings = layout_data.layers[source_idx]
                new_bindings = [
                    LayoutBinding(value=binding.value, params=binding.params.copy())
                    for binding in source_bindings
                ]
            else:
                print_error_message(f"Source layer '{copy_from}' has no binding data")
                raise typer.Exit(1)
        else:
            # Create empty layer with default &none bindings (80 keys for Glove80)
            new_bindings = [LayoutBinding(value="&none", params=[]) for _ in range(80)]

        # Insert the layer
        layout_data.layer_names.insert(position, layer_name)
        layout_data.layers.insert(position, new_bindings)

        # Determine output path
        if output is None:
            output = layout_file

        if output.exists() and output != layout_file and not force:
            print_error_message(
                f"Output file already exists: {output}. Use --force to overwrite."
            )
            raise typer.Exit(1)

        # Save the modified layout
        output_content = json.dumps(
            layout_data.model_dump(by_alias=True, exclude_unset=True, mode="json"),
            indent=2,
            ensure_ascii=False,
        )
        output.write_text(output_content, encoding="utf-8")

        print_success_message("Layer added successfully")
        print_list_item(f"File: {output}")
        print_list_item(f"Layer: {layer_name}")
        print_list_item(f"Position: {position}")
        if copy_from:
            print_list_item(f"Copied from: {copy_from}")
        elif import_from:
            print_list_item(f"Imported from: {import_from}")
            if import_layer:
                print_list_item(f"Source layer: {import_layer}")
        print_list_item(f"Total layers: {len(layout_data.layer_names)}")

    except Exception as e:
        print_error_message(f"Failed to add layer '{layer_name}': {e}")
        raise typer.Exit(1) from None


@layout_app.command(name="remove-layer")
@handle_errors
def remove_layer(
    layout_file: Annotated[Path, typer.Argument(help="Path to layout JSON file")],
    layer_name: Annotated[str, typer.Argument(help="Name of the layer to remove")],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output", "-o", help="Output file (default: overwrite original)"
        ),
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files")
    ] = False,
) -> None:
    """Remove a layer from the layout.

    Removes both the layer name and its corresponding binding data.

    Examples:
        # Remove a layer
        glovebox layout remove-layer layout.json "UnusedLayer"

        # Remove layer and save to different file
        glovebox layout remove-layer layout.json "UnusedLayer" --output modified_layout.json
    """
    import json

    from glovebox.layout.version_manager import create_version_manager

    try:
        version_manager = create_version_manager()
        layout_data = version_manager._load_layout(layout_file)

        # Check if layer exists
        if layer_name not in layout_data.layer_names:
            print_error_message(f"Layer '{layer_name}' not found")
            raise typer.Exit(1)

        # Find layer position
        layer_idx = layout_data.layer_names.index(layer_name)

        # Remove layer name and bindings
        layout_data.layer_names.pop(layer_idx)
        if layer_idx < len(layout_data.layers):
            layout_data.layers.pop(layer_idx)

        # Determine output path
        if output is None:
            output = layout_file

        if output.exists() and output != layout_file and not force:
            print_error_message(
                f"Output file already exists: {output}. Use --force to overwrite."
            )
            raise typer.Exit(1)

        # Save the modified layout
        output_content = json.dumps(
            layout_data.model_dump(by_alias=True, exclude_unset=True, mode="json"),
            indent=2,
            ensure_ascii=False,
        )
        output.write_text(output_content, encoding="utf-8")

        print_success_message("Layer removed successfully")
        print_list_item(f"File: {output}")
        print_list_item(f"Removed layer: {layer_name}")
        print_list_item(f"Position was: {layer_idx}")
        print_list_item(f"Remaining layers: {len(layout_data.layer_names)}")

    except Exception as e:
        print_error_message(f"Failed to remove layer '{layer_name}': {e}")
        raise typer.Exit(1) from None


@layout_app.command(name="move-layer")
@handle_errors
def move_layer(
    layout_file: Annotated[Path, typer.Argument(help="Path to layout JSON file")],
    layer_name: Annotated[str, typer.Argument(help="Name of the layer to move")],
    new_position: Annotated[int, typer.Argument(help="New position (0-based index)")],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output", "-o", help="Output file (default: overwrite original)"
        ),
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files")
    ] = False,
) -> None:
    """Move a layer to a new position in the layout.

    Reorders layers by moving the specified layer to a new position.
    All other layers shift accordingly.

    Examples:
        # Move layer to beginning
        glovebox layout move-layer layout.json "Symbol" 0

        # Move layer to end
        glovebox layout move-layer layout.json "Symbol" -1

        # Move layer to specific position
        glovebox layout move-layer layout.json "Symbol" 5

        # Move layer and save to different file
        glovebox layout move-layer layout.json "Symbol" 2 --output reordered_layout.json
    """
    import json

    from glovebox.layout.version_manager import create_version_manager

    try:
        version_manager = create_version_manager()
        layout_data = version_manager._load_layout(layout_file)

        # Check if layer exists
        if layer_name not in layout_data.layer_names:
            print_error_message(f"Layer '{layer_name}' not found")
            raise typer.Exit(1)

        # Find current position
        current_idx = layout_data.layer_names.index(layer_name)

        # Normalize new position
        total_layers = len(layout_data.layer_names)
        if new_position < 0:
            new_position = max(0, total_layers + new_position)
        elif new_position >= total_layers:
            new_position = total_layers - 1

        # Check if move is needed
        if current_idx == new_position:
            print_success_message(
                f"Layer '{layer_name}' is already at position {new_position}"
            )
            return

        # Remove layer and bindings from current position
        layer_name_to_move = layout_data.layer_names.pop(current_idx)
        layer_bindings = None
        if current_idx < len(layout_data.layers):
            layer_bindings = layout_data.layers.pop(current_idx)

        # Insert at new position
        layout_data.layer_names.insert(new_position, layer_name_to_move)
        if layer_bindings is not None:
            layout_data.layers.insert(new_position, layer_bindings)

        # Determine output path
        if output is None:
            output = layout_file

        if output.exists() and output != layout_file and not force:
            print_error_message(
                f"Output file already exists: {output}. Use --force to overwrite."
            )
            raise typer.Exit(1)

        # Save the modified layout
        output_content = json.dumps(
            layout_data.model_dump(by_alias=True, exclude_unset=True, mode="json"),
            indent=2,
            ensure_ascii=False,
        )
        output.write_text(output_content, encoding="utf-8")

        print_success_message("Layer moved successfully")
        print_list_item(f"File: {output}")
        print_list_item(f"Layer: {layer_name}")
        print_list_item(f"From position: {current_idx}")
        print_list_item(f"To position: {new_position}")

    except Exception as e:
        print_error_message(f"Failed to move layer '{layer_name}': {e}")
        raise typer.Exit(1) from None


@layout_app.command(name="list-layers")
@handle_errors
def list_layers(
    layout_file: Annotated[Path, typer.Argument(help="Path to layout JSON file")],
    output_format: Annotated[
        str,
        typer.Option(
            "--output-format", help="Output format: text (default), json, or table"
        ),
    ] = "text",
) -> None:
    """List all layers in the layout with their positions.

    Shows layer names, positions, and binding counts for each layer.

    Examples:
        # List layers in text format
        glovebox layout list-layers layout.json

        # List layers in JSON format for automation
        glovebox layout list-layers layout.json --output-format json

        # List layers in table format
        glovebox layout list-layers layout.json --output-format table
    """
    from glovebox.layout.version_manager import create_version_manager

    try:
        version_manager = create_version_manager()
        layout_data = version_manager._load_layout(layout_file)

        layers_info = []
        for i, layer_name in enumerate(layout_data.layer_names):
            binding_count = (
                len(layout_data.layers[i]) if i < len(layout_data.layers) else 0
            )
            layers_info.append(
                {"position": i, "name": layer_name, "binding_count": binding_count}
            )

        if output_format.lower() == "json":
            from glovebox.cli.helpers.output_formatter import OutputFormatter

            formatter = OutputFormatter()
            result_data = {
                "total_layers": len(layout_data.layer_names),
                "layers": layers_info,
            }
            print(formatter.format(result_data, "json"))
        elif output_format.lower() == "table":
            from glovebox.cli.helpers.output_formatter import OutputFormatter

            formatter = OutputFormatter()
            formatter.print_formatted(layers_info, "table")
        else:
            print_success_message(f"Layout has {len(layout_data.layer_names)} layers:")
            for layer_info in layers_info:
                print_list_item(
                    f"{layer_info['position']:2d}: {layer_info['name']} ({layer_info['binding_count']} bindings)"
                )

    except Exception as e:
        print_error_message(f"Failed to list layers: {e}")
        raise typer.Exit(1) from None


@layout_app.command(name="export-layer")
@handle_errors
def export_layer(
    layout_file: Annotated[Path, typer.Argument(help="Path to layout JSON file")],
    layer_name: Annotated[str, typer.Argument(help="Name of the layer to export")],
    output: Annotated[Path, typer.Option("--output", "-o", help="Output JSON file")],
    format: Annotated[
        str,
        typer.Option(
            "--format",
            help="Export format: bindings (array of bindings), layer (layer object), or full (minimal layout)",
        ),
    ] = "bindings",
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files")
    ] = False,
) -> None:
    """Export a layer to an external JSON file.

    Exports layer data in various formats that can be imported by add-layer.
    This enables sharing and reusing individual layers across layouts.

    Export Formats:
        bindings - Array of binding objects (compact format)
        layer    - Layer object with name and bindings
        full     - Minimal layout with just this layer (for compatibility)

    Examples:
        # Export layer as bindings array (most compact)
        glovebox layout export-layer layout.json "Symbol" --output symbol_layer.json

        # Export as layer object
        glovebox layout export-layer layout.json "Symbol" --output symbol_layer.json --format layer

        # Export as minimal full layout
        glovebox layout export-layer layout.json "Symbol" --output symbol_layout.json --format full

        # Force overwrite existing file
        glovebox layout export-layer layout.json "Symbol" --output symbol.json --force
    """
    import json

    from glovebox.layout.version_manager import create_version_manager

    try:
        version_manager = create_version_manager()
        layout_data = version_manager._load_layout(layout_file)

        # Check if layer exists
        if layer_name not in layout_data.layer_names:
            available_layers = ", ".join(layout_data.layer_names)
            print_error_message(
                f"Layer '{layer_name}' not found. Available layers: {available_layers}"
            )
            raise typer.Exit(1)

        # Find layer data
        layer_idx = layout_data.layer_names.index(layer_name)
        if layer_idx >= len(layout_data.layers):
            print_error_message(f"Layer '{layer_name}' has no binding data")
            raise typer.Exit(1)

        layer_bindings = layout_data.layers[layer_idx]

        # Check output file
        if output.exists() and not force:
            print_error_message(
                f"Output file already exists: {output}. Use --force to overwrite."
            )
            raise typer.Exit(1)

        # Generate export data based on format
        if format == "bindings":
            # Simple array of bindings
            export_data = [
                binding.model_dump(by_alias=True, exclude_unset=True)
                for binding in layer_bindings
            ]
        elif format == "layer":
            # Layer object with name and bindings
            export_data = {
                "name": layer_name,
                "bindings": [
                    binding.model_dump(by_alias=True, exclude_unset=True)
                    for binding in layer_bindings
                ],
            }
        elif format == "full":
            # Minimal layout with just this layer
            export_data = {
                "keyboard": layout_data.keyboard,
                "title": f"Exported layer: {layer_name}",
                "layer_names": [layer_name],
                "layers": [
                    [
                        binding.model_dump(by_alias=True, exclude_unset=True)
                        for binding in layer_bindings
                    ]
                ],
            }
        else:
            print_error_message(
                f"Invalid format: {format}. Use: bindings, layer, or full"
            )
            raise typer.Exit(1)

        # Write export file
        export_content = json.dumps(export_data, indent=2, ensure_ascii=False)
        output.write_text(export_content, encoding="utf-8")

        print_success_message("Layer exported successfully")
        print_list_item(f"Source: {layout_file}")
        print_list_item(f"Layer: {layer_name}")
        print_list_item(f"Output: {output}")
        print_list_item(f"Format: {format}")
        print_list_item(f"Bindings: {len(layer_bindings)}")

    except Exception as e:
        print_error_message(f"Failed to export layer '{layer_name}': {e}")
        raise typer.Exit(1) from None


def register_commands(app: typer.Typer) -> None:
    """Register layout commands with the main app.

    Args:
        app: The main Typer app
    """
    app.add_typer(layout_app, name="layout")
