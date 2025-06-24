"""MoErgo API client for layout management."""

from typing import Any

from glovebox.core.cache import create_cache_from_user_config
from glovebox.core.cache.cache_manager import CacheManager

from .base_client import MoErgoBaseClient
from .credentials import CredentialManager
from .firmware_client import MoErgoFirmwareClient
from .layout_client import MoErgoLayoutClient
from .models import FirmwareCompileResponse, MoErgoLayout
from .utility_client import MoErgoUtilityClient


class MoErgoClient(MoErgoBaseClient):
    """Unified MoErgo API client with all functionality."""

    def __init__(
        self,
        credential_manager: CredentialManager | None = None,
        cache: CacheManager | None = None,
    ):
        super().__init__(credential_manager, cache)

        # Initialize specialized clients
        self._layout_client = MoErgoLayoutClient(credential_manager, cache)
        self._firmware_client = MoErgoFirmwareClient(credential_manager, cache)
        self._utility_client = MoErgoUtilityClient(credential_manager, cache)

        # Sync tokens and session when they change
        self._sync_clients()

    def _sync_clients(self) -> None:
        """Sync tokens and session across all client instances."""
        for client in [
            self._layout_client,
            self._firmware_client,
            self._utility_client,
        ]:
            client._tokens = self._tokens
            client.session = self.session

    def _ensure_authenticated(self) -> None:
        """Override to sync clients after authentication."""
        super()._ensure_authenticated()
        self._sync_clients()

    def _authenticate(self) -> None:
        """Override to sync clients after authentication."""
        super()._authenticate()
        self._sync_clients()

    # Layout operations - delegate to layout client
    def get_layout(self, layout_uuid: str, use_cache: bool = True) -> MoErgoLayout:
        """Get layout configuration by UUID."""
        self._sync_clients()
        return self._layout_client.get_layout(layout_uuid, use_cache)

    def get_layout_meta(
        self, layout_uuid: str, use_cache: bool = True
    ) -> dict[str, Any]:
        """Get layout metadata only (without full config) by UUID."""
        self._sync_clients()
        return self._layout_client.get_layout_meta(layout_uuid, use_cache)

    def list_user_layouts(self) -> list[dict[str, str]]:
        """List user's layouts with their UUIDs and status."""
        self._sync_clients()
        return self._layout_client.list_user_layouts()

    def save_layout(
        self, layout_uuid: str, layout_meta: dict[str, Any]
    ) -> dict[str, Any]:
        """Create or update layout using PUT endpoint."""
        self._sync_clients()
        return self._layout_client.save_layout(layout_uuid, layout_meta)

    def update_layout(
        self, layout_uuid: str, layout_data: dict[str, Any]
    ) -> MoErgoLayout:
        """Update layout configuration."""
        self._sync_clients()
        return self._layout_client.update_layout(layout_uuid, layout_data)

    def create_layout(self, layout_data: dict[str, Any]) -> MoErgoLayout:
        """Create new layout."""
        self._sync_clients()
        return self._layout_client.create_layout(layout_data)

    def delete_layout(self, layout_uuid: str) -> bool:
        """Delete a single layout using direct DELETE request."""
        self._sync_clients()
        return self._layout_client.delete_layout(layout_uuid)

    def batch_delete_layouts(self, layout_uuids: list[str]) -> dict[str, bool]:
        """Delete multiple layouts in a batch operation."""
        self._sync_clients()
        return self._layout_client.batch_delete_layouts(layout_uuids)

    def list_public_layouts(
        self, tags: list[str] | None = None, use_cache: bool = True
    ) -> list[str]:
        """List public layouts (up to 950 most recent UUIDs)."""
        self._sync_clients()
        return self._layout_client.list_public_layouts(tags, use_cache)

    # Firmware operations - delegate to firmware client
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
        """Compile firmware for a layout."""
        self._sync_clients()
        return self._firmware_client.compile_firmware(
            layout_uuid,
            keymap,
            kconfig,
            board,
            firmware_version,
            timeout,
            max_retries,
            initial_retry_delay,
        )

    def download_firmware(
        self,
        firmware_location: str,
        output_path: str | None = None,
        use_cache: bool = True,
    ) -> bytes:
        """Download compiled firmware from MoErgo servers."""
        self._sync_clients()
        return self._firmware_client.download_firmware(
            firmware_location, output_path, use_cache
        )

    # Utility operations - delegate to utility client
    def get_user_info(self) -> dict[str, Any]:
        """Get current user information."""
        self._sync_clients()
        return self._utility_client.get_user_info()

    def validate_authentication(self) -> bool:
        """Validate authentication by making a test API call to the server."""
        self._sync_clients()
        return self._utility_client.validate_authentication()

    def test_layout_endpoints(
        self, layout_uuid: str, layout_data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Test different HTTP methods on layout endpoints to discover capabilities."""
        self._sync_clients()
        return self._utility_client.test_layout_endpoints(layout_uuid, layout_data)


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
    if user_config is not None:
        cache = create_cache_from_user_config(user_config, tag="moergo")
    else:
        from glovebox.config import create_user_config

        default_user_config = create_user_config()
        cache = create_cache_from_user_config(default_user_config._config, tag="moergo")

    return MoErgoClient(credential_manager, cache)
