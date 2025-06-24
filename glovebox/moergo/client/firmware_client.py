"""MoErgo API client for firmware operations."""

import time
import zlib
from typing import Any, cast
from urllib.parse import urljoin

import requests

from glovebox.core.cache.cache_manager import CacheManager
from glovebox.core.cache.models import CacheKey

from .base_client import MoErgoBaseClient
from .credentials import CredentialManager
from .models import (
    APIError,
    CompilationError,
    FirmwareCompileRequest,
    FirmwareCompileResponse,
    NetworkError,
    TimeoutError,
)


class MoErgoFirmwareClient(MoErgoBaseClient):
    """Client for MoErgo firmware operations."""

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
        self,
        firmware_location: str,
        output_path: str | None = None,
        use_cache: bool = True,
    ) -> bytes:
        """
        Download compiled firmware from MoErgo servers.

        Args:
            firmware_location: Location path from compile response
            output_path: Optional local file path to save firmware
            use_cache: Whether to use cached results (default: True)

        Returns:
            Firmware content as bytes (decompressed if .gz file)
        """
        # Generate cache key for this firmware
        cache_key = CacheKey.from_parts("firmware_download", firmware_location)

        # Try cache first if enabled
        if use_cache and self._cache:
            cached_data = self._cache.get(cache_key)
            if cached_data is not None and isinstance(cached_data, bytes):
                # Save to file if path provided
                if output_path:
                    from pathlib import Path

                    output_file = Path(output_path)
                    output_file.parent.mkdir(parents=True, exist_ok=True)
                    output_file.write_bytes(cached_data)

                return cast(bytes, cached_data)

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

            # Cache the firmware data for 30 days - firmware builds are immutable
            if use_cache and self._cache:
                self._cache.set(cache_key, firmware_data, ttl=3600 * 24 * 30)

            # Save to file if path provided
            if output_path:
                from pathlib import Path

                output_file = Path(output_path)
                output_file.parent.mkdir(parents=True, exist_ok=True)
                output_file.write_bytes(firmware_data)

            return firmware_data

        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Failed to download firmware: {e}") from e


def create_moergo_firmware_client(
    credential_manager: CredentialManager | None = None,
    cache: CacheManager | None = None,
) -> MoErgoFirmwareClient:
    """Factory function to create MoErgo firmware client.

    Args:
        credential_manager: Optional credential manager
        cache: Optional cache manager

    Returns:
        Configured MoErgo firmware client
    """
    return MoErgoFirmwareClient(credential_manager, cache)
