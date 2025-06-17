"""Version management for keymap layouts."""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from glovebox.adapters.file_adapter import create_file_adapter
from glovebox.core.errors import LayoutError
from glovebox.layout.models import LayoutData
from glovebox.protocols import FileAdapterProtocol


logger = logging.getLogger(__name__)


class VersionManager:
    """Manages keymap versions and upgrades."""

    def __init__(self, file_adapter: FileAdapterProtocol | None = None):
        """Initialize version manager."""
        self._file_adapter = file_adapter or create_file_adapter()
        self._masters_dir = Path.home() / ".glovebox" / "masters"

    def import_master(
        self, json_file: Path, name: str, force: bool = False
    ) -> dict[str, Any]:
        """Import a master layout version.

        Args:
            json_file: Path to master layout JSON file
            name: Version name (e.g., "v42-pre")
            force: Overwrite existing version

        Returns:
            Dict with success status and metadata
        """
        try:
            # Load and validate layout
            layout_data = self._load_layout(json_file)
            keyboard = layout_data.keyboard

            # Create masters directory structure
            keyboard_dir = self._masters_dir / keyboard
            keyboard_dir.mkdir(parents=True, exist_ok=True)

            # Check if version already exists
            master_file = keyboard_dir / f"{name}.json"
            if master_file.exists() and not force:
                raise LayoutError(
                    f"Master version {name} already exists. Use --force to overwrite."
                )

            # Copy master file
            shutil.copy2(json_file, master_file)

            # Update versions metadata
            self._update_versions_metadata(keyboard, name, layout_data)

            logger.info("Imported master version %s for keyboard %s", name, keyboard)
            return {
                "success": True,
                "version": name,
                "keyboard": keyboard,
                "path": str(master_file),
                "title": layout_data.title,
            }

        except Exception as e:
            logger.error("Failed to import master version: %s", e)
            raise LayoutError(f"Failed to import master version: {e}") from e

    def upgrade_layout(
        self,
        custom_layout: Path,
        to_master: str,
        output: Path | None = None,
        strategy: str = "preserve-custom",
        from_master: str | None = None,
    ) -> dict[str, Any]:
        """Upgrade custom layout to new master version.

        Args:
            custom_layout: Path to custom layout
            to_master: Target master version
            output: Output path (default: auto-generated)
            strategy: Upgrade strategy (only "preserve-custom" supported)
            from_master: Source master version (auto-detected if not provided)

        Returns:
            Dict with upgrade results
        """
        try:
            # Load custom layout
            custom_data = self._load_layout(custom_layout)

            # Determine output path
            if output is None:
                output = custom_layout.parent / f"{custom_layout.stem}-{to_master}.json"

            # Determine source master version
            if from_master:
                source_version = from_master
            elif custom_data.base_version:
                source_version = custom_data.base_version
            else:
                raise LayoutError(
                    f"Cannot determine source master version. "
                    f"Layout '{custom_layout.name}' has no base_version metadata. "
                    f"Use --from-master to specify the source version manually."
                )

            # Load old and new master versions
            old_master_data = self._load_master(custom_data.keyboard, source_version)
            new_master_data = self._load_master(custom_data.keyboard, to_master)

            # Perform upgrade
            upgraded_data = self._merge_layouts(
                old_master=old_master_data,
                new_master=new_master_data,
                custom=custom_data,
                strategy=strategy,
            )

            # Update metadata
            upgraded_data.base_version = to_master
            upgraded_data.version = f"{custom_data.version}-{to_master}"
            upgraded_data.date = datetime.now()

            # Save upgraded layout
            self._save_layout(upgraded_data, output)

            logger.info("Upgraded layout from %s to %s", source_version, to_master)
            return {
                "success": True,
                "from_version": source_version,
                "to_version": to_master,
                "output_path": str(output),
                "preserved_customizations": self._get_preserved_items(
                    custom_data, old_master_data
                ),
            }

        except Exception as e:
            logger.error("Failed to upgrade layout: %s", e)
            raise LayoutError(f"Failed to upgrade layout: {e}") from e

    def list_masters(self, keyboard: str) -> list[dict[str, Any]]:
        """List available master versions for a keyboard."""
        keyboard_dir = self._masters_dir / keyboard
        if not keyboard_dir.exists():
            return []

        versions = []
        for json_file in keyboard_dir.glob("*.json"):
            try:
                layout_data = self._load_layout(json_file)
                versions.append(
                    {
                        "name": json_file.stem,
                        "title": layout_data.title,
                        "date": layout_data.date.isoformat()
                        if layout_data.date
                        else None,
                        "creator": layout_data.creator,
                    }
                )
            except Exception as e:
                logger.warning("Failed to load master %s: %s", json_file, e)

        return sorted(versions, key=lambda x: x["date"] or "", reverse=True)

    def _load_layout(self, json_file: Path) -> LayoutData:
        """Load and validate layout from JSON file."""
        if not json_file.exists():
            raise LayoutError(f"Layout file not found: {json_file}")

        content = self._file_adapter.read_text(json_file)
        data = json.loads(content)
        return LayoutData.model_validate(data)

    def _load_master(self, keyboard: str, version: str) -> LayoutData:
        """Load master version by keyboard and version name."""
        master_file = self._masters_dir / keyboard / f"{version}.json"
        if not master_file.exists():
            raise LayoutError(
                f"Master version {version} not found for keyboard {keyboard}"
            )
        return self._load_layout(master_file)

    def _save_layout(self, layout_data: LayoutData, output_path: Path) -> None:
        """Save layout to JSON file."""
        # Use model_dump with serialization mode for proper datetime handling
        data = layout_data.model_dump(by_alias=True, exclude_unset=True, mode="json")
        content = json.dumps(data, indent=2, ensure_ascii=False)
        self._file_adapter.write_text(output_path, content)

    def _merge_layouts(
        self,
        old_master: LayoutData,
        new_master: LayoutData,
        custom: LayoutData,
        strategy: str,
    ) -> LayoutData:
        """Merge custom changes into new master version."""
        if strategy != "preserve-custom":
            raise LayoutError(f"Unsupported strategy: {strategy}")

        logger.debug("Starting layout merge process")
        logger.debug("Old master layers: %s", old_master.layer_names)
        logger.debug("New master layers: %s", new_master.layer_names)
        logger.debug("Custom layers: %s", custom.layer_names)

        # Start with new master as base
        merged = new_master.model_copy(deep=True)
        logger.debug("Base merged layers (from new master): %s", merged.layer_names)

        # Preserve custom metadata
        merged.title = custom.title
        merged.creator = custom.creator
        merged.notes = custom.notes
        merged.tags = custom.tags.copy()
        logger.debug(
            "Preserved custom metadata: title='%s', creator='%s'",
            custom.title,
            custom.creator,
        )

        # Preserve custom behaviors
        merged.hold_taps = custom.hold_taps.copy()
        merged.combos = custom.combos.copy()
        merged.macros = custom.macros.copy()
        merged.input_listeners = custom.input_listeners.copy()
        logger.debug(
            "Preserved behaviors: %d hold-taps, %d combos, %d macros",
            len(custom.hold_taps),
            len(custom.combos),
            len(custom.macros),
        )

        # Preserve custom config parameters (ensure proper copying)
        merged.config_parameters = [
            param.model_copy() if hasattr(param, "model_copy") else param
            for param in custom.config_parameters
        ]
        logger.debug(
            "Preserved config parameters: %d items", len(custom.config_parameters)
        )

        # Preserve custom code
        merged.custom_defined_behaviors = custom.custom_defined_behaviors
        merged.custom_devicetree = custom.custom_devicetree
        logger.debug("Preserved custom code sections")

        # Layer merging: preserve custom layers, update others
        old_master_layer_set = set(old_master.layer_names)
        new_master_layer_set = set(new_master.layer_names)
        custom_layer_set = set(custom.layer_names)

        # Find layers that are truly custom (not in old master)
        custom_only_layers = custom_layer_set - old_master_layer_set
        logger.debug(
            "Layers only in custom (to preserve): %s", list(custom_only_layers)
        )

        # Find layers that were removed in new master
        removed_in_new_master = old_master_layer_set - new_master_layer_set
        logger.debug("Layers removed in new master: %s", list(removed_in_new_master))

        # Find layers added in new master
        added_in_new_master = new_master_layer_set - old_master_layer_set
        logger.debug("Layers added in new master: %s", list(added_in_new_master))

        # Find layers that were intentionally removed from custom (exist in old master but not in custom)
        intentionally_removed_from_custom = old_master_layer_set - custom_layer_set
        logger.debug(
            "Layers intentionally removed from custom: %s",
            list(intentionally_removed_from_custom),
        )

        # Remove layers from merged that were:
        # 1. Removed in new master but exist in custom, OR
        # 2. Intentionally removed from custom (exist in old master but not custom)
        layers_to_remove_from_merged = []
        for i, layer_name in enumerate(merged.layer_names):
            should_remove = False

            if layer_name in removed_in_new_master and layer_name in custom_layer_set:
                logger.debug(
                    "Marking layer '%s' for removal (removed in new master but exists in custom)",
                    layer_name,
                )
                should_remove = True
            elif layer_name in intentionally_removed_from_custom:
                logger.debug(
                    "Marking layer '%s' for removal (intentionally removed from custom)",
                    layer_name,
                )
                should_remove = True

            if should_remove:
                layers_to_remove_from_merged.append(i)

        # Remove in reverse order to maintain indices
        for i in reversed(layers_to_remove_from_merged):
            if i < len(merged.layer_names) and i < len(merged.layers):
                removed_name = merged.layer_names.pop(i)
                merged.layers.pop(i)
                logger.debug("Removed layer '%s' at index %d", removed_name, i)

        # Add custom-only layers back to merged
        for i, layer_name in enumerate(custom.layer_names):
            if layer_name in custom_only_layers and i < len(custom.layers):
                logger.debug("Adding custom layer '%s' back to merged", layer_name)
                # Find the best insertion point
                if i < len(merged.layer_names):
                    merged.layer_names.insert(i, layer_name)
                    merged.layers.insert(i, custom.layers[i])
                    logger.debug(
                        "Inserted custom layer '%s' at index %d", layer_name, i
                    )
                else:
                    merged.layer_names.append(layer_name)
                    merged.layers.append(custom.layers[i])
                    logger.debug("Appended custom layer '%s' at end", layer_name)

        # IMPORTANT: Replace layer contents for layers that exist in both custom and new master
        # This preserves customizations within existing layers
        common_layers = custom_layer_set & new_master_layer_set
        logger.debug(
            "Layers common to both custom and new master: %s", list(common_layers)
        )

        for layer_name in common_layers:
            try:
                # Find indices in both layouts
                custom_idx = custom.layer_names.index(layer_name)
                merged_idx = merged.layer_names.index(layer_name)

                if custom_idx < len(custom.layers) and merged_idx < len(merged.layers):
                    # Simple comparison - check if they're different
                    custom_layer = (
                        custom.layers[custom_idx]
                        if isinstance(custom.layers[custom_idx], list)
                        else []
                    )
                    merged_layer = (
                        merged.layers[merged_idx]
                        if isinstance(merged.layers[merged_idx], list)
                        else []
                    )

                    if custom_layer != merged_layer:
                        # Get old master layer for analysis
                        old_master_idx = (
                            old_master.layer_names.index(layer_name)
                            if layer_name in old_master.layer_names
                            else -1
                        )
                        old_master_layer = (
                            old_master.layers[old_master_idx]
                            if old_master_idx >= 0
                            and old_master_idx < len(old_master.layers)
                            and isinstance(old_master.layers[old_master_idx], list)
                            else []
                        )

                        # Use helper function to analyze the differences (for logging only)
                        analysis = self._analyze_layer_differences(
                            layer_name, custom_layer, merged_layer, old_master_layer
                        )

                        # Log summary
                        logger.info(
                            "Layer '%s': %d user customizations, %d master improvements - preserving custom version",
                            layer_name,
                            len(analysis.get("user_customizations", [])),
                            len(analysis.get("master_improvements", [])),
                        )

                        # Simple replacement
                        merged.layers[merged_idx] = custom.layers[custom_idx]
                    else:
                        logger.debug(
                            "Layer '%s' content unchanged (same key mappings)",
                            layer_name,
                        )

            except (ValueError, IndexError) as e:
                logger.warning(
                    "Failed to replace content for layer '%s': %s", layer_name, e
                )

        logger.debug("Final merged layers: %s", merged.layer_names)
        logger.debug("Layer merge completed")
        return merged

    def _analyze_layer_differences(
        self,
        layer_name: str,
        custom_layer: list[Any],
        new_master_layer: list[Any],
        old_master_layer: list[Any],
    ) -> dict[str, Any]:
        """Analyze differences between layer versions to identify customizations vs improvements.

        Args:
            layer_name: Name of the layer being analyzed
            custom_layer: Layer data from custom layout
            new_master_layer: Layer data from new master
            old_master_layer: Layer data from old master

        Returns:
            Dict with analysis results including user customizations and master improvements
        """
        try:
            user_customizations = []
            new_master_improvements = []

            # Compare each key position
            max_keys = max(
                len(custom_layer), len(new_master_layer), len(old_master_layer)
            )

            for i in range(max_keys):
                custom_key = custom_layer[i] if i < len(custom_layer) else None
                new_master_key = (
                    new_master_layer[i] if i < len(new_master_layer) else None
                )
                old_master_key = (
                    old_master_layer[i] if i < len(old_master_layer) else None
                )

                # Skip if custom and new master are the same
                if custom_key == new_master_key:
                    continue

                # Convert to strings for safe comparison and display
                custom_str = str(custom_key) if custom_key is not None else "None"
                new_master_str = (
                    str(new_master_key) if new_master_key is not None else "None"
                )
                old_master_str = (
                    str(old_master_key) if old_master_key is not None else "None"
                )

                # Truncate long strings for readability
                custom_str = (
                    custom_str[:50] + "..." if len(custom_str) > 50 else custom_str
                )
                new_master_str = (
                    new_master_str[:50] + "..."
                    if len(new_master_str) > 50
                    else new_master_str
                )
                old_master_str = (
                    old_master_str[:50] + "..."
                    if len(old_master_str) > 50
                    else old_master_str
                )

                # Determine if this is a user customization or master improvement
                if old_master_key is not None:
                    if custom_key != old_master_key:
                        # User made a change from old master -> this is a customization
                        user_customizations.append(
                            {
                                "key_index": i,
                                "type": "user_customization",
                                "description": f"Key {i:2d}: User customized '{old_master_str}' → '{custom_str}' (NewMaster has '{new_master_str}')",
                            }
                        )
                    elif new_master_key != old_master_key:
                        # User kept old master, but new master changed -> this is an improvement
                        new_master_improvements.append(
                            {
                                "key_index": i,
                                "type": "master_improvement",
                                "description": f"Key {i:2d}: NewMaster improved '{old_master_str}' → '{new_master_str}' (User kept old)",
                            }
                        )
                else:
                    # No old master reference, treat as customization
                    user_customizations.append(
                        {
                            "key_index": i,
                            "type": "user_customization",
                            "description": f"Key {i:2d}: Custom='{custom_str}' vs NewMaster='{new_master_str}' (no old master ref)",
                        }
                    )

            return {
                "layer_name": layer_name,
                "user_customizations": user_customizations,
                "master_improvements": new_master_improvements,
                "total_differences": len(user_customizations)
                + len(new_master_improvements),
            }

        except Exception as e:
            logger.warning("Failed to analyze layer '%s': %s", layer_name, e)
            return {
                "layer_name": layer_name,
                "user_customizations": [],
                "master_improvements": [],
                "total_differences": 0,
                "error": str(e),
            }

    def _get_preserved_items(
        self, custom: LayoutData, old_master: LayoutData
    ) -> dict[str, Any]:
        """Get list of items that were preserved during upgrade."""
        preserved: dict[str, Any] = {
            "custom_layers": [],
            "custom_behaviors": [],
            "custom_config": [],
        }

        # Find custom layers
        old_layer_names = set(old_master.layer_names)
        preserved["custom_layers"] = [
            name for name in custom.layer_names if name not in old_layer_names
        ]

        # Find custom behaviors
        if custom.hold_taps:
            preserved["custom_behaviors"].append(f"{len(custom.hold_taps)} hold-taps")
        if custom.combos:
            preserved["custom_behaviors"].append(f"{len(custom.combos)} combos")
        if custom.macros:
            preserved["custom_behaviors"].append(f"{len(custom.macros)} macros")

        # Find custom config
        if custom.config_parameters:
            preserved["custom_config"] = [
                str(param) for param in custom.config_parameters
            ]

        return preserved

    def _update_versions_metadata(
        self, keyboard: str, version: str, layout_data: LayoutData
    ) -> None:
        """Update versions metadata file."""
        versions_file = self._masters_dir / keyboard / "versions.yaml"

        # Load existing metadata
        metadata: dict[str, Any] = {}
        if versions_file.exists():
            try:
                with versions_file.open() as f:
                    metadata = yaml.safe_load(f) or {}
            except Exception as e:
                logger.warning("Failed to load versions metadata: %s", e)

        # Update metadata
        if "versions" not in metadata:
            metadata["versions"] = {}

        metadata["versions"][version] = {
            "title": layout_data.title,
            "creator": layout_data.creator,
            "date": layout_data.date.isoformat() if layout_data.date else None,
            "imported": datetime.now().isoformat(),
        }

        # Save metadata
        try:
            with versions_file.open("w") as f:
                yaml.safe_dump(metadata, f, default_flow_style=False)
        except Exception as e:
            logger.warning("Failed to save versions metadata: %s", e)


def create_version_manager() -> VersionManager:
    """Create a version manager instance."""
    return VersionManager()
