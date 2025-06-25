"""Layout comparison service using the new diffing library.

This is a migration wrapper that maintains the existing API while using
the new glovebox.layout.diffing library underneath.
"""

import difflib
import json
from pathlib import Path
from typing import Any

from glovebox.config import UserConfig
from glovebox.layout.diffing.diff import LayoutDiffSystem
from glovebox.layout.diffing.patch import LayoutPatchSystem
from glovebox.layout.models import LayoutData
from glovebox.layout.utils.json_operations import load_layout_file, save_layout_file
from glovebox.layout.utils.validation import validate_output_path
from glovebox.protocols import FileAdapterProtocol


class LayoutComparisonService:
    """Service for comparing and patching layouts using the new diffing library."""

    def __init__(
        self, user_config: UserConfig, file_adapter: FileAdapterProtocol
    ) -> None:
        """Initialize the comparison service with user configuration and file adapter."""
        self.user_config = user_config
        self.file_adapter = file_adapter
        self.diff_system = LayoutDiffSystem()
        self.patch_system = LayoutPatchSystem()

    def compare_layouts(
        self,
        layout1_path: Path,
        layout2_path: Path,
        output_format: str = "summary",
        compare_dtsi: bool = False,
    ) -> dict[str, Any]:
        """Compare two layouts and return differences.

        Args:
            layout1_path: Path to first layout file
            layout2_path: Path to second layout file
            output_format: Output format ('summary', 'detailed', 'dtsi', 'json', 'pretty')
            compare_dtsi: Include custom DTSI code comparison

        Returns:
            Dictionary with comparison results compatible with original API
        """
        layout1_data = load_layout_file(layout1_path, self.file_adapter)
        layout2_data = load_layout_file(layout2_path, self.file_adapter)

        # Create diff using new library
        diff = self.diff_system.create_layout_diff(layout1_data, layout2_data)

        # Convert to legacy format for API compatibility
        comparison = self._convert_to_legacy_format(
            diff, layout1_data, layout2_data, layout1_path, layout2_path
        )

        # Add DTSI comparison if requested
        if compare_dtsi or output_format.lower() == "dtsi":
            self._add_dtsi_comparison(comparison, layout1_data, layout2_data)

        # Format-specific processing
        if output_format.lower() == "json":
            self._format_json(comparison, diff)
        elif output_format.lower() == "detailed":
            self._format_detailed(comparison, diff)
        elif output_format.lower() == "pretty":
            self._format_pretty(comparison, diff)
        else:
            self._format_summary(comparison)

        return comparison

    def _add_dtsi_comparison(
        self, comparison: dict[str, Any], layout1: LayoutData, layout2: LayoutData
    ) -> None:
        """Add DTSI comparison to the results."""
        behaviors_diff = self._create_unified_diff(
            layout1.custom_defined_behaviors,
            layout2.custom_defined_behaviors,
            "custom_defined_behaviors",
        )
        devicetree_diff = self._create_unified_diff(
            layout1.custom_devicetree,
            layout2.custom_devicetree,
            "custom_devicetree",
        )

        comparison["custom_dtsi"] = {
            "custom_defined_behaviors": {
                "changed": bool(behaviors_diff),
                "differences": behaviors_diff,
            },
            "custom_devicetree": {
                "changed": bool(devicetree_diff),
                "differences": devicetree_diff,
            },
        }

    def apply_patch(
        self,
        source_layout_path: Path,
        patch_file_path: Path,
        output: Path | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """Apply a patch to transform a layout.

        Args:
            source_layout_path: Path to source layout file
            patch_file_path: Path to JSON diff patch file
            output: Output path (defaults to source with -patched suffix)
            force: Whether to overwrite existing files

        Returns:
            Dictionary with patch operation details
        """
        # Load source layout and patch data
        layout_data = load_layout_file(source_layout_path, self.file_adapter)
        patch_data = self._load_patch_file(patch_file_path)

        # Apply patch using new library
        patched_data = self.patch_system.apply_patch(layout_data, patch_data)

        # Determine output path
        if output is None:
            output = (
                source_layout_path.parent / f"{source_layout_path.stem}-patched.json"
            )

        validate_output_path(output, source_layout_path, force)

        # Save patched layout
        save_layout_file(patched_data, output, self.file_adapter)

        return {
            "source": source_layout_path,
            "patch": patch_file_path,
            "output": output,
        }

    def create_dtsi_patch(
        self,
        layout1_path: Path,
        layout2_path: Path,
        output: Path | None = None,
        section: str = "both",
    ) -> dict[str, Any]:
        """Create a unified diff patch for custom DTSI sections.

        Args:
            layout1_path: Path to original layout file
            layout2_path: Path to modified layout file
            output: Output patch file path
            section: DTSI section ('behaviors', 'devicetree', 'both')

        Returns:
            Dictionary with patch creation details
        """
        layout1_data = load_layout_file(layout1_path, self.file_adapter)
        layout2_data = load_layout_file(layout2_path, self.file_adapter)

        # Determine output path
        if output is None:
            output = Path(f"{layout1_path.stem}-to-{layout2_path.stem}.patch")

        # Generate patches
        patch_sections = self._generate_dtsi_patches(
            layout1_data, layout2_data, section
        )

        if not patch_sections:
            return {
                "source": layout1_path,
                "target": layout2_path,
                "output": None,
                "sections": section,
                "has_differences": False,
            }

        # Write patch file
        patch_content = "\n".join(patch_sections)
        output.write_text(patch_content)

        return {
            "source": layout1_path,
            "target": layout2_path,
            "output": output,
            "sections": section,
            "patch_lines": len(patch_sections),
            "has_differences": True,
        }

    def _convert_to_legacy_format(
        self,
        diff: dict[str, Any],
        layout1: LayoutData,
        layout2: LayoutData,
        layout1_path: Path,
        layout2_path: Path,
    ) -> dict[str, Any]:
        """Convert new diff format to legacy format for API compatibility."""
        # Extract information from new diff format
        layout_changes = diff.get("layout_changes", {})
        movements = diff.get("movements", {})
        statistics = diff.get("statistics", {})

        # Build legacy format
        comparison = {
            "success": True,
            "layout1": str(layout1_path),
            "layout2": str(layout2_path),
            "deepdiff_summary": {
                "has_changes": statistics.get("total_operations", 0) > 0,
                "change_types": self._extract_change_types(diff),
                "total_changes": statistics.get("total_operations", 0),
            },
            "metadata": self._convert_metadata_changes(layout_changes),
            "layers": self._convert_layer_changes(layout_changes, movements),
            "behaviors": self._convert_behavior_changes(layout_changes),
            "config": self._convert_config_changes(layout_changes),
            "custom_dtsi": {
                "custom_defined_behaviors": {"changed": False, "differences": []},
                "custom_devicetree": {"changed": False, "differences": []},
            },
        }

        return comparison

    def _convert_metadata_changes(
        self, layout_changes: dict[str, Any]
    ) -> dict[str, Any]:
        """Convert metadata changes to legacy format."""
        return {
            "title": {"changed": False, "old": "", "new": ""},
            "keyboard": {"changed": False, "old": "", "new": ""},
            "notes": {"changed": False, "old": "", "new": ""},
            "tags": {"changed": False, "added": [], "removed": []},
            "version": {"changed": False, "old": "", "new": ""},
        }

    def _convert_layer_changes(
        self, layout_changes: dict[str, Any], movements: dict[str, Any]
    ) -> dict[str, Any]:
        """Convert layer changes to legacy format."""
        layer_data = layout_changes.get("layers", {})
        layer_names_data = layout_changes.get("layer_names", {})
        behavior_changes = movements.get("behavior_changes", [])

        # Build the "changed" layers structure that the CLI expects
        changed_layers = {}

        # Group behavior changes by layer
        layers_with_changes: dict[int, list[dict[str, Any]]] = {}
        for change in behavior_changes:
            layer_idx = change["layer"]
            if layer_idx not in layers_with_changes:
                layers_with_changes[layer_idx] = []
            layers_with_changes[layer_idx].append(change)

        # Convert to the expected format with layer names
        for layer_idx, changes in layers_with_changes.items():
            # Use layer index as key for now, CLI might need layer names
            layer_key = f"layer_{layer_idx}"
            changed_layers[layer_key] = {
                "total_key_differences": len(changes),
                "key_changes": [
                    {
                        "key_index": change["position"],
                        "from": f"{change['from']['value']} {change['from']['params'][0]['value'] if change['from'].get('params') else ''}".strip(),
                        "to": f"{change['to']['value']} {change['to']['params'][0]['value'] if change['to'].get('params') else ''}".strip(),
                    }
                    for change in changes
                ],
            }

        return {
            "count_changed": len(layer_data.get("added", [])) > 0
            or len(layer_data.get("removed", [])) > 0
            or len(changed_layers) > 0,
            "layers_added": layer_data.get("added", []),
            "layers_removed": layer_data.get("removed", []),
            "layers_modified": layer_data.get("modified", []),
            "layer_names_changed": layer_names_data.get("order_changed", False),
            "reordering": layer_data.get("reordered", False),
            "behavior_changes": behavior_changes,
            "changed": changed_layers,  # Add the expected "changed" field
        }

    def _convert_behavior_changes(
        self, layout_changes: dict[str, Any]
    ) -> dict[str, Any]:
        """Convert behavior changes to legacy format."""
        behaviors = layout_changes.get("behaviors", {})

        return {
            "hold_taps": {
                "count_changed": len(behaviors.get("hold_taps", {}).get("added", []))
                > 0
                or len(behaviors.get("hold_taps", {}).get("removed", [])) > 0,
                "added": behaviors.get("hold_taps", {}).get("added", []),
                "removed": behaviors.get("hold_taps", {}).get("removed", []),
                "modified": behaviors.get("hold_taps", {}).get("modified", []),
            },
            "combos": {
                "count_changed": len(behaviors.get("combos", {}).get("added", [])) > 0
                or len(behaviors.get("combos", {}).get("removed", [])) > 0,
                "added": behaviors.get("combos", {}).get("added", []),
                "removed": behaviors.get("combos", {}).get("removed", []),
                "modified": behaviors.get("combos", {}).get("modified", []),
            },
            "macros": {
                "count_changed": len(behaviors.get("macros", {}).get("added", [])) > 0
                or len(behaviors.get("macros", {}).get("removed", [])) > 0,
                "added": behaviors.get("macros", {}).get("added", []),
                "removed": behaviors.get("macros", {}).get("removed", []),
                "modified": behaviors.get("macros", {}).get("modified", []),
            },
            "input_listeners": {
                "count_changed": len(
                    behaviors.get("input_listeners", {}).get("added", [])
                )
                > 0
                or len(behaviors.get("input_listeners", {}).get("removed", [])) > 0,
                "added": behaviors.get("input_listeners", {}).get("added", []),
                "removed": behaviors.get("input_listeners", {}).get("removed", []),
                "modified": behaviors.get("input_listeners", {}).get("modified", []),
            },
        }

    def _convert_config_changes(self, layout_changes: dict[str, Any]) -> dict[str, Any]:
        """Convert config changes to legacy format."""
        config = layout_changes.get("config", {})

        return {
            "count_changed": len(config.get("added", [])) > 0
            or len(config.get("removed", [])) > 0,
            "added": config.get("added", []),
            "removed": config.get("removed", []),
            "modified": config.get("modified", []),
        }

    def _extract_change_types(self, diff: dict[str, Any]) -> list[str]:
        """Extract change types from new diff format."""
        change_types = []
        if diff.get("statistics", {}).get("additions", 0) > 0:
            change_types.append("additions")
        if diff.get("statistics", {}).get("removals", 0) > 0:
            change_types.append("removals")
        if diff.get("statistics", {}).get("replacements", 0) > 0:
            change_types.append("replacements")
        return change_types

    def _format_summary(self, comparison: dict[str, Any]) -> None:
        """Format comparison for summary output."""
        # Summary format doesn't need additional processing
        pass

    def _format_detailed(
        self, comparison: dict[str, Any], diff: dict[str, Any]
    ) -> None:
        """Format comparison for detailed output."""
        # Add detailed movement tracking
        comparison["detailed_movements"] = diff.get("movements", {})

    def _format_json(self, comparison: dict[str, Any], diff: dict[str, Any]) -> None:
        """Format comparison for JSON output."""
        # Add the JSON patch from the new diff system
        comparison["json_patch"] = diff.get("json_patch", [])
        comparison["full_diff"] = diff

    def _format_pretty(self, comparison: dict[str, Any], diff: dict[str, Any]) -> None:
        """Format comparison for pretty output."""
        # Create a pretty representation of the changes
        pretty_lines = []

        # Summary
        stats = diff.get("statistics", {})
        if stats.get("total_operations", 0) > 0:
            pretty_lines.append(f"Total operations: {stats['total_operations']}")
            if stats.get("additions", 0) > 0:
                pretty_lines.append(f"  Additions: {stats['additions']}")
            if stats.get("removals", 0) > 0:
                pretty_lines.append(f"  Removals: {stats['removals']}")
            if stats.get("replacements", 0) > 0:
                pretty_lines.append(f"  Replacements: {stats['replacements']}")
            pretty_lines.append("")

        # Layer changes
        layer_changes = diff.get("layout_changes", {}).get("layers", {})
        if (
            layer_changes.get("added")
            or layer_changes.get("removed")
            or layer_changes.get("modified")
        ):
            pretty_lines.append("Layer Changes:")
            for added in layer_changes.get("added", []):
                pretty_lines.append(f"  + Added layer at index {added}")
            for removed in layer_changes.get("removed", []):
                pretty_lines.append(f"  - Removed layer at index {removed}")
            for modified in layer_changes.get("modified", []):
                pretty_lines.append(f"  ~ Modified layer at index {modified}")
            pretty_lines.append("")

        # Behavior changes
        movements = diff.get("movements", {})
        if movements.get("behavior_changes"):
            pretty_lines.append("Key Binding Changes:")
            for change in movements["behavior_changes"][:10]:  # Limit to first 10
                layer = change["layer"]
                pos = change["position"]
                from_val = change["from"]["value"]
                to_val = change["to"]["value"]
                if change["from"].get("params"):
                    from_param = change["from"]["params"][0]["value"]
                    from_str = f"{from_val} {from_param}"
                else:
                    from_str = from_val
                if change["to"].get("params"):
                    to_param = change["to"]["params"][0]["value"]
                    to_str = f"{to_val} {to_param}"
                else:
                    to_str = to_val
                pretty_lines.append(f"  Layer {layer}[{pos}]: {from_str} → {to_str}")

            if len(movements["behavior_changes"]) > 10:
                remaining = len(movements["behavior_changes"]) - 10
                pretty_lines.append(f"  ... and {remaining} more changes")

        comparison["deepdiff_pretty"] = (
            "\n".join(pretty_lines) if pretty_lines else "No changes found"
        )

    def _generate_dtsi_patches(
        self, layout1: LayoutData, layout2: LayoutData, section: str
    ) -> list[str]:
        """Generate unified diff patches for DTSI sections."""
        patch_sections = []

        if section in ["behaviors", "both"]:
            behaviors_patch = self._create_unified_diff(
                layout1.custom_defined_behaviors,
                layout2.custom_defined_behaviors,
                "custom_defined_behaviors",
            )
            if behaviors_patch:
                patch_sections.extend(behaviors_patch)

        if section in ["devicetree", "both"]:
            devicetree_patch = self._create_unified_diff(
                layout1.custom_devicetree,
                layout2.custom_devicetree,
                "custom_devicetree",
            )
            if devicetree_patch:
                patch_sections.extend(devicetree_patch)

        return patch_sections

    def _create_unified_diff(self, text1: str, text2: str, filename: str) -> list[str]:
        """Create unified diff between two text sections."""
        if text1 == text2:
            return []

        lines1 = text1.splitlines(keepends=True)
        lines2 = text2.splitlines(keepends=True)

        diff_lines = list(
            difflib.unified_diff(
                lines1,
                lines2,
                fromfile=f"a/{filename}",
                tofile=f"b/{filename}",
                lineterm="",
            )
        )

        return diff_lines

    def _load_patch_file(self, patch_file_path: Path) -> dict[str, Any]:
        """Load patch data from file."""
        with patch_file_path.open() as f:
            result: dict[str, Any] = json.load(f)
            return result


def create_layout_comparison_service(
    user_config: UserConfig,
    file_adapter: FileAdapterProtocol,
) -> LayoutComparisonService:
    """Factory function to create a layout comparison service with explicit dependencies."""
    return LayoutComparisonService(user_config, file_adapter)
