"""Workspace and compilation configuration models."""

import tempfile
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class UserWorkspaceConfig(BaseModel):
    """User workspace configuration for compilation operations."""

    # Base directory for temporary workspaces
    root_directory: Path = Field(
        default_factory=lambda: Path(tempfile.gettempdir()) / "glovebox-workspaces",
        description="Base directory for temporary workspaces",
    )

    # Whether to remove workspace after compilation
    cleanup_after_build: bool = Field(
        default=True, description="Whether to remove workspace after compilation"
    )

    # Whether to preserve workspace on build failure for debugging
    preserve_on_failure: bool = Field(
        default=False,
        description="Whether to preserve workspace on build failure for debugging",
    )

    # Maximum number of old workspaces to keep
    max_preserved_workspaces: int = Field(
        default=5, description="Maximum number of old workspaces to keep", ge=0
    )

    @field_validator("root_directory", mode="before")
    @classmethod
    def expand_root_directory(cls, v: str | Path) -> Path:
        """Expand and resolve the root directory path."""
        if isinstance(v, str):
            v = Path(v)
        return v.expanduser().resolve()


class UserArtifactConfig(BaseModel):
    """User artifact configuration for build output management."""

    # Artifact naming strategy
    naming_strategy: Literal["zmk_github_actions", "descriptive", "preserve"] = Field(
        default="zmk_github_actions", description="Artifact naming strategy to use"
    )


class UserCompilationConfig(BaseModel):
    """User compilation configuration combining workspace and artifact settings."""

    # Workspace configuration
    workspace: UserWorkspaceConfig = Field(
        default_factory=UserWorkspaceConfig,
        description="Workspace management configuration",
    )

    # Artifact configuration
    artifacts: UserArtifactConfig = Field(
        default_factory=UserArtifactConfig,
        description="Artifact handling configuration",
    )
