import copy
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import jsonpatch  # type: ignore
from deepdiff import DeepDiff
from pydantic import BaseModel

from glovebox.layout.models import LayoutData


class LayoutDiffSystem:
    """Diff and patch system specifically for LayoutData structures."""

    def __init__(self) -> None:
        self.diff_engine = DeepDiff

    def create_layout_diff(
        self,
        base_layout: LayoutData,
        modified_layout: LayoutData,
        track_movements: bool = True,
    ) -> dict[str, Any]:
        """Create a comprehensive diff between two layouts."""

        # Convert to dict for comparison
        base_dict = base_layout.model_dump(
            mode="json", by_alias=True, exclude_unset=True
        )
        modified_dict = modified_layout.model_dump(
            mode="json", by_alias=True, exclude_unset=True
        )

        # Create standard JSON patch
        patch = jsonpatch.make_patch(base_dict, modified_dict)

        # Use DeepDiff for detailed analysis
        deep_diff = DeepDiff(
            base_dict,
            modified_dict,
            ignore_order=False,
            report_repetition=True,
            view="tree",
            max_passes=5,
        )

        # Analyze specific layout changes
        layout_changes = self._analyze_layout_changes(base_dict, modified_dict)

        # Track key binding movements if requested
        movements = {}
        if track_movements:
            movements = self._track_binding_movements(base_dict, modified_dict)

        return {
            "metadata": {
                "base_version": base_layout.version,
                "modified_version": modified_layout.version,
                "base_uuid": base_layout.uuid,
                "modified_uuid": modified_layout.uuid,
                "timestamp": datetime.now().isoformat(),
                "diff_type": "layout_diff_v1",
            },
            "json_patch": patch.patch,
            "deep_diff": deep_diff.to_json(),
            "layout_changes": layout_changes,
            "movements": movements,
            "statistics": self._calculate_diff_statistics(patch.patch),
        }

    def _analyze_layout_changes(
        self, base: dict[str, Any], modified: dict[str, Any]
    ) -> dict[str, Any]:
        """Analyze specific layout-related changes."""

        changes: dict[str, Any] = {
            "layers": {"added": [], "removed": [], "modified": [], "reordered": False},
            "behaviors": {
                "hold_taps": {"added": [], "removed": [], "modified": []},
                "combos": {"added": [], "removed": [], "modified": []},
                "macros": {"added": [], "removed": [], "modified": []},
                "input_listeners": {"added": [], "removed": [], "modified": []},
            },
            "config_parameters": {"added": [], "removed": [], "modified": []},
            "custom_code": {"devicetree_changed": False, "behaviors_changed": False},
            "layer_names": {"renamed": [], "order_changed": False},
        }

        # Analyze layer changes
        base_layers = base.get("layers", [])
        modified_layers = modified.get("layers", [])
        base_names = base.get("layer_names", [])
        modified_names = modified.get("layer_names", [])

        # Check for layer additions/removals
        if len(modified_layers) > len(base_layers):
            changes["layers"]["added"] = list(
                range(len(base_layers), len(modified_layers))
            )
        elif len(modified_layers) < len(base_layers):
            changes["layers"]["removed"] = list(
                range(len(modified_layers), len(base_layers))
            )

        # Check for layer modifications
        for i in range(min(len(base_layers), len(modified_layers))):
            if base_layers[i] != modified_layers[i]:
                changes["layers"]["modified"].append(i)

        # Check for layer name changes
        for i in range(min(len(base_names), len(modified_names))):
            if base_names[i] != modified_names[i]:
                changes["layer_names"]["renamed"].append(
                    {"index": i, "from": base_names[i], "to": modified_names[i]}
                )

        # Check if layer order changed (same names but different order)
        if set(base_names) == set(modified_names) and base_names != modified_names:
            changes["layers"]["reordered"] = True
            changes["layer_names"]["order_changed"] = True

        # Analyze behavior changes
        for behavior_type in ["holdTaps", "combos", "macros", "inputListeners"]:
            python_key = behavior_type.replace("holdTaps", "hold_taps").replace(
                "inputListeners", "input_listeners"
            )
            base_behaviors = {b.get("name"): b for b in base.get(behavior_type, [])}
            modified_behaviors = {
                b.get("name"): b for b in modified.get(behavior_type, [])
            }

            # Added behaviors
            added = set(modified_behaviors.keys()) - set(base_behaviors.keys())
            changes["behaviors"][python_key]["added"] = list(added)

            # Removed behaviors
            removed = set(base_behaviors.keys()) - set(modified_behaviors.keys())
            changes["behaviors"][python_key]["removed"] = list(removed)

            # Modified behaviors
            for name in set(base_behaviors.keys()) & set(modified_behaviors.keys()):
                if base_behaviors[name] != modified_behaviors[name]:
                    changes["behaviors"][python_key]["modified"].append(name)

        # Check custom code changes
        if base.get("custom_devicetree") != modified.get("custom_devicetree"):
            changes["custom_code"]["devicetree_changed"] = True
        if base.get("custom_defined_behaviors") != modified.get(
            "custom_defined_behaviors"
        ):
            changes["custom_code"]["behaviors_changed"] = True

        return changes

    def _track_binding_movements(
        self, base: dict[str, Any], modified: dict[str, Any]
    ) -> dict[str, list[dict[str, Any]]]:
        """Track movements of key bindings across layers and positions."""

        movements: dict[str, list[dict[str, Any]]] = {
            "within_layer": [],  # Bindings that moved within the same layer
            "between_layers": [],  # Bindings that moved to different layers
            "behavior_changes": [],  # Same position but behavior changed
        }

        # Create binding signatures for all positions
        base_signatures = self._create_binding_signatures(base)
        modified_signatures = self._create_binding_signatures(modified)

        # Track movements
        for sig, base_positions in base_signatures.items():
            if sig in modified_signatures:
                modified_positions = modified_signatures[sig]

                for base_pos in base_positions:
                    for mod_pos in modified_positions:
                        if base_pos != mod_pos:
                            if base_pos["layer"] == mod_pos["layer"]:
                                movements["within_layer"].append(
                                    {
                                        "signature": sig,
                                        "from": base_pos,
                                        "to": mod_pos,
                                        "binding": base_pos["binding"],
                                    }
                                )
                            else:
                                movements["between_layers"].append(
                                    {
                                        "signature": sig,
                                        "from": base_pos,
                                        "to": mod_pos,
                                        "binding": base_pos["binding"],
                                    }
                                )

        # Track behavior changes at same position
        base_layers = base.get("layers", [])
        modified_layers = modified.get("layers", [])

        for layer_idx in range(min(len(base_layers), len(modified_layers))):
            base_layer = base_layers[layer_idx]
            modified_layer = modified_layers[layer_idx]

            for pos_idx in range(min(len(base_layer), len(modified_layer))):
                if base_layer[pos_idx] != modified_layer[pos_idx]:
                    movements["behavior_changes"].append(
                        {
                            "layer": layer_idx,
                            "position": pos_idx,
                            "from": base_layer[pos_idx],
                            "to": modified_layer[pos_idx],
                        }
                    )

        return movements

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

        # Add semantic descriptions
        semantic = {
            "summary": self._generate_diff_summary(diff),
            # "layer_changes": self._describe_layer_changes(diff),
            # "behavior_changes": self._describe_behavior_changes(diff),
            # "impact_analysis": self._analyze_impact(diff),
        }

        diff["semantic"] = semantic
        return diff

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

        # Filter out unchanged elements
        minimal_patch = []
        for op in full_diff["json_patch"]:
            # Include only actual changes, not moves that don't change content
            if op["op"] != "test":  # Skip test operations
                minimal_patch.append(op)

        return {
            "metadata": full_diff["metadata"],
            "json_patch": minimal_patch,
            "statistics": self._calculate_diff_statistics(minimal_patch),
        }
