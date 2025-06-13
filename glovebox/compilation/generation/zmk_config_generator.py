"""ZMK Config content generator for dynamic workspace creation."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from glovebox.adapters import FileAdapter
from glovebox.compilation.models.build_matrix import BuildTargetConfig, BuildYamlConfig
from glovebox.compilation.models.west_config import (
    WestDefaults,
    WestManifest,
    WestManifestConfig,
    WestProject,
    WestRemote,
    WestSelf,
)
from glovebox.core.errors import GloveboxError


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile


logger = logging.getLogger(__name__)


class ZmkConfigGenerationError(GloveboxError):
    """Error in ZMK config content generation."""


class ZmkConfigContentGenerator:
    """Generate ZMK config repository content on-the-fly.

    Creates the necessary files (build.yaml, west.yml, keymap, conf)
    for a ZMK config repository without requiring an external repository.
    """

    def __init__(
        self,
        file_adapter: FileAdapter | None = None,
    ) -> None:
        """Initialize ZMK config content generator.

        Args:
            file_adapter: File operations adapter
        """
        self.file_adapter = file_adapter
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def generate_config_workspace(
        self,
        workspace_path: Path,
        keymap_file: Path,
        config_file: Path,
        keyboard_profile: "KeyboardProfile",
        shield_name: str | None = None,
        board_name: str = "nice_nano_v2",
        separate_config_path: Path | None = None,
    ) -> bool:
        """Generate complete ZMK config workspace from glovebox files.

        Args:
            workspace_path: Directory to create workspace in
            keymap_file: Source keymap file
            config_file: Source config file
            keyboard_profile: Keyboard profile for build configuration
            shield_name: Shield name (defaults to keyboard name)
            board_name: Board name for builds
            separate_config_path: Optional separate directory for config files

        Returns:
            bool: True if workspace generated successfully

        Raises:
            ZmkConfigGenerationError: If generation fails
        """
        try:
            self.logger.info("Generating ZMK config workspace at %s", workspace_path)

            # Ensure workspace directory exists
            if not self._ensure_workspace_directory(workspace_path):
                return False

            # Determine shield name
            effective_shield = shield_name or keyboard_profile.keyboard_name

            # Generate build.yaml for GitHub Actions style builds
            if not self._generate_build_yaml(
                workspace_path, effective_shield, board_name
            ):
                return False

            # Generate west.yml for workspace configuration
            if not self._generate_west_yml(
                workspace_path, keyboard_profile, separate_config_path
            ):
                return False

            # Create config directory and copy keymap/config files
            if not self._setup_config_directory(
                workspace_path,
                keymap_file,
                config_file,
                effective_shield,
                separate_config_path,
            ):
                return False

            # Generate additional files for compatibility
            if not self._generate_additional_files(workspace_path, keyboard_profile):
                return False

            self.logger.info("ZMK config workspace generated successfully")
            return True

        except Exception as e:
            msg = f"Failed to generate ZMK config workspace: {e}"
            self.logger.error(msg)
            raise ZmkConfigGenerationError(msg) from e

    def _ensure_workspace_directory(self, workspace_path: Path) -> bool:
        """Ensure workspace directory exists.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            bool: True if directory exists or was created
        """
        try:
            if self.file_adapter:
                self.file_adapter.create_directory(workspace_path)
                return True
            else:
                workspace_path.mkdir(parents=True, exist_ok=True)
                return True
        except Exception as e:
            self.logger.error("Failed to create workspace directory: %s", e)
            return False

    def _generate_build_yaml(
        self, workspace_path: Path, shield_name: str, board_name: str
    ) -> bool:
        """Generate build.yaml file for GitHub Actions builds.

        Args:
            workspace_path: Path to workspace
            shield_name: Shield name for builds
            board_name: Board name for builds

        Returns:
            bool: True if build.yaml generated successfully
        """
        build_yaml_content = self._create_build_yaml_content(shield_name, board_name)
        build_yaml_path = workspace_path / "build.yaml"

        try:
            if self.file_adapter:
                self.file_adapter.write_text(build_yaml_path, build_yaml_content)
            else:
                build_yaml_path.write_text(build_yaml_content)

            self.logger.debug("Generated build.yaml at %s", build_yaml_path)
            return True
        except Exception as e:
            self.logger.error("Failed to generate build.yaml: %s", e)
            return False

    def _create_build_yaml_content(self, shield_name: str, board_name: str) -> str:
        """Create build.yaml content using BuildYamlConfig model.

        Args:
            shield_name: Shield name for builds
            board_name: Board name for builds

        Returns:
            str: build.yaml content
        """
        # Detect if this is a split keyboard by shield name patterns
        is_split = any(
            indicator in shield_name.lower()
            for indicator in ["corne", "crkbd", "lily58", "sofle", "kyria", "glove80"]
        )

        # Create BuildYamlConfig based on keyboard type
        if is_split:
            if "glove80" in shield_name.lower():
                # Glove80 uses board array format (boards, not shields)
                build_config = BuildYamlConfig(
                    board=[f"{shield_name}_lh", f"{shield_name}_rh"],
                    shield=[],
                    include=[],
                )
            else:
                # Standard ZMK split keyboards use include format with shields
                left_suffix = "_left"
                right_suffix = "_right"
                build_config = BuildYamlConfig(
                    board=[],
                    shield=[],
                    include=[
                        BuildTargetConfig(
                            board=board_name, shield=f"{shield_name}{left_suffix}"
                        ).model_dump(exclude_none=True),
                        BuildTargetConfig(
                            board=board_name, shield=f"{shield_name}{right_suffix}"
                        ).model_dump(exclude_none=True),
                    ],
                )
        else:
            # Generate single keyboard build target
            build_config = BuildYamlConfig(
                board=[],
                shield=[],
                include=[
                    BuildTargetConfig(board=board_name, shield=shield_name).model_dump(
                        exclude_none=True
                    )
                ],
            )

        # Convert to YAML with GitHub Actions matrix header comment
        header_comment = """# This file generates the GitHub Actions matrix.
