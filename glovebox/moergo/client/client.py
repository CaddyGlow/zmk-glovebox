"""MoErgo API client for layout management."""

import json
from datetime import datetime, timedelta
from typing import Any, Optional
from urllib.parse import urljoin

import requests

from glovebox.core.cache import CacheKey, create_default_cache

from .auth import Glove80Auth
from .credentials import CredentialManager
from .models import (
    APIError,
    AuthenticationError,
    AuthTokens,
    MoErgoLayout,
    NetworkError,
    UserCredentials,
    ValidationError,
)


class MoErgoClient:
    """Client for interacting with MoErgo Glove80 API."""

    BASE_URL = "https://my.glove80.com/api/"

    def __init__(self, credential_manager: CredentialManager | None = None):
        self.credential_manager = credential_manager or CredentialManager()
        self.auth_client = Glove80Auth()
        self.session = requests.Session()
        self._tokens: AuthTokens | None = None

        # Initialize cache for API responses
        self._cache = create_default_cache()

        # Set common headers
        self.session.headers.update(
            {
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
                "referer": "https://my.glove80.com/",
                "sec-ch-ua": '"Not.A/Brand";v="99", "Chromium";v="136"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Linux"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
                "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            }
        )

    def _get_full_url(self, endpoint: str) -> str:
        """Get full URL for API endpoint."""
        return urljoin(self.BASE_URL, endpoint)

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

            return response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                raise AuthenticationError(
                    "Authentication failed",
                    status_code=response.status_code,
                    response_data=response.json() if response.content else None,
                ) from e
            elif response.status_code == 400:
                raise ValidationError(
                    f"Request validation failed: {response.text}",
                    status_code=response.status_code,
                    response_data=response.json() if response.content else None,
                ) from e
            else:
                raise APIError(
                    f"API request failed: {e}",
                    status_code=response.status_code,
                    response_data=response.json() if response.content else None,
                ) from e
        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Network error: {e}") from e
        except ValueError as e:
            raise APIError(f"Invalid JSON response: {e}") from e

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
        """Perform authentication flow."""
        credentials = self.credential_manager.load_credentials()
        if not credentials:
            raise AuthenticationError(
                "No stored credentials found. Please login first."
            )

        # Try simple password auth first
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
        except Exception as e:
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

    def get_layout(self, layout_uuid: str) -> MoErgoLayout:
        """Get layout configuration by UUID."""
        self._ensure_authenticated()

        endpoint = f"layouts/v1/{layout_uuid}/config"
        try:
            response = self.session.get(self._get_full_url(endpoint))
            data = self._handle_response(response)
            return MoErgoLayout(**data)
        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Network error: {e}") from e

    def get_layout_meta(
        self, layout_uuid: str, use_cache: bool = True
    ) -> dict[str, Any]:
        """Get layout metadata only (without full config) by UUID.

        Args:
            layout_uuid: UUID of the layout
            use_cache: Whether to use cached results (default: True)

        Returns:
            Layout metadata dictionary
        """
        # Generate cache key for this request
        cache_key = CacheKey.from_parts("layout_meta", layout_uuid)

        # Try cache first if enabled
        if use_cache:
            cached_data = self._cache.get(cache_key)
            if cached_data is not None:
                return cached_data  # type: ignore[no-any-return]

        self._ensure_authenticated()

        endpoint = f"layouts/v1/{layout_uuid}/meta"
        try:
            response = self.session.get(self._get_full_url(endpoint))
            data = self._handle_response(response)

            # Cache the result for 1 hour (layout metadata doesn't change often)
            if use_cache:
                self._cache.set(cache_key, data, ttl=3600)

            return data  # type: ignore[no-any-return]
        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Network error: {e}") from e

    def list_user_layouts(self) -> list[dict[str, str]]:
        """List user's layouts with their UUIDs and status."""
        self._ensure_authenticated()

        # Extract user ID from ID token
        import base64

        try:
            # Decode the ID token to get user ID
            assert self._tokens is not None, (
                "Tokens should be available after authentication"
            )
            token_parts = self._tokens.id_token.split(".")
            payload = base64.b64decode(token_parts[1] + "==")  # Add padding
            token_data = json.loads(payload)
            user_id = token_data["sub"]
        except Exception as e:
            raise APIError(f"Failed to extract user ID from token: {e}") from e

        endpoint = f"layouts/v1/users/{user_id}"

        try:
            assert self._tokens is not None, (
                "Tokens should be available after authentication"
            )
            headers = {
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
                "authorization": f"Bearer {self._tokens.id_token}",
                "referer": "https://my.glove80.com/",
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
            }

            response = self.session.get(self._get_full_url(endpoint), headers=headers)

            layout_list = self._handle_response(response)

            # Parse the "uuid:status" format into structured data
            parsed_layouts = []
            for layout_entry in layout_list:
                uuid, status = layout_entry.split(":")
                parsed_layouts.append({"uuid": uuid, "status": status})

            return parsed_layouts

        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Network error: {e}") from e

    def save_layout(
        self, layout_uuid: str, layout_meta: dict[str, Any]
    ) -> dict[str, Any]:
        """Create or update layout using PUT endpoint.

        Args:
            layout_uuid: UUID for the layout (client-generated for new layouts)
            layout_meta: LayoutMeta object data to send

        Returns:
            API response data
        """
        self._ensure_authenticated()

        endpoint = f"layouts/v1/{layout_uuid}"

        try:
            # Use ID token for write operations (PUT requires ID token, not access token)
            assert self._tokens is not None, (
                "Tokens should be available after authentication"
            )
            headers = {
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
                "authorization": f"Bearer {self._tokens.id_token}",
                "content-type": "application/json",
                "origin": "https://my.glove80.com",
                "referer": "https://my.glove80.com/",
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
            }

            response = self.session.put(
                self._get_full_url(endpoint), json=layout_meta, headers=headers
            )

            return self._handle_response(response)  # type: ignore[no-any-return]
        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Network error: {e}") from e

    def update_layout(
        self, layout_uuid: str, layout_data: dict[str, Any]
    ) -> MoErgoLayout:
        """Update layout configuration."""
        # Delegate to save_layout method
        response_data = self.save_layout(layout_uuid, layout_data)
        return MoErgoLayout(**response_data)

    def create_layout(self, layout_data: dict[str, Any]) -> MoErgoLayout:
        """Create new layout."""
        import uuid

        # Generate new UUID for the layout
        layout_uuid = str(uuid.uuid4())

        # Delegate to save_layout method
        response_data = self.save_layout(layout_uuid, layout_data)
        return MoErgoLayout(**response_data)

    def delete_layout(self, layout_uuid: str) -> bool:
        """Delete a single layout."""
        return self.batch_delete_layouts([layout_uuid])[layout_uuid]

    def batch_delete_layouts(self, layout_uuids: list[str]) -> dict[str, bool]:
        """Delete multiple layouts in a batch operation.

        Args:
            layout_uuids: List of layout UUIDs to delete

        Returns:
            Dictionary mapping UUID to deletion success (True/False)
        """
        self._ensure_authenticated()

        endpoint = "layouts/v1/batchDelete"

        try:
            assert self._tokens is not None, (
                "Tokens should be available after authentication"
            )
            headers = {
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
                "authorization": f"Bearer {self._tokens.id_token}",
                "content-type": "text/plain;charset=UTF-8",
                "origin": "https://my.glove80.com",
                "referer": "https://my.glove80.com/",
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
            }

            response = self.session.post(
                self._get_full_url(endpoint),
                data=json.dumps(layout_uuids),
                headers=headers,
            )

            return self._handle_response(response)  # type: ignore[no-any-return]

        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Network error: {e}") from e

    def list_public_layouts(
        self, tags: list[str] | None = None, use_cache: bool = True
    ) -> list[str]:
        """List public layouts (up to 950 most recent UUIDs).

        Args:
            tags: Optional list of tags to filter by
            use_cache: Whether to use cached results (default: True)

        Returns:
            List of layout UUIDs for public layouts
        """
        # Generate cache key for this request
        tags_key = ",".join(sorted(tags)) if tags else "all"
        cache_key = CacheKey.from_parts("public_layouts", tags_key)

        # Try cache first if enabled (cache for 10 minutes since this list can change)
        if use_cache:
            cached_data = self._cache.get(cache_key)
            if cached_data is not None:
                return cached_data  # type: ignore[no-any-return]

        self._ensure_authenticated()

        endpoint = "layouts/v1"

        # Add tag filtering if provided
        params = {}
        if tags:
            params["tags"] = ",".join(tags)

        try:
            assert self._tokens is not None, (
                "Tokens should be available after authentication"
            )
            headers = {
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
                "authorization": f"Bearer {self._tokens.id_token}",
                "referer": "https://my.glove80.com/",
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
            }

            response = self.session.get(
                self._get_full_url(endpoint), headers=headers, params=params
            )

            data = self._handle_response(response)

            # Cache the result for 10 minutes (public layouts list can change)
            if use_cache:
                self._cache.set(cache_key, data, ttl=600)

            return data  # type: ignore[no-any-return]

        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Network error: {e}") from e

    def get_user_info(self) -> dict[str, Any]:
        """Get current user information."""
        self._ensure_authenticated()

        # This endpoint needs to be discovered
        # TODO: Implement once API endpoint is discovered
        raise NotImplementedError("User info endpoint not yet discovered")

    def is_authenticated(self) -> bool:
        """Check if client is currently authenticated."""
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
        self._cache.clear()

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics and performance metrics."""
        stats = self._cache.get_stats()
        return {
            "total_entries": stats.total_entries,
            "total_size_mb": round(stats.total_size_bytes / (1024 * 1024), 2),
            "hit_rate": round(stats.hit_rate, 1),
            "miss_rate": round(stats.miss_rate, 1),
            "hit_count": stats.hit_count,
            "miss_count": stats.miss_count,
            "eviction_count": stats.eviction_count,
        }


def create_moergo_client(
    credential_manager: CredentialManager | None = None,
) -> MoErgoClient:
    """Factory function to create MoErgo client."""
    return MoErgoClient(credential_manager)
