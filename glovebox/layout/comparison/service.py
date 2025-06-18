"""Layout comparison service for diff and patch operations."""

import difflib
import json
from pathlib import Path
from typing import Any

from glovebox.layout.models import LayoutBinding, LayoutData, LayoutParam
from glovebox.layout.utils.json_operations import load_json_data, load_layout_file
from glovebox.layout.utils.validation import validate_output_path


class LayoutComparisonService:
    """Service for comparing and patching layouts."""

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
            output_format: Output format ('summary', 'detailed', 'dtsi', 'json')
            compare_dtsi: Include custom DTSI code comparison

        Returns:
            Dictionary with comparison results
        """
        layout1_data = load_layout_file(layout1_path)
        layout2_data = load_layout_file(layout2_path)

        # Build comparison result
        comparison = self._build_comparison_result(
            layout1_data, layout2_data, layout1_path, layout2_path
        )

        # Add DTSI comparison if requested
        if compare_dtsi or output_format.lower() in ["detailed", "dtsi"]:
            self._add_dtsi_comparison(comparison, layout1_data, layout2_data)

        # Add layer comparison details
        if output_format.lower() in ["detailed", "json"]:
            self._add_detailed_layer_comparison(comparison, layout1_data, layout2_data)

        return comparison

    def apply_patch(
        self,
        source_layout_path: Path,
        patch_file_path: Path,
        output: Path | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """Apply a JSON diff patch to transform a layout.

        Args:
            source_layout_path: Path to source layout file
            patch_file_path: Path to JSON diff patch file
            output: Output path (defaults to source with -patched suffix)
            force: Whether to overwrite existing files

        Returns:
            Dictionary with patch operation details
        """
        # Load source layout and patch data
        layout_data = load_layout_file(source_layout_path)
        patch_data = self._load_patch_file(patch_file_path)

        # Apply the patch
        patched_data = self._apply_patch_to_layout(layout_data, patch_data)

        # Determine output path
        if output is None:
            output = (
                source_layout_path.parent / f"{source_layout_path.stem}-patched.json"
            )

        validate_output_path(output, source_layout_path, force)

        # Save patched layout
        from glovebox.layout.utils.json_operations import save_layout_file

        save_layout_file(patched_data, output)

        # Calculate changes applied
        total_changes = self._count_patch_changes(patch_data)

        return {
            "source": source_layout_path,
            "patch": patch_file_path,
            "output": output,
            "total_changes": total_changes,
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
        layout1_data = load_layout_file(layout1_path)
        layout2_data = load_layout_file(layout2_path)

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

    def _build_comparison_result(
        self,
        layout1: LayoutData,
        layout2: LayoutData,
        layout1_path: Path,
        layout2_path: Path,
    ) -> dict[str, Any]:
        """Build basic comparison result structure."""
        # Compare basic metadata
        metadata_changes = {}
        if layout1.title != layout2.title:
            metadata_changes["title"] = {"from": layout1.title, "to": layout2.title}
        if layout1.version != layout2.version:
            metadata_changes["version"] = {
                "from": layout1.version,
                "to": layout2.version,
            }
        if layout1.creator != layout2.creator:
            metadata_changes["creator"] = {
                "from": layout1.creator,
                "to": layout2.creator,
            }

        # Compare layers
        layout1_layers = set(layout1.layer_names)
        layout2_layers = set(layout2.layer_names)
        added_layers = list(layout2_layers - layout1_layers)
        removed_layers = list(layout1_layers - layout2_layers)

        # Compare behavior counts
        layout1_behaviors = (
            len(layout1.hold_taps) + len(layout1.combos) + len(layout1.macros)
        )
        layout2_behaviors = (
            len(layout2.hold_taps) + len(layout2.combos) + len(layout2.macros)
        )

        # Compare config parameter counts
        layout1_config = len(layout1.config_parameters)
        layout2_config = len(layout2.config_parameters)

        return {
            "success": True,
            "layout1": str(layout1_path),
            "layout2": str(layout2_path),
            "metadata": metadata_changes,
            "layers": {
                "added": added_layers,
                "removed": removed_layers,
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
                "custom_defined_behaviors": {"changed": False, "differences": []},
                "custom_devicetree": {"changed": False, "differences": []},
            },
        }

    def _add_dtsi_comparison(
        self, comparison: dict[str, Any], layout1: LayoutData, layout2: LayoutData
    ) -> None:
        """Add custom DTSI comparison to results."""
        behaviors1 = layout1.custom_defined_behaviors or ""
        behaviors2 = layout2.custom_defined_behaviors or ""
        devicetree1 = layout1.custom_devicetree or ""
        devicetree2 = layout2.custom_devicetree or ""

        # Compare behaviors
        if self._normalize_dtsi_content(behaviors1) != self._normalize_dtsi_content(
            behaviors2
        ):
            comparison["custom_dtsi"]["custom_defined_behaviors"]["changed"] = True
            # Add unified diff for merge tool compatibility
            unified_diff = list(
                difflib.unified_diff(
                    behaviors1.splitlines(keepends=True) if behaviors1 else [],
                    behaviors2.splitlines(keepends=True) if behaviors2 else [],
                    fromfile="layout1/custom_defined_behaviors",
                    tofile="layout2/custom_defined_behaviors",
                    lineterm="",
                )
            )
            comparison["custom_dtsi"]["custom_defined_behaviors"].update(
                {
                    "from_content": behaviors1,
                    "to_content": behaviors2,
                    "unified_diff": unified_diff,
                    "patch_string": "\\n".join(unified_diff) if unified_diff else "",
                    "patch_ready": True,
                }
            )

        # Compare devicetree
        if self._normalize_dtsi_content(devicetree1) != self._normalize_dtsi_content(
            devicetree2
        ):
            comparison["custom_dtsi"]["custom_devicetree"]["changed"] = True
            # Add unified diff for merge tool compatibility
            unified_diff = list(
                difflib.unified_diff(
                    devicetree1.splitlines(keepends=True) if devicetree1 else [],
                    devicetree2.splitlines(keepends=True) if devicetree2 else [],
                    fromfile="layout1/custom_devicetree",
                    tofile="layout2/custom_devicetree",
                    lineterm="",
                )
            )
            comparison["custom_dtsi"]["custom_devicetree"].update(
                {
                    "from_content": devicetree1,
                    "to_content": devicetree2,
                    "unified_diff": unified_diff,
                    "patch_string": "\\n".join(unified_diff) if unified_diff else "",
                    "patch_ready": True,
                }
            )

    def _add_detailed_layer_comparison(
        self, comparison: dict[str, Any], layout1: LayoutData, layout2: LayoutData
    ) -> None:
        """Add detailed layer-by-layer comparison."""
        layout1_layers = set(layout1.layer_names)
        layout2_layers = set(layout2.layer_names)
        common_layers = layout1_layers & layout2_layers

        for layer_name in sorted(common_layers):
            try:
                layer1_idx = layout1.layer_names.index(layer_name)
                layer2_idx = layout2.layer_names.index(layer_name)

                if layer1_idx < len(layout1.layers) and layer2_idx < len(
                    layout2.layers
                ):
                    layer1_bindings = layout1.layers[layer1_idx]
                    layer2_bindings = layout2.layers[layer2_idx]

                    if layer1_bindings != layer2_bindings:
                        key_changes = self._compare_layer_bindings(
                            layer1_bindings, layer2_bindings
                        )

                        if key_changes:
                            comparison["layers"]["changed"][layer_name] = {
                                "total_key_differences": len(key_changes),
                                "key_changes": key_changes,
                            }
            except (ValueError, IndexError):
                continue

    def _compare_layer_bindings(
        self, layer1: list[LayoutBinding], layer2: list[LayoutBinding]
    ) -> list[dict[str, Any]]:
        """Compare bindings between two layers."""
        key_changes = []
        max_keys = max(len(layer1), len(layer2))

        for i in range(max_keys):
            key1 = layer1[i] if i < len(layer1) else None
            key2 = layer2[i] if i < len(layer2) else None

            if key1 != key2:
                key_changes.append(
                    {
                        "key_index": i,
                        "from": self._key_to_dtsi(key1),
                        "to": self._key_to_dtsi(key2),
                    }
                )

        return key_changes

    def _key_to_dtsi(self, key_obj: LayoutBinding | None) -> str | None:
        """Convert key binding to DTSI format string."""
        if key_obj is None:
            return None

        if hasattr(key_obj, "params") and key_obj.params:
            params_str = " ".join(
                str(p.value) if hasattr(p, "value") else str(p) for p in key_obj.params
            )
            return f"{key_obj.value} {params_str}"
        else:
            return str(key_obj.value)

    def _normalize_dtsi_content(self, content: str) -> list[str]:
        """Normalize DTSI content for comparison."""
        if not content:
            return []

        lines = []
        for line in content.splitlines():
            normalized = line.strip()
            if normalized:
                lines.append(normalized)
        return lines

    def _load_patch_file(self, patch_file_path: Path) -> dict[str, Any]:
        """Load and validate patch file."""
        if not patch_file_path.exists():
            raise FileNotFoundError(f"Patch file not found: {patch_file_path}")

        patch_data = load_json_data(patch_file_path)

        if not isinstance(patch_data, dict) or "layers" not in patch_data:
            raise ValueError(
                "Invalid patch file format. Must be JSON diff output from diff command"
            )

        return patch_data

    def _apply_patch_to_layout(
        self, layout_data: LayoutData, patch_data: dict[str, Any]
    ) -> LayoutData:
        """Apply patch data to layout."""
        patched_data = layout_data.model_copy(deep=True)

        # Apply metadata changes
        if "metadata" in patch_data and patch_data["metadata"]:
            for field, change in patch_data["metadata"].items():
                if isinstance(change, dict) and "to" in change:
                    setattr(patched_data, field, change["to"])

        # Apply layer changes
        self._apply_layer_changes(patched_data, patch_data.get("layers", {}))

        return patched_data

    def _apply_layer_changes(
        self, patched_data: LayoutData, layers_patch: dict[str, Any]
    ) -> None:
        """Apply layer structure changes."""
        # Remove layers
        removed_layers = layers_patch.get("removed", [])
        for layer_name in removed_layers:
            if layer_name in patched_data.layer_names:
                idx = patched_data.layer_names.index(layer_name)
                patched_data.layer_names.pop(idx)
                if idx < len(patched_data.layers):
                    patched_data.layers.pop(idx)

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
                self._apply_key_change(patched_data, layer_idx, key_change)

    def _apply_key_change(
        self, patched_data: LayoutData, layer_idx: int, key_change: dict[str, Any]
    ) -> None:
        """Apply a single key change."""
        key_idx = key_change.get("key_index")
        new_value = key_change.get("to")

        if (
            key_idx is not None
            and new_value is not None
            and key_idx < len(patched_data.layers[layer_idx])
        ):
            # Convert DTSI string back to LayoutBinding object
            if new_value == "None" or new_value is None:
                patched_data.layers[layer_idx][key_idx] = LayoutBinding(
                    value="&none", params=[]
                )
            else:
                # Parse DTSI string
                parts = new_value.split()
                value = parts[0] if parts else "&none"
                params = [LayoutParam(value=param, params=[]) for param in parts[1:]]

                patched_data.layers[layer_idx][key_idx] = LayoutBinding(
                    value=value, params=params
                )

    def _count_patch_changes(self, patch_data: dict[str, Any]) -> int:
        """Count total changes in patch data."""
        total_changes = 0

        if "metadata" in patch_data:
            total_changes += len(patch_data["metadata"])

        if "layers" in patch_data:
            layers_patch = patch_data["layers"]
            total_changes += len(layers_patch.get("removed", []))
            for layer_changes in layers_patch.get("changed", {}).values():
                total_changes += len(layer_changes.get("key_changes", []))

        return total_changes

    def _generate_dtsi_patches(
        self, layout1: LayoutData, layout2: LayoutData, section: str
    ) -> list[str]:
        """Generate unified diff patches for DTSI sections."""
        patch_sections = []

        if section in ["behaviors", "both"]:
            behaviors1 = layout1.custom_defined_behaviors or ""
            behaviors2 = layout2.custom_defined_behaviors or ""

            if behaviors1 != behaviors2:
                behaviors_patch = self._create_section_patch(
                    behaviors1, behaviors2, "custom_defined_behaviors"
                )
                if behaviors_patch:
                    patch_sections.extend(behaviors_patch)
                    patch_sections.append("")

        if section in ["devicetree", "both"]:
            devicetree1 = layout1.custom_devicetree or ""
            devicetree2 = layout2.custom_devicetree or ""

            if devicetree1 != devicetree2:
                devicetree_patch = self._create_section_patch(
                    devicetree1, devicetree2, "custom_devicetree"
                )
                if devicetree_patch:
                    patch_sections.extend(devicetree_patch)

        return patch_sections

    def _create_section_patch(
        self, content1: str, content2: str, section_name: str
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


def create_layout_comparison_service() -> LayoutComparisonService:
    """Create a LayoutComparisonService instance.

    Returns:
        LayoutComparisonService instance
    """
    return LayoutComparisonService()
