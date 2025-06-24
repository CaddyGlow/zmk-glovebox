"""Layout comparison CLI commands."""

from pathlib import Path
from typing import Annotated, Any

import typer

from glovebox.adapters import create_file_adapter
from glovebox.cli.commands.layout.base import LayoutOutputCommand
from glovebox.cli.decorators import handle_errors
from glovebox.cli.helpers.parameters import OutputFormatOption, ProfileOption
from glovebox.layout.comparison import create_layout_comparison_service


@handle_errors
def diff(
    ctx: typer.Context,
    layout1: Annotated[Path, typer.Argument(help="First layout file to compare")],
    layout2: Annotated[Path, typer.Argument(help="Second layout file to compare")],
    output_format: Annotated[
        str,
        typer.Option(
            "--format",
            help="Output format: summary (default), detailed, dtsi, pretty, or json",
        ),
    ] = "summary",
    compare_dtsi: Annotated[
        bool,
        typer.Option(
            "--compare-dtsi", help="Include detailed custom DTSI code comparison"
        ),
    ] = False,
    output_patch: Annotated[
        Path | None,
        typer.Option(
            "--output-patch",
            help="Create unified diff patch file for DTSI sections",
        ),
    ] = None,
    patch_section: Annotated[
        str,
        typer.Option(
            "--patch-section",
            help="DTSI section for patch: behaviors, devicetree, or both",
        ),
    ] = "both",
) -> None:
    """Compare two layouts showing differences with optional patch creation.

    Shows differences between two layout files, focusing on layers,
    behaviors, custom DTSI code, and configuration changes. Can also
    create unified diff patch files for DTSI sections.

    Output Formats:
        summary  - Basic difference counts (default)
        detailed - Individual key differences within layers
        dtsi     - Detailed DTSI code differences with unified diff
        pretty   - Human-readable DeepDiff output
        json     - Structured data with exact key changes for automation

    The --compare-dtsi flag enables detailed custom DTSI code comparison
    for any output format. The --output-patch option creates a unified
    diff patch file (replaces the old create-patch command).

    Examples:
        # Basic comparison showing layer and config changes
        glovebox layout diff my-layout-v41.json my-layout-v42.json

        # Detailed view with individual key differences
        glovebox layout diff layout1.json layout2.json --format detailed

        # Include custom DTSI code differences
        glovebox layout diff layout1.json layout2.json --compare-dtsi

        # Create patch file for DTSI sections
        glovebox layout diff old.json new.json --output-patch changes.patch

        # Create patch for specific DTSI section
        glovebox layout diff old.json new.json --output-patch behaviors.patch --patch-section behaviors

        # JSON output with structured key change data
        glovebox layout diff layout1.json layout2.json --format json

        # Compare and create patch in one command
        glovebox layout diff layout1.json layout2.json --format detailed --output-patch changes.patch

        # Compare your custom layout with a master version
        glovebox layout diff ~/.glovebox/masters/glove80/v42-rc3.json my-custom.json --format detailed
    """
    command = LayoutOutputCommand()
    command.validate_layout_file(layout1)
    command.validate_layout_file(layout2)

    try:
        from glovebox.cli.helpers.profile import get_user_config_from_context
        from glovebox.config import create_user_config

        user_config = get_user_config_from_context(ctx) or create_user_config()
        file_adapter = create_file_adapter()
        comparison_service = create_layout_comparison_service(user_config, file_adapter)
        result = comparison_service.compare_layouts(
            layout1_path=layout1,
            layout2_path=layout2,
            output_format=output_format,
            compare_dtsi=compare_dtsi,
        )

        if output_format.lower() == "json":
            command.format_output(result, "json")
        elif output_format.lower() == "pretty":
            # Use DeepDiff's pretty output
            if "deepdiff_pretty" in result:
                print(result["deepdiff_pretty"])
            else:
                from glovebox.cli.helpers import print_success_message

                print_success_message("No significant differences found")
        else:
            # Generate text output from comparison result
            differences = _format_comparison_text(result, output_format, compare_dtsi)
            if not differences:
                from glovebox.cli.helpers import print_success_message

                print_success_message("No significant differences found")
            else:
                from glovebox.cli.helpers import print_list_item, print_success_message

                print_success_message(f"Found {len(differences)} difference(s):")
                for diff in differences:
                    print_list_item(diff)

        # Create patch file if requested
        if output_patch:
            try:
                patch_result = comparison_service.create_dtsi_patch(
                    layout1_path=layout1,
                    layout2_path=layout2,
                    output=output_patch,
                    section=patch_section,
                )

                if patch_result["has_differences"]:
                    from glovebox.cli.helpers import (
                        print_list_item,
                        print_success_message,
                    )

                    print_success_message("Created patch file successfully")
                    print_list_item(f"Patch file: {patch_result['output']}")
                    print_list_item(f"Sections: {patch_result['sections']}")
                    print_list_item(f"Size: {patch_result['patch_lines']} lines")
                else:
                    from glovebox.cli.helpers import print_success_message

                    print_success_message(
                        "No differences found in specified DTSI sections for patch"
                    )

            except Exception as e:
                from glovebox.cli.helpers import print_error_message

                print_error_message(f"Failed to create patch file: {e}")

    except Exception as e:
        command.handle_service_error(e, "compare layouts")


