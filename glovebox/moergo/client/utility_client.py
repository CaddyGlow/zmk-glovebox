"""MoErgo API client utility and testing methods."""

from typing import Any

import requests

from glovebox.core.cache_v2.cache_manager import CacheManager

from .base_client import MoErgoBaseClient
from .credentials import CredentialManager


class MoErgoUtilityClient(MoErgoBaseClient):
    """Client for MoErgo utility and testing operations."""

    def get_user_info(self) -> dict[str, Any]:
        """Get current user information."""
        self._ensure_authenticated()

        # This endpoint needs to be discovered
        # TODO: Implement once API endpoint is discovered
        raise NotImplementedError("User info endpoint not yet discovered")

    def validate_authentication(self) -> bool:
        """Validate authentication by making a test API call to the server."""
        try:
            self._ensure_authenticated()
            # For utility client, we need to import and use the layout client method
            from .layout_client import MoErgoLayoutClient

            layout_client = MoErgoLayoutClient(self.credential_manager, self._cache)
            layout_client._tokens = self._tokens
            layout_client.session = self.session
            layout_client.list_user_layouts()
            return True
        except Exception:
            # If validation fails, try to re-authenticate
            try:
                self._authenticate()
                return True
            except Exception:
                return False

    def test_layout_endpoints(
        self, layout_uuid: str, layout_data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Test different HTTP methods on layout endpoints to discover capabilities.

        Args:
            layout_uuid: UUID of layout to test with
            layout_data: Optional layout data for POST/PUT tests

        Returns:
            Dict with results of different HTTP method tests
        """
        self._ensure_authenticated()

        endpoint = f"layouts/v1/{layout_uuid}"
        results = {}

        # Standard headers for all requests
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

        # Test GET (try with access token)
        try:
            get_headers = {"authorization": f"Bearer {self._tokens.access_token}"}
            response = self.session.get(
                self._get_full_url(endpoint), headers=get_headers
            )
            results["GET"] = {
                "status_code": response.status_code,
                "success": response.status_code == 200,
                "error": None if response.status_code == 200 else response.text[:200],
            }
        except Exception as e:
            results["GET"] = {"status_code": None, "success": False, "error": str(e)}

        # Test PUT (current method we use)
        if layout_data:
            try:
                response = self.session.put(
                    self._get_full_url(endpoint), json=layout_data, headers=headers
                )
                results["PUT"] = {
                    "status_code": response.status_code,
                    "success": response.status_code in [200, 201, 204],
                    "error": None
                    if response.status_code in [200, 201, 204]
                    else response.text[:200],
                }
            except Exception as e:
                results["PUT"] = {
                    "status_code": None,
                    "success": False,
                    "error": str(e),
                }

        # Test POST (try with access token instead of ID token)
        if layout_data:
            try:
                post_headers = headers.copy()
                post_headers["authorization"] = f"Bearer {self._tokens.access_token}"
                response = self.session.post(
                    self._get_full_url(endpoint), json=layout_data, headers=post_headers
                )
                results["POST"] = {
                    "status_code": response.status_code,
                    "success": response.status_code in [200, 201, 204],
                    "error": None
                    if response.status_code in [200, 201, 204]
                    else response.text[:200],
                }
            except Exception as e:
                results["POST"] = {
                    "status_code": None,
                    "success": False,
                    "error": str(e),
                }

        # Test PATCH
        if layout_data:
            try:
                response = self.session.patch(
                    self._get_full_url(endpoint), json=layout_data, headers=headers
                )
                results["PATCH"] = {
                    "status_code": response.status_code,
                    "success": response.status_code in [200, 201, 204],
                    "error": None
                    if response.status_code in [200, 201, 204]
                    else response.text[:200],
                }
            except Exception as e:
                results["PATCH"] = {
                    "status_code": None,
                    "success": False,
                    "error": str(e),
                }

        # Test DELETE
        try:
            response = self.session.delete(
                self._get_full_url(endpoint), headers=headers
            )
            results["DELETE"] = {
                "status_code": response.status_code,
                "success": response.status_code in [200, 204],
                "error": None
                if response.status_code in [200, 204]
                else response.text[:200],
            }
        except Exception as e:
            results["DELETE"] = {"status_code": None, "success": False, "error": str(e)}

        return results


def create_moergo_utility_client(
    credential_manager: CredentialManager | None = None,
    cache: CacheManager | None = None,
) -> MoErgoUtilityClient:
    """Factory function to create MoErgo utility client.

    Args:
        credential_manager: Optional credential manager
        cache: Optional cache manager

    Returns:
        Configured MoErgo utility client
    """
    return MoErgoUtilityClient(credential_manager, cache)
