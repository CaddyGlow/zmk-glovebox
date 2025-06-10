"""Build matrix models for ZMK compilation."""

from dataclasses import dataclass, field

from pydantic import BaseModel, Field


@dataclass
class BuildTarget:
    """Individual build target from build.yaml.

    Represents a single compilation target with board, shield,
    and configuration options following GitHub Actions pattern.
    """

    board: str
    shield: str | None = None
    cmake_args: list[str] = field(default_factory=list)
    snippet: str | None = None
    artifact_name: str | None = None


@dataclass
class BuildMatrix:
    """Complete build matrix resolved from build.yaml.

    Contains all build targets and default configurations
    for ZMK compilation matrix builds.
    """

    targets: list[BuildTarget] = field(default_factory=list)
    board_defaults: list[str] = field(default_factory=list)
    shield_defaults: list[str] = field(default_factory=list)


class BuildYamlConfig(BaseModel):
    """Configuration parsed from ZMK config repository build.yaml.

    Compatible with GitHub Actions workflow build matrix format.
    """

    board: list[str] = Field(default_factory=list)
    shield: list[str] = Field(default_factory=list)
    include: list[BuildTarget] = Field(default_factory=list)


class BuildTargetConfig(BaseModel):
    """Individual build target configuration from build.yaml.

    Pydantic model version for validation and serialization.
    """

    board: str
    shield: str | None = None
    cmake_args: list[str] = Field(default_factory=list)
    snippet: str | None = None
    artifact_name: str | None = None
