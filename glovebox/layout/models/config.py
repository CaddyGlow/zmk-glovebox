"""Configuration models for layout settings."""

from pydantic import Field

from glovebox.models.base import GloveboxBaseModel

from .types import ConfigValue


class ConfigParameter(GloveboxBaseModel):
    """Model for configuration parameters."""

    param_name: str = Field(alias="paramName")
    value: ConfigValue
    description: str | None = None
