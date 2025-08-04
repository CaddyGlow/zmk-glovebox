"""Models for MoErgo API client."""

from datetime import datetime
from typing import Any

from pydantic import Field

from glovebox.layout.models import LayoutData
from glovebox.models.base import GloveboxBaseModel


class LayoutMeta(GloveboxBaseModel):
    """Layout metadata from MoErgo API response."""

    uuid: str
    date: int
    creator: str
    parent_uuid: str | None = None
    firmware_api_version: str
    title: str
    notes: str = ""
    tags: list[str] = Field(default_factory=list)
    unlisted: bool = False
    deleted: bool = False
    compiled: bool = False
    searchable: bool = True

    @property
    def created_datetime(self) -> datetime:
        """Convert timestamp to datetime."""
        return datetime.fromtimestamp(self.date)


class MoErgoLayout(GloveboxBaseModel):
    """Complete layout response from MoErgo API."""

    layout_meta: LayoutMeta
    config: LayoutData


class AuthTokens(GloveboxBaseModel):
    """Authentication tokens from Cognito."""

    access_token: str
    refresh_token: str
    id_token: str
    token_type: str = "Bearer"
    expires_in: int

    @property
    def expires_at(self) -> float:
        """Calculate token expiration time as timestamp."""
        return datetime.now().timestamp() + self.expires_in


class UserCredentials(GloveboxBaseModel):
    """User login credentials."""

    username: str
    password: str


class APIError(Exception):
    """Base exception for MoErgo API errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_data: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class AuthenticationError(APIError):
    """Authentication-related errors."""

    pass


class NetworkError(APIError):
    """Network-related errors."""

    pass


class ValidationError(APIError):
    """Request validation errors."""

    pass


class TimeoutError(APIError):
    """Request timeout errors."""

    pass


class CompilationError(APIError):
    """Firmware compilation errors."""

    def __init__(
        self,
        message: str,
        detail: list[str] | None = None,
        status_code: int | None = None,
        response_data: dict[str, Any] | None = None,
    ):
        super().__init__(message, status_code, response_data)
        self.detail = detail or []


class FirmwareCompileRequest(GloveboxBaseModel):
    """Request payload for firmware compilation."""

    keymap: str
    kconfig: str = ""
    board: str = "glove80"


class FirmwareCompileResponse(GloveboxBaseModel):
    """Response from firmware compilation endpoint."""

    location: str
