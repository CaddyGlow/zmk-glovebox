"""MoErgo API client for layout operations."""

import base64
import json
from typing import Any

import requests

from glovebox.core.cache.cache_manager import CacheManager
from glovebox.core.cache.models import CacheKey

from .base_client import MoErgoBaseClient
from .credentials import CredentialManager
from .models import APIError, MoErgoLayout, NetworkError


class MoErgoLayoutClient(MoErgoBaseClient):
    """Client for MoErgo layout operations."""

    def get_layout(self, layout_uuid: str, use_cache: bool = True) -> MoErgoLayout:
        """Get layout configuration by UUID.

        Args:
            layout_uuid: UUID of the layout to retrieve
            use_cache: Whether to use cached results (default: True)

        Returns:
            Layout configuration data
        """
        # Generate cache key for this request
        cache_key = CacheKey.from_parts("layout_config", layout_uuid)

        # Try cache first if enabled
        if use_cache and self._cache:
            cached_data = self._cache.get(cache_key)
            if cached_data is not None:
                return MoErgoLayout(**cached_data)

        self._ensure_authenticated()

        endpoint = f"layouts/v1/{layout_uuid}/config"
        try:
            response = self.session.get(self._get_full_url(endpoint))
            data = self._handle_response(response)
            layout = MoErgoLayout(**data)

            # Cache the result for 30 days - layouts are immutable
            if use_cache and self._cache:
                self._cache.set(cache_key, data, ttl=3600 * 24 * 30)

            return layout
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
        if use_cache and self._cache:
            cached_data = self._cache.get(cache_key)
            if cached_data is not None:
                return cached_data  # type: ignore[no-any-return]

        self._ensure_authenticated()

        endpoint = f"layouts/v1/{layout_uuid}/meta"
        try:
            response = self.session.get(self._get_full_url(endpoint))
            data = self._handle_response(response)

            # Cache the result for 30 days layout are immutalbe
            if use_cache and self._cache:
                self._cache.set(cache_key, data, ttl=3600 * 24 * 30)

            return data  # type: ignore[no-any-return]
        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Network error: {e}") from e

    def list_user_layouts(self) -> list[dict[str, str]]:
        """List user's layouts with their UUIDs and status."""
        self._ensure_authenticated()

        # Extract user ID from ID token
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

        TODO: this is not working a layout_uuid is immutable
        we can only update wih a new uuid and we can set
        the parend_uuid = layout_uuid if we want to have them link.

        Args:
            layout_uuid: UUID for the layout (client-generated for new layouts)
            layout_meta: LayoutMeta object data to send

        Returns:
            API response data
        """
        self._ensure_authenticated()

        endpoint = f"layouts/v1/{layout_uuid}"
        layout_title = layout_meta.get("layout_meta", {}).get("title", "Unknown")

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

            result = self._handle_response(response)
            return result  # type: ignore[no-any-return]
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
        """Delete a single layout using direct DELETE request."""
        self._ensure_authenticated()

        endpoint = f"layouts/v1/{layout_uuid}"

        # Try to get layout title before deletion
        layout_title = None
        try:
            layout = self.get_layout(layout_uuid)
            layout_title = layout.layout_meta.title
        except Exception:
            pass  # Don't fail deletion if we can't get title

        # Use same headers as other operations
        assert self._tokens is not None, (
            "Tokens should be available after authentication"
        )
        headers = {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "authorization": f"Bearer {self._tokens.id_token}",
            "origin": "https://my.glove80.com",
            "referer": "https://my.glove80.com/",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        }

        try:
            response = self.session.delete(
                self._get_full_url(endpoint), headers=headers
            )
            return response.status_code == 204
        except requests.exceptions.RequestException:
            return False

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
        if use_cache and self._cache:
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
            if use_cache and self._cache:
                ttl = 600
                if tags and "glove80-standard" in tags:
                    ttl = 3600 * 2
                self._cache.set(cache_key, data, ttl=ttl)

            return data  # type: ignore[no-any-return]

        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Network error: {e}") from e


def create_moergo_layout_client(
    credential_manager: CredentialManager | None = None,
    cache: CacheManager | None = None,
) -> MoErgoLayoutClient:
    """Factory function to create MoErgo layout client.

    Args:
        credential_manager: Optional credential manager
        cache: Optional cache manager

    Returns:
        Configured MoErgo layout client
    """
    return MoErgoLayoutClient(credential_manager, cache)
