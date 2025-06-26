"""Unified output formatters for layout CLI commands."""

import json
import logging
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from glovebox.cli.helpers import print_list_item, print_success_message
from glovebox.cli.helpers.output_formatter import OutputFormatter


logger = logging.getLogger(__name__)
console = Console()


class LayoutOutputFormatter:
    """Unified output formatter for layout operations."""

    def __init__(self, icon_mode: str = "emoji") -> None:
        self.base_formatter = OutputFormatter()
        self.icon_mode = icon_mode

    def format_results(
        self,
        results: dict[str, Any],
        output_format: str = "text",
        title: str = "Layout Results",
    ) -> None:
        """Format and output results in the specified format.

        Args:
            results: Results dictionary
            output_format: Output format (text, json, table)
            title: Title for output display
        """
        if output_format.lower() == "json":
            self._format_json(results)
        elif output_format.lower() == "table":
            self._format_table(results, title)
        else:
            self._format_text(results, title)

    def format_field_results(
        self, results: dict[str, Any], output_format: str = "text"
    ) -> None:
        """Format field operation results with specialized formatting.

        Args:
            results: Field operation results
            output_format: Output format
        """
        if output_format.lower() == "json":
            self._format_json(results)
        elif output_format.lower() == "table":
            self._format_field_table(results)
        else:
            self._format_field_text(results)

    def format_layer_results(
        self, layers: list[str], output_format: str = "text"
    ) -> None:
        """Format layer listing results.

        Args:
            layers: List of layer names
            output_format: Output format
        """
        if output_format.lower() == "json":
            print(json.dumps({"layers": layers}, indent=2))
        elif output_format.lower() == "table":
            self._format_layer_table(layers)
        else:
            self._format_layer_text(layers)

    def format_comparison_results(
        self, diff_results: dict[str, Any], output_format: str = "text"
    ) -> None:
        """Format layout comparison results.

        Args:
            diff_results: Comparison results
            output_format: Output format
        """
        if output_format.lower() == "json":
            # For JSON output, return just the clean LayoutDiff data
            if "diff" in diff_results:
                self._format_json(diff_results["diff"])
            else:
                self._format_json(diff_results)
        elif output_format.lower() == "table":
            self._format_comparison_table(diff_results)
        else:
            self._format_comparison_text(diff_results)

    def format_file_operation_results(
        self,
        operation: str,
        input_file: Path,
        output_file: Path | None = None,
        output_format: str = "text",
    ) -> None:
        """Format file operation results (save, export, etc.).

        Args:
            operation: Operation performed
            input_file: Input file path
            output_file: Output file path (if different)
            output_format: Output format
        """
        results = {
            "operation": operation,
            "input_file": str(input_file),
        }
        if output_file:
            results["output_file"] = str(output_file)

        if output_format.lower() == "json":
            self._format_json(results)
        else:
            from glovebox.cli.helpers import print_list_item, print_success_message

            print_success_message(f"{operation.title()} completed", icon_mode=self.icon_mode)
            print_list_item(f"Input: {input_file}")
            if output_file:
                print_list_item(f"Output: {output_file}")

    def _format_json(self, results: dict[str, Any]) -> None:
        """Format results as JSON."""
        try:
            serializable_results = self._make_json_serializable(results)
            print(json.dumps(serializable_results, indent=2))
        except Exception as e:
            logger.error("Failed to serialize results to JSON: %s", e)
            print_success_message("Operation completed (JSON serialization failed)", icon_mode=self.icon_mode)

    def _format_table(self, results: dict[str, Any], title: str) -> None:
        """Format results as a table."""
        table = Table(title=title)
        table.add_column("Operation", style="cyan")
        table.add_column("Result", style="green")

        for key, value in results.items():
            if isinstance(value, list | dict):
                value_str = json.dumps(value, indent=2) if value else "(empty)"
            else:
                value_str = str(value)
            table.add_row(key, value_str)

        console.print(table)

    def _format_text(self, data: Any, title: str | None = None) -> None:
        """Format data as text with flexible handling for different data types."""
        from glovebox.cli.helpers import print_list_item, print_success_message

        if title:
            print_success_message(f"{title}:", icon_mode=self.icon_mode)

        if isinstance(data, dict):
            if not data:
                print_success_message("No results to display", icon_mode=self.icon_mode)
                return

            for key, value in data.items():
                if isinstance(value, list) and value:
                    print_list_item(f"{key}:")
                    for item in value:
                        print_list_item(f"  {item}")
                else:
                    print_list_item(f"{key}: {value}")
        elif isinstance(data, list):
            for item in data:
                print_list_item(str(item))
        else:
            print_list_item(str(data))

    def _format_field_table(self, results: dict[str, Any]) -> None:
        """Format field operation results as a specialized table."""
        table = Table(title="Field Operations")
        table.add_column("Field Path", style="cyan")
        table.add_column("Operation", style="yellow")
        table.add_column("Result", style="green")

        for key, value in results.items():
            if key.startswith("get:"):
                field_path = key[4:]
                table.add_row(field_path, "GET", str(value))
            elif key == "operations":
                if isinstance(value, list):
                    for op in value:
                        parts = op.split(" ", 2)
                        if len(parts) >= 3:
                            operation = parts[0]
                            field_path = parts[1]
                            result = " ".join(parts[2:])
                            table.add_row(field_path, operation.upper(), result)
                        else:
                            table.add_row("", "OPERATION", op)
            else:
                table.add_row("", key.upper(), str(value))

        console.print(table)

    def _format_field_text(self, results: dict[str, Any]) -> None:
        """Format field operation results as text."""
        if not results:
            print_success_message("No operations performed", icon_mode=self.icon_mode)
            return

        print_success_message("Field operation results:", icon_mode=self.icon_mode)

        for key, value in results.items():
            if key.startswith("get:"):
                field_name = key[4:]
                from glovebox.cli.helpers.theme import Icons
                print_list_item(f"{Icons.get_icon('FILE', self.icon_mode)} {field_name}: {value}")
            elif key == "operations":
                if isinstance(value, list) and value:
                    from glovebox.cli.helpers.theme import Icons
                    print_list_item(f"{Icons.get_icon('SUCCESS', self.icon_mode)} Operations performed:")
                    for op in value:
                        print_list_item(f"   {op}")
            elif key == "output_file":
                from glovebox.cli.helpers.theme import Icons
                print_list_item(f"{Icons.get_icon('SAVE', self.icon_mode)} Saved to: {value}")
            else:
                print_list_item(f"{key}: {value}")

    def _format_layer_table(self, layers: list[str]) -> None:
        """Format layer names as a table."""
        table = Table(title="Layout Layers")
        table.add_column("Index", style="cyan")
        table.add_column("Layer Name", style="green")

        for i, layer in enumerate(layers):
            table.add_row(str(i), layer)

        console.print(table)

    def _format_layer_text(self, layers: list[str]) -> None:
        """Format layer names as text."""
        if not layers:
            print_success_message("No layers found", icon_mode=self.icon_mode)
            return

        print_success_message(f"Found {len(layers)} layers:", icon_mode=self.icon_mode)
        for i, layer in enumerate(layers):
            print_list_item(f"{i}: {layer}")

    def _format_comparison_table(self, diff_results: dict[str, Any]) -> None:
        """Format comparison results as a table."""
        table = Table(title="Layout Comparison")
        table.add_column("Section", style="cyan")
        table.add_column("Changes", style="yellow")
        table.add_column("Details", style="green")

        for section, changes in diff_results.items():
            if isinstance(changes, dict):
                change_count = len(changes)
                change_type = "modifications"
            elif isinstance(changes, list):
                change_count = len(changes)
                change_type = "items"
            else:
                change_count = 1
                change_type = "change"

            details = json.dumps(changes, indent=2) if changes else "(no changes)"
            table.add_row(section, f"{change_count} {change_type}", details)

        console.print(table)

    def _format_comparison_text(self, diff_results: dict[str, Any]) -> None:
        """Format comparison results as text."""
        if not diff_results:
            print_success_message("No differences found", icon_mode=self.icon_mode)
            return

        # Handle new LayoutDiff format
        has_changes = diff_results.get("has_changes", False)
        summary = diff_results.get("summary", {})
        detailed = diff_results.get("detailed", False)

        if not has_changes:
            print_success_message("No differences found", icon_mode=self.icon_mode)
            return

        # Show basic info
        source_file = diff_results.get("source_file", "unknown")
        target_file = diff_results.get("target_file", "unknown")
        print_success_message("Layout comparison results:", icon_mode=self.icon_mode)
        from glovebox.cli.helpers.theme import Icons
        print_list_item(f"{Icons.get_icon('FILE', self.icon_mode)} Source: {Path(source_file).name}")
        print_list_item(f"{Icons.get_icon('FILE', self.icon_mode)} Target: {Path(target_file).name}")
        print_list_item("")

        if detailed:
            # Show detailed view with specific changes
            self._format_detailed_changes(diff_results)
        else:
            # Show summary counts
            self._format_summary_changes(summary)

        # Show diff file creation if it happened
        if "diff_file_created" in diff_results:
            diff_info = diff_results["diff_file_created"]
            print_list_item("")
            from glovebox.cli.helpers.theme import Icons
            print_list_item(
                f"{Icons.get_icon('SAVE', self.icon_mode)} Diff file saved: {diff_info.get('diff_file', 'unknown')}"
            )

    def _format_summary_changes(self, summary: dict[str, Any]) -> None:
        """Format summary view of changes."""
        from glovebox.cli.helpers.theme import Icons

        # Show summary counts
        if "layers" in summary:
            layer_summary = summary["layers"]
            if any(layer_summary.values()):
                print_list_item(
                    f"{Icons.get_icon('STATS', self.icon_mode)} Layers: {layer_summary['added']} added, {layer_summary['removed']} removed, {layer_summary['modified']} modified"
                )

        if "behaviors" in summary:
            behavior_summary = summary["behaviors"]
            for behavior_type, counts in behavior_summary.items():
                if any(counts.values()):
                    display_name = behavior_type.replace("_", " ").title()
                    print_list_item(
                        f"{Icons.get_icon('STATS', self.icon_mode)} {display_name}: {counts['added']} added, {counts['removed']} removed, {counts['modified']} modified"
                    )

        if summary.get("metadata_changes", 0) > 0:
            print_list_item(
                f"{Icons.get_icon('STATS', self.icon_mode)} Metadata: {summary['metadata_changes']} field(s) changed"
            )

        if summary.get("dtsi_changes", 0) > 0:
            print_list_item(f"{Icons.get_icon('STATS', self.icon_mode)} DTSI: {summary['dtsi_changes']} section(s) changed")

    def _format_detailed_changes(self, diff_results: dict[str, Any]) -> None:
        """Format detailed view of specific changes."""
        diff_data = diff_results.get("diff", {})

        # Show layer changes in detail
        if "layers" in diff_data and diff_data["layers"]:
            self._format_detailed_layer_changes(diff_data["layers"])

        # Show behavior changes in detail
        for behavior_type in ["hold_taps", "combos", "macros", "input_listeners"]:
            if behavior_type in diff_data and diff_data[behavior_type]:
                self._format_detailed_behavior_changes(
                    behavior_type, diff_data[behavior_type]
                )

        # Show metadata changes in detail
        self._format_detailed_metadata_changes(diff_data)

        # Show DTSI changes in detail
        self._format_detailed_dtsi_changes(diff_data)

    def _format_detailed_layer_changes(self, layer_changes: dict[str, Any]) -> None:
        """Format detailed layer changes."""
        from glovebox.cli.helpers.theme import Icons

        added = layer_changes.get("added", [])
        removed = layer_changes.get("removed", [])
        modified = layer_changes.get("modified", [])

        if added:
            print_list_item(f"{Icons.get_icon('STATS', self.icon_mode)} Added Layers ({len(added)}):")
            for layer in added:
                layer_name = layer.get("name", "Unknown")
                position = layer.get("new_position")
                if position is not None:
                    print_list_item(f"  + {layer_name} (at position {position})")
                else:
                    print_list_item(f"  + {layer_name}")

        if removed:
            print_list_item(f"{Icons.get_icon('STATS', self.icon_mode)} Removed Layers ({len(removed)}):")
            for layer in removed:
                layer_name = layer.get("name", "Unknown")
                position = layer.get("original_position")
                if position is not None:
                    print_list_item(f"  - {layer_name} (was at position {position})")
                else:
                    print_list_item(f"  - {layer_name}")

        if modified:
            print_list_item(f"{Icons.get_icon('STATS', self.icon_mode)} Modified Layers ({len(modified)}):")
            for layer_mod in modified:
                # Modified layers are stored as {layer_name: {patch, positions, etc}}
                if isinstance(layer_mod, dict) and len(layer_mod) == 1:
                    layer_name = list(layer_mod.keys())[0]
                    layer_info = layer_mod[layer_name]

                    if isinstance(layer_info, dict):
                        # Extract position and patch information
                        original_pos = layer_info.get("original_position")
                        new_pos = layer_info.get("new_position")
                        position_changed = layer_info.get("position_changed", False)
                        patch_operations = layer_info.get("patch", [])

                        # Build position info
                        position_info = ""
                        if (
                            position_changed
                            and original_pos is not None
                            and new_pos is not None
                        ):
                            position_info = f" (moved {original_pos}→{new_pos})"
                        elif original_pos is not None:
                            position_info = f" (position {original_pos})"

                        # Count content changes
                        if isinstance(patch_operations, list) and patch_operations:
                            total_changes = len(patch_operations)
                            print_list_item(
                                f"  ~ {layer_name}{position_info}: {total_changes} patch operations"
                            )

                            # Show specific patch operations (limited to first few)
                            for patch_op in patch_operations[:3]:
                                if isinstance(patch_op, dict):
                                    op_type = patch_op.get("op", "unknown")
                                    path = patch_op.get("path", "")
                                    value = str(patch_op.get("value", ""))[:30]
                                    print_list_item(
                                        f"    {op_type.upper()} {path}: {value}"
                                    )

                            if len(patch_operations) > 3:
                                remaining = len(patch_operations) - 3
                                print_list_item(
                                    f"    ... and {remaining} more operations"
                                )
                        elif position_changed:
                            # Position changed but no content changes
                            print_list_item(
                                f"  ~ {layer_name}{position_info}: Position changed only"
                            )
                        else:
                            print_list_item(
                                f"  ~ {layer_name}{position_info}: Modified"
                            )
                    else:
                        # Fallback for old structure (patch_operations directly)
                        if isinstance(layer_info, list):
                            total_changes = len(layer_info)
                            print_list_item(
                                f"  ~ {layer_name}: {total_changes} patch operations"
                            )
                        else:
                            print_list_item(f"  ~ {layer_name}: Modified")
                else:
                    # Fallback for unexpected structure
                    print_list_item("  ~ Unknown layer: Modified")

    def _format_detailed_behavior_changes(
        self, behavior_type: str, behavior_changes: dict[str, Any]
    ) -> None:
        """Format detailed behavior changes."""
        display_name = behavior_type.replace("_", " ").title()
        added = behavior_changes.get("added", [])
        removed = behavior_changes.get("removed", [])
        modified = behavior_changes.get("modified", [])

        if added or removed or modified:
            from glovebox.cli.helpers.theme import Icons
            print_list_item(f"{Icons.get_icon('STATS', self.icon_mode)} {display_name} Changes:")

            for behavior in added:
                name = behavior.get("name", "Unknown")
                print_list_item(f"  + Added: {name}")

            for behavior in removed:
                name = behavior.get("name", "Unknown")
                print_list_item(f"  - Removed: {name}")

            for behavior in modified:
                name = behavior.get("name", "Unknown")
                changes = behavior.get("changes", {})
                change_count = len(changes)
                print_list_item(f"  ~ Modified: {name} ({change_count} field changes)")

                # Show specific field changes (limited)
                for field_name, change_info in list(changes.items())[:3]:
                    if (
                        isinstance(change_info, dict)
                        and "old" in change_info
                        and "new" in change_info
                    ):
                        old_val = str(change_info["old"])[:25]
                        new_val = str(change_info["new"])[:25]
                        print_list_item(f"    {field_name}: '{old_val}' → '{new_val}'")

    def _format_detailed_metadata_changes(self, diff_data: dict[str, Any]) -> None:
        """Format detailed metadata changes."""
        # List of simple metadata fields that use JSON patches
        metadata_fields = [
            "keyboard",
            "title",
            "firmware_api_version",
            "locale",
            "uuid",
            "parent_uuid",
            "date",
            "creator",
            "notes",
            "tags",
            "variables",
            "config_parameters",
            "version",
            "base_version_patch",
            "base_layout",
            "layer_names",
            "last_firmware_build",
        ]

        metadata_changes = []
        for field in metadata_fields:
            if field in diff_data and diff_data[field]:
                # For JSON patch operations, show operation type
                patches = diff_data[field]
                if isinstance(patches, list) and patches:
                    operation_count = len(patches)
                    metadata_changes.append(f"  ~ {field}: {operation_count} changes")

        if metadata_changes:
            from glovebox.cli.helpers.theme import Icons
            print_list_item(f"{Icons.get_icon('STATS', self.icon_mode)} Metadata Changes:")
            for change in metadata_changes:
                print_list_item(change)

    def _format_detailed_dtsi_changes(self, diff_data: dict[str, Any]) -> None:
        """Format detailed DTSI changes."""
        dtsi_changes = []

        if diff_data.get("custom_defined_behaviors"):
            dtsi_changes.append("  ~ Custom behaviors modified")

        if diff_data.get("custom_devicetree"):
            dtsi_changes.append("  ~ Custom devicetree modified")

        if dtsi_changes:
            from glovebox.cli.helpers.theme import Icons
            print_list_item(f"{Icons.get_icon('STATS', self.icon_mode)} DTSI Changes:")
            for change in dtsi_changes:
                print_list_item(change)

    def format_detailed_comparison_text(
        self, result: dict[str, Any], output_format: str, compare_dtsi: bool
    ) -> list[str]:
        """Format comparison result for detailed text output (moved from comparison.py)."""
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
            differences.append(
                f"Removed layers: {', '.join(sorted(layers['removed']))}"
            )

        # Add layer overview for summary format or detailed key changes for detailed format
        changed_layers = layers.get("changed", {})
        if changed_layers:
            if output_format.lower() == "detailed":
                # Show detailed key changes for each layer
                for layer_name, layer_changes in changed_layers.items():
                    key_count = layer_changes.get("total_key_differences", 0)
                    differences.append(
                        f"Layer '{layer_name}': {key_count} key differences"
                    )

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

    def format_compilation_result(
        self, result: dict[str, Any], output_format: str = "text"
    ) -> None:
        """Format compilation results with specialized formatting."""
        if output_format.lower() == "json":
            self._format_json(result)
        elif output_format.lower() == "table":
            self._format_compilation_table(result)
        else:
            self._format_compilation_text(result)

    def format_validation_result(
        self, result: dict[str, Any], output_format: str = "text"
    ) -> None:
        """Format validation results with specialized formatting."""
        if output_format.lower() == "json":
            self._format_json(result)
        else:
            self._format_validation_text(result)

    def format_edit_result(
        self, result: dict[str, Any], output_format: str = "text"
    ) -> None:
        """Format edit operation results with specialized formatting."""
        if output_format.lower() == "json":
            self._format_json(result)
        elif output_format.lower() == "table":
            self._format_edit_table(result)
        else:
            self._format_edit_text(result)

    def _format_compilation_table(self, result: dict[str, Any]) -> None:
        """Format compilation results as a table."""
        table = Table(title="Compilation Results")
        table.add_column("File Type", style="cyan")
        table.add_column("Output Path", style="green")

        output_files = result.get("output_files", {})
        for file_type, file_path in output_files.items():
            table.add_row(file_type.title(), str(file_path))

        console.print(table)

    def _format_compilation_text(self, result: dict[str, Any]) -> None:
        """Format compilation results as text."""
        from glovebox.cli.helpers import print_list_item, print_success_message

        if result.get("success"):
            print_success_message("Layout generated successfully", icon_mode=self.icon_mode)
            output_files = result.get("output_files", {})
            for file_type, file_path in output_files.items():
                print_list_item(f"{file_type}: {file_path}")
        else:
            from glovebox.cli.helpers import print_error_message

            print_error_message("Layout generation failed")
            for error in result.get("errors", []):
                print_list_item(error)

    def _format_validation_text(self, result: dict[str, Any]) -> None:
        """Format validation results as text."""
        from glovebox.cli.helpers import (
            print_error_message,
            print_list_item,
            print_success_message,
        )

        if result.get("valid"):
            print_success_message(f"Layout file {result.get('file')} is valid", icon_mode=self.icon_mode)
        else:
            print_error_message(f"Layout file {result.get('file')} is invalid")
            for error in result.get("errors", []):
                print_list_item(error)

    def _format_edit_table(self, result: dict[str, Any]) -> None:
        """Format edit operation results as a table."""
        table = Table(title="Edit Operations")
        table.add_column("Operation", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Details", style="yellow")

        operations = result.get("operations", [])
        for op in operations:
            table.add_row("EDIT", "SUCCESS", op)

        if result.get("output_file"):
            table.add_row("SAVE", "SUCCESS", f"Saved to: {result['output_file']}")

        console.print(table)

    def _format_edit_text(self, result: dict[str, Any]) -> None:
        """Format edit operation results as text."""
        import json

        from rich.console import Console
        from rich.table import Table

        from glovebox.cli.helpers import print_list_item, print_success_message

        console = Console()

        # Handle get operations (field retrieval)
        for key, value in result.items():
            if key.startswith("get:"):
                field_name = key[4:]
                if isinstance(value, dict | list):
                    print_success_message(f"{field_name}:", icon_mode=self.icon_mode)
                    print(json.dumps(value, indent=2))
                else:
                    print_list_item(f"{field_name}: {value}")

        # Handle layer listing
        if "layers" in result:
            print_success_message("Layers:", icon_mode=self.icon_mode)
            for i, layer in enumerate(result["layers"]):
                print_list_item(f"{i}: {layer}")

        # Handle variable usage display
        if "variable_usage" in result:
            usage = result["variable_usage"]
            if usage:
                table = Table(title="Variable Usage")
                table.add_column("Variable", style="cyan")
                table.add_column("Used In", style="green")
                table.add_column("Count", style="blue")

                for var_name, paths in usage.items():
                    usage_str = (
                        "\n".join(paths[:5])
                        if len(paths) <= 5
                        else "\n".join(paths[:5]) + f"\n... and {len(paths) - 5} more"
                    )
                    table.add_row(var_name, usage_str, str(len(paths)))

                console.print(table)
            else:
                print_list_item("No variable usage found")

        # Handle write operations (existing functionality)
        operations = result.get("operations", [])
        if operations:
            print_success_message("Operations performed:", icon_mode=self.icon_mode)
            for op in operations:
                print_list_item(op)

        # Handle output file indication
        if result.get("output_file"):
            print_list_item(f"Saved to: {result['output_file']}")

    def _make_json_serializable(self, obj: Any) -> Any:
        """Convert object to JSON-serializable format."""
        if hasattr(obj, "model_dump"):
            return obj.model_dump(mode="json")
        elif hasattr(obj, "to_dict"):
            return obj.to_dict()
        elif isinstance(obj, dict):
            return {k: self._make_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_json_serializable(item) for item in obj]
        elif isinstance(obj, Path):
            return str(obj)
        elif isinstance(obj, str | int | float | bool) or obj is None:
            return obj
        else:
            return str(obj)


def create_layout_output_formatter(icon_mode: str = "emoji") -> LayoutOutputFormatter:
    """Create a layout output formatter instance.

    Returns:
        Configured LayoutOutputFormatter instance
    """
    return LayoutOutputFormatter(icon_mode)
