from collections import OrderedDict
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

import jsonpatch  # type: ignore[import-untyped]

from glovebox.layout.models import LayoutData


if TYPE_CHECKING:
    from glovebox.layout.diffing.models import LayoutDiff


class LayoutPatchSystem:
    """System for applying patches to LayoutData objects."""

    def __init__(self) -> None:
        self.validation_enabled = True

    def apply_patch(
        self,
        layout: LayoutData,
        diff: "LayoutDiff",
        skip_dtsi: bool = False,
    ) -> LayoutData:
        """Apply a diff to a layout.

        Args:
            layout: Base layout to apply changes to
            diff: LayoutDiff object containing changes
            skip_dtsi: Whether to skip DTSI changes even if present in diff

        Returns:
            New LayoutData instance with changes applied
        """

        # Convert to dict for manipulation
        target_dict = layout.model_dump(mode="json", by_alias=True, exclude_unset=True)

        # Apply layer changes (existing logic)
        if hasattr(diff, "layers") and diff.layers:
            target_dict = self._apply_changes(
                target_dict, {"layers": diff.layers.model_dump()}
            )

        # Apply behavior changes
        if hasattr(diff, "hold_taps") and diff.hold_taps:
            target_dict["holdTaps"] = self._apply_behavior_changes(
                target_dict.get("holdTaps", []), diff.hold_taps.model_dump()
            )

        if hasattr(diff, "combos") and diff.combos:
            target_dict["combos"] = self._apply_behavior_changes(
                target_dict.get("combos", []), diff.combos.model_dump()
            )

        if hasattr(diff, "macros") and diff.macros:
            target_dict["macros"] = self._apply_behavior_changes(
                target_dict.get("macros", []), diff.macros.model_dump()
            )

        if hasattr(diff, "input_listeners") and diff.input_listeners:
            target_dict["inputListeners"] = self._apply_behavior_changes(
                target_dict.get("inputListeners", []),
                diff.input_listeners.model_dump(),
                name_field="code",
            )

        # Apply simple field patches (exclude DTSI fields and layer_names which are handled separately)
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
            "base_version_patch",  # This is the aliased field, not base_version
            "base_layout",
            "last_firmware_build",
        ]

        for field in simple_fields:
            patch_data = getattr(diff, field, None)
            if patch_data is not None:
                # Ensure patch_data is a list of operations, not a string
                if isinstance(patch_data, str):
                    continue  # Skip string fields (these should be DTSI fields)
                patch = jsonpatch.JsonPatch(patch_data)
                target_dict[field] = patch.apply(target_dict.get(field))

        # Apply DTSI changes if not skipped
        if not skip_dtsi:
            for dtsi_field in ["custom_defined_behaviors", "custom_devicetree"]:
                diff_text = getattr(diff, dtsi_field, None)
                if diff_text:
                    # Apply unified diff
                    original = target_dict.get(dtsi_field, "")
                    target_dict[dtsi_field] = self._apply_unified_diff(
                        original, diff_text
                    )

        # Create new layout from patched data
        return LayoutData.model_validate(target_dict)

    def _apply_changes(
        self, target_dict: dict[str, Any], changes: dict[str, Any]
    ) -> dict[str, Any]:
        """Apply changes to target dictionary"""
        target_layer_dict = OrderedDict(
            zip(
                target_dict.get("layer_names", []),
                target_dict.get("layers", []),
                strict=False,
            )
        )

        # Remove layers
        for layer_info in changes["layers"]["removed"]:
            layer_name = layer_info["name"]
            if layer_name in target_layer_dict:
                del target_layer_dict[layer_name]

        # Add layers with position information
        added_layers_with_positions = []
        for layer_info in changes["layers"]["added"]:
            layer_name = layer_info["name"]
            layer_data = layer_info["data"]
            new_position = layer_info.get("new_position")
            target_layer_dict[layer_name] = layer_data
            if new_position is not None:
                added_layers_with_positions.append((layer_name, new_position))

        # Modify layers and collect position changes
        position_changes = {}
        for modification in changes["layers"]["modified"]:
            for layer_name, layer_info in modification.items():
                if layer_name in target_layer_dict:
                    # Handle new structure with position information
                    if isinstance(layer_info, dict) and "patch" in layer_info:
                        patch_data = layer_info["patch"]
                        if (
                            patch_data
                        ):  # Only apply if there are actual patch operations
                            patch = jsonpatch.JsonPatch(patch_data)
                            target_layer_dict[layer_name] = patch.apply(
                                target_layer_dict[layer_name]
                            )

                        # Track position changes
                        new_position = layer_info.get("new_position")
                        if new_position is not None:
                            position_changes[layer_name] = new_position
                    else:
                        # Fallback for old structure (direct patch data)
                        if layer_info:
                            patch = jsonpatch.JsonPatch(layer_info)
                            target_layer_dict[layer_name] = patch.apply(
                                target_layer_dict[layer_name]
                            )

        # Reconstruct layer order based on position information
        if position_changes or added_layers_with_positions:
            # Create list of (layer_name, position) tuples
            layer_positions = []

            # Add existing layers with their new positions (or current positions)
            for layer_name in target_layer_dict:
                if layer_name in position_changes:
                    layer_positions.append((layer_name, position_changes[layer_name]))
                else:
                    # Keep original position relative to other unchanged layers
                    current_names = list(target_layer_dict.keys())
                    current_index = current_names.index(layer_name)
                    layer_positions.append((layer_name, current_index))

            # Sort by position and reconstruct ordered dict
            layer_positions.sort(key=lambda x: x[1])
            new_target_layer_dict = OrderedDict()
            for layer_name, _ in layer_positions:
                new_target_layer_dict[layer_name] = target_layer_dict[layer_name]

            target_layer_dict = new_target_layer_dict

        # Update the target dictionary
        target_dict["layer_names"] = list(target_layer_dict.keys())
        target_dict["layers"] = list(target_layer_dict.values())

        return target_dict

    def _apply_behavior_changes(
        self,
        target_list: list[dict[str, Any]],
        changes: dict[str, Any],
        name_field: str = "name",
    ) -> list[dict[str, Any]]:
        """Apply behavior changes to a list.

        Args:
            target_list: Current list of behaviors
            changes: Changes to apply (added, removed, modified)
            name_field: Field name to use as identifier (default: "name")

        Returns:
            Updated list of behaviors
        """
        from collections import OrderedDict

        # Create OrderedDict
        target_dict = OrderedDict((item[name_field], item) for item in target_list)

        # Remove behaviors
        for removed in changes.get("removed", []):
            name = removed["name"]
            if name in target_dict:
                del target_dict[name]

        # Add behaviors
        for added in changes.get("added", []):
            name = added["name"]
            target_dict[name] = added["data"]

        # Modify behaviors
        for modified in changes.get("modified", []):
            for name, patch_data in modified.items():
                if name in target_dict:
                    patch = jsonpatch.JsonPatch(patch_data)
                    target_dict[name] = patch.apply(target_dict[name])

        return list(target_dict.values())

    def _apply_unified_diff(self, original: str, unified_diff: str) -> str:
        """Apply a unified diff to original text.

        Args:
            original: Original text content
            unified_diff: Unified diff string to apply

        Returns:
            Modified text content
        """
        import subprocess
        import tempfile
        from pathlib import Path

        try:
            from glovebox.core.structlog_logger import get_struct_logger

            local_logger = get_struct_logger(__name__)

            # Create temporary files for patch operation
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                original_file = temp_path / "original.txt"
                diff_file = temp_path / "changes.diff"

                # Write original content
                original_file.write_text(original, encoding="utf-8")

                # Write diff content
                diff_file.write_text(unified_diff, encoding="utf-8")

                # Apply patch using GNU patch
                result = subprocess.run(
                    ["patch", "-o", "-", str(original_file)],
                    input=unified_diff,
                    text=True,
                    capture_output=True,
                    check=False,
                )

                if result.returncode == 0:
                    return result.stdout
                else:
                    # Fall back to original if patch fails
                    local_logger.warning(
                        "failed_to_apply_unified_diff",
                        error=result.stderr.decode()
                        if result.stderr
                        else "unknown error",
                    )
                    return original

        except Exception as e:
            # Fall back to original on any error
            from glovebox.core.structlog_logger import get_struct_logger

            local_logger = get_struct_logger(__name__)
            local_logger.warning("error_applying_unified_diff", error=str(e))
            return original

    def _apply_patch_forgiving(
        self,
        patch: Any,
        layout_dict: dict[str, Any],  # jsonpatch.JsonPatch
    ) -> dict[str, Any]:
        """Apply JSON patch with forgiving behavior for missing fields.

        Attempts to apply each patch operation individually, skipping operations
        that fail due to non-existent fields rather than failing the entire patch.
        """
        try:
            # Try applying the entire patch first (fastest path)
            return cast(dict[str, Any], patch.apply(layout_dict))
        except jsonpatch.JsonPatchException:
            # If patch fails, apply operations one by one, skipping failures
            result_dict = layout_dict.copy()
            skipped_operations = []

            for operation in patch.patch:
                try:
                    single_patch = jsonpatch.JsonPatch([operation])
                    result_dict = single_patch.apply(result_dict)
                except jsonpatch.JsonPatchException as e:
                    # Skip operations that fail on non-existent fields
                    op_type = operation.get("op", "unknown")
                    op_path = operation.get("path", "unknown")
                    skipped_operations.append(f"{op_type} at {op_path}")

            # Note: We don't log here since this class doesn't have a logger
            # The calling code can check if operations were skipped if needed
            return result_dict

    def _validate_diff_format(self, diff: dict[str, Any]) -> None:
        """Validate that the diff has the expected format."""
        required_keys = ["layout_changes"]
        for key in required_keys:
            if key not in diff:
                raise ValueError(f"Diff missing required key: {key}")

    def _update_metadata_after_patch(
        self, layout_dict: dict[str, Any], base_layout: LayoutData, diff: dict[str, Any]
    ) -> dict[str, Any]:
        """Update metadata fields after applying patch."""

        # Update version information
        if "version" in layout_dict:
            # Increment patch version
            current_version = layout_dict["version"]
            parts = current_version.split(".")
            if len(parts) == 3:
                parts[2] = str(int(parts[2]) + 1)
                layout_dict["version"] = ".".join(parts)

        # Track base version
        layout_dict["base_version"] = base_layout.version
        layout_dict["parent_uuid"] = base_layout.uuid

        # Update modification timestamp
        layout_dict["date"] = datetime.now().isoformat()

        return layout_dict
