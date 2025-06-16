"""West manifest and commands configuration models based on official schemas.

Models based on:
- https://github.com/zephyrproject-rtos/west/blob/main/src/west/manifest-schema.yml
- https://github.com/zephyrproject-rtos/west/blob/main/src/west/west-commands-schema.yml
"""

import configparser
import yaml
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

    def to_yaml(self) -> str:
        """Serialize manifest to YAML string.

        Returns:
            str: YAML representation of the manifest
        """
        return yaml.safe_dump(
            self.model_dump(by_alias=True, exclude_none=True),
            default_flow_style=False,
            sort_keys=False,
        )

    @classmethod
    def from_yaml(cls, yaml_content: str) -> "WestManifest":
        """Create WestManifest from YAML string.

        Args:
            yaml_content: YAML string content

        Returns:
            WestManifest: Parsed manifest
        """
        data = yaml.safe_load(yaml_content)
        return cls(**data)

    @classmethod
    def from_repository_config(
        cls,
        repository: str,
        branch: str = "main",
        config_path: str = "config",
        import_file: str = "app/west.yml",
    ) -> "WestManifest":
        """Create west manifest from repository and branch information.

        Args:
            repository: Repository specification (e.g., 'zmkfirmware/zmk-config' or full URL)
            branch: Git branch/revision to use

        Returns:
            WestManifest: Configured manifest
        """
        # Parse repository to get remote info
        # TODO: algo to be confirmed
        # TODO: should use the repository setter
        if "/" in repository:
            if repository.startswith("https://github.com/"):
                repo_parts = repository.replace("https://github.com/", "").split("/")
            else:
                repo_parts = repository.split("/")
            remote_name = repo_parts[0]
            repo_name = repo_parts[1]
            url_base = f"https://github.com/{remote_name}"
        else:
            remote_name = "zmkfirmware"
            repo_name = repository
            url_base = "https://github.com/zmkfirmware"

        return cls(
            remotes=[WestRemote(name=remote_name, url_base=url_base)],
            projects=[
                WestProject(
                    name=repo_name,
                    remote=remote_name,
                    revision=branch,
                    import_=import_file,
                )
            ],
            self=WestSelf(path=config_path),
        )

    @property
    def repository(self) -> str | None:
        """Get repository specification from first project.

        Returns:
            str | None: Repository specification or None if no projects
        """
        if not self.projects or not self.projects[0].remote:
            return None

        project = self.projects[0]
        remote = next(
            (r for r in (self.remotes or []) if r.name == project.remote), None
        )

        if not remote:
            return None

        # Extract owner from URL base
        if remote.url_base.startswith("https://github.com/"):
            owner = remote.url_base.replace("https://github.com/", "")
            return f"{owner}/{project.name}"

        return project.name

    @repository.setter
    def repository(self, value: str) -> None:
        """Set repository specification, updating remotes and projects.

        Args:
            value: Repository specification (e.g., 'zmkfirmware/zmk-config')
        """
        # Parse repository to get remote info
        if "/" in value:
            if value.startswith("https://github.com/"):
                repo_parts = value.replace("https://github.com/", "").split("/")
            else:
                repo_parts = value.split("/")
            remote_name = repo_parts[0]
            repo_name = repo_parts[1]
            url_base = f"https://github.com/{remote_name}"
        else:
            remote_name = "zmkfirmware"
            repo_name = value
            url_base = "https://github.com/zmkfirmware"

        # Update remotes
        if not self.remotes:
            self.remotes = []

        # Find or create remote
        remote = next((r for r in self.remotes if r.name == remote_name), None)
        if remote:
            remote.url_base = url_base
        else:
            self.remotes.append(WestRemote(name=remote_name, url_base=url_base))

        # Update projects
        if not self.projects:
            self.projects = []

        if self.projects:
            # Update first project
            self.projects[0].name = repo_name
            self.projects[0].remote = remote_name
        else:
            # Create new project
            self.projects.append(
                WestProject(
                    name=repo_name,
                    remote=remote_name,
                    import_="app/west.yml",
                )
            )

    @property
    def branch(self) -> str:
        """Get branch/revision from first project.

        Returns:
            str: Branch/revision, defaults to 'main'
        """
        if self.projects and self.projects[0].revision:
            return self.projects[0].revision
        return "main"

    @branch.setter
    def branch(self, value: str) -> None:
        """Set branch/revision for first project.

        Args:
            value: Branch/revision to set
        """
        if not self.projects:
            self.projects = [WestProject(name="", revision=value)]
        else:
            self.projects[0].revision = value


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
