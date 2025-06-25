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

    def __init__(self) -> None:
        self.base_formatter = OutputFormatter()

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
            print_success_message(f"{operation.title()} completed")
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
            print_success_message("Operation completed (JSON serialization failed)")

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

    def _format_text(self, results: dict[str, Any], title: str) -> None:
        """Format results as text."""
        if not results:
            print_success_message("No results to display")
            return

        print_success_message(f"{title}:")
        for key, value in results.items():
            if isinstance(value, list) and value:
                print_list_item(f"{key}:")
                for item in value:
                    print_list_item(f"  {item}")
            else:
                print_list_item(f"{key}: {value}")

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
            print_success_message("No operations performed")
            return

        print_success_message("Field operation results:")

        for key, value in results.items():
            if key.startswith("get:"):
                field_name = key[4:]
                print_list_item(f"📄 {field_name}: {value}")
            elif key == "operations":
                if isinstance(value, list) and value:
                    print_list_item("✅ Operations performed:")
                    for op in value:
                        print_list_item(f"   {op}")
            elif key == "output_file":
                print_list_item(f"💾 Saved to: {value}")
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
            print_success_message("No layers found")
            return

        print_success_message(f"Found {len(layers)} layers:")
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
            print_success_message("No differences found")
            return

        print_success_message("Layout comparison results:")
        for section, changes in diff_results.items():
            if changes:
                print_list_item(
                    f"📊 {section}: {len(changes) if isinstance(changes, list | dict) else 1} changes"
                )
            else:
                print_list_item(f"✅ {section}: no changes")

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


def create_layout_output_formatter() -> LayoutOutputFormatter:
    """Create a layout output formatter instance.

    Returns:
        Configured LayoutOutputFormatter instance
    """
    return LayoutOutputFormatter()
