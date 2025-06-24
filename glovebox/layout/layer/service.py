"""Layout layer service for layer management operations."""

import json
import re
from pathlib import Path
from typing import Any

from glovebox.layout.models import LayoutBinding, LayoutData
from glovebox.layout.utils.json_operations import (
    load_json_data,
    load_layout_file,
    save_json_data,
    save_layout_file,
)
from glovebox.layout.utils.validation import (
    validate_layer_exists,
    validate_layer_has_bindings,
    validate_layer_name_unique,
    validate_output_path,
    validate_position_index,
)
from glovebox.protocols import FileAdapterProtocol


class LayoutLayerService:
    """Service for managing layout layers."""

    def __init__(self, file_adapter: FileAdapterProtocol) -> None:
        """Initialize the layer service with required dependencies."""
        self.file_adapter = file_adapter

    def add_layer(
        self,
        layout_file: Path,
        layer_name: str,
        position: int | None = None,
        copy_from: str | None = None,
        import_from: Path | None = None,
        import_layer: str | None = None,
        output: Path | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """Add a new layer to the layout.

        Args:
            layout_file: Path to layout JSON file
            layer_name: Name of the new layer
            position: Position to insert (defaults to end)
            copy_from: Copy bindings from existing layer name
            import_from: Import layer from external JSON file
            import_layer: Specific layer name when importing from full layout
            output: Output file path (defaults to input file)
            force: Whether to overwrite existing files

        Returns:
            Dictionary with operation details

        Raises:
            ValueError: If parameters are invalid or layer already exists
            FileNotFoundError: If import file doesn't exist
        """
        # Load WITHOUT variable resolution to preserve original variable references
        layout_data = load_layout_file(
            layout_file, self.file_adapter, skip_variable_resolution=True
        )

        # Validate mutually exclusive options
        source_count = sum(bool(x) for x in [copy_from, import_from])
        if source_count > 1:
            raise ValueError("Cannot use copy_from and import_from together")

        if import_layer and not import_from:
            raise ValueError("import_layer requires import_from")

        # Validate layer name is unique
        validate_layer_name_unique(layout_data, layer_name)

        # Determine and validate position
        position = validate_position_index(position, len(layout_data.layer_names))

        # Create layer bindings based on source
        new_bindings = self._create_layer_bindings(
            layout_data, copy_from, import_from, import_layer
        )

        # Insert the layer
        layout_data.layer_names.insert(position, layer_name)
        layout_data.layers.insert(position, new_bindings)

        # Save the modified layout
        output_path = output if output is not None else layout_file
        validate_output_path(output_path, layout_file, force)
        save_layout_file(layout_data, output_path, self.file_adapter)

        return {
            "output_path": output_path,
            "layer_name": layer_name,
            "position": position,
            "total_layers": len(layout_data.layer_names),
            "copy_from": copy_from,
            "import_from": import_from,
            "import_layer": import_layer,
        }

    def remove_layer(
        self,
        layout_file: Path,
        layer_identifier: str,
        output: Path | None = None,
        force: bool = False,
        warn_on_no_match: bool = True,
    ) -> dict[str, Any]:
        """Remove layer(s) from the layout.

        Args:
            layout_file: Path to layout JSON file
            layer_identifier: Layer identifier - can be:
                - Layer name (exact match)
                - Index (0-based, e.g., "0", "15")
                - Regex pattern (e.g., "Mouse.*", "Mouse*", ".*Index")
            output: Output file path (defaults to input file)
            force: Whether to overwrite existing files
            warn_on_no_match: Whether to include warnings for no matches

        Returns:
            Dictionary with operation details including warnings

        Raises:
            ValueError: If output path is invalid (but not for no layer matches)
        """
        # Load WITHOUT variable resolution to preserve original variable references
        layout_data = load_layout_file(
            layout_file, self.file_adapter, skip_variable_resolution=True
        )

        # Find layers to remove based on identifier type
        layers_to_remove = self._find_layers_to_remove(layout_data, layer_identifier)

        warnings = []
        if not layers_to_remove and warn_on_no_match:
            warnings.append(
                f"No layers found matching identifier '{layer_identifier}'. "
                f"Available layers: {', '.join(layout_data.layer_names)}"
            )

        removed_layers = []
        if layers_to_remove:
            # Sort by index in descending order to remove from end to start
            # This prevents index shifting issues
            layers_to_remove.sort(key=lambda x: x["index"], reverse=True)

            for layer_info in layers_to_remove:
                idx = layer_info["index"]
                name = layer_info["name"]

                # Remove layer name and bindings
                layout_data.layer_names.pop(idx)
                if idx < len(layout_data.layers):
                    layout_data.layers.pop(idx)

                removed_layers.append({"name": name, "position": idx})

            # Save the modified layout only if we actually removed layers
            output_path = output if output is not None else layout_file
            validate_output_path(output_path, layout_file, force)
            save_layout_file(layout_data, output_path, self.file_adapter)
        else:
            # No layers removed, use original file path
            output_path = layout_file

        return {
            "output_path": output_path,
            "removed_layers": removed_layers,
            "removed_count": len(removed_layers),
            "remaining_layers": len(layout_data.layer_names),
            "warnings": warnings,
            "had_matches": len(layers_to_remove) > 0,
        }

    def move_layer(
        self,
        layout_file: Path,
        layer_name: str,
        new_position: int,
        output: Path | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """Move a layer to a new position.

        Args:
            layout_file: Path to layout JSON file
            layer_name: Name of layer to move
            new_position: New position (0-based index, can be negative)
            output: Output file path (defaults to input file)
            force: Whether to overwrite existing files

        Returns:
            Dictionary with operation details

        Raises:
            ValueError: If layer doesn't exist or positions are invalid
        """
        # Load WITHOUT variable resolution to preserve original variable references
        layout_data = load_layout_file(
            layout_file, self.file_adapter, skip_variable_resolution=True
        )

        # Validate layer exists and get current position
        current_idx = validate_layer_exists(layout_data, layer_name)

        # Normalize new position
        total_layers = len(layout_data.layer_names)
        if new_position < 0:
            new_position = max(0, total_layers + new_position)
        elif new_position >= total_layers:
            new_position = total_layers - 1

        # Check if move is needed
        if current_idx == new_position:
            return {
                "output_path": layout_file,
                "layer_name": layer_name,
                "from_position": current_idx,
                "to_position": new_position,
                "moved": False,
            }

        # Remove and reinsert layer
        layer_name_to_move = layout_data.layer_names.pop(current_idx)
        layer_bindings = None
        if current_idx < len(layout_data.layers):
            layer_bindings = layout_data.layers.pop(current_idx)

        layout_data.layer_names.insert(new_position, layer_name_to_move)
        if layer_bindings is not None:
            layout_data.layers.insert(new_position, layer_bindings)

        # Save the modified layout
        output_path = output if output is not None else layout_file
        validate_output_path(output_path, layout_file, force)
        save_layout_file(layout_data, output_path, self.file_adapter)

        return {
            "output_path": output_path,
            "layer_name": layer_name,
            "from_position": current_idx,
            "to_position": new_position,
            "moved": True,
        }

    def list_layers(self, layout_file: Path) -> dict[str, Any]:
        """List all layers with their details.

        Args:
            layout_file: Path to layout JSON file

        Returns:
            Dictionary with layer information
        """
        # Load WITHOUT variable resolution to preserve original variable references
        layout_data = load_layout_file(
            layout_file, self.file_adapter, skip_variable_resolution=True
        )

        layers_info = []
        for i, layer_name in enumerate(layout_data.layer_names):
            binding_count = (
                len(layout_data.layers[i]) if i < len(layout_data.layers) else 0
            )
            layers_info.append(
                {
                    "position": i,
                    "name": layer_name,
                    "binding_count": binding_count,
                }
            )

        return {
            "total_layers": len(layout_data.layer_names),
            "layers": layers_info,
        }

    def export_layer(
        self,
        layout_file: Path,
        layer_name: str,
        output: Path,
        format_type: str = "bindings",
        force: bool = False,
    ) -> dict[str, Any]:
        """Export a layer to an external JSON file.

        Args:
            layout_file: Path to layout JSON file
            layer_name: Name of layer to export
            output: Output JSON file path
            format_type: Export format ('bindings', 'layer', 'full')
            force: Whether to overwrite existing files

        Returns:
            Dictionary with operation details

        Raises:
            ValueError: If layer doesn't exist or format is invalid
        """
        # Load WITHOUT variable resolution to preserve original variable references
        layout_data = load_layout_file(
            layout_file, self.file_adapter, skip_variable_resolution=True
        )

        # Validate layer exists and has bindings
        layer_idx = validate_layer_exists(layout_data, layer_name)
        validate_layer_has_bindings(layout_data, layer_name, layer_idx)

        # Validate output path
        validate_output_path(output, force=force)

        layer_bindings = layout_data.layers[layer_idx]

        # Generate export data based on format
        export_data = self._create_export_data(
            layout_data, layer_name, layer_bindings, format_type
        )

        # Save export file
        save_json_data(export_data, output, self.file_adapter)

        return {
            "source_file": layout_file,
            "layer_name": layer_name,
            "output_file": output,
            "format": format_type,
            "binding_count": len(layer_bindings),
        }

    def _create_layer_bindings(
        self,
        layout_data: LayoutData,
        copy_from: str | None,
        import_from: Path | None,
        import_layer: str | None,
    ) -> list[LayoutBinding]:
        """Create layer bindings from various sources."""
        if import_from:
            return self._import_layer_bindings(import_from, import_layer)
        elif copy_from:
            return self._copy_layer_bindings(layout_data, copy_from)
        else:
            # Create empty layer with default &none bindings (80 keys for Glove80)
            return [LayoutBinding(value="&none", params=[]) for _ in range(80)]

    def _import_layer_bindings(
        self, import_from: Path, import_layer: str | None
    ) -> list[LayoutBinding]:
        """Import layer bindings from external file."""
        if not import_from.exists():
            raise FileNotFoundError(f"Import file not found: {import_from}")

        import_content = json.loads(import_from.read_text(encoding="utf-8"))

        if isinstance(import_content, list):
            # Single layer format: array of bindings
            return self._convert_to_layout_bindings(import_content)
        elif isinstance(import_content, dict):
            if import_layer:
                # Import specific layer from full layout
                return self._import_specific_layer(import_content, import_layer)
            elif "bindings" in import_content:
                # Layer object format
                return self._convert_to_layout_bindings(import_content["bindings"])
            else:
                raise ValueError(
                    "Import file appears to be a full layout. "
                    "Use import_layer to specify which layer to import"
                )
        else:
            raise ValueError(
                "Invalid import file format. "
                "Expected array of bindings or layout object"
            )

    def _import_specific_layer(
        self, import_data: dict[str, Any], import_layer: str
    ) -> list[LayoutBinding]:
        """Import a specific layer from full layout data."""
        if "layer_names" not in import_data or "layers" not in import_data:
            raise ValueError("Import file is not a valid layout JSON")

        if import_layer not in import_data["layer_names"]:
            available_layers = ", ".join(import_data["layer_names"])
            raise ValueError(
                f"Layer '{import_layer}' not found in import file. "
                f"Available layers: {available_layers}"
            )

        layer_idx = import_data["layer_names"].index(import_layer)
        if layer_idx >= len(import_data["layers"]):
            raise ValueError(
                f"Layer '{import_layer}' has no binding data in import file"
            )

        return self._convert_to_layout_bindings(import_data["layers"][layer_idx])

    def _copy_layer_bindings(
        self, layout_data: LayoutData, copy_from: str
    ) -> list[LayoutBinding]:
        """Copy bindings from existing layer."""
        source_idx = validate_layer_exists(layout_data, copy_from)
        validate_layer_has_bindings(layout_data, copy_from, source_idx)

        source_bindings = layout_data.layers[source_idx]
        return [
            LayoutBinding(value=binding.value, params=binding.params.copy())
            for binding in source_bindings
        ]

    def _convert_to_layout_bindings(
        self, bindings_data: list[Any]
    ) -> list[LayoutBinding]:
        """Convert raw binding data to LayoutBinding objects."""
        return [
            LayoutBinding.model_validate(binding)
            if isinstance(binding, dict)
            else LayoutBinding(value=str(binding), params=[])
            for binding in bindings_data
        ]

    def _find_layers_to_remove(
        self, layout_data: LayoutData, layer_identifier: str
    ) -> list[dict[str, Any]]:
        """Find layers to remove based on identifier type.

        Args:
            layout_data: Layout data containing layers
            layer_identifier: Identifier (name, index, or regex pattern)

        Returns:
            List of dictionaries with layer info {"name": str, "index": int}
        """
        layers_to_remove = []

        # Try to parse as integer index first
        try:
            index = int(layer_identifier)
            if 0 <= index < len(layout_data.layer_names):
                return [{"name": layout_data.layer_names[index], "index": index}]
            else:
                return []
        except ValueError:
            # Not an integer, continue with name/pattern matching
            pass

        # Check for exact layer name match first
        for i, layer_name in enumerate(layout_data.layer_names):
            if layer_name == layer_identifier:
                return [{"name": layer_name, "index": i}]

        # Try regex pattern matching
        try:
            # Convert shell-style wildcards to regex if needed
            pattern = layer_identifier
            if "*" in pattern and not any(c in pattern for c in "[]{}()^$+?\\|"):
                # Simple wildcard pattern - convert to regex
                pattern = pattern.replace("*", ".*")

            # Compile regex pattern
            regex = re.compile(pattern)

            # Find all matching layers
            for i, layer_name in enumerate(layout_data.layer_names):
                if regex.match(layer_name):
                    layers_to_remove.append({"name": layer_name, "index": i})

        except re.error:
            # Invalid regex pattern - return empty list
            return []

        return layers_to_remove

    def _create_export_data(
        self,
        layout_data: LayoutData,
        layer_name: str,
        layer_bindings: list[LayoutBinding],
        format_type: str,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Create export data in the specified format."""
        if format_type == "bindings":
            # Simple array of bindings
            return [
                binding.model_dump(by_alias=True, exclude_unset=True)
                for binding in layer_bindings
            ]
        elif format_type == "layer":
            # Layer object with name and bindings
            return {
                "name": layer_name,
                "bindings": [
                    binding.model_dump(by_alias=True, exclude_unset=True)
                    for binding in layer_bindings
                ],
            }
        elif format_type == "full":
            # Minimal layout with just this layer
            return {
                "keyboard": layout_data.keyboard,
                "title": f"Exported layer: {layer_name}",
                "layer_names": [layer_name],
                "layers": [
                    [
                        binding.model_dump(by_alias=True, exclude_unset=True)
                        for binding in layer_bindings
                    ]
                ],
            }
        else:
            raise ValueError(
                f"Invalid format: {format_type}. Use: bindings, layer, or full"
            )


def create_layout_layer_service(
    file_adapter: FileAdapterProtocol,
) -> LayoutLayerService:
    """Create a LayoutLayerService instance with explicit dependencies.

    Args:
        file_adapter: Required FileAdapter for file operations

    Returns:
        LayoutLayerService instance
    """
    return LayoutLayerService(file_adapter)
