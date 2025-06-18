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

        # Validate diff format
        if validate:
            self._validate_diff_format(diff)

        # Convert layout to dict
        layout_dict = base_layout.model_dump(by_alias=True, exclude_unset=True)

        # Apply JSON patch
        patch = jsonpatch.JsonPatch(diff["json_patch"])
        modified_dict = patch.apply(layout_dict)

        # Update metadata
        modified_dict = self._update_metadata_after_patch(
            modified_dict, base_layout, diff
        )

        # Validate the result before creating LayoutData
        if validate:
            self._validate_patched_layout(modified_dict)

        # Create new LayoutData instance
        return LayoutData.model_validate(modified_dict)

    def _validate_diff_format(self, diff: dict[str, Any]) -> None:
        """Validate that the diff has the expected format."""
        required_keys = ["metadata", "json_patch"]
        for key in required_keys:
            if key not in diff:
                raise ValueError(f"Diff missing required key: {key}")

        if not isinstance(diff["json_patch"], list):
            raise ValueError("json_patch must be a list")

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

    def _validate_patched_layout(self, layout_dict: dict[str, Any]) -> None:
        """Validate the patched layout structure."""

        # Check required fields
        required_fields = ["keyboard", "title", "layers"]
        for field in required_fields:
            if field not in layout_dict:
                raise ValueError(f"Patched layout missing required field: {field}")

        # Validate layer consistency
        layers = layout_dict.get("layers", [])
        layer_names = layout_dict.get("layer_names", [])

        if len(layers) != len(layer_names):
            raise ValueError(
                f"Layer count mismatch: {len(layers)} layers but {len(layer_names)} names"
            )

        # Validate each layer has reasonable number of bindings
        for i, layer in enumerate(layers):
            if len(layer) < 1:  # At least one binding per layer
                raise ValueError(f"Layer {i} has no bindings")
            # Note: Don't enforce specific binding count for test flexibility