# For simple board + shield combinations, add them to the top level board and
# shield arrays, for more control, add individual board + shield combinations
# to the `include` property. You can also use the `cmake-args` property to
# pass flags to the build command, `snippet` to add a Zephyr snippet, and
# `artifact-name` to assign a name to distinguish build outputs from each other:
#
# board: [ "nice_nano_v2" ]
# shield: [ "corne_left", "corne_right" ]
# include:
#   - board: bdn9_rev2
#   - board: nice_nano_v2
#     shield: reviung41
#   - board: nice_nano_v2
#     shield: corne_left
#     snippet: studio-rpc-usb-uart
#     cmake-args: -DCONFIG_ZMK_STUDIO=y
#     artifact-name: corne_left_with_studio
#
---"""

        # Serialize BuildYamlConfig to YAML, excluding empty arrays
        config_dict = build_config.model_dump(exclude_none=True, exclude_unset=True)

        # Remove empty arrays for cleaner output
        if not config_dict.get("board"):
            config_dict.pop("board", None)
        if not config_dict.get("shield"):
            config_dict.pop("shield", None)
        if not config_dict.get("include"):
            config_dict.pop("include", None)

        yaml_content = yaml.dump(config_dict, default_flow_style=False, sort_keys=False)

        return f"{header_comment}\n{yaml_content}"

    def _generate_west_yml(
        self,
        workspace_path: Path,
        keyboard_profile: "KeyboardProfile",
        separate_config_path: Path | None = None,
    ) -> bool:
        """Generate west.yml for ZMK workspace configuration using WestManifestConfig.

        Args:
            workspace_path: Path to workspace
            keyboard_profile: Keyboard profile to determine ZMK repository
            separate_config_path: Optional separate directory for config files

        Returns:
            bool: True if west.yml generated successfully
        """
        west_config = self._create_west_config(keyboard_profile)

        # Determine where to place west.yml
        config_dir = (
            separate_config_path
            if separate_config_path
            else (workspace_path / "config")
        )
        west_yml_path = config_dir / "west.yml"

        try:
            # Ensure config directory exists
            if self.file_adapter:
                self.file_adapter.create_directory(config_dir)
            else:
                config_dir.mkdir(parents=True, exist_ok=True)

            # Serialize west config to YAML
            west_yml_content = self._serialize_west_config(west_config)

            # Write west.yml
            if self.file_adapter:
                self.file_adapter.write_text(west_yml_path, west_yml_content)
            else:
                west_yml_path.write_text(west_yml_content)

            self.logger.debug("Generated west.yml at %s", west_yml_path)
            return True
        except Exception as e:
            self.logger.error("Failed to generate west.yml: %s", e)
            return False

    def _create_west_config(
        self, keyboard_profile: "KeyboardProfile"
    ) -> WestManifestConfig:
        """Create WestManifestConfig from keyboard profile.

        Args:
            keyboard_profile: Keyboard profile to determine ZMK repository

        Returns:
            WestManifestConfig: West manifest configuration
        """
        # Determine the correct ZMK repository and branch based on firmware config
        if keyboard_profile.firmware_config is not None:
            # Use firmware configuration's repository and branch
            build_options = keyboard_profile.firmware_config.build_options
            repository_url = build_options.repository
            branch = build_options.branch

            # Extract repository name and organization from URL or org/repo format
            if repository_url.startswith("https://github.com/"):
                repo_path = repository_url.replace("https://github.com/", "")
                org_name, repo_name = repo_path.split("/")
            elif "/" in repository_url:
                # Handle org/repo format (e.g., "moergo-sc/zmk")
                org_name, repo_name = repository_url.split("/")
            else:
                # Fallback for unknown formats
                org_name = "zmkfirmware"
                repo_name = "zmk"
        elif "glove80" in keyboard_profile.keyboard_name.lower():
            # Fallback: Glove80 uses MoErgo's ZMK fork
            org_name = "moergo-sc"
            repo_name = "zmk"
            branch = "main"
        else:
            # Fallback: Standard ZMK repository for other keyboards
            org_name = "zmkfirmware"
            repo_name = "zmk"
            branch = "main"

        # Create west manifest configuration
        return WestManifestConfig(
            manifest=WestManifest(
                defaults=WestDefaults(remote=org_name)
                if org_name == "zmkfirmware"
                else None,
                remotes=[
                    WestRemote(name=org_name, url_base=f"https://github.com/{org_name}")
                ],
                projects=[
                    WestProject(
                        name=repo_name,
                        remote=org_name,
                        revision=branch,
                        import_="app/west.yml",
                    )
                ],
                self=WestSelf(path="config"),
            )
        )

    def _serialize_west_config(self, west_config: WestManifestConfig) -> str:
        """Serialize WestManifestConfig to YAML string.

        Args:
            west_config: West manifest configuration

        Returns:
            str: YAML content for west.yml
        """
        # Convert to dict for YAML serialization, using aliases
        config_dict = west_config.model_dump(by_alias=True, exclude_none=True)

        # Add header comment
        header_comment = "# West configuration for ZMK - Generated by Glovebox"

        # Serialize to YAML
        yaml_content = yaml.dump(config_dict, default_flow_style=False, sort_keys=False)

        return f"{header_comment}\n{yaml_content}"

    def _setup_config_directory(
        self,
        workspace_path: Path,
        keymap_file: Path,
        config_file: Path,
        shield_name: str,
        separate_config_path: Path | None = None,
    ) -> bool:
        """Setup config directory with keymap and config files.

        Args:
            workspace_path: Path to workspace
            keymap_file: Source keymap file
            config_file: Source config file
            shield_name: Shield name for file naming
            separate_config_path: Optional separate directory for config files

        Returns:
            bool: True if config directory setup successfully
        """
        # Always create workspace config directory for west.yml
        workspace_config_dir = workspace_path / "config"

        # Determine where to put the actual config files
        config_dir = (
            separate_config_path if separate_config_path else workspace_config_dir
        )

        try:
            # Ensure both directories exist
            if self.file_adapter:
                self.file_adapter.create_directory(workspace_config_dir)
                if separate_config_path:
                    self.file_adapter.create_directory(separate_config_path)
            else:
                workspace_config_dir.mkdir(parents=True, exist_ok=True)
                if separate_config_path:
                    separate_config_path.mkdir(parents=True, exist_ok=True)

            # Copy keymap file
            keymap_dest = config_dir / f"{shield_name}.keymap"
            if self.file_adapter:
                keymap_content = self.file_adapter.read_text(keymap_file)
                self.file_adapter.write_text(keymap_dest, keymap_content)
            else:
                keymap_content = keymap_file.read_text()
                keymap_dest.write_text(keymap_content)

            # Copy config file
            config_dest = config_dir / f"{shield_name}.conf"
            if self.file_adapter:
                config_content = self.file_adapter.read_text(config_file)
                self.file_adapter.write_text(config_dest, config_content)
            else:
                config_content = config_file.read_text()
                config_dest.write_text(config_content)

            self.logger.debug("Copied keymap and config files to %s", config_dir)
            return True

        except Exception as e:
            self.logger.error("Failed to setup config directory: %s", e)
            return False

    def _generate_additional_files(
        self, workspace_path: Path, keyboard_profile: "KeyboardProfile"
    ) -> bool:
        """Generate additional files for workspace compatibility.

        Args:
            workspace_path: Path to workspace
            keyboard_profile: Keyboard profile for metadata

        Returns:
            bool: True if additional files generated successfully
        """
        try:
            # Generate README.md for the workspace
            readme_content = self._create_readme_content(keyboard_profile)
            readme_path = workspace_path / "README.md"

            if self.file_adapter:
                self.file_adapter.write_text(readme_path, readme_content)
            else:
                readme_path.write_text(readme_content)

            # Generate .gitignore for the workspace
            gitignore_content = """# ZMK Workspace - Generated by Glovebox
