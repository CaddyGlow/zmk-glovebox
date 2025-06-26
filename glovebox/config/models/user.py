"""User configuration models."""

import os
from pathlib import Path

# Import bookmark models
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field, field_serializer, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Import for icon mode enum
from glovebox.cli.helpers.theme import IconMode

from .cache import CacheTTLConfig
from .firmware import UserFirmwareConfig


if TYPE_CHECKING:
    from glovebox.layout.models import BookmarkCollection
else:
    # Import at runtime to avoid circular imports
    try:
        from glovebox.layout.models import BookmarkCollection
    except ImportError:
        # Handle case where layout models aren't available yet
        BookmarkCollection = None


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

    profiles_paths: Annotated[list[Path], NoDecode] = []

    # Paths for user-defined keyboards and layouts (stored as string, accessed as list[Path])
    @field_validator("profiles_paths", mode="before")
    @classmethod
    def decode_profiles_paths(cls, v: Any) -> list[Path]:
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
    log_level: str = "WARNING"

    # Version check settings
    disable_version_checks: bool = Field(
        default=False,
        description="Disable automatic version checks for ZMK firmware updates",
    )

    # DeepDiff settings
    # TODO: not in use yet
    # deepdiff_delta_serializer: str = Field(
    #     default="json",
    #     description="Serializer for DeepDiff delta objects: 'json' (default) or 'pickle'",
    # )

    # Cache settings
    cache_path: Path = Field(
        default_factory=lambda: (
            Path(os.environ["XDG_CACHE_HOME"]) / "glovebox"
            if "XDG_CACHE_HOME" in os.environ
            else Path.home() / ".cache" / "glovebox"
        ),
        description="Directory for caching build artifacts and dependencies",
    )
    cache_strategy: str = Field(
        default="shared",
        description="Cache strategy: 'shared' (default) or 'disabled'",
    )

    # Comprehensive cache TTL configuration
    cache_ttls: CacheTTLConfig = Field(
        default_factory=lambda: CacheTTLConfig(),  # type: ignore[call-arg]
        description="TTL configuration for all cache types across domains",
    )

    # UI settings
    icon_mode: "IconMode" = Field(
        default=IconMode.EMOJI,
        description="Icon display mode: 'emoji' (default), 'nerdfont', or 'text'",
    )

    # Editor settings
    editor: str = Field(
        default_factory=lambda: os.environ.get("EDITOR", "nano"),
        description="Default text editor for interactive config editing (defaults to $EDITOR or 'nano')",
    )

    # Firmware settings
    firmware: UserFirmwareConfig = Field(default_factory=UserFirmwareConfig)

    # Layout bookmarks
    layout_bookmarks: "BookmarkCollection | None" = Field(
        default=None, description="Collection of saved layout bookmarks for easy access"
    )

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

    # @field_validator("deepdiff_delta_serializer")
    # @classmethod
    # def validate_deepdiff_delta_serializer(cls, v: str) -> str:
    #     """Validate DeepDiff delta serializer is a recognized value."""
    #     valid_serializers = ["json", "pickle"]
    #     # Strip whitespace and convert to lowercase
    #     lower_v = v.strip().lower()
    #     if lower_v not in valid_serializers:
    #         raise ValueError(
    #             f"DeepDiff delta serializer must be one of {valid_serializers}"
    #         )
    #     return lower_v  # Always normalize to lowercase

    @field_validator("cache_path", mode="before")
    @classmethod
    def validate_cache_path(cls, v: Any) -> Path:
        """Validate and expand cache path, respecting XDG_CACHE_HOME."""
        if isinstance(v, str):
            # Handle string paths by expanding user home directory
            path = Path(v).expanduser()
        elif isinstance(v, Path):
            path = v.expanduser()
        else:
            # Use default XDG cache logic
            xdg_cache = os.environ.get("XDG_CACHE_HOME")
            if xdg_cache:
                path = Path(xdg_cache) / "glovebox"
            else:
                path = Path.home() / ".cache" / "glovebox"

        return path.resolve()

    @field_validator("cache_strategy")
    @classmethod
    def validate_cache_strategy(cls, v: str) -> str:
        """Validate cache strategy is a recognized value."""
        valid_strategies = ["shared", "disabled"]
        # Strip whitespace and convert to lowercase
        lower_v = v.strip().lower()
        if lower_v not in valid_strategies:
            raise ValueError(f"Cache strategy must be one of {valid_strategies}")
        return lower_v  # Always normalize to lowercase

    @field_validator("icon_mode", mode="before")
    @classmethod
    def validate_icon_mode(cls, v: Any) -> "IconMode":
        """Validate and convert icon mode to IconMode enum."""
        if isinstance(v, IconMode):
            return v
        if isinstance(v, str):
            # Strip whitespace and convert to lowercase
            lower_v = v.strip().lower()
            try:
                return IconMode(lower_v)
            except ValueError:
                valid_modes = [mode.value for mode in IconMode]
                raise ValueError(f"Icon mode must be one of {valid_modes}") from None
        raise ValueError(f"Icon mode must be a string or IconMode enum, got {type(v)}")

    @field_serializer("icon_mode", when_used="json")
    def serialize_icon_mode(self, value: "IconMode") -> str:
        """Serialize IconMode enum to string for config file storage."""
        return value.value


# Rebuild model to resolve forward references
if not TYPE_CHECKING and BookmarkCollection is not None:
    UserConfigData.model_rebuild()
