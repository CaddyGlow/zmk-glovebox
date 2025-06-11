"""West manifest and commands configuration models based on official schemas.

Models based on:
- https://github.com/zephyrproject-rtos/west/blob/main/src/west/manifest-schema.yml
- https://github.com/zephyrproject-rtos/west/blob/main/src/west/west-commands-schema.yml
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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
