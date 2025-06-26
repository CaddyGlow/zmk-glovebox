"""Base MoErgo API client with authentication and core methods."""

import json
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

import requests

from glovebox.config.models.moergo import MoErgoServiceConfig
from glovebox.core.cache import create_cache_from_user_config
from glovebox.core.cache.cache_manager import CacheManager

from .auth import create_cognito_auth, Glove80Auth
from .credentials import create_credential_manager, CredentialManager
from .models import (
    APIError,
    AuthenticationError,
    AuthTokens,
    NetworkError,
    UserCredentials,
    ValidationError,
)


class MoErgoBaseClient:
    """Base client for MoErgo API with authentication and core functionality."""

    def __init__(
        self,
        credential_manager: CredentialManager | None = None,
        cache: CacheManager | None = None,
        moergo_config: MoErgoServiceConfig | None = None,
    ):
        self.config = moergo_config or MoErgoServiceConfig()
        self.credential_manager = credential_manager or create_credential_manager(
            self.config.credentials
        )
        self.auth_client = create_cognito_auth(self.config.cognito)
        self.session = requests.Session()
        self._tokens: AuthTokens | None = None
        self._cache = cache
        self._initialize_session()

    @property
    def base_url(self) -> str:
        """Get the base URL for the MoErgo API."""
        return f"{self.config.api_base_url.rstrip('/')}/api/"

    def _initialize_session(self) -> None:
        """Initialize the session with common headers."""
        # Set common headers
        self.session.headers.update(
            {
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
                "referer": self.config.cognito.referer_url,
                "sec-ch-ua": '"Not.A/Brand";v="99", "Chromium";v="136"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Linux"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
                "user-agent": self.config.cognito.user_agent,
            }
        )

    def _get_full_url(self, endpoint: str) -> str:
        """Get full URL for API endpoint."""
        return urljoin(self.base_url, endpoint)

    def _handle_response(self, response: requests.Response) -> Any:
        """Handle API response and raise appropriate exceptions."""
        try:
            response.raise_for_status()

            # Handle 204 No Content responses
            if response.status_code == 204:
                return {"success": True, "status": "no_content"}

            # Handle empty responses
            if not response.content.strip():
                return {"success": True, "status": "empty_response"}

            # Try to parse JSON response
            try:
                return response.json()
            except ValueError as json_error:
                # If JSON parsing fails, provide more context about the response
                content_preview = response.text[:200] if response.text else "(empty)"
                raise APIError(
                    f"Server returned invalid JSON response. Status: {response.status_code}, "
                    f"Content-Type: {response.headers.get('content-type', 'unknown')}, "
                    f"Content preview: {content_preview}"
                ) from json_error
        except requests.exceptions.HTTPError as e:

            def safe_json_parse(resp: requests.Response) -> Any:
                """Safely parse JSON response, returning None if parsing fails."""
                if not resp.content:
                    return None
                try:
                    return resp.json()
                except (ValueError, TypeError):
                    return None

            if response.status_code == 401:
                raise AuthenticationError(
                    "Authentication failed",
                    status_code=response.status_code,
                    response_data=safe_json_parse(response),
                ) from e
            elif response.status_code == 400:
                raise ValidationError(
                    f"Request validation failed: {response.text}",
                    status_code=response.status_code,
                    response_data=safe_json_parse(response),
                ) from e
            else:
                raise APIError(
                    f"API request failed: {e}",
                    status_code=response.status_code,
                    response_data=safe_json_parse(response),
                ) from e
        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Network error: {e}") from e

    def _is_token_expired(self) -> bool:
        """Check if current token is expired."""
        if not self._tokens:
            return True

        # Add 5 minute buffer
        expires_at = self._tokens.expires_at - 300
        return datetime.now().timestamp() > expires_at

    def _ensure_authenticated(self) -> None:
        """Ensure client is authenticated with valid tokens."""
        # Try to load existing tokens
        if not self._tokens:
            self._tokens = self.credential_manager.load_tokens()

        # Check if token is valid
        if not self._tokens or self._is_token_expired():
            self._authenticate()

        # Update session headers with token
        if self._tokens:
            self.session.headers.update(
                {
                    "Authorization": f"{self._tokens.token_type} {self._tokens.access_token}",
                    "X-ID-Token": self._tokens.id_token,  # Some endpoints might need ID token
                }
            )

    def _authenticate(self) -> None:
        """Perform authentication flow with refresh token priority."""
        # Try refresh token first if we have existing tokens
        if self._tokens and self._tokens.refresh_token:
            try:
                result = self.auth_client.refresh_token(self._tokens.refresh_token)
                if result and "AuthenticationResult" in result:
                    auth_result = result["AuthenticationResult"]
                    # Refresh tokens don't return new refresh tokens by default
                    # Keep the existing one unless a new one is provided
                    new_refresh_token = auth_result.get(
                        "RefreshToken", self._tokens.refresh_token
                    )

                    self._tokens = AuthTokens(
                        access_token=auth_result["AccessToken"],
                        refresh_token=new_refresh_token,
                        id_token=auth_result["IdToken"],
                        token_type=auth_result.get("TokenType", "Bearer"),
                        expires_in=auth_result["ExpiresIn"],
                    )

                    # Store tokens for future use
                    self.credential_manager.store_tokens(self._tokens)
                    return
            except Exception:
                # If refresh fails, fall through to full authentication
                pass

        # Fall back to full authentication if refresh fails or no refresh token
        credentials = self.credential_manager.load_credentials()
        if not credentials:
            raise AuthenticationError(
                "No stored credentials found. Please login first."
            )

        # Try simple password auth
        try:
            result = self.auth_client.simple_login_attempt(
                credentials.username, credentials.password
            )
            if result and "AuthenticationResult" in result:
                auth_result = result["AuthenticationResult"]
                self._tokens = AuthTokens(
                    access_token=auth_result["AccessToken"],
                    refresh_token=auth_result["RefreshToken"],
                    id_token=auth_result["IdToken"],
                    token_type=auth_result.get("TokenType", "Bearer"),
                    expires_in=auth_result["ExpiresIn"],
                )

                # Store tokens for future use
                self.credential_manager.store_tokens(self._tokens)
                return
        except Exception:
            pass  # Fall through to SRP auth

        # If simple auth fails, we need SRP implementation
        # For now, raise an error indicating SRP is needed
        raise AuthenticationError(
            "Simple password authentication failed. SRP authentication not yet implemented. "
            "Please check your credentials or contact support."
        )

    def login(self, username: str, password: str) -> None:
        """Login and store credentials securely."""
        credentials = UserCredentials(username=username, password=password)

        # Test authentication before storing
        result = self.auth_client.simple_login_attempt(username, password)

        if not result or "AuthenticationResult" not in result:
            raise AuthenticationError("Login failed. Please check your credentials.")

        # Store credentials if authentication succeeds
        self.credential_manager.store_credentials(credentials)

        # Store tokens
        auth_result = result["AuthenticationResult"]
        self._tokens = AuthTokens(
            access_token=auth_result["AccessToken"],
            refresh_token=auth_result["RefreshToken"],
            id_token=auth_result["IdToken"],
            token_type=auth_result.get("TokenType", "Bearer"),
            expires_in=auth_result["ExpiresIn"],
        )

        self.credential_manager.store_tokens(self._tokens)

    def logout(self) -> None:
        """Clear stored credentials and tokens."""
        self.credential_manager.clear_credentials()
        self._tokens = None
        if "Authorization" in self.session.headers:
            del self.session.headers["Authorization"]

    def is_authenticated(self) -> bool:
        """Check if client is currently authenticated with valid tokens."""
        try:
            self._ensure_authenticated()
            return True
        except AuthenticationError:
            return False

    def get_credential_info(self) -> dict[str, Any]:
        """Get information about stored credentials."""
        return self.credential_manager.get_storage_info()

    def clear_cache(self) -> None:
        """Clear all cached API responses."""
        if self._cache:
            self._cache.clear()

    def renew_token_if_needed(self, buffer_minutes: int = 10) -> bool:
        """
        Proactively renew tokens if they're close to expiring.

        Useful for long-running processes that want to avoid token expiration
        during operations.

        Args:
            buffer_minutes: Renew token if it expires within this many minutes

        Returns:
            True if token was renewed, False if renewal wasn't needed
        """
        if not self._tokens:
            self._tokens = self.credential_manager.load_tokens()

        if not self._tokens:
            return False

        # Check if token expires within buffer period
        buffer_seconds = buffer_minutes * 60
        expires_at = self._tokens.expires_at - buffer_seconds

        if datetime.now().timestamp() > expires_at:
            try:
                self._authenticate()
                return True
            except AuthenticationError:
                # If renewal fails, let it fail on next actual API call
                return False

        return False

    def get_token_info(self) -> dict[str, Any]:
        """
        Get information about current tokens.

        Returns:
            Dict with token status information
        """
        if not self._tokens:
            self._tokens = self.credential_manager.load_tokens()

        if not self._tokens:
            return {
                "authenticated": False,
                "expires_at": None,
                "expires_in_minutes": None,
                "needs_renewal": True,
            }

        expires_at_dt = datetime.fromtimestamp(self._tokens.expires_at)
        expires_in_seconds = self._tokens.expires_at - datetime.now().timestamp()
        expires_in_minutes = max(0, expires_in_seconds / 60)

        return {
            "authenticated": True,
            "expires_at": expires_at_dt.isoformat(),
            "expires_in_minutes": round(expires_in_minutes, 1),
            "needs_renewal": expires_in_minutes < 5,
        }
