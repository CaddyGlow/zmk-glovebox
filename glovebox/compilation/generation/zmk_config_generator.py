"""ZMK Config content generator for dynamic workspace creation."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from glovebox.adapters import FileAdapter
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
    ) -> bool:
        """Generate complete ZMK config workspace from glovebox files.

        Args:
            workspace_path: Directory to create workspace in
            keymap_file: Source keymap file
            config_file: Source config file
            keyboard_profile: Keyboard profile for build configuration
            shield_name: Shield name (defaults to keyboard name)
            board_name: Board name for builds

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
            if not self._generate_west_yml(workspace_path, keyboard_profile):
                return False

            # Create config directory and copy keymap/config files
            if not self._setup_config_directory(
                workspace_path, keymap_file, config_file, effective_shield
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
        """Create build.yaml content for split keyboard.

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

        if is_split:
            # Generate split keyboard build targets with appropriate suffixes
            if "glove80" in shield_name.lower():
                # Glove80 uses board array format (boards, not shields)
                return f"""# ZMK Build Configuration - Generated by Glovebox
# This file generates the GitHub Actions matrix
# For simple board + shield combinations, add them
# to the top level board and shield arrays, for more
# control, add individual board + shield combinations to
# the `include` property, e.g:
#
board: [ "{shield_name}_lh", "{shield_name}_rh" ]
"""
            else:
                # Standard ZMK split keyboards use include format with shields
                left_suffix = "_left"
                right_suffix = "_right"
                return f"""# ZMK Build Configuration - Generated by Glovebox
include:
  - board: {board_name}
    shield: {shield_name}{left_suffix}
  - board: {board_name}
    shield: {shield_name}{right_suffix}
"""
        else:
            # Generate single keyboard build target
            return f"""# ZMK Build Configuration - Generated by Glovebox
include:
  - board: {board_name}
    shield: {shield_name}
"""

    def _generate_west_yml(
        self, workspace_path: Path, keyboard_profile: "KeyboardProfile"
    ) -> bool:
        """Generate west.yml for ZMK workspace configuration.

        Args:
            workspace_path: Path to workspace
            keyboard_profile: Keyboard profile to determine ZMK repository

        Returns:
            bool: True if west.yml generated successfully
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

            west_yml_content = f"""# West configuration for ZMK - Generated by Glovebox
manifest:
  defaults:
    remote: {org_name}
  remotes:
    - name: {org_name}
      url-base: https://github.com/{org_name}
  projects:
    - name: {repo_name}
      remote: {org_name}
      revision: {branch}
      import: app/west.yml
  self:
    path: config
"""
        elif "glove80" in keyboard_profile.keyboard_name.lower():
            # Fallback: Glove80 uses MoErgo's ZMK fork
            west_yml_content = """# West configuration for ZMK - Generated by Glovebox
manifest:
  remotes:
    - name: moergo-sc
      url-base: https://github.com/moergo-sc
  projects:
    - name: zmk
      remote: moergo-sc
      revision: main
      import: app/west.yml
  self:
    path: config
"""
        else:
            # Fallback: Standard ZMK repository for other keyboards
            west_yml_content = """# West configuration for ZMK - Generated by Glovebox
manifest:
  defaults:
    remote: zmkfirmware
  remotes:
    - name: zmkfirmware
      url-base: https://github.com/zmkfirmware
  projects:
    - name: zmk
      remote: zmkfirmware
      revision: main
      import: app/west.yml
  self:
    path: config
"""

        west_yml_path = workspace_path / "config" / "west.yml"

        try:
            # Ensure config directory exists
            config_dir = workspace_path / "config"
            if self.file_adapter:
                self.file_adapter.create_directory(config_dir)
            else:
                config_dir.mkdir(parents=True, exist_ok=True)

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

    def _setup_config_directory(
        self,
        workspace_path: Path,
        keymap_file: Path,
        config_file: Path,
        shield_name: str,
    ) -> bool:
        """Setup config directory with keymap and config files.

        Args:
            workspace_path: Path to workspace
            keymap_file: Source keymap file
            config_file: Source config file
            shield_name: Shield name for file naming

        Returns:
            bool: True if config directory setup successfully
        """
        config_dir = workspace_path / "config"

        try:
            # Ensure config directory exists
            if self.file_adapter:
                self.file_adapter.create_directory(config_dir)
            else:
                config_dir.mkdir(parents=True, exist_ok=True)

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
