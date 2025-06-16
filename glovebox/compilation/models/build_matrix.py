"""Gihub Actions build matrix models for ZMK compilation.
https://github.com/zmkfirmware/unified-zmk-config-template/blob/main/build.yaml
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class BuildTarget(BaseModel):
    """Individual build target configuration from build.yaml.

    Pydantic model version for validation and serialization.
    """

    board: str
    shield: str | None = None
    cmake_args: list[str] = Field(default_factory=list)
    snippet: str | None = None
    artifact_name_: str | None = Field(default=None, alias="artifact_name")

    @property
    def artifact_name(self) -> str:
        """Get artifact name, computing if not explicitly set.

        Returns computed name following GitHub Actions pattern:
        <board>-<shield>-zmk or just <board>-zmk if no shield

        Returns:
            str: Artifact name (explicit or computed)
        """
        if self.artifact_name_ is not None:
            return self.artifact_name_

        return f"{self.name}-zmk"

    @artifact_name.setter
    def artifact_name(self, value: str | None) -> None:
        """Set explicit artifact name."""
        self.artifact_name_ = value

    @property
    def name(self) -> str:
        """Get target name."""
        if self.shield:
            return f"{self.board}-{self.shield}"
        return self.board


class BuildMatrix(BaseModel):
    """Configuration parsed from ZMK config repository build.yaml.

    Compatible with GitHub Actions workflow build matrix format.
    """

    board: list[str] | None = Field(default_factory=list)
    shield: list[str] | None = Field(default_factory=list)
    include: list[BuildTarget] | None = Field(default_factory=list)

    @property
    def targets(self) -> list[BuildTarget]:
        targets: list[BuildTarget] = []
        targets.extend(self.include if self.include else [])
        if len(targets) == 0:
            targets.extend(self._default_combinations())
        return targets

    def _default_combinations(
        self,
    ) -> list[BuildTarget]:
        """Generate board/shield combinations.

        Args:
            config: Build configuration with defaults

        Returns:
            list[BuildTarget]: Generated build targets
        """
        targets: list[BuildTarget] = []
        boards = self.board or []
        shields = self.shield or []

        # If shields specified, create board+shield combinations
        for board in boards:
            for shield in shields:
                targets.append(BuildTarget(board=board, shield=shield))
        else:
            # No shields, just boards
            for board in boards:
                targets.append(BuildTarget(board=board))

        return targets

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "BuildMatrix":
        """Load BuildMatrix from YAML file."""
        import yaml

        with yaml_path.open("r") as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def to_yaml(self, yaml_path: Path) -> None:
        """Save BuildMatrix to YAML file, explicitly including None fields."""

        data = self.model_dump()

        # Filter out None values in YAML output
        data = {k: v for k, v in data.items() if v is not None}

        with yaml_path.open("w") as f:
            yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)