@handle_errors
def patch(
    ctx: typer.Context,
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
    command = LayoutOutputCommand()
    command.validate_layout_file(source_layout)

    try:
        from glovebox.cli.helpers.profile import get_user_config_from_context
        from glovebox.config import create_user_config

        user_config = get_user_config_from_context(ctx) or create_user_config()
        file_adapter = create_file_adapter()
        comparison_service = create_layout_comparison_service(user_config, file_adapter)
        result = comparison_service.apply_patch(
            source_layout_path=source_layout,
            patch_file_path=patch_file,
            output=output,
            force=force,
        )

        # Show success with details
        command.print_operation_success(
            "Applied patch successfully",
            {
                "source": result["source"],
                "patch": result["patch"],
                "output": result["output"],
                "applied_changes": result["total_changes"],
            },
        )

    except Exception as e:
        command.handle_service_error(e, "apply patch")


def _format_comparison_text(
    result: dict[str, Any], output_format: str, compare_dtsi: bool
) -> list[str]:
    """Format comparison result for text output."""
    differences = []

    # Add metadata changes
    for field, change in result.get("metadata", {}).items():
        if isinstance(change, dict) and "from" in change and "to" in change:
            # Handle long content fields differently based on output format
            if field in ["custom_defined_behaviors", "custom_devicetree"]:
                # Only show DTSI fields when compare_dtsi flag is set
                if compare_dtsi:
                    if output_format.lower() == "detailed":
                        # Show full content in detailed mode
                        differences.append(
                            f"{field.title()}: '{change['from']}' → '{change['to']}'"
                        )
                    else:
                        # Show summary in other modes
                        differences.append(f"{field.title()}: Content differs")
            else:
                # Normal metadata fields - show full content
                # Handle list modifications differently
                if (
                    change["from"] == "list_modified"
                    and change["to"] == "list_modified"
                ):
                    differences.append(f"{field.title()}: List modified")
                else:
                    differences.append(
                        f"{field.title()}: '{change['from']}' → '{change['to']}'"
                    )

    # Add layer changes
    layers = result.get("layers", {})
    if layers.get("added"):
        differences.append(f"Added layers: {', '.join(sorted(layers['added']))}")
    if layers.get("removed"):
        differences.append(f"Removed layers: {', '.join(sorted(layers['removed']))}")

    # Add layer overview for summary format or detailed key changes for detailed format
    changed_layers = layers.get("changed", {})
    if changed_layers:
        if output_format.lower() == "detailed":
            # Show detailed key changes for each layer
            for layer_name, layer_changes in changed_layers.items():
                key_count = layer_changes.get("total_key_differences", 0)
                differences.append(f"Layer '{layer_name}': {key_count} key differences")

                # Show individual key changes (limited)
                key_changes = layer_changes.get("key_changes", [])
                if key_changes:
                    for key_change in key_changes[:5]:
                        key_idx = key_change.get("key_index")
                        from_val = key_change.get("from", "None")
                        to_val = key_change.get("to", "None")
                        # Truncate long values
                        from_str = (
                            from_val[:40] + "..."
                            if len(str(from_val)) > 40
                            else str(from_val)
                        )
                        to_str = (
                            to_val[:40] + "..."
                            if len(str(to_val)) > 40
                            else str(to_val)
                        )
                        differences.append(
                            f"  Key {key_idx:2d}: '{from_str}' → '{to_str}'"
                        )

                    # Show truncation if needed
                    total_changes = len(key_changes)
                    if total_changes > 5:
                        differences.append(
                            f"  ... and {total_changes - 5} more changes"
                        )
                else:
                    # Fallback when key_changes is empty but differences exist
                    if key_count > 0:
                        differences.append(
                            f"  • {key_count} key differences (detailed changes available in JSON format)"
                        )
        else:
            # Show summary of layer changes with breakdown
            total_key_changes = sum(
                layer_data.get("total_key_differences", 0)
                for layer_data in changed_layers.values()
            )
            layer_count = len(changed_layers)
            differences.append(
                f"Layers: {layer_count} changed ({total_key_changes} total key differences)"
            )

            # Show per-layer breakdown
            for layer_name, layer_data in sorted(changed_layers.items()):
                key_count = layer_data.get("total_key_differences", 0)
                differences.append(f"  - {layer_name}: {key_count} changes")

    # Add behavior changes
    behaviors = result.get("behaviors", {})
    if behaviors.get("changed"):
        count1 = behaviors.get("layout1_count", 0)
        count2 = behaviors.get("layout2_count", 0)
        if count1 == count2:
            differences.append(f"Behaviors: {count1} modified")
        else:
            differences.append(f"Behaviors: {count1} → {count2}")

        # Add detailed behavior breakdown for detailed format
        if output_format.lower() == "detailed":
            detailed_changes = behaviors.get("detailed_changes", {})
            for behavior_type, changes in detailed_changes.items():
                added = changes.get("added", [])
                removed = changes.get("removed", [])
                changed = changes.get("changed", [])

                if added or removed or changed:
                    differences.append(f"  {behavior_type.title()}:")

                    for behavior in added:
                        differences.append(
                            f"    + Added: {behavior['name']} ({behavior['type']})"
                        )

                    for behavior in removed:
                        differences.append(
                            f"    - Removed: {behavior['name']} ({behavior['type']})"
                        )

                    for behavior in changed:
                        field_changes = behavior.get("field_changes", {})
                        field_count = len(field_changes)
                        differences.append(
                            f"    ~ Changed: {behavior['name']} ({field_count} fields modified)"
                        )

                        # Show specific field changes
                        for field_name, change in field_changes.items():
                            if (
                                isinstance(change, dict)
                                and "from" in change
                                and "to" in change
                            ):
                                from_val = change["from"]
                                to_val = change["to"]
                                # Truncate long values for readability
                                from_str = (
                                    str(from_val)[:30] + "..."
                                    if len(str(from_val)) > 30
                                    else str(from_val)
                                )
                                to_str = (
                                    str(to_val)[:30] + "..."
                                    if len(str(to_val)) > 30
                                    else str(to_val)
                                )
                                differences.append(
                                    f"      • {field_name}: '{from_str}' → '{to_str}'"
                                )
        else:
            # Show summary of behavior types changed
            detailed_changes = behaviors.get("detailed_changes", {})
            behavior_changes_summary: list[str] = []
            for behavior_type, changes in detailed_changes.items():
                added_count = len(changes.get("added", []))
                removed_count = len(changes.get("removed", []))
                changed_count = len(changes.get("changed", []))

                if added_count or removed_count or changed_count:
                    type_summary: list[str] = []
                    if added_count:
                        type_summary.append(f"+{added_count}")
                    if removed_count:
                        type_summary.append(f"-{removed_count}")
                    if changed_count:
                        type_summary.append(f"~{changed_count}")
                    behavior_changes_summary.append(
                        f"{behavior_type}: {'/'.join(type_summary)}"
                    )

            if behavior_changes_summary:
                differences.append(f"  - {', '.join(behavior_changes_summary)}")

    # Add config changes
    config = result.get("config", {})
    if config.get("changed"):
        count1 = config.get("layout1_count", 0)
        count2 = config.get("layout2_count", 0)
        differences.append(f"Config parameters: {count1} → {count2}")

        # Show detailed config changes in detailed mode
        if output_format.lower() == "detailed":
            # Look for config parameter changes in metadata
            config_changes = []
            for field, change in result.get("metadata", {}).items():
                # Config parameters are stored as metadata fields
                if (
                    (field.startswith("config_") or field in ["config_parameters"])
                    and isinstance(change, dict)
                    and "from" in change
                    and "to" in change
                ):
                    config_changes.append(
                        f"    {field}: '{change['from']}' → '{change['to']}'"
                    )

            # If no specific config changes found, check if we can extract from the comparison data
            if not config_changes and count1 != count2:
                differences.append(
                    f"  • Added {count2 - count1} config parameters (details in JSON format)"
                )

            for config_change in config_changes:
                differences.append(config_change)

    # Add DTSI changes (only when compare_dtsi flag is set)
    if compare_dtsi and output_format.lower() == "detailed":
        dtsi = result.get("custom_dtsi", {})
        if dtsi.get("custom_defined_behaviors", {}).get("changed"):
            differences.append("custom_defined_behaviors: Content differs")
        if dtsi.get("custom_devicetree", {}).get("changed"):
            differences.append("custom_devicetree: Content differs")

    return differences
