"""Layout comparison service for diff and patch operations using DeepDiff."""

import difflib
import json
from pathlib import Path
from typing import Any

from deepdiff import DeepDiff
from deepdiff.delta import Delta

from glovebox.config import UserConfig, create_user_config
from glovebox.layout.models import LayoutBinding, LayoutData, LayoutParam
from glovebox.layout.utils.json_operations import load_json_data, load_layout_file
from glovebox.layout.utils.validation import validate_output_path


class LayoutComparisonService:
    """Service for comparing and patching layouts."""

    def __init__(self, user_config: UserConfig | None = None) -> None:
        """Initialize the comparison service with user configuration."""
        self.user_config = user_config or create_user_config()

    def _create_behavior_compare_func(self):
        """Create a simple comparison function for behavior lists that maps items by name."""

        def behavior_compare_func(item1, item2, level=None):
            """Compare behavior items by their 'name' field for better DeepDiff performance."""
            try:
                # Handle behavior objects that have a 'name' field
                if hasattr(item1, "name") and hasattr(item2, "name"):
                    return item1.name == item2.name
                # Handle dictionary representations
                elif (
                    isinstance(item1, dict)
                    and isinstance(item2, dict)
                    and "name" in item1
                    and "name" in item2
                ):
                    return item1["name"] == item2["name"]
                # For other types, fall back to default comparison
                else:
                    from deepdiff.helper import CannotCompare

                    raise CannotCompare() from None
            except Exception:
                from deepdiff.helper import CannotCompare

                raise CannotCompare() from None

        return behavior_compare_func

    def compare_layouts(
        self,
        layout1_path: Path,
        layout2_path: Path,
        output_format: str = "summary",
        compare_dtsi: bool = False,
    ) -> dict[str, Any]:
        """Compare two layouts and return differences using DeepDiff.

        Args:
            layout1_path: Path to first layout file
            layout2_path: Path to second layout file
            output_format: Output format ('summary', 'detailed', 'dtsi', 'json')
            compare_dtsi: Include custom DTSI code comparison

        Returns:
            Dictionary with comparison results including DeepDiff data and JSON patch
        """
        layout1_data = load_layout_file(layout1_path)
        layout2_data = load_layout_file(layout2_path)

        # Use Pydantic objects directly with behavior comparison function
        deep_diff = DeepDiff(
            layout1_data,
            layout2_data,
            ignore_order=True,
            verbose_level=1,
            iterable_compare_func=self._create_behavior_compare_func(),
            cache_size=1000,
        )

        # Build comparison result using DeepDiff
        comparison = self._build_deepdiff_comparison_result(
            layout1_data, layout2_data, layout1_path, layout2_path, deep_diff
        )

        # Add DTSI comparison if explicitly requested or dtsi format
        if compare_dtsi or output_format.lower() == "dtsi":
            self._add_dtsi_comparison(comparison, layout1_data, layout2_data)

        # Add basic layer comparison for all formats (fast)
        if output_format.lower() in ["summary"]:
            # For summary, only do basic counts without detailed comparison
            pass  # Basic layer info is already in _build_deepdiff_comparison_result
        else:
            # Add layer comparison with DeepDiff for non-summary formats
            self._add_layer_comparison_with_deepdiff(
                comparison, layout1_data, layout2_data, deep_diff
            )

        # Add detailed behavior comparison for JSON and detailed formats only
        if output_format.lower() in ["detailed", "json"]:
            self._add_detailed_behavior_comparison_with_deepdiff(
                comparison, layout1_data, layout2_data, deep_diff
            )

        # Add detailed layer comparison for specific formats only
        if output_format.lower() in ["detailed", "json"]:
            self._add_detailed_layer_comparison_with_deepdiff(
                comparison, layout1_data, layout2_data, deep_diff
            )

        # Generate JSON patch using DeepDiff Delta
        if output_format.lower() == "json":
            comparison["json_patch"] = self._create_json_patch_from_deepdiff(deep_diff)
            # Convert to JSON for delta creation (required for serialization)
            layout1_json = layout1_data.model_dump(mode="json")
            layout2_json = layout2_data.model_dump(mode="json")
            comparison["deepdiff_delta"] = self._create_deepdiff_delta(
                layout1_json, layout2_json
            )

        # Generate pretty output using DeepDiff
        if output_format.lower() == "pretty":
            pretty_output = deep_diff.pretty() if deep_diff else ""
            if pretty_output.strip():  # Only add if there's actual content
                comparison["deepdiff_pretty"] = pretty_output

        return comparison

    def apply_patch(
        self,
        source_layout_path: Path,
        patch_file_path: Path,
        output: Path | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """Apply a DeepDiff JSON patch to transform a layout.

        Args:
            source_layout_path: Path to source layout file
            patch_file_path: Path to JSON diff patch file (can be DeepDiff or traditional format)
            output: Output path (defaults to source with -patched suffix)
            force: Whether to overwrite existing files

        Returns:
            Dictionary with patch operation details
        """
        # Load source layout and patch data
        layout_data = load_layout_file(source_layout_path)
        patch_data = self._load_patch_file(patch_file_path)

        # Apply the patch using JSON patch operations if available, otherwise fallback
        if (
            "json_patch" in patch_data
            and patch_data["json_patch"]["format"] == "deepdiff_json_patch"
        ):
            patched_data = self._apply_json_patch_operations(layout_data, patch_data)
        elif "deepdiff_delta" in patch_data:
            patched_data = self._apply_deepdiff_delta_patch(layout_data, patch_data)
        else:
            patched_data = self._apply_legacy_patch_to_layout(layout_data, patch_data)

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

    def _build_deepdiff_comparison_result(
        self,
        layout1: LayoutData,
        layout2: LayoutData,
        layout1_path: Path,
        layout2_path: Path,
        deep_diff: DeepDiff,
    ) -> dict[str, Any]:
        """Build comparison result structure using DeepDiff."""
        # Extract metadata changes from DeepDiff
        metadata_changes = self._extract_metadata_changes_from_deepdiff(deep_diff)

        # Extract layer changes from DeepDiff
        layer_info = self._extract_layer_changes_from_deepdiff(
            deep_diff, layout1, layout2
        )

        # Extract behavior changes from DeepDiff
        behavior_info = self._extract_behavior_changes_from_deepdiff(
            deep_diff, layout1, layout2
        )

        # Extract config changes from DeepDiff
        config_info = self._extract_config_changes_from_deepdiff(
            deep_diff, layout1, layout2
        )

        return {
            "success": True,
            "layout1": str(layout1_path),
            "layout2": str(layout2_path),
            "deepdiff_summary": {
                "has_changes": bool(deep_diff),
                "change_types": list(deep_diff.keys()) if deep_diff else [],
                "total_changes": len(deep_diff.get("values_changed", {}))
                + len(deep_diff.get("dictionary_item_added", {}))
                + len(deep_diff.get("dictionary_item_removed", {}))
                + len(deep_diff.get("iterable_item_added", {}))
                + len(deep_diff.get("iterable_item_removed", {})),
            },
            "metadata": metadata_changes,
            "layers": layer_info,
            "behaviors": behavior_info,
            "config": config_info,
            "custom_dtsi": {
                "custom_defined_behaviors": {"changed": False, "differences": []},
                "custom_devicetree": {"changed": False, "differences": []},
            },
        }

    def _add_layer_comparison(
        self, comparison: dict[str, Any], layout1: LayoutData, layout2: LayoutData
    ) -> None:
        """Add basic layer comparison counts for summary output."""
        layout1_layers = set(layout1.layer_names)
        layout2_layers = set(layout2.layer_names)
        common_layers = layout1_layers & layout2_layers

        changed_layers = {}
        total_key_differences = 0

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
                        # Count differences without storing details
                        key_changes = self._count_layer_differences(
                            layer1_bindings, layer2_bindings
                        )
                        if key_changes > 0:
                            changed_layers[layer_name] = {
                                "total_key_differences": key_changes
                            }
                            total_key_differences += key_changes
            except (ValueError, IndexError):
                continue

        # Update the comparison with basic layer change counts
        comparison["layers"]["changed"] = changed_layers

    def _count_layer_differences(
        self, layer1: list[LayoutBinding], layer2: list[LayoutBinding]
    ) -> int:
        """Count the number of key differences between two layers."""
        max_keys = max(len(layer1), len(layer2))
        differences = 0

        for i in range(max_keys):
            key1 = layer1[i] if i < len(layer1) else None
            key2 = layer2[i] if i < len(layer2) else None

            if key1 != key2:
                differences += 1

        return differences

    def _add_detailed_behavior_comparison(
        self, comparison: dict[str, Any], layout1: LayoutData, layout2: LayoutData
    ) -> None:
        """Add detailed behavior-by-behavior comparison."""
        behavior_changes = {
            "hold_taps": {"added": [], "removed": [], "changed": []},
            "combos": {"added": [], "removed": [], "changed": []},
            "macros": {"added": [], "removed": [], "changed": []},
        }

        # Compare hold_taps
        behavior_changes["hold_taps"] = self._compare_behavior_list(
            layout1.hold_taps, layout2.hold_taps, "hold_tap"
        )

        # Compare combos
        behavior_changes["combos"] = self._compare_behavior_list(
            layout1.combos, layout2.combos, "combo"
        )

        # Compare macros
        behavior_changes["macros"] = self._compare_behavior_list(
            layout1.macros, layout2.macros, "macro"
        )

        # Update comparison with detailed behavior changes
        comparison["behaviors"]["detailed_changes"] = behavior_changes

    def _compare_behavior_list(
        self, behaviors1: list, behaviors2: list, behavior_type: str
    ) -> dict[str, list]:
        """Compare two lists of behaviors and return detailed changes."""
        # Create lookup by name
        behaviors1_dict = {b.name: b for b in behaviors1}
        behaviors2_dict = {b.name: b for b in behaviors2}

        names1 = set(behaviors1_dict.keys())
        names2 = set(behaviors2_dict.keys())

        added = []
        removed = []
        changed = []

        # Find added behaviors
        for name in names2 - names1:
            behavior = behaviors2_dict[name]
            added.append(
                {
                    "name": name,
                    "type": behavior_type,
                    "behavior_data": behavior.model_dump(mode="json"),
                }
            )

        # Find removed behaviors
        for name in names1 - names2:
            behavior = behaviors1_dict[name]
            removed.append(
                {
                    "name": name,
                    "type": behavior_type,
                    "behavior_data": behavior.model_dump(mode="json"),
                }
            )

        # Find changed behaviors using DeepDiff
        for name in names1 & names2:
            behavior1 = behaviors1_dict[name]
            behavior2 = behaviors2_dict[name]

            behavior1_data = behavior1.model_dump(mode="json")
            behavior2_data = behavior2.model_dump(mode="json")

            # Use DeepDiff for accurate comparison
            from deepdiff import DeepDiff

            diff = DeepDiff(
                behavior1_data,
                behavior2_data,
                ignore_order=True,
                verbose_level=1,  # Reduced verbosity for performance
                cache_size=200,  # Smaller cache for individual behavior comparisons
            )

            if diff:
                # Convert DeepDiff output to our format
                field_changes = self._convert_deepdiff_to_field_changes(diff)

                if field_changes:
                    changed.append(
                        {
                            "name": name,
                            "type": behavior_type,
                            "field_changes": field_changes,
                            "from_behavior": behavior1_data,
                            "to_behavior": behavior2_data,
                            "deepdiff_details": diff,  # Include raw DeepDiff for debugging
                        }
                    )

        return {"added": added, "removed": removed, "changed": changed}

    def _convert_deepdiff_to_field_changes(self, diff: dict) -> dict[str, dict]:
        """Convert DeepDiff output to our field_changes format."""
        field_changes = {}

        # Handle value changes
        if "values_changed" in diff:
            for path, change in diff["values_changed"].items():
                # Extract field name from root['field_name'] format
                # For nested paths, show a more descriptive path
                path_str = str(path)
                if path_str.startswith("root["):
                    # Convert root['field']['subfield'][0]['value'] to field.subfield[0].value
                    field_name = (
                        path_str.replace("root['", "")
                        .replace("']", "")
                        .replace("']['", ".")
                        .replace("'][", ".")
                        .replace("'", "")
                    )
                else:
                    field_name = path_str

                field_changes[field_name] = {
                    "from": change["old_value"],
                    "to": change["new_value"],
                }

        # Handle items added
        if "dictionary_item_added" in diff:
            for path in diff["dictionary_item_added"]:
                field_name = (
                    path.replace("root['", "").replace("']", "").split("'][")[0]
                )
                if field_name not in field_changes:
                    field_changes[field_name] = {"from": None, "to": "added"}

        # Handle items removed
        if "dictionary_item_removed" in diff:
            for path in diff["dictionary_item_removed"]:
                field_name = (
                    path.replace("root['", "").replace("']", "").split("'][")[0]
                )
                if field_name not in field_changes:
                    field_changes[field_name] = {"from": "removed", "to": None}

        # Handle list changes (for arrays like bindings)
        if "iterable_item_added" in diff or "iterable_item_removed" in diff:
            for change_type in ["iterable_item_added", "iterable_item_removed"]:
                if change_type in diff:
                    for path, _value in diff[change_type].items():
                        field_name = (
                            path.replace("root['", "").replace("']", "").split("'][")[0]
                        )
                        if field_name not in field_changes:
                            field_changes[field_name] = {
                                "from": "list_modified",
                                "to": "list_modified",
                            }

        return field_changes

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

        if not isinstance(patch_data, dict):
            raise ValueError(
                "Invalid patch file format. Must be JSON diff output from diff command"
            )

        # Validate that patch contains at least one supported section
        valid_sections = ["layers", "behaviors", "custom_dtsi", "metadata"]
        if not any(section in patch_data for section in valid_sections):
            raise ValueError(
                "Patch file must contain at least one of: layers, behaviors, custom_dtsi, metadata"
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

        # Apply behavior changes
        self._apply_behavior_changes(patched_data, patch_data.get("behaviors", {}))

        # Apply custom DTSI changes
        self._apply_custom_dtsi_changes(patched_data, patch_data.get("custom_dtsi", {}))

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

    def _apply_behavior_changes(
        self, patched_data: LayoutData, behaviors_patch: dict[str, Any]
    ) -> None:
        """Apply behavior changes from patch data."""
        if not behaviors_patch:
            return

        # Apply hold_tap changes
        if "hold_taps" in behaviors_patch:
            self._apply_behavior_type_changes(
                patched_data.hold_taps, behaviors_patch["hold_taps"], "HoldTapBehavior"
            )

        # Apply combo changes
        if "combos" in behaviors_patch:
            self._apply_behavior_type_changes(
                patched_data.combos, behaviors_patch["combos"], "ComboBehavior"
            )

        # Apply macro changes
        if "macros" in behaviors_patch:
            self._apply_behavior_type_changes(
                patched_data.macros, behaviors_patch["macros"], "MacroBehavior"
            )

    def _apply_behavior_type_changes(
        self, behavior_list: list, changes: dict[str, Any], behavior_class_name: str
    ) -> None:
        """Apply changes for a specific behavior type."""
        from glovebox.layout.models import (
            ComboBehavior,
            HoldTapBehavior,
            MacroBehavior,
        )

        # Map class names to actual classes
        behavior_classes = {
            "HoldTapBehavior": HoldTapBehavior,
            "ComboBehavior": ComboBehavior,
            "MacroBehavior": MacroBehavior,
        }
        behavior_class = behavior_classes[behavior_class_name]

        # Remove behaviors
        removed_names = {item["name"] for item in changes.get("removed", [])}
        behavior_list[:] = [b for b in behavior_list if b.name not in removed_names]

        # Add new behaviors
        for added_item in changes.get("added", []):
            behavior_data = added_item["behavior_data"]
            new_behavior = behavior_class.model_validate(behavior_data)
            behavior_list.append(new_behavior)

        # Modify existing behaviors
        for changed_item in changes.get("changed", []):
            behavior_name = changed_item["name"]
            to_behavior_data = changed_item["to_behavior"]

            # Find and replace the behavior
            for i, behavior in enumerate(behavior_list):
                if behavior.name == behavior_name:
                    modified_behavior = behavior_class.model_validate(to_behavior_data)
                    behavior_list[i] = modified_behavior
                    break

    def _apply_custom_dtsi_changes(
        self, patched_data: LayoutData, dtsi_patch: dict[str, Any]
    ) -> None:
        """Apply custom DTSI changes from patch data."""
        if not dtsi_patch:
            return

        # Apply custom_defined_behaviors changes
        behaviors_changes = dtsi_patch.get("custom_defined_behaviors", {})
        if behaviors_changes.get("changed") and "to_content" in behaviors_changes:
            patched_data.custom_defined_behaviors = behaviors_changes["to_content"]

        # Apply custom_devicetree changes
        devicetree_changes = dtsi_patch.get("custom_devicetree", {})
        if devicetree_changes.get("changed") and "to_content" in devicetree_changes:
            patched_data.custom_devicetree = devicetree_changes["to_content"]

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

        if "behaviors" in patch_data:
            behaviors_patch = patch_data["behaviors"]
            for behavior_type in ["hold_taps", "combos", "macros"]:
                if behavior_type in behaviors_patch:
                    changes = behaviors_patch[behavior_type]
                    total_changes += len(changes.get("added", []))
                    total_changes += len(changes.get("removed", []))
                    total_changes += len(changes.get("changed", []))

        if "custom_dtsi" in patch_data:
            dtsi_patch = patch_data["custom_dtsi"]
            if dtsi_patch.get("custom_defined_behaviors", {}).get("changed"):
                total_changes += 1
            if dtsi_patch.get("custom_devicetree", {}).get("changed"):
                total_changes += 1

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

    # New DeepDiff-based methods
    def _extract_metadata_changes_from_deepdiff(
        self, deep_diff: DeepDiff
    ) -> dict[str, Any]:
        """Extract metadata changes from DeepDiff result."""
        metadata_changes = {}

        # Check for metadata field changes (all root-level scalar fields)
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
            "version",
            "base_version",
            "base_layout",
            "custom_defined_behaviors",
            "custom_devicetree",
        ]

        # Handle direct value changes
        if "values_changed" in deep_diff:
            for path, change in deep_diff["values_changed"].items():
                # Extract field name from path like "root['title']"
                field_name = self._extract_field_name_from_path(str(path))
                if field_name in metadata_fields:
                    metadata_changes[field_name] = {
                        "from": change["old_value"],
                        "to": change["new_value"],
                    }

        # Handle items added to lists/dicts
        if "iterable_item_added" in deep_diff:
            for path, _value in deep_diff["iterable_item_added"].items():
                field_name = self._extract_field_name_from_path(str(path))
                if (
                    field_name in ["tags", "layer_names"]
                    and field_name not in metadata_changes
                ):
                    metadata_changes[field_name] = {
                        "from": "list_modified",
                        "to": "list_modified",
                    }

        # Handle items removed from lists/dicts
        if "iterable_item_removed" in deep_diff:
            for path, _value in deep_diff["iterable_item_removed"].items():
                field_name = self._extract_field_name_from_path(str(path))
                if (
                    field_name in ["tags", "layer_names"]
                    and field_name not in metadata_changes
                ):
                    metadata_changes[field_name] = {
                        "from": "list_modified",
                        "to": "list_modified",
                    }

        # Handle dictionary items added/removed
        for change_type in ["dictionary_item_added", "dictionary_item_removed"]:
            if change_type in deep_diff:
                for path in deep_diff[change_type]:
                    field_name = self._extract_field_name_from_path(str(path))
                    if field_name in metadata_fields:
                        change_desc = "added" if "added" in change_type else "removed"
                        if field_name not in metadata_changes:
                            metadata_changes[field_name] = {
                                "from": f"field_{change_desc}",
                                "to": f"field_{change_desc}",
                            }

        return metadata_changes

    def _extract_layer_changes_from_deepdiff(
        self, deep_diff: DeepDiff, layout1: LayoutData, layout2: LayoutData
    ) -> dict[str, Any]:
        """Extract layer changes from DeepDiff result."""
        layout1_layers = set(layout1.layer_names)
        layout2_layers = set(layout2.layer_names)

        # Fast layer comparison without individual DeepDiff calls
        changed_layers = {}
        common_layers = layout1_layers & layout2_layers

        for layer_name in common_layers:
            try:
                layer1_idx = layout1.layer_names.index(layer_name)
                layer2_idx = layout2.layer_names.index(layer_name)

                if layer1_idx < len(layout1.layers) and layer2_idx < len(
                    layout2.layers
                ):
                    layer1_bindings = layout1.layers[layer1_idx]
                    layer2_bindings = layout2.layers[layer2_idx]

                    # Fast comparison - just check if lists are different
                    if layer1_bindings != layer2_bindings:
                        # Count differences without DeepDiff for speed
                        max_keys = max(len(layer1_bindings), len(layer2_bindings))
                        differences = 0
                        for i in range(max_keys):
                            key1 = (
                                layer1_bindings[i] if i < len(layer1_bindings) else None
                            )
                            key2 = (
                                layer2_bindings[i] if i < len(layer2_bindings) else None
                            )
                            if key1 != key2:
                                differences += 1

                        if differences > 0:
                            changed_layers[layer_name] = {
                                "total_key_differences": differences
                            }
            except (ValueError, IndexError):
                continue

        return {
            "added": list(layout2_layers - layout1_layers),
            "removed": list(layout1_layers - layout2_layers),
            "changed": changed_layers,
            "layout1_count": len(layout1.layer_names),
            "layout2_count": len(layout2.layer_names),
        }

    def _extract_behavior_changes_from_deepdiff(
        self, deep_diff: DeepDiff, layout1: LayoutData, layout2: LayoutData
    ) -> dict[str, Any]:
        """Extract behavior changes from DeepDiff result."""
        layout1_behaviors = (
            len(layout1.hold_taps) + len(layout1.combos) + len(layout1.macros)
        )
        layout2_behaviors = (
            len(layout2.hold_taps) + len(layout2.combos) + len(layout2.macros)
        )

        # Check if behavior content has changed by looking for changes in behavior sections
        behavior_content_changed = False

        if "values_changed" in deep_diff:
            for path in deep_diff["values_changed"]:
                # Check if any changes are in behavior-related paths
                if any(
                    behavior_section in str(path)
                    for behavior_section in ["combos", "macros", "hold_taps"]
                ):
                    behavior_content_changed = True
                    break

        # Also check for items added/removed in behavior arrays
        if not behavior_content_changed:
            for change_type in [
                "iterable_item_added",
                "iterable_item_removed",
                "iterable_items_removed_at_indexes",
            ]:
                if change_type in deep_diff:
                    for path in deep_diff[change_type]:
                        if any(
                            behavior_section in str(path)
                            for behavior_section in ["combos", "macros", "hold_taps"]
                        ):
                            behavior_content_changed = True
                            break
                    if behavior_content_changed:
                        break

        return {
            "layout1_count": layout1_behaviors,
            "layout2_count": layout2_behaviors,
            "changed": layout1_behaviors != layout2_behaviors
            or behavior_content_changed,
        }

    def _extract_config_changes_from_deepdiff(
        self, deep_diff: DeepDiff, layout1: LayoutData, layout2: LayoutData
    ) -> dict[str, Any]:
        """Extract config parameter changes from DeepDiff result."""
        layout1_config = len(layout1.config_parameters)
        layout2_config = len(layout2.config_parameters)

        return {
            "layout1_count": layout1_config,
            "layout2_count": layout2_config,
            "changed": layout1_config != layout2_config,
        }

    def _extract_field_name_from_path(self, path: str) -> str:
        """Extract field name from DeepDiff path string."""
        # Handle both Pydantic object paths like "root.title" and JSON dict paths like "root['title']"
        import re

        # Try Pydantic object path format first: "root.field_name"
        pydantic_match = re.search(r"root\.([^.\[]+)", path)
        if pydantic_match:
            return pydantic_match.group(1)

        # Fall back to JSON dict path format: "root['field_name']"
        dict_match = re.search(r"root\['([^']+)'\]", path)
        return dict_match.group(1) if dict_match else ""

    def _add_layer_comparison_with_deepdiff(
        self,
        comparison: dict[str, Any],
        layout1: LayoutData,
        layout2: LayoutData,
        deep_diff: DeepDiff,
    ) -> None:
        """Add layer comparison using DeepDiff data."""
        # Extract layer-specific changes from DeepDiff
        layer_changes = {}
        total_key_differences = 0

        if (
            "values_changed" in deep_diff
            or "iterable_item_added" in deep_diff
            or "iterable_item_removed" in deep_diff
        ):
            # Analyze layer changes
            for layer_name in set(layout1.layer_names) & set(layout2.layer_names):
                try:
                    layer1_idx = layout1.layer_names.index(layer_name)
                    layer2_idx = layout2.layer_names.index(layer_name)

                    if layer1_idx < len(layout1.layers) and layer2_idx < len(
                        layout2.layers
                    ):
                        layer1_bindings = layout1.layers[layer1_idx]
                        layer2_bindings = layout2.layers[layer2_idx]

                        # Use DeepDiff to compare the layer bindings (minimal for speed)
                        layer_diff = DeepDiff(
                            [b.model_dump(mode="json") for b in layer1_bindings],
                            [b.model_dump(mode="json") for b in layer2_bindings],
                            ignore_order=False,  # Position matters for key bindings
                            verbose_level=1,  # Reduced verbosity for performance
                            cache_size=100,  # Very small cache for layer comparisons
                        )

                        if layer_diff:
                            key_changes = (
                                len(layer_diff.get("values_changed", {}))
                                + len(layer_diff.get("iterable_item_added", {}))
                                + len(layer_diff.get("iterable_item_removed", {}))
                            )

                            if key_changes > 0:
                                layer_changes[layer_name] = {
                                    "total_key_differences": key_changes
                                }
                                total_key_differences += key_changes

                except (ValueError, IndexError):
                    continue

        comparison["layers"]["changed"] = layer_changes

    def _add_detailed_behavior_comparison_with_deepdiff(
        self,
        comparison: dict[str, Any],
        layout1: LayoutData,
        layout2: LayoutData,
        deep_diff: DeepDiff,
    ) -> None:
        """Add detailed behavior comparison using DeepDiff."""
        behavior_changes = {
            "hold_taps": self._compare_behavior_list_with_deepdiff(
                layout1.hold_taps, layout2.hold_taps, "hold_tap"
            ),
            "combos": self._compare_behavior_list_with_deepdiff(
                layout1.combos, layout2.combos, "combo"
            ),
            "macros": self._compare_behavior_list_with_deepdiff(
                layout1.macros, layout2.macros, "macro"
            ),
        }

        comparison["behaviors"]["detailed_changes"] = behavior_changes

        # Update changed flag based on detailed comparison
        has_behavior_changes = any(
            changes.get("added") or changes.get("removed") or changes.get("changed")
            for changes in behavior_changes.values()
        )
        comparison["behaviors"]["changed"] = has_behavior_changes

    def _add_detailed_layer_comparison_with_deepdiff(
        self,
        comparison: dict[str, Any],
        layout1: LayoutData,
        layout2: LayoutData,
        deep_diff: DeepDiff,
    ) -> None:
        """Add detailed layer comparison using DeepDiff."""
        for layer_name in set(layout1.layer_names) & set(layout2.layer_names):
            try:
                layer1_idx = layout1.layer_names.index(layer_name)
                layer2_idx = layout2.layer_names.index(layer_name)

                if layer1_idx < len(layout1.layers) and layer2_idx < len(
                    layout2.layers
                ):
                    layer1_bindings = layout1.layers[layer1_idx]
                    layer2_bindings = layout2.layers[layer2_idx]

                    layer_diff = DeepDiff(
                        [b.model_dump(mode="json") for b in layer1_bindings],
                        [b.model_dump(mode="json") for b in layer2_bindings],
                        ignore_order=False,  # Keep order for layer bindings (position matters)
                        verbose_level=1,  # Reduced verbosity for performance
                        cache_size=100,  # Very small cache for layer comparisons
                    )

                    if layer_diff:
                        key_changes = self._convert_layer_deepdiff_to_changes(
                            layer_diff, layer1_bindings, layer2_bindings
                        )

                        if key_changes:
                            comparison["layers"]["changed"][layer_name] = {
                                "total_key_differences": len(key_changes),
                                "key_changes": key_changes,
                            }
            except (ValueError, IndexError):
                continue

    def _compare_behavior_list_with_deepdiff(
        self, behaviors1: list, behaviors2: list, behavior_type: str
    ) -> dict[str, list]:
        """Compare two lists of behaviors using optimized DeepDiff with item mapping."""
        # Convert behaviors to JSON for DeepDiff
        behaviors1_json = [b.model_dump(mode="json") for b in behaviors1]
        behaviors2_json = [b.model_dump(mode="json") for b in behaviors2]

        # Use DeepDiff with behavior comparison function
        diff = DeepDiff(
            behaviors1_json,
            behaviors2_json,
            ignore_order=True,
            verbose_level=1,
            iterable_compare_func=self._create_behavior_compare_func(),
            cache_size=500,
        )

        # Initialize result structure
        added = []
        removed = []
        changed = []

        # Process iterable item additions (new behaviors)
        if "iterable_item_added" in diff:
            for _path, item_data in diff["iterable_item_added"].items():
                added.append(
                    {
                        "name": item_data.get("name", "unknown"),
                        "type": behavior_type,
                        "behavior_data": item_data,
                    }
                )

        # Process iterable item removals (deleted behaviors)
        if "iterable_item_removed" in diff:
            for _path, item_data in diff["iterable_item_removed"].items():
                removed.append(
                    {
                        "name": item_data.get("name", "unknown"),
                        "type": behavior_type,
                        "behavior_data": item_data,
                    }
                )

        # Process value changes (modified behaviors)
        if "values_changed" in diff:
            for path, change in diff["values_changed"].items():
                # Extract behavior name from the changed data
                old_data = change["old_value"]
                new_data = change["new_value"]

                # If this is a top-level behavior change (not a nested field)
                if self._is_behavior_level_change(path):
                    behavior_name = new_data.get("name") or old_data.get(
                        "name", "unknown"
                    )
                    field_changes = self._convert_deepdiff_to_field_changes(
                        {"values_changed": {path: change}}
                    )

                    changed.append(
                        {
                            "name": behavior_name,
                            "type": behavior_type,
                            "field_changes": field_changes,
                            "from_behavior": old_data,
                            "to_behavior": new_data,
                            "deepdiff_details": {"values_changed": {path: change}},
                        }
                    )
                else:
                    # This is a field-level change within a behavior
                    behavior_name = self._extract_behavior_name_from_path(
                        path, behaviors1_json, behaviors2_json
                    )
                    if behavior_name:
                        # Check if we already have an entry for this behavior
                        existing_change = None
                        for change_entry in changed:
                            if change_entry["name"] == behavior_name:
                                existing_change = change_entry
                                break

                        if not existing_change:
                            # Create new change entry for this behavior
                            behavior_index = self._extract_behavior_index_from_path(
                                path
                            )
                            old_behavior = (
                                behaviors1_json[behavior_index]
                                if behavior_index < len(behaviors1_json)
                                else {}
                            )
                            new_behavior = (
                                behaviors2_json[behavior_index]
                                if behavior_index < len(behaviors2_json)
                                else {}
                            )

                            field_changes = self._convert_deepdiff_to_field_changes(
                                {"values_changed": {path: change}}
                            )

                            changed.append(
                                {
                                    "name": behavior_name,
                                    "type": behavior_type,
                                    "field_changes": field_changes,
                                    "from_behavior": old_behavior,
                                    "to_behavior": new_behavior,
                                    "deepdiff_details": {
                                        "values_changed": {path: change}
                                    },
                                }
                            )
                        else:
                            # Update existing change entry with additional field changes
                            additional_field_changes = (
                                self._convert_deepdiff_to_field_changes(
                                    {"values_changed": {path: change}}
                                )
                            )
                            existing_change["field_changes"].update(
                                additional_field_changes
                            )
                            existing_change["deepdiff_details"]["values_changed"][
                                path
                            ] = change

        return {"added": added, "removed": removed, "changed": changed}

    def _is_behavior_level_change(self, path: str) -> bool:
        """Check if a DeepDiff path represents a top-level behavior change."""
        import re

        # Pattern for root[index] (top-level behavior replacement)
        return bool(re.match(r"root\[\d+\]$", str(path)))

    def _extract_behavior_name_from_path(
        self, path: str, behaviors1: list, behaviors2: list
    ) -> str | None:
        """Extract behavior name from a DeepDiff path."""
        import re

        match = re.search(r"root\[(\d+)\]", str(path))
        if match:
            index = int(match.group(1))
            # Try to get name from either behavior list
            if index < len(behaviors2):
                return behaviors2[index].get("name")
            elif index < len(behaviors1):
                return behaviors1[index].get("name")
        return None

    def _extract_behavior_index_from_path(self, path: str) -> int:
        """Extract behavior index from a DeepDiff path."""
        import re

        match = re.search(r"root\[(\d+)\]", str(path))
        return int(match.group(1)) if match else -1

    def _convert_layer_deepdiff_to_changes(
        self, layer_diff: DeepDiff, layer1_bindings: list, layer2_bindings: list
    ) -> list[dict[str, Any]]:
        """Convert layer DeepDiff to key changes format."""
        key_changes = []

        # Handle individual key changes
        if "values_changed" in layer_diff:
            for path, _change in layer_diff["values_changed"].items():
                # Extract key index from path like "root[0]['value']"
                import re

                match = re.search(r"root\[(\d+)\]", str(path))
                if match:
                    key_index = int(match.group(1))
                    key_changes.append(
                        {
                            "key_index": key_index,
                            "from": self._key_to_dtsi(
                                layer1_bindings[key_index]
                                if key_index < len(layer1_bindings)
                                else None
                            ),
                            "to": self._key_to_dtsi(
                                layer2_bindings[key_index]
                                if key_index < len(layer2_bindings)
                                else None
                            ),
                        }
                    )

        return key_changes

    def _create_json_patch_from_deepdiff(self, deep_diff: DeepDiff) -> dict[str, Any]:
        """Create a JSON patch representation from DeepDiff."""
        patch = {
            "format": "deepdiff_json_patch",
            "operations": [],
        }

        # Convert DeepDiff changes to JSON patch operations
        if "values_changed" in deep_diff:
            for path, change in deep_diff["values_changed"].items():
                patch["operations"].append(
                    {
                        "op": "replace",
                        "path": str(path),
                        "from": change["old_value"],
                        "value": change["new_value"],
                    }
                )

        if "dictionary_item_added" in deep_diff:
            for path, value in deep_diff["dictionary_item_added"].items():
                patch["operations"].append(
                    {"op": "add", "path": str(path), "value": value}
                )

        if "dictionary_item_removed" in deep_diff:
            for path in deep_diff["dictionary_item_removed"]:
                patch["operations"].append({"op": "remove", "path": str(path)})

        if "iterable_item_added" in deep_diff:
            for path, value in deep_diff["iterable_item_added"].items():
                patch["operations"].append(
                    {"op": "add", "path": str(path), "value": value}
                )

        if "iterable_item_removed" in deep_diff:
            for path in deep_diff["iterable_item_removed"]:
                patch["operations"].append({"op": "remove", "path": str(path)})

        return patch

    def _create_deepdiff_delta(
        self, layout1_json: dict, layout2_json: dict
    ) -> dict[str, Any]:
        """Create DeepDiff Delta for patch application using configured serializer."""
        try:
            import base64
            import pickle

            # Create DeepDiff with proper settings for Delta
            diff = DeepDiff(
                layout1_json,
                layout2_json,
                ignore_order=True,
                verbose_level=2,
                report_repetition=True,
            )

            if not diff:
                serializer = self.user_config._config.deepdiff_delta_serializer
                if serializer == "pickle":
                    return {
                        "delta_base64": "",
                        "format": "deepdiff_delta",
                        "serializer": serializer,
                        "note": "No changes detected",
                    }
                else:  # json
                    return {
                        "delta_json": "",
                        "format": "deepdiff_delta",
                        "serializer": serializer,
                        "note": "No changes detected",
                    }

            delta = Delta(diff)

            # Choose serialization method based on user configuration
            serializer = self.user_config._config.deepdiff_delta_serializer

            if serializer == "pickle":
                # Use pickle for more reliable binary serialization
                delta_bytes = pickle.dumps(delta)
                # Base64 encode binary data for JSON compatibility
                encoded_delta = base64.b64encode(delta_bytes).decode("ascii")
                return {
                    "delta_base64": encoded_delta,
                    "format": "deepdiff_delta",
                    "serializer": serializer,
                    "size_bytes": len(delta_bytes),
                }
            else:  # serializer == "json" (default)
                # Use DeepDiff's JSON serialization for true JSON compatibility
                try:
                    from deepdiff.serialization import json_dumps, json_loads

                    # Create delta with JSON serializer
                    delta_json = Delta(diff, serializer=json_dumps)
                    delta_output = delta_json.dumps()

                    # Handle both string and bytes output
                    if isinstance(delta_output, bytes):
                        delta_str = delta_output.decode("utf-8")
                    else:
                        delta_str = delta_output

                    return {
                        "delta_json": delta_str,
                        "format": "deepdiff_delta",
                        "serializer": serializer,
                        "size_chars": len(delta_str),
                    }
                except Exception as json_error:
                    # Fallback to pickle with base64 if JSON serialization fails
                    delta_bytes = delta.dumps()  # Uses pickle internally
                    encoded_delta = base64.b64encode(delta_bytes).decode("ascii")
                    return {
                        "delta_base64": encoded_delta,
                        "format": "deepdiff_delta",
                        "serializer": serializer,
                        "size_bytes": len(delta_bytes),
                        "note": f"JSON serialization failed, used pickle fallback: {str(json_error)}",
                    }
        except Exception as e:
            return {
                "error": f"Failed to create delta: {str(e)}",
                "format": "deepdiff_delta",
                "serializer": getattr(
                    self.user_config._config, "deepdiff_delta_serializer", "json"
                ),
            }

    def _apply_deepdiff_delta_patch(
        self, layout_data: LayoutData, patch_data: dict[str, Any]
    ) -> LayoutData:
        """Apply a DeepDiff Delta patch to layout data using the configured serializer."""
        try:
            import base64
            import pickle

            # Convert layout to JSON
            layout_json = layout_data.model_dump(mode="json")

            # Load and apply delta
            delta_data = patch_data["deepdiff_delta"]

            # Check for available delta formats
            has_json_delta = "delta_json" in delta_data and delta_data["delta_json"]
            has_base64_delta = (
                "delta_base64" in delta_data and delta_data["delta_base64"]
            )

            if not (has_json_delta or has_base64_delta):
                raise ValueError("Invalid or empty delta format")

            # Determine serializer from patch metadata or user config
            patch_serializer = delta_data.get("serializer", "json")
            config_serializer = self.user_config._config.deepdiff_delta_serializer

            delta = None

            # Try JSON format first if available and serializer is json
            if has_json_delta and patch_serializer == "json":
                try:
                    from deepdiff.serialization import json_dumps, json_loads

                    delta_str = delta_data["delta_json"]
                    # Handle both string and bytes input for loads
                    if isinstance(delta_str, str):
                        delta = Delta.loads(delta_str, serializer=json_loads)
                    else:
                        delta_bytes = delta_str.encode("utf-8")
                        delta = Delta.loads(delta_bytes, serializer=json_loads)
                except Exception:
                    pass

            # Try base64 format if JSON failed or not available
            if delta is None and has_base64_delta:
                # Decode base64 delta
                delta_b64 = delta_data["delta_base64"]
                delta_bytes = base64.b64decode(delta_b64.encode("ascii"))

                # Try serializers in order of preference
                serializers_to_try = [patch_serializer]
                if config_serializer != patch_serializer:
                    serializers_to_try.append(config_serializer)

                # Only add fallback to pickle if user has explicitly configured it
                if config_serializer == "pickle" and "pickle" not in serializers_to_try:
                    serializers_to_try.append("pickle")

                # Always add json as final fallback (default behavior)
                if "json" not in serializers_to_try:
                    serializers_to_try.append("json")

                for serializer in serializers_to_try:
                    try:
                        if serializer == "pickle":
                            delta = pickle.loads(delta_bytes)
                            break
                        else:  # json or fallback (uses Delta.loads with default pickle deserializer)
                            delta = Delta.loads(delta_bytes)
                            break
                    except Exception:
                        continue

            if delta is None:
                raise ValueError(
                    "Could not deserialize delta with any available method"
                )

            patched_json = layout_json + delta

            # Convert back to LayoutData
            return LayoutData.model_validate(patched_json)

        except Exception as e:
            # Fallback to legacy patch application
            return self._apply_legacy_patch_to_layout(layout_data, patch_data)

    def _apply_legacy_patch_to_layout(
        self, layout_data: LayoutData, patch_data: dict[str, Any]
    ) -> LayoutData:
        """Apply legacy patch format to layout data."""
        # This is the original patch application method renamed
        patched_data = layout_data.model_copy(deep=True)

        # Apply metadata changes
        if "metadata" in patch_data and patch_data["metadata"]:
            for field, change in patch_data["metadata"].items():
                if isinstance(change, dict) and "to" in change:
                    setattr(patched_data, field, change["to"])

        # Apply layer changes
        self._apply_layer_changes(patched_data, patch_data.get("layers", {}))

        # Apply behavior changes
        self._apply_behavior_changes(patched_data, patch_data.get("behaviors", {}))

        # Apply custom DTSI changes
        self._apply_custom_dtsi_changes(patched_data, patch_data.get("custom_dtsi", {}))

        return patched_data

    def _apply_json_patch_operations(
        self, layout_data: LayoutData, patch_data: dict[str, Any]
    ) -> LayoutData:
        """Apply JSON patch operations from DeepDiff to layout data."""
        try:
            # Convert layout to JSON
            layout_json = layout_data.model_dump(mode="json")

            # Apply each operation in the JSON patch
            operations = patch_data["json_patch"]["operations"]

            for operation in operations:
                op_type = operation["op"]
                path = operation["path"]

                if op_type == "replace":
                    self._apply_json_replace_operation(
                        layout_json, path, operation["value"]
                    )
                elif op_type == "remove":
                    self._apply_json_remove_operation(layout_json, path)
                elif op_type == "add":
                    self._apply_json_add_operation(
                        layout_json, path, operation["value"]
                    )

            # Convert back to LayoutData
            return LayoutData.model_validate(layout_json)

        except Exception as e:
            # Fallback to legacy patch application
            return self._apply_legacy_patch_to_layout(layout_data, patch_data)

    def _apply_json_replace_operation(
        self, layout_json: dict, path: str, value: Any
    ) -> None:
        """Apply a JSON patch replace operation."""
        # Parse path like "root['title']" or "root['hold_taps'][0]['name']"
        field_path = self._parse_json_patch_path(path)
        self._set_nested_value(layout_json, field_path, value)

    def _apply_json_remove_operation(self, layout_json: dict, path: str) -> None:
        """Apply a JSON patch remove operation."""
        # Parse path like "root['hold_taps'][0]"
        field_path = self._parse_json_patch_path(path)
        self._remove_nested_value(layout_json, field_path)

    def _apply_json_add_operation(
        self, layout_json: dict, path: str, value: Any
    ) -> None:
        """Apply a JSON patch add operation."""
        # Parse path and add value
        field_path = self._parse_json_patch_path(path)
        self._set_nested_value(layout_json, field_path, value)

    def _parse_json_patch_path(self, path: str) -> list[str | int]:
        """Parse a JSON patch path into a list of keys/indices."""
        import re

        # Remove 'root' prefix
        path = path.replace("root", "")

        # Find all keys and array indices
        # Matches ['key'] and [0] patterns
        parts = []
        for match in re.finditer(r"\['([^']+)'\]|\[(\d+)\]", path):
            if match.group(1):  # String key
                parts.append(match.group(1))
            elif match.group(2):  # Integer index
                parts.append(int(match.group(2)))

        return parts

    def _set_nested_value(self, data: dict, path: list[str | int], value: Any) -> None:
        """Set a nested value in a dictionary using a path."""
        current = data
        for key in path[:-1]:
            if isinstance(key, int):
                current = current[key]
            else:
                current = current[key]

        final_key = path[-1]
        current[final_key] = value

    def _remove_nested_value(self, data: dict, path: list[str | int]) -> None:
        """Remove a nested value from a dictionary using a path."""
        current = data
        for key in path[:-1]:
            if isinstance(key, int):
                current = current[key]
            else:
                current = current[key]

        final_key = path[-1]
        if isinstance(final_key, int) and isinstance(current, list):
            if 0 <= final_key < len(current):
                del current[final_key]
        else:
            if final_key in current:
                del current[final_key]


def create_layout_comparison_service(
    user_config: UserConfig | None = None,
) -> LayoutComparisonService:
    """Create a LayoutComparisonService instance.

    Args:
        user_config: Optional user configuration. If not provided, will create default config.

    Returns:
        LayoutComparisonService instance
    """
    return LayoutComparisonService(user_config=user_config)
