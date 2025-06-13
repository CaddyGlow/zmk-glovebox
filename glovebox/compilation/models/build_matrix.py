"""Build matrix models for ZMK compilation."""

from dataclasses import dataclass, field
from typing import Any

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

    board: list[str] | None = Field(default_factory=list)
    shield: list[str] | None = Field(default_factory=list)
    include: list[dict[str, Any]] | None = Field(default_factory=list)

    def get_board_name(self) -> str | None:
        """Extract board name from Github Actions build matrix.

        Returns:
            str | None: Board name for compilation, or None if no board found
        """
        if self.board and len(self.board):
            return self.board[0]
        if self.include and len(self.include):
            # Extract board from first include entry
            first_include = self.include[0]
            return first_include.get("board")
        return None

    def get_shields(self) -> list[str]:
        """Extract shield names from Github Actions build matrix.

        Returns:
            list[str]: List of shield names for compilation
        """
        result = []

        # Add shields from shield list
        if self.shield:
            result.extend(self.shield)

        # Add shields from include entries
        if self.include:
            for target in self.include:
                shield = target.get("shield")
                if shield is not None:
                    result.append(shield)

        return result


class BuildTargetConfig(BaseModel):
    """Individual build target configuration from build.yaml.

    Pydantic model version for validation and serialization.
    """

    board: str
    shield: str | None = None
    cmake_args: list[str] = Field(default_factory=list)
    snippet: str | None = None
    artifact_name: str | None = None
