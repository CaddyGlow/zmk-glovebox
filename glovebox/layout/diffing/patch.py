from collections import OrderedDict
from datetime import datetime
from typing import Any

import jsonpatch  # type: ignore

from glovebox.layout.models import LayoutData


class LayoutPatchSystem:
    """System for applying patches to LayoutData objects."""

    def __init__(self) -> None:
        self.validation_enabled = True

    def apply_patch(
        self, base_layout: LayoutData, diff: dict[str, Any], validate: bool = True
    ) -> LayoutData:
        """Apply a diff to a base layout and return the modified layout."""

        # Convert layout to dict
        layout_dict = base_layout.model_dump(
            by_alias=True, exclude_unset=True, mode="json"
        )

        # Apply JSON patch with forgiving behavior for missing fields
        # patch = jsonpatch.JsonPatch(diff["json_patch"])
        layer_changes = diff["full_diff"]["layout_changes"]
        modified_dict = self._apply_changes(layout_dict, layer_changes)

        # Update metadata
        # modified_dict = self._update_metadata_after_patch(
        #     modified_dict, base_layout, diff
        # )

        # Create new LayoutData instance
        return LayoutData.model_validate(modified_dict)

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

        # Add layers
        for layer_info in changes["layers"]["added"]:
            layer_name = layer_info["name"]
            layer_data = layer_info["data"]
            target_layer_dict[layer_name] = layer_data

        # Modify layers
        for modification in changes["layers"]["modified"]:
            for layer_name, patch_data in modification.items():
                if layer_name in target_layer_dict:
                    patch = jsonpatch.JsonPatch(patch_data)
                    target_layer_dict[layer_name] = patch.apply(
                        target_layer_dict[layer_name]
                    )

        # Update the target dictionary
        target_dict["layer_names"] = list(target_layer_dict.keys())
        target_dict["layers"] = list(target_layer_dict.values())

        return target_dict

    def _apply_patch_forgiving(
        self, patch: jsonpatch.JsonPatch, layout_dict: dict[str, Any]
    ) -> dict[str, Any]:
        """Apply JSON patch with forgiving behavior for missing fields.

        Attempts to apply each patch operation individually, skipping operations
        that fail due to non-existent fields rather than failing the entire patch.
        """
        try:
            # Try applying the entire patch first (fastest path)
            return patch.apply(layout_dict)
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
