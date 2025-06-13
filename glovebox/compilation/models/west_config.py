"""West manifest and commands configuration models based on official schemas.

Models based on:
- https://github.com/zephyrproject-rtos/west/blob/main/src/west/manifest-schema.yml
- https://github.com/zephyrproject-rtos/west/blob/main/src/west/west-commands-schema.yml
"""

import configparser
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


# West command specification
class WestCommand(BaseModel):
    """West command specification."""

    name: str | None = None
    class_: str | None = Field(default=None, serialization_alias="class")
    help: str | None = None


class WestCommandsFile(BaseModel):
    """West commands file specification."""

    file: str
    commands: list[WestCommand]


class WestCommandsConfig(BaseModel):
    """West commands configuration from west-commands.yml."""

    west_commands: list[WestCommandsFile] = Field(serialization_alias="west-commands")


class WestRemote(BaseModel):
    """West remote configuration."""

    name: str
    url_base: str = Field(serialization_alias="url-base")


class WestProject(BaseModel):
    """West project configuration."""

    name: str
    remote: str | None = None
    repo_path: str | None = Field(default=None, serialization_alias="repo-path")
    revision: str = "main"
    path: str | None = None
    clone_depth: int | None = Field(default=None, serialization_alias="clone-depth")
    west_commands: str | None = Field(default=None, serialization_alias="west-commands")
    import_: str | list[str] | dict[str, Any] | None = Field(
        default=None, serialization_alias="import"
    )
    groups: list[str] | None = None


class WestDefaults(BaseModel):
    """West defaults configuration."""

    remote: str | None = None
    revision: str = "main"


class WestSelf(BaseModel):
    """West self configuration for manifest repository."""

    path: str | None = None
    west_commands: str | None = Field(default=None, serialization_alias="west-commands")
    import_: str | list[str] | dict[str, Any] | None = Field(
        default=None, serialization_alias="import"
    )
    model_config = {
        "populate_by_name": True,
    }


class WestManifest(BaseModel):
    """West manifest configuration."""

    defaults: WestDefaults | None = None
    remotes: list[WestRemote] | None = None
    projects: list[WestProject] | None = None
    self: WestSelf | None = None
    group_filter: list[str] | None = Field(
        default=None, serialization_alias="group-filter"
    )
    model_config = {
        "populate_by_name": True,
    }


class WestManifestConfig(BaseModel):
    """Complete west.yml manifest configuration."""

    version: str | None = None
    manifest: WestManifest


@dataclass
class WestManifestSection:
    """West manifest section configuration for .west/config file."""

    path: str = "config"
    file: str = "west.yml"


@dataclass
class WestZephyrSection:
    """West zephyr section configuration for .west/config file."""

    base: str = "zephyr"


@dataclass
class WestWorkspaceConfig:
    """West workspace configuration for .west/config file.

    This handles the .west/config INI file that configures west workspace settings,
    separate from the west.yml manifest file.
    """

    manifest: WestManifestSection
    zephyr: WestZephyrSection

    def to_ini_string(self) -> str:
        """Serialize to INI format string.

        Returns:
            str: INI format content for .west/config file
        """
        config = configparser.ConfigParser()

        # Add manifest section
        config.add_section("manifest")
        config.set("manifest", "path", self.manifest.path)
        config.set("manifest", "file", self.manifest.file)

        # Add zephyr section
        config.add_section("zephyr")
        config.set("zephyr", "base", self.zephyr.base)

        # Write to string
        output = StringIO()
        config.write(output)
        return output.getvalue()

    @classmethod
    def from_ini_file(cls, config_path: Path) -> "WestWorkspaceConfig":
        """Load from .west/config file.

        Args:
            config_path: Path to .west/config file

        Returns:
            WestWorkspaceConfig: Loaded configuration
        """
        config = configparser.ConfigParser()
        config.read(config_path)

        return cls(
            manifest=WestManifestSection(
                path=config.get("manifest", "path"), file=config.get("manifest", "file")
            ),
            zephyr=WestZephyrSection(base=config.get("zephyr", "base")),
        )

    @classmethod
    def create_default(
        cls, config_path: str = "config", zephyr_base: str = "zephyr"
    ) -> "WestWorkspaceConfig":
        """Create default west workspace config.

        Args:
            config_path: Path to config directory relative to workspace
            zephyr_base: Path to zephyr directory relative to workspace

        Returns:
            WestWorkspaceConfig: Default configuration
        """
        return cls(
            manifest=WestManifestSection(path=config_path),
            zephyr=WestZephyrSection(base=zephyr_base),
        )
