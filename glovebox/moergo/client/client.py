"""MoErgo API client for layout management."""

import json
import time
import zlib
from datetime import datetime, timedelta
from typing import Any, Optional
from urllib.parse import urljoin

import requests

from glovebox.core.cache import (
    CacheKey,
    CacheManager,
    create_cache_from_user_config,
    create_default_cache,
)

from .auth import Glove80Auth
from .credentials import CredentialManager
from .models import (
    APIError,
    AuthenticationError,
    AuthTokens,
    CompilationError,
    FirmwareCompileRequest,
    FirmwareCompileResponse,
    MoErgoLayout,
    NetworkError,
    TimeoutError,
    UserCredentials,
    ValidationError,
)


class MoErgoClient:
    """Client for interacting with MoErgo Glove80 API."""

    BASE_URL = "https://my.glove80.com/api/"

    def __init__(
        self,
        credential_manager: CredentialManager | None = None,
        cache: CacheManager | None = None,
    ):
        self.credential_manager = credential_manager or CredentialManager()
        self.auth_client = Glove80Auth()
        self.session = requests.Session()
        self._tokens: AuthTokens | None = None

        # Initialize cache for API responses
        self._cache = cache or create_default_cache()

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

    def _handle_compile_response(self, response: requests.Response) -> Any:
        """Handle compilation API response with specific error handling."""
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 400:
                # Handle compilation failures
                try:
                    error_data = response.json()
                    message = error_data.get("message", "Compilation failed")
                    detail = error_data.get("detail", [])
                    raise CompilationError(
                        message,
                        detail=detail,
                        status_code=response.status_code,
                        response_data=error_data,
                    ) from e
                except ValueError:
                    # If response is not JSON, fall back to generic error
                    raise CompilationError(
                        f"Compilation failed: {response.text}",
                        status_code=response.status_code,
                    ) from e
            else:
                # For other status codes, use the standard handler
                return self._handle_response(response)
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

    def get_layout(self, layout_uuid: str) -> MoErgoLayout:
        """Get layout configuration by UUID."""
        self._ensure_authenticated()

        endpoint = f"layouts/v1/{layout_uuid}/config"
        try:
            response = self.session.get(self._get_full_url(endpoint))
            data = self._handle_response(response)
            layout = MoErgoLayout(**data)

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
        """Check if client is currently authenticated with valid tokens."""
        try:
            self._ensure_authenticated()
            return True
        except AuthenticationError:
            return False

    def validate_authentication(self) -> bool:
        """Validate authentication by making a test API call to the server."""
        try:
            self._ensure_authenticated()
            # Make a lightweight API call to test if tokens are valid
            # This will trigger re-authentication if tokens are invalid
            self.list_user_layouts()
            return True
        except (AuthenticationError, Exception):
            # If validation fails, try to re-authenticate
            try:
                self._authenticate()
                return True
            except AuthenticationError:
                return False

    def get_credential_info(self) -> dict[str, Any]:
        """Get information about stored credentials."""
        return self.credential_manager.get_storage_info()

    def clear_cache(self) -> None:
        """Clear all cached API responses."""
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

    def compile_firmware(
        self,
        layout_uuid: str,
        keymap: str,
        kconfig: str = "",
        board: str = "glove80",
        firmware_version: str = "v25.05",
        timeout: int = 300,
        max_retries: int = 3,
        initial_retry_delay: float = 15.0,
    ) -> FirmwareCompileResponse:
        """
        Compile firmware for a layout.

        Args:
            layout_uuid: UUID of the layout
            keymap: ZMK keymap content
            kconfig: ZMK Kconfig content (optional)
            board: Target board (default: "glove80")
            firmware_version: Firmware API version (default: "v25.05")
            timeout: Request timeout in seconds (default: 300)
            max_retries: Maximum retry attempts on timeout (default: 3)
            initial_retry_delay: Initial delay before retry in seconds (default: 15.0)

        Returns:
            FirmwareCompileResponse with location of compiled firmware
        """
        self._ensure_authenticated()

        endpoint = f"firmware/{firmware_version}/{layout_uuid}"

        # Prepare request payload
        compile_request = FirmwareCompileRequest(
            keymap=keymap, kconfig=kconfig, board=board
        )

        # Retry logic for timeouts only
        last_timeout_error = None
        for attempt in range(max_retries + 1):  # +1 for initial attempt
            try:
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

                response = self.session.post(
                    self._get_full_url(endpoint),
                    json=compile_request.model_dump(
                        by_alias=True, exclude_unset=True, mode="json"
                    ),
                    headers=headers,
                    timeout=timeout,
                )

                data = self._handle_compile_response(response)
                return FirmwareCompileResponse(**data)

            except requests.exceptions.Timeout as e:
                last_timeout_error = e

                # If this is not the last attempt, wait and retry
                if attempt < max_retries:
                    # Calculate delay with exponential backoff
                    delay = initial_retry_delay * (2**attempt)
                    time.sleep(delay)
                    continue
                else:
                    # Final timeout - raise
                    raise TimeoutError(
                        f"Firmware compilation timed out after {max_retries + 1} attempts "
                        f"({timeout} seconds each)"
                    ) from e

            except CompilationError:
                # Don't retry compilation errors - raise immediately
                raise
            except requests.exceptions.RequestException as e:
                # Don't retry other network errors - raise immediately
                raise NetworkError(f"Network error: {e}") from e
            except Exception:
                # Don't retry other errors - raise immediately
                raise

        # This should never be reached, but just in case
        raise TimeoutError("Unexpected end of retry loop") from last_timeout_error

    def download_firmware(
        self, firmware_location: str, output_path: str | None = None
    ) -> bytes:
        """
        Download compiled firmware from MoErgo servers.

        Args:
            firmware_location: Location path from compile response
            output_path: Optional local file path to save firmware

        Returns:
            Firmware content as bytes (decompressed if .gz file)
        """
        # Construct full download URL
        download_url = urljoin("https://my.glove80.com/", firmware_location)

        try:
            # Download doesn't need authentication - firmware URLs are signed
            headers = {
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
                "referer": "https://my.glove80.com/",
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
            }

            response = self.session.get(download_url, headers=headers)
            response.raise_for_status()

            firmware_data = response.content

            # Only decompress if filename ends with .gz
            if firmware_location.endswith(".gz"):
                try:
                    firmware_data = zlib.decompress(firmware_data)
                except zlib.error as e:
                    raise APIError(f"Failed to decompress firmware data: {e}") from e

            # Save to file if path provided
            if output_path:
                from pathlib import Path

                output_file = Path(output_path)
                output_file.parent.mkdir(parents=True, exist_ok=True)
                output_file.write_bytes(firmware_data)

            return firmware_data

        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Failed to download firmware: {e}") from e

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


def create_moergo_client(
    credential_manager: CredentialManager | None = None,
    user_config: Any = None,
) -> MoErgoClient:
    """Factory function to create MoErgo client.

    Args:
        credential_manager: Optional credential manager
        user_config: Optional user configuration for cache settings

    Returns:
        Configured MoErgo client
    """
    cache = None
    if user_config is not None:
        cache = create_cache_from_user_config(user_config)

    return MoErgoClient(credential_manager, cache)
