"""Version check service for ZMK firmware and Glovebox application updates."""

import json
import logging
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from glovebox.config import create_user_config
from glovebox.config.user_config import UserConfig
from glovebox.core.cache import create_cache_from_user_config
from glovebox.core.cache.cache_manager import CacheManager
from glovebox.core.cache.models import CacheKey
from glovebox.utils.xdg import get_version_check_state_file


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

    def __init__(self, user_config: UserConfig, cache: CacheManager) -> None:
        """Initialize version checker with required dependencies.

        Args:
            user_config: User configuration instance
            cache: Cache manager instance
        """
        self.logger = logging.getLogger(__name__)
        self._user_config = user_config
        self._cache = cache

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
            if self._user_config._config.disable_version_checks and not force:
                return VersionCheckResult(has_update=False, check_disabled=True)

            # Check if we're in a rate limit backoff period
            if not force and self._is_rate_limited():
                self.logger.debug("Skipping version check due to rate limit backoff")
                return VersionCheckResult(
                    has_update=False,
                    current_version=self._get_current_zmk_version(),
                    last_check=datetime.now(),
                )

            # Check cache if not forcing
            if not force:
                cached_result = self._get_cached_result(include_prereleases)
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
            self._cache_result(result, include_prereleases)

            return result

        except Exception as e:
            self.logger.debug("Failed to check for ZMK updates: %s", e)
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

            # Create request with User-Agent to avoid rate limiting
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Glovebox/1.0 (https://github.com/glovebox/glovebox)",
                    "Accept": "application/vnd.github.v3+json",
                },
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 403:
                    # Rate limit exceeded - cache a longer failure result
                    self.logger.debug(
                        "GitHub API rate limit exceeded, will retry later"
                    )
                    self._cache_rate_limit_failure()
                    return None
                elif response.status != 200:
                    self.logger.debug("GitHub API returned status %d", response.status)
                    return None

                releases = json.loads(response.read().decode())

                # Find the latest release (stable or prerelease)
                for release in releases:
                    if not include_prereleases and release.get("prerelease", False):
                        continue

                    if release.get("draft", False):
                        continue

                    return VersionInfo(**release)

        except urllib.error.HTTPError as e:
            if e.code == 403:
                self.logger.debug("GitHub API rate limit exceeded, will retry later")
                self._cache_rate_limit_failure()
            else:
                self.logger.debug("HTTP error fetching ZMK releases: %s", e)
        except Exception as e:
            self.logger.debug("Failed to fetch ZMK releases from GitHub: %s", e)

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

    def _get_cached_result(
        self, include_prereleases: bool
    ) -> VersionCheckResult | None:
        """Get cached version check result."""
        try:
            cache_key = CacheKey.from_parts(
                "zmk_version_check", str(include_prereleases)
            )

            cached_data = self._cache.get(cache_key)
            if cached_data is None:
                return None

            # Parse datetime if present
            if cached_data.get("last_check"):
                cached_data["last_check"] = datetime.fromisoformat(
                    cached_data["last_check"]
                )

            return VersionCheckResult(**cached_data)

        except Exception as e:
            self.logger.debug("Failed to load cached version check: %s", e)
            return None

    def _cache_result(
        self, result: VersionCheckResult, include_prereleases: bool
    ) -> None:
        """Cache version check result."""
        try:
            data = result.model_dump(by_alias=True, exclude_unset=True, mode="json")

            # The datetime is already converted to ISO format string by model_dump(mode="json")
            # No need to call .isoformat() again as data["last_check"] is already a string

            cache_key = CacheKey.from_parts(
                "zmk_version_check", str(include_prereleases)
            )

            # Cache for 7 days
            self._cache.set(cache_key, data, ttl=7 * 24 * 60 * 60)

        except Exception as e:
            self.logger.debug("Failed to cache version check result: %s", e)

    def _is_cache_valid(self, cached_result: VersionCheckResult) -> bool:
        """Check if cached result is still valid (less than 7 days old)."""
        if not cached_result.last_check:
            return False

        age = datetime.now() - cached_result.last_check
        return age < timedelta(days=7)

    def _cache_rate_limit_failure(self) -> None:
        """Cache a rate limit failure to prevent immediate retries."""
        try:
            cache_key = CacheKey.from_parts("zmk_version_check", "rate_limit")
            # Cache for 6 hours when rate limited
            self._cache.set(
                cache_key,
                {"rate_limited_at": datetime.now().isoformat()},
                ttl=6 * 60 * 60,
            )
        except Exception as e:
            self.logger.debug("Failed to cache rate limit info: %s", e)

    def _is_rate_limited(self) -> bool:
        """Check if we're currently in a rate limit backoff period."""
        try:
            cache_key = CacheKey.from_parts("zmk_version_check", "rate_limit")
            rate_limit_data = self._cache.get(cache_key)

            if rate_limit_data and "rate_limited_at" in rate_limit_data:
                rate_limited_at = datetime.fromisoformat(
                    rate_limit_data["rate_limited_at"]
                )
                # Back off for 6 hours after rate limit
                backoff_duration = timedelta(hours=6)
                return datetime.now() - rate_limited_at < backoff_duration

            return False
        except Exception as e:
            self.logger.debug("Failed to check rate limit status: %s", e)
            return False

    def disable_version_checks(self) -> None:
        """Disable automatic version checks."""
        try:
            self._user_config._config.disable_version_checks = True
            self._user_config.save()
            self.logger.info("Version checks disabled")
        except Exception as e:
            self.logger.error("Failed to disable version checks: %s", e)

    def enable_version_checks(self) -> None:
        """Enable automatic version checks."""
        try:
            self._user_config._config.disable_version_checks = False
            self._user_config.save()
            self.logger.info("Version checks enabled")
        except Exception as e:
            self.logger.error("Failed to enable version checks: %s", e)


