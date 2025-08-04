import hashlib
import json
import logging
from collections import OrderedDict
from datetime import datetime
from typing import TYPE_CHECKING, Any

import jsonpatch  # type: ignore
from deepdiff import DeepDiff

from glovebox.layout.models import LayoutData


if TYPE_CHECKING:
    from glovebox.layout.diffing.models import LayoutDiff


logger = logging.getLogger(__name__)


class LayoutDiffSystem:
    """Diff and patch system specifically for LayoutData structures."""

    def __init__(self) -> None:
        self.diff_engine = DeepDiff

    def create_layout_diff(
        self,
        base_layout: LayoutData,
        modified_layout: LayoutData,
        include_dtsi: bool = False,
    ) -> "LayoutDiff":
        """Create a comprehensive diff between two layouts.

        Args:
            base_layout: Base layout for comparison
            modified_layout: Modified layout for comparison
            include_dtsi: Whether to include custom DTSI fields in diff

        Returns:
            LayoutDiff object containing all changes
        """
        from glovebox.layout.diffing.models import LayoutDiff

        # Convert to dict for comparison
        base_dict = base_layout.model_dump(
            mode="json", by_alias=True, exclude_unset=True
        )
        modified_dict = modified_layout.model_dump(
            mode="json", by_alias=True, exclude_unset=True
        )

        # Create diff data starting with metadata
        diff_data = {
            # Diff metadata
            "base_version": base_layout.version,
            "modified_version": modified_layout.version,
            "base_uuid": base_layout.uuid,
            "modified_uuid": modified_layout.uuid,
            "timestamp": datetime.now(),
            "diff_type": "layout_diff_v2",
            # Analyze structured lists
            "layers": self._analyze_layout_changes(base_dict, modified_dict),
            "holdTaps": self._analyze_behavior_changes(
                base_dict.get("holdTaps", []), modified_dict.get("holdTaps", [])
            ),
            "combos": self._analyze_behavior_changes(
                base_dict.get("combos", []), modified_dict.get("combos", [])
            ),
            "macros": self._analyze_behavior_changes(
                base_dict.get("macros", []), modified_dict.get("macros", [])
            ),
            "inputListeners": self._analyze_behavior_changes(
                base_dict.get("inputListeners", []),
                modified_dict.get("inputListeners", []),
                name_field="code",  # inputListeners use 'code' not 'name'
            ),
        }

        # Analyze simple fields (excluding layer_names which is handled with layers)
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
            "base_version_changes",
            "base_layout",
            "last_firmware_build",
        ]

        for field in simple_fields:
            base_value = base_dict.get(field)
            modified_value = modified_dict.get(field)
            if base_value != modified_value:
                patch = jsonpatch.make_patch(base_value, modified_value)
                if patch.patch:
                    diff_data[field] = patch.patch

        # Handle DTSI fields if requested
        if include_dtsi:
            import difflib

            for dtsi_field in ["custom_defined_behaviors", "custom_devicetree"]:
                base_text = base_dict.get(dtsi_field, "")
                modified_text = modified_dict.get(dtsi_field, "")
                if base_text != modified_text:
                    # Create unified diff
                    diff = "\n".join(
                        difflib.unified_diff(
                            base_text.splitlines(keepends=True),
                            modified_text.splitlines(keepends=True),
                            fromfile=f"base/{dtsi_field}",
                            tofile=f"modified/{dtsi_field}",
                        )
                    )
                    if diff:
                        diff_data[dtsi_field] = diff

        return LayoutDiff.model_validate(diff_data)

    def _analyze_layout_changes(
        self, base: dict[str, Any], modified: dict[str, Any]
    ) -> dict[str, Any]:
        """Enhanced version that stores data needed for applying changes"""
        changes: dict[str, Any] = {"added": [], "removed": [], "modified": []}

        base_layer_dict = OrderedDict(
            zip(base.get("layer_names", []), base.get("layers", []), strict=False)
        )
        modified_layer_dict = OrderedDict(
            zip(
                modified.get("layer_names", []),
                modified.get("layers", []),
                strict=False,
            )
        )

        # Create position mappings
        base_layer_names = list(base.get("layer_names", []))
        modified_layer_names = list(modified.get("layer_names", []))

        base_positions = {name: idx for idx, name in enumerate(base_layer_names)}
        modified_positions = {
            name: idx for idx, name in enumerate(modified_layer_names)
        }

        # Store removed layers with their original positions
        removed_layers = base_layer_dict.keys() - modified_layer_dict.keys()
        changes["removed"] = [
            {"name": name, "data": [], "original_position": base_positions.get(name)}
            for name in removed_layers
        ]

        # Store added layers with their new positions
        added_layers = modified_layer_dict.keys() - base_layer_dict.keys()
        changes["added"] = [
            {
                "name": name,
                "data": modified_layer_dict[name],
                "new_position": modified_positions.get(name),
            }
            for name in added_layers
        ]

        # Store modifications with position information
        for k, v in base_layer_dict.items():
            if k in modified_layer_dict:
                patch = jsonpatch.make_patch(v, modified_layer_dict[k])
                original_pos = base_positions.get(k)
                new_pos = modified_positions.get(k)

                # Store if there are content changes OR position changes
                if patch.patch or original_pos != new_pos:
                    change_info = {
                        k: {
                            "patch": patch.patch,
                            "original_position": original_pos,
                            "new_position": new_pos,
                            "position_changed": original_pos != new_pos,
                        }
                    }
                    changes["modified"].append(change_info)

        return changes

    def _analyze_behavior_changes(
        self,
        base_behaviors: list[dict[str, Any]],
        modified_behaviors: list[dict[str, Any]],
        name_field: str = "name",
    ) -> dict[str, Any]:
        """Generic method to analyze changes in behavior lists.

        Args:
            base_behaviors: List of behaviors in base layout
            modified_behaviors: List of behaviors in modified layout
            name_field: Field name to use as identifier (default: "name")

        Returns:
            Dictionary with added, removed, and modified behaviors
        """
        from collections import OrderedDict

        # Create OrderedDict by name
        base_dict = OrderedDict(
            (behavior[name_field], behavior) for behavior in base_behaviors
        )
        modified_dict = OrderedDict(
            (behavior[name_field], behavior) for behavior in modified_behaviors
        )

        changes: dict[str, Any] = {"added": [], "removed": [], "modified": []}

        # Find removed behaviors (only store name)
        removed_names = base_dict.keys() - modified_dict.keys()
        changes["removed"] = [{"name": name, "data": []} for name in removed_names]

        # Find added behaviors (store full data)
        added_names = modified_dict.keys() - base_dict.keys()
        changes["added"] = [
            {"name": name, "data": modified_dict[name]} for name in added_names
        ]

        # Find modified behaviors
        for name in base_dict.keys() & modified_dict.keys():
            patch = jsonpatch.make_patch(base_dict[name], modified_dict[name])
            if patch.patch:  # Only store if there are actual changes
                changes["modified"].append({name: patch.patch})

        return changes

    # def _analyze_layout_changes(
    #     self, base: dict[str, Any], modified: dict[str, Any]
    # ) -> dict[str, Any]:
    #     """Analyze specific layout-related changes."""
    #
    #     changes: dict[str, Any] = {
    #         "layers": {"added": [], "removed": [], "modified": [], "reordered": False},
    #         "behaviors": {
    #             "hold_taps": {"added": [], "removed": [], "modified": []},
    #             "combos": {"added": [], "removed": [], "modified": []},
    #             "macros": {"added": [], "removed": [], "modified": []},
    #             "input_listeners": {"added": [], "removed": [], "modified": []},
    #         },
    #         "config_parameters": {"added": [], "removed": [], "modified": []},
    #         "custom_code": {"devicetree_changed": False, "behaviors_changed": False},
    #         "layer_names": {"renamed": [], "order_changed": False},
    #     }
    #
    #     # Analyze layer changes
    #     base_layer_dict = OrderedDict(
    #         zip(base.get("layer_names", []), base.get("layers", []), strict=False)
    #     )
    #     modified_layer_dict = OrderedDict(
    #         zip(
    #             modified.get("layer_names", []),
    #             modified.get("layers", []),
    #             strict=False,
    #         )
    #     )
    #
    #     # Check for layer additions/removals
    #     changes["layers"]["removed"] = list(
    #         base_layer_dict.keys() - modified_layer_dict.keys()
    #     )
    #     changes["layers"]["added"] = list(
    #         modified_layer_dict.keys() - base_layer_dict.keys()
    #     )
    #
    #     # Check for layer modifications
    #     for k, v in base_layer_dict.items():
    #         if k in modified_layer_dict:
    #             diff = DeepDiff(v, modified_layer_dict[k])
    #             logger.debug("Diff for %s: %s", k, diff)
    #             patch = jsonpatch.make_patch(v, modified_layer_dict[k])
    #             changes["layers"]["modified"].append({k: patch.patch})
    #
    #     # # Check if layer order changed (same names but different order)
    #     # if set(base_names) == set(modified_names) and base_names != modified_names:
    #     #     changes["layers"]["reordered"] = True
    #     #     changes["layer_names"]["order_changed"] = True
    #
    #     # Analyze behavior changes
    #     for behavior_type in ["holdTaps", "combos", "macros", "inputListeners"]:
    #         python_key = behavior_type.replace("holdTaps", "hold_taps").replace(
    #             "inputListeners", "input_listeners"
    #         )
    #         base_behaviors = {b.get("name"): b for b in base.get(behavior_type, [])}
    #         modified_behaviors = {
    #             b.get("name"): b for b in modified.get(behavior_type, [])
    #         }
    #
    #         # Added behaviors
    #         added = set(modified_behaviors.keys()) - set(base_behaviors.keys())
    #         changes["behaviors"][python_key]["added"] = list(added)
    #
    #         # Removed behaviors
    #         removed = set(base_behaviors.keys()) - set(modified_behaviors.keys())
    #         changes["behaviors"][python_key]["removed"] = list(removed)
    #
    #         # Modified behaviors
    #         for name in set(base_behaviors.keys()) & set(modified_behaviors.keys()):
    #             if base_behaviors[name] != modified_behaviors[name]:
    #                 changes["behaviors"][python_key]["modified"].append(name)
    #
    #     # Check custom code changes
    #     if base.get("custom_devicetree") != modified.get("custom_devicetree"):
    #         changes["custom_code"]["devicetree_changed"] = True
    #     if base.get("custom_defined_behaviors") != modified.get(
    #         "custom_defined_behaviors"
    #     ):
    #         changes["custom_code"]["behaviors_changed"] = True
    #
    #     return changes

    def _create_binding_signatures(
        self, layout_dict: dict[str, Any]
    ) -> dict[str, list[dict[str, Any]]]:
        """Create signatures for all bindings to track movements."""
        signatures: dict[str, list[dict[str, Any]]] = {}

        layers = layout_dict.get("layers", [])
        for layer_idx, layer in enumerate(layers):
            for pos_idx, binding in enumerate(layer):
                # Create signature from binding content
                sig = self._calculate_binding_signature(binding)

                position_info = {
                    "layer": layer_idx,
                    "position": pos_idx,
                    "binding": binding,
                }

                if sig not in signatures:
                    signatures[sig] = []
                signatures[sig].append(position_info)

        return signatures

    def _calculate_binding_signature(self, binding: dict[str, Any]) -> str:
        """Calculate a unique signature for a binding."""
        # Create a deterministic string representation
        content = json.dumps(binding, sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def _calculate_diff_statistics(self, patch: list[dict[str, Any]]) -> dict[str, int]:
        """Calculate statistics about the diff."""
        stats = {
            "total_operations": len(patch),
            "additions": 0,
            "removals": 0,
            "replacements": 0,
            "moves": 0,
        }

        for op in patch:
            op_type = op.get("op", "")
            if op_type == "add":
                stats["additions"] += 1
            elif op_type == "remove":
                stats["removals"] += 1
            elif op_type == "replace":
                stats["replacements"] += 1
            elif op_type == "move":
                stats["moves"] += 1

        return stats


class AdvancedLayoutDiffSystem(LayoutDiffSystem):
    """Extended diff system with advanced features."""

    def create_semantic_diff(
        self, base_layout: LayoutData, modified_layout: LayoutData
    ) -> dict[str, Any]:
        """Create a human-readable semantic diff."""

        diff = self.create_layout_diff(base_layout, modified_layout)

        # Convert LayoutDiff to dict and add semantic descriptions
        diff_dict = diff.model_dump(mode="json", by_alias=True, exclude_unset=True)

        # Add semantic descriptions
        semantic = {
            "summary": self._generate_diff_summary(diff_dict),
            # "layer_changes": self._describe_layer_changes(diff_dict),
            # "behavior_changes": self._describe_behavior_changes(diff_dict),
            # "impact_analysis": self._analyze_impact(diff_dict),
        }

        diff_dict["semantic"] = semantic
        return diff_dict

    def _generate_diff_summary(self, diff: dict[str, Any]) -> str:
        """Generate a human-readable summary of changes."""
        stats = diff["statistics"]
        changes = diff["layout_changes"]

        summary_parts = []

        if changes["layers"]["added"]:
            summary_parts.append(f"Added {len(changes['layers']['added'])} layers")
        if changes["layers"]["removed"]:
            summary_parts.append(f"Removed {len(changes['layers']['removed'])} layers")
        if changes["layers"]["modified"]:
            summary_parts.append(
                f"Modified {len(changes['layers']['modified'])} layers"
            )

        total_behavior_changes = 0
        for _behavior_type, changes_dict in changes["behaviors"].items():
            total = (
                len(changes_dict["added"])
                + len(changes_dict["removed"])
                + len(changes_dict["modified"])
            )
            if total > 0:
                total_behavior_changes += total

        if total_behavior_changes > 0:
            summary_parts.append(f"Changed {total_behavior_changes} behaviors")

        return "; ".join(summary_parts) if summary_parts else "No significant changes"

    def create_minimal_diff(
        self, base_layout: LayoutData, modified_layout: LayoutData
    ) -> dict[str, Any]:
        """Create a minimal diff containing only the changes."""

        full_diff = self.create_layout_diff(base_layout, modified_layout)

        # Convert to dict format
        diff_dict = full_diff.model_dump(mode="json", by_alias=True, exclude_unset=True)

        # For now, return the full diff as the minimal format
        # TODO: Implement actual minimal diff logic for new format
        return diff_dict