.west/
build/
*.tmp
*.swp
*.swo
*~
"""
            gitignore_path = workspace_path / ".gitignore"

            if self.file_adapter:
                self.file_adapter.write_text(gitignore_path, gitignore_content)
            else:
                gitignore_path.write_text(gitignore_content)

            self.logger.debug("Generated additional workspace files")
            return True

        except Exception as e:
            self.logger.error("Failed to generate additional files: %s", e)
            return False

    def _create_readme_content(self, keyboard_profile: "KeyboardProfile") -> str:
        """Create README.md content for the workspace.

        Args:
            keyboard_profile: Keyboard profile for metadata

        Returns:
            str: README.md content
        """
        return f"""# {keyboard_profile.keyboard_config.description}

ZMK configuration workspace generated by Glovebox.

## Keyboard Information

- **Keyboard**: {keyboard_profile.keyboard_name}
- **Vendor**: {keyboard_profile.keyboard_config.vendor}
- **Key Count**: {keyboard_profile.keyboard_config.key_count}
- **Generated**: Dynamically by Glovebox

## Building

This workspace uses the ZMK build system with west.

```bash
# Initialize workspace
west init -l config

# Update dependencies
west update

# Export Zephyr for CMake
west zephyr-export

# Build firmware
west build -s zmk/app -p always -b nice_nano_v2 -d build/left -- -DSHIELD={keyboard_profile.keyboard_name}_left
west build -s zmk/app -p always -b nice_nano_v2 -d build/right -- -DSHIELD={keyboard_profile.keyboard_name}_right
```

