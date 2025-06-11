"""User configuration models."""

from pathlib import Path
from typing import Annotated, Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from .firmware import UserFirmwareConfig
from .workspace import UserArtifactConfig, UserCompilationConfig, UserWorkspaceConfig


class UserConfigData(BaseSettings):
    """User configuration data model with automatic environment variable support.

    This model represents user-specific configuration settings with validation
    and automatic environment variable parsing.

    Precedence order (highest to lowest):
    1. Environment variables (highest)
    2. Constructor arguments (file data)
    3. .env file
    4. Default values (lowest)
    """

    model_config = SettingsConfigDict(
        env_prefix="GLOVEBOX_",
        env_nested_delimiter="__",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        json_schema_extra={
            "env_ignore_empty": True,
        },
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: Any,
        env_settings: Any,
        dotenv_settings: Any,
        file_secret_settings: Any,
    ) -> tuple[Any, ...]:
        """
        Customize the sources and their precedence order.

        Returns sources in priority order: env > init > dotenv > file_secret
        This ensures environment variables override file configuration.
        """
        return (
            env_settings,  # Highest precedence: environment variables
            init_settings,  # Second: constructor arguments (file data)
            dotenv_settings,  # Third: .env file
            file_secret_settings,  # Lowest: file secrets
        )

    keyboard_paths: Annotated[list[Path], NoDecode] = []

    # Paths for user-defined keyboards and layouts (stored as string, accessed as list[Path])
    @field_validator("keyboard_paths", mode="before")
    @classmethod
    def decode_keyboard_paths(cls, v: Any) -> list[Path]:
        if isinstance(v, str):
            return [Path(path.strip()) for path in v.split(",") if path.strip()]
        elif isinstance(v, list):
            return [
                Path(path.strip() if isinstance(path, str) else path)
                for path in v
                if str(path).strip()
            ]
        return []

    # Default profile (keyboard/firmware combination)
    profile: str = Field(
        default="glove80/v25.05",
        description="Default keyboard/firmware profile (e.g., 'glove80/v25.05')",
    )

    # Logging
    log_level: str = "INFO"

    # Firmware settings
    firmware: UserFirmwareConfig = Field(default_factory=UserFirmwareConfig)

    # Compilation settings
    compilation: UserCompilationConfig = Field(default_factory=UserCompilationConfig)

    @field_validator("profile")
    @classmethod
    def validate_profile(cls, v: str) -> str:
        """Validate profile follows keyboard/firmware or keyboard-only format."""
        if not v or not v.strip():
            raise ValueError(
                "Profile must be in format 'keyboard/firmware' (e.g., 'glove80/v25.05') or 'keyboard' (e.g., 'glove80')"
            )

        # Handle keyboard-only format (no slash)
        if "/" not in v:
            if not v.strip():
                raise ValueError("Keyboard name cannot be empty")
            return v.strip()

        # Handle keyboard/firmware format
        parts = v.split("/")
        if len(parts) != 2 or not all(part.strip() for part in parts):
            raise ValueError(
                "Profile must be in format 'keyboard/firmware' (e.g., 'glove80/v25.05') or 'keyboard' (e.g., 'glove80')"
            )

        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is a recognized value."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        # Strip whitespace and convert to uppercase
        upper_v = v.strip().upper()
        if upper_v not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return upper_v  # Always normalize to uppercase
