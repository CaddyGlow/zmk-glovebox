"""Layout comparison service using the new LayoutDiff format."""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from glovebox.config import UserConfig
from glovebox.layout.diffing.diff import LayoutDiffSystem
from glovebox.layout.diffing.patch import LayoutPatchSystem
from glovebox.layout.models import LayoutData
from glovebox.layout.utils.json_operations import load_layout_file, save_layout_file
from glovebox.layout.utils.validation import validate_output_path
from glovebox.protocols import FileAdapterProtocol


if TYPE_CHECKING:
    from glovebox.layout.diffing.models import LayoutDiff


class LayoutComparisonService:
    """Service for comparing and patching layouts using the new LayoutDiff format."""

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
        output_format: str = "text",
        include_dtsi: bool = False,
        detailed: bool = False,
    ) -> dict[str, Any]:
        """Compare two layouts and return differences.

        Args:
            layout1_path: Path to first layout file
            layout2_path: Path to second layout file
            output_format: Output format ('text', 'json', 'table')
            include_dtsi: Include custom DTSI fields in diff output
            detailed: Show detailed key changes within layers

        Returns:
            Dictionary with comparison results in LayoutDiff format
        """
        layout1_data = load_layout_file(layout1_path, self.file_adapter)
        layout2_data = load_layout_file(layout2_path, self.file_adapter)

        # Create diff using new library
        diff = self.diff_system.create_layout_diff(
            layout1_data, layout2_data, include_dtsi=include_dtsi
        )

        # Convert to dict for CLI output
        result = {
            "source_file": str(layout1_path),
            "target_file": str(layout2_path),
            "diff": diff.model_dump(mode="json", by_alias=True, exclude_unset=True),
            "has_changes": self._has_changes(diff),
            "summary": self._create_summary(diff),
            "detailed": detailed,  # Pass through detailed flag
        }

        # Add format-specific data
        if detailed:
            result["detailed_output"] = self._format_detailed(diff)

        return result

    def apply_patch(
        self,
        source_layout_path: Path,
        patch_file_path: Path,
        output: Path | None = None,
        force: bool = False,
        skip_dtsi: bool = False,
    ) -> dict[str, Any]:
        """Apply a LayoutDiff patch to transform a layout.

        Args:
            source_layout_path: Path to source layout file
            patch_file_path: Path to LayoutDiff JSON file
            output: Output path (defaults to source with -patched suffix)
            force: Whether to overwrite existing files
            skip_dtsi: Whether to skip DTSI changes even if present in patch

        Returns:
            Dictionary with patch operation details
        """
        # Load source layout and patch data
        layout_data = load_layout_file(source_layout_path, self.file_adapter)
        patch_data = self._load_diff_file(patch_file_path)

        # Apply patch using new library
        patched_data = self.patch_system.apply_patch(
            layout_data, patch_data, skip_dtsi=skip_dtsi
        )

        # Determine output path
        if output is None:
            output = (
                source_layout_path.parent / f"{source_layout_path.stem}-patched.json"
            )

        validate_output_path(output, source_layout_path, force)

        # Save patched layout
        save_layout_file(patched_data, output, self.file_adapter)

        return {
            "source": str(source_layout_path),
            "patch": str(patch_file_path),
            "output": str(output),
            "success": True,
        }

    def create_diff_file(
        self,
        layout1_path: Path,
        layout2_path: Path,
        output_path: Path,
        include_dtsi: bool = False,
    ) -> dict[str, Any]:
        """Create a LayoutDiff file for later patching.

        Args:
            layout1_path: Path to base layout file
            layout2_path: Path to modified layout file
            output_path: Path for the diff file
            include_dtsi: Include custom DTSI fields in diff

        Returns:
            Dictionary with diff creation details
        """
        layout1_data = load_layout_file(layout1_path, self.file_adapter)
        layout2_data = load_layout_file(layout2_path, self.file_adapter)

        # Create diff
        diff = self.diff_system.create_layout_diff(
            layout1_data, layout2_data, include_dtsi=include_dtsi
        )

        # Save diff file
        diff_dict = diff.model_dump(mode="json", by_alias=True, exclude_unset=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(diff_dict, f, indent=2, ensure_ascii=False)

        return {
            "base_layout": str(layout1_path),
            "modified_layout": str(layout2_path),
            "diff_file": str(output_path),
            "has_changes": self._has_changes(diff),
            "include_dtsi": include_dtsi,
        }

    def _load_diff_file(self, diff_file_path: Path) -> "LayoutDiff":
        """Load a LayoutDiff from a JSON file."""
        from glovebox.layout.diffing.models import LayoutDiff

        with diff_file_path.open("r", encoding="utf-8") as f:
            diff_data = json.load(f)

        return LayoutDiff.model_validate(diff_data)

    def _has_changes(self, diff: "LayoutDiff") -> bool:
        """Check if the diff contains any changes."""
        # Check structured changes
        if diff.layers and any(
            diff.layers.model_dump().get(key, [])
            for key in ["added", "removed", "modified"]
        ):
            return True

        # Check behavior changes
        for behavior_field in ["hold_taps", "combos", "macros", "input_listeners"]:
            if hasattr(diff, behavior_field):
                behavior_changes = getattr(diff, behavior_field)
                if behavior_changes and any(
                    behavior_changes.model_dump().get(key, [])
                    for key in ["added", "removed", "modified"]
                ):
                    return True

        # Check simple field changes (JSON patches)
        simple_fields = [
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

        for field in simple_fields:
            if getattr(diff, field, None) is not None:
                return True

        # Check DTSI changes
        return bool(diff.custom_defined_behaviors or diff.custom_devicetree)

    def _create_summary(self, diff: "LayoutDiff") -> dict[str, Any]:
        """Create a summary of changes in the diff."""
        summary = {
            "layers": {"added": 0, "removed": 0, "modified": 0},
            "behaviors": {
                "hold_taps": {"added": 0, "removed": 0, "modified": 0},
                "combos": {"added": 0, "removed": 0, "modified": 0},
                "macros": {"added": 0, "removed": 0, "modified": 0},
                "input_listeners": {"added": 0, "removed": 0, "modified": 0},
            },
            "metadata_changes": 0,
            "dtsi_changes": 0,
        }

        # Count layer changes
        if diff.layers:
            layer_dict = diff.layers.model_dump()
            summary["layers"]["added"] = len(layer_dict.get("added", []))
            summary["layers"]["removed"] = len(layer_dict.get("removed", []))
            summary["layers"]["modified"] = len(layer_dict.get("modified", []))

        # Count behavior changes
        for behavior_type in ["hold_taps", "combos", "macros", "input_listeners"]:
            if hasattr(diff, behavior_type):
                behavior_changes = getattr(diff, behavior_type)
                if behavior_changes:
                    behavior_dict = behavior_changes.model_dump()
                    summary["behaviors"][behavior_type]["added"] = len(
                        behavior_dict.get("added", [])
                    )
                    summary["behaviors"][behavior_type]["removed"] = len(
                        behavior_dict.get("removed", [])
                    )
                    summary["behaviors"][behavior_type]["modified"] = len(
                        behavior_dict.get("modified", [])
                    )

        # Count metadata changes
        simple_fields = [
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

        summary["metadata_changes"] = sum(
            1 for field in simple_fields if getattr(diff, field, None) is not None
        )

        # Count DTSI changes
        dtsi_changes = 0
        if diff.custom_defined_behaviors:
            dtsi_changes += 1
        if diff.custom_devicetree:
            dtsi_changes += 1
        summary["dtsi_changes"] = dtsi_changes

        return summary

    def _format_pretty(self, diff: "LayoutDiff") -> str:
        """Format diff for pretty output."""
        lines = []
        summary = self._create_summary(diff)

        # Diff metadata
        lines.append(f"Diff: {diff.base_version} → {diff.modified_version}")
        lines.append(f"Timestamp: {diff.timestamp}")
        lines.append("")

        # Layer changes
        layer_summary = summary["layers"]
        if any(layer_summary.values()):
            lines.append("Layer Changes:")
            if layer_summary["added"]:
                lines.append(f"  + {layer_summary['added']} layers added")
            if layer_summary["removed"]:
                lines.append(f"  - {layer_summary['removed']} layers removed")
            if layer_summary["modified"]:
                lines.append(f"  ~ {layer_summary['modified']} layers modified")
            lines.append("")

        # Behavior changes
        behavior_summary = summary["behaviors"]
        behavior_changes = [
            (behavior_type, counts)
            for behavior_type, counts in behavior_summary.items()
            if any(counts.values())
        ]

        if behavior_changes:
            lines.append("Behavior Changes:")
            for behavior_type, counts in behavior_changes:
                display_name = behavior_type.replace("_", " ").title()
                if counts["added"]:
                    lines.append(f"  + {counts['added']} {display_name} added")
                if counts["removed"]:
                    lines.append(f"  - {counts['removed']} {display_name} removed")
                if counts["modified"]:
                    lines.append(f"  ~ {counts['modified']} {display_name} modified")
            lines.append("")

        # Metadata changes
        if summary["metadata_changes"]:
            lines.append(f"Metadata: {summary['metadata_changes']} field(s) changed")
            lines.append("")

        # DTSI changes
        if summary["dtsi_changes"]:
            lines.append(f"DTSI: {summary['dtsi_changes']} section(s) changed")
            if diff.custom_defined_behaviors:
                lines.append("  ~ Custom behaviors modified")
            if diff.custom_devicetree:
                lines.append("  ~ Custom devicetree modified")

        return "\n".join(lines) if lines else "No changes detected"

    def _format_detailed(self, diff: "LayoutDiff") -> dict[str, Any]:
        """Format diff for detailed output."""
        return {
            "diff_metadata": {
                "base_version": diff.base_version,
                "modified_version": diff.modified_version,
                "base_uuid": diff.base_uuid,
                "modified_uuid": diff.modified_uuid,
                "timestamp": diff.timestamp.isoformat(),
                "diff_type": diff.diff_type,
            },
            "changes": diff.model_dump(mode="json", by_alias=True, exclude_unset=True),
            "summary": self._create_summary(diff),
        }


def create_layout_comparison_service(
    user_config: UserConfig,
    file_adapter: FileAdapterProtocol,
) -> LayoutComparisonService:
    """Factory function to create a layout comparison service with explicit dependencies."""
    return LayoutComparisonService(user_config, file_adapter)