## Generated by Glovebox

This workspace was automatically generated by [Glovebox](https://github.com/your-repo/glovebox)
for dynamic ZMK firmware compilation.
"""

    def update_for_layout_changes(
        self,
        workspace_path: Path,
        keymap_file: Path,
        config_file: Path,
        shield_name: str,
    ) -> bool:
        """Update workspace files when layout changes.

        Args:
            workspace_path: Path to workspace
            keymap_file: Updated keymap file
            config_file: Updated config file
            shield_name: Shield name for file naming

        Returns:
            bool: True if update successful
        """
        try:
            self.logger.info("Updating ZMK config workspace for layout changes")

            # Update keymap and config files in workspace
            return self._setup_config_directory(
                workspace_path, keymap_file, config_file, shield_name
            )

        except Exception as e:
            msg = f"Failed to update ZMK config workspace: {e}"
            self.logger.error(msg)
            raise ZmkConfigGenerationError(msg) from e


def create_zmk_config_content_generator(
    file_adapter: FileAdapter | None = None,
) -> ZmkConfigContentGenerator:
    """Create ZMK config content generator instance.

    Args:
        file_adapter: File operations adapter

    Returns:
        ZmkConfigContentGenerator: New generator instance
    """
    return ZmkConfigContentGenerator(file_adapter=file_adapter)
