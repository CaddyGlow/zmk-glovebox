"""Version check service for ZMK firmware updates."""

import json
import logging
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from glovebox.config import create_user_config


logger = logging.getLogger(__name__)


class VersionInfo(BaseModel):
    """Version information from GitHub API."""

    tag_name: str
    name: str
    published_at: str
    html_url: str
    prerelease: bool


class VersionCheckResult(BaseModel):
    """Result of version check."""

    has_update: bool
    current_version: str | None = None
    latest_version: str | None = None
    latest_url: str | None = None
    is_prerelease: bool = False
    check_disabled: bool = False
    last_check: datetime | None = None


class ZmkVersionChecker:
    """Service to check for ZMK firmware updates."""

    def __init__(self) -> None:
        """Initialize version checker."""
        self.logger = logging.getLogger(__name__)
        self.cache_file = Path.home() / ".cache" / "glovebox" / "zmk_version_check.json"
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)

    def check_for_updates(
        self, force: bool = False, include_prereleases: bool = False
    ) -> VersionCheckResult:
        """Check for ZMK firmware updates.

        Args:
            force: Force check even if cached result is recent
            include_prereleases: Include pre-release versions

        Returns:
            Version check result
        """
        try:
            # Check user settings
            user_config = create_user_config()
            if user_config._config.disable_version_checks and not force:
                return VersionCheckResult(has_update=False, check_disabled=True)

            # Check cache if not forcing
            if not force:
                cached_result = self._get_cached_result()
                if cached_result and self._is_cache_valid(cached_result):
                    return cached_result

            # Get current ZMK version from Docker image
            current_version = self._get_current_zmk_version()

            # Fetch latest version from GitHub
            latest_version_info = self._fetch_latest_version(include_prereleases)

            if not latest_version_info:
                return VersionCheckResult(
                    has_update=False,
                    current_version=current_version,
                    last_check=datetime.now(),
                )

            # Compare versions
            has_update = self._compare_versions(
                current_version, latest_version_info.tag_name
            )

            result = VersionCheckResult(
                has_update=has_update,
                current_version=current_version,
                latest_version=latest_version_info.tag_name,
                latest_url=latest_version_info.html_url,
                is_prerelease=latest_version_info.prerelease,
                last_check=datetime.now(),
            )

            # Cache the result
            self._cache_result(result)

            return result

        except Exception as e:
            self.logger.warning("Failed to check for ZMK updates: %s", e)
            return VersionCheckResult(
                has_update=False, current_version=None, last_check=datetime.now()
            )

    def _get_current_zmk_version(self) -> str | None:
        """Get current ZMK version from Docker image tag."""
        try:
            # For now, we'll use a simple approach - extract from common ZMK image names
            # This could be enhanced to inspect actual Docker images
            from glovebox.compilation.models import ZmkCompilationConfig

            config = ZmkCompilationConfig()
            image = config.image  # e.g., "zmkfirmware/zmk-build-arm:stable"

            if ":" in image:
                tag = image.split(":")[-1]
                if tag != "stable" and tag != "latest":
                    return tag

            return "stable"  # Default assumption

        except Exception as e:
            self.logger.debug("Could not determine current ZMK version: %s", e)
            return None

    def _fetch_latest_version(
        self, include_prereleases: bool = False
    ) -> VersionInfo | None:
        """Fetch latest ZMK version from GitHub API."""
        try:
            url = "https://api.github.com/repos/zmkfirmware/zmk/releases"

            with urllib.request.urlopen(url, timeout=10) as response:
                if response.status != 200:
                    self.logger.warning(
                        "GitHub API returned status %d", response.status
                    )
                    return None

                releases = json.loads(response.read().decode())

                # Find the latest release (stable or prerelease)
                for release in releases:
                    if not include_prereleases and release.get("prerelease", False):
                        continue

                    if release.get("draft", False):
                        continue

                    return VersionInfo(**release)

        except Exception as e:
            self.logger.warning("Failed to fetch ZMK releases from GitHub: %s", e)

        return None

    def _compare_versions(self, current: str | None, latest: str) -> bool:
        """Compare version strings to determine if update is available."""
        if not current:
            return True  # Unknown current version, assume update available

        if current == "stable" or current == "latest":
            # For stable/latest tags, we can't easily compare - assume no update needed
            # unless the latest release is significantly newer
            return False

        # Simple version comparison - could be enhanced with proper semver
        try:
            # Remove 'v' prefix if present
            current_clean = current.lstrip("v")
            latest_clean = latest.lstrip("v")

            # Basic string comparison for now
            return current_clean != latest_clean

        except Exception:
            return False

    def _get_cached_result(self) -> VersionCheckResult | None:
        """Get cached version check result."""
        try:
            if not self.cache_file.exists():
                return None

            with self.cache_file.open() as f:
                data = json.load(f)

            # Parse datetime
            if data.get("last_check"):
                data["last_check"] = datetime.fromisoformat(data["last_check"])

            return VersionCheckResult(**data)

        except Exception as e:
            self.logger.debug("Failed to load cached version check: %s", e)
            return None

    def _cache_result(self, result: VersionCheckResult) -> None:
        """Cache version check result."""
        try:
            data = result.model_dump()

            # Convert datetime to string
            if data.get("last_check"):
                data["last_check"] = data["last_check"].isoformat()

            with self.cache_file.open("w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            self.logger.debug("Failed to cache version check result: %s", e)

    def _is_cache_valid(self, cached_result: VersionCheckResult) -> bool:
        """Check if cached result is still valid (less than 24 hours old)."""
        if not cached_result.last_check:
            return False

        age = datetime.now() - cached_result.last_check
        return age < timedelta(hours=24)

    def disable_version_checks(self) -> None:
        """Disable automatic version checks."""
        try:
            user_config = create_user_config()
            user_config._config.disable_version_checks = True
            user_config.save()
            self.logger.info("Version checks disabled")
        except Exception as e:
            self.logger.error("Failed to disable version checks: %s", e)

    def enable_version_checks(self) -> None:
        """Enable automatic version checks."""
        try:
            user_config = create_user_config()
            user_config._config.disable_version_checks = False
            user_config.save()
            self.logger.info("Version checks enabled")
        except Exception as e:
            self.logger.error("Failed to enable version checks: %s", e)


def create_zmk_version_checker() -> ZmkVersionChecker:
    """Factory function to create ZMK version checker."""
    return ZmkVersionChecker()