def create_zmk_version_checker(
    user_config: UserConfig | None = None,
) -> ZmkVersionChecker:
    """Factory function to create ZMK version checker with proper dependencies.

    Args:
        user_config: Optional user configuration instance (creates new if None)

    Returns:
        Configured ZmkVersionChecker instance
    """
    if user_config is None:
        user_config = create_user_config()

    cache = create_cache_from_user_config(user_config._config, tag="version_check")
    return ZmkVersionChecker(user_config, cache)


class GloveboxVersionCheckResult(BaseModel):
    """Result of Glovebox version check."""

    has_update: bool
    current_version: str | None = None
    latest_version: str | None = None
    latest_url: str | None = None
    is_prerelease: bool = False
    check_disabled: bool = False
    last_check: datetime | None = None


class GloveboxVersionChecker:
    """Service to check for Glovebox application updates."""

    def __init__(self, user_config: UserConfig) -> None:
        """Initialize Glovebox version checker.

        Args:
            user_config: User configuration instance
        """
        self.logger = logging.getLogger(__name__)
        self._user_config = user_config
        self._state_file = get_version_check_state_file()

    def check_for_updates(
        self, force: bool = False, include_prereleases: bool = False
    ) -> GloveboxVersionCheckResult:
        """Check for Glovebox application updates.

        Args:
            force: Force check even if recently checked
            include_prereleases: Include pre-release versions

        Returns:
            Version check result
        """
        try:
            # Check user settings
            if self._user_config._config.disable_version_checks and not force:
                return GloveboxVersionCheckResult(has_update=False, check_disabled=True)

            # Load state and check 12-hour interval
            state = self._load_state()
            if not force and self._is_check_recent(state):
                return self._result_from_state(state)

            # Get current version
            current_version = self._get_current_version()

            # Fetch latest version from GitHub
            latest_version_info = self._fetch_latest_version(include_prereleases)

            if not latest_version_info:
                return GloveboxVersionCheckResult(
                    has_update=False,
                    current_version=current_version,
                    last_check=datetime.now(),
                )

            # Compare versions
            has_update = self._compare_versions(
                current_version, latest_version_info.tag_name
            )

            result = GloveboxVersionCheckResult(
                has_update=has_update,
                current_version=current_version,
                latest_version=latest_version_info.tag_name,
                latest_url=latest_version_info.html_url,
                is_prerelease=latest_version_info.prerelease,
                last_check=datetime.now(),
            )

            # Save state
            self._save_state(result)

            return result

        except Exception as e:
            self.logger.debug("Failed to check for Glovebox updates: %s", e)
            return GloveboxVersionCheckResult(
                has_update=False, current_version=None, last_check=datetime.now()
            )

    def _get_current_version(self) -> str | None:
        """Get current Glovebox version."""
        try:
            from glovebox._version import __version__

            return __version__
        except ImportError:
            try:
                from importlib.metadata import distribution

                return distribution("zmk-glovebox").version
            except Exception:
                self.logger.debug("Could not determine current Glovebox version")
                return None

    def _fetch_latest_version(
        self, include_prereleases: bool = False
    ) -> VersionInfo | None:
        """Fetch latest Glovebox version from GitHub API."""
        try:
            url = "https://api.github.com/repos/CaddyGlow/zmk-glovebox/releases"

            # Create request with User-Agent to avoid rate limiting
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Glovebox/1.0 (https://github.com/CaddyGlow/zmk-glovebox)",
                    "Accept": "application/vnd.github.v3+json",
                },
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status != 200:
                    self.logger.debug("GitHub API returned status %d", response.status)
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
            self.logger.debug("Failed to fetch Glovebox releases from GitHub: %s", e)

        return None

    def _compare_versions(self, current: str | None, latest: str) -> bool:
        """Compare version strings to determine if update is available."""
        if not current:
            return True  # Unknown current version, assume update available

        # Handle dev versions
        if "dev" in current:
            # For dev versions, don't show updates to the same base version
            # Extract base version from dev version (e.g., "0.1.1.dev1+g29de9d7" -> "0.1.1")
            base_version = current.split(".dev")[0]
            latest_clean = latest.lstrip("v")

            # If latest version matches the base version, no update needed
            if base_version == latest_clean:
                return False

            # Otherwise, show the update
            return True

        try:
            # Remove 'v' prefix if present
            current_clean = current.lstrip("v")
            latest_clean = latest.lstrip("v")

            # Basic comparison
            return current_clean != latest_clean

        except Exception:
            return False

    def _load_state(self) -> dict[str, Any]:
        """Load version check state from file."""
        try:
            if self._state_file.exists():
                with self._state_file.open("r") as f:
                    data: dict[str, Any] = json.load(f)
                    return data
        except Exception as e:
            self.logger.debug("Failed to load version check state: %s", e)

        return {}

    def _save_state(self, result: GloveboxVersionCheckResult) -> None:
        """Save version check state to file."""
        try:
            # Ensure parent directory exists
            self._state_file.parent.mkdir(parents=True, exist_ok=True)

            # Load existing state
            state = self._load_state()

            # Update with new Glovebox state
            state["glovebox"] = result.model_dump(
                by_alias=True, exclude_unset=True, mode="json"
            )

            # Write atomically
            temp_file = self._state_file.with_suffix(".tmp")
            with temp_file.open("w") as f:
                json.dump(state, f, indent=2)
            temp_file.replace(self._state_file)

        except Exception as e:
            self.logger.debug("Failed to save version check state: %s", e)

    def _is_check_recent(self, state: dict[str, Any]) -> bool:
        """Check if last check was within 12 hours."""
        try:
            if "glovebox" not in state or "last_check" not in state["glovebox"]:
                return False

            last_check = datetime.fromisoformat(state["glovebox"]["last_check"])
            age = datetime.now() - last_check
            return age < timedelta(hours=12)

        except Exception:
            return False

    def _result_from_state(self, state: dict[str, Any]) -> GloveboxVersionCheckResult:
        """Create result from saved state."""
        try:
            glovebox_state = state.get("glovebox", {})
            if glovebox_state.get("last_check"):
                glovebox_state["last_check"] = datetime.fromisoformat(
                    glovebox_state["last_check"]
                )
            return GloveboxVersionCheckResult(**glovebox_state)
        except Exception:
            return GloveboxVersionCheckResult(has_update=False)


def create_glovebox_version_checker(
    user_config: UserConfig | None = None,
) -> GloveboxVersionChecker:
    """Factory function to create Glovebox version checker.

    Args:
        user_config: Optional user configuration instance (creates new if None)

    Returns:
        Configured GloveboxVersionChecker instance
    """
    if user_config is None:
        user_config = create_user_config()

    return GloveboxVersionChecker(user_config)
