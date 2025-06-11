#!/usr/bin/env python3
"""Script to generate base dependencies cache from existing ZMK workspace.

This script allows you to create a base dependencies cache entry from an existing
ZMK workspace, which can speed up future compilations by reusing the dependencies.

Usage:
    python scripts/generate_base_cache.py --workspace /path/to/existing/workspace
    python scripts/generate_base_cache.py --workspace /path/to/workspace --zmk-repo moergo-sc/zmk --zmk-revision main
    python scripts/generate_base_cache.py --workspace /path/to/workspace --cache-root ~/.glovebox/cache/custom
"""

import argparse
import logging
import sys
from pathlib import Path


# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from glovebox.compilation.cache.base_dependencies_cache import (
    BaseDependenciesCache,
    create_base_dependencies_cache,
)


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def detect_zmk_info_from_workspace(workspace_path: Path) -> tuple[str, str] | None:
    """Detect ZMK repository and revision from existing workspace.

    Args:
        workspace_path: Path to existing workspace

    Returns:
        tuple[str, str] | None: (repo_url, revision) or None if not detected
    """
    logger = logging.getLogger(__name__)

    # Try to read west.yml from workspace
    west_yml_path = workspace_path / "west.yml"
    config_west_yml_path = workspace_path / "config" / "west.yml"

    # Check both possible locations
    for yml_path in [west_yml_path, config_west_yml_path]:
        if yml_path.exists():
            try:
                import yaml

                with yml_path.open() as f:
                    west_config = yaml.safe_load(f)

                # Extract ZMK project info
                manifest = west_config.get("manifest", {})
                projects = manifest.get("projects", [])

                for project in projects:
                    if project.get("name") == "zmk":
                        remote_name = project.get("remote")
                        revision = project.get("revision", "main")

                        # Find the remote URL
                        remotes = manifest.get("remotes", [])
                        for remote in remotes:
                            if remote.get("name") == remote_name:
                                url_base = remote.get("url-base", "")
                                if url_base.startswith("https://github.com/"):
                                    org = url_base.replace("https://github.com/", "")
                                    repo_url = f"{org}/zmk"
                                    logger.info(
                                        "Detected ZMK info from %s: %s@%s",
                                        yml_path,
                                        repo_url,
                                        revision,
                                    )
                                    return repo_url, revision

            except Exception as e:
                logger.debug("Failed to parse %s: %s", yml_path, e)
                continue

    # Try to detect from zmk directory git info
    zmk_dir = workspace_path / "zmk"
    if zmk_dir.exists() and (zmk_dir / ".git").exists():
        try:
            import subprocess

            # Get remote origin URL
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=zmk_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                origin_url = result.stdout.strip()

                # Get current branch/revision
                result = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=zmk_dir,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                revision = result.stdout.strip() if result.returncode == 0 else "main"

                # Normalize URL
                if origin_url.startswith("https://github.com/"):
                    repo_url = origin_url.replace("https://github.com/", "").replace(
                        ".git", ""
                    )
                elif origin_url.startswith("git@github.com:"):
                    repo_url = origin_url.replace("git@github.com:", "").replace(
                        ".git", ""
                    )
                else:
                    repo_url = origin_url

                logger.info("Detected ZMK info from git: %s@%s", repo_url, revision)
                return repo_url, revision

        except Exception as e:
            logger.debug("Failed to get git info from zmk directory: %s", e)

    logger.warning("Could not auto-detect ZMK repository info from workspace")
    return None


def validate_workspace(workspace_path: Path) -> bool:
    """Validate that the workspace contains required ZMK dependencies.

    Args:
        workspace_path: Path to workspace to validate

    Returns:
        bool: True if workspace is valid
    """
    logger = logging.getLogger(__name__)

    required_dirs = [".west", "zephyr", "zmk"]
    missing_dirs = []

    for dir_name in required_dirs:
        dir_path = workspace_path / dir_name
        if not dir_path.exists():
            missing_dirs.append(dir_name)

    if missing_dirs:
        logger.error(
            "Workspace is missing required directories: %s", ", ".join(missing_dirs)
        )
        return False

    logger.info("Workspace validation passed")
    return True


def copy_workspace_to_cache(
    source_workspace: Path,
    cache: BaseDependenciesCache,
    cache_key: str,
    zmk_repo_url: str,
    zmk_revision: str,
) -> bool:
    """Copy existing workspace to cache location.

    Args:
        source_workspace: Source workspace path
        cache: Base dependencies cache instance
        cache_key: Cache key for the workspace
        zmk_repo_url: ZMK repository URL
        zmk_revision: ZMK revision

    Returns:
        bool: True if copy succeeded
    """
    logger = logging.getLogger(__name__)

    try:
        cache_path = cache.cache_root / cache_key

        # Ensure cache directory exists
        cache.cache_root.mkdir(parents=True, exist_ok=True)

        logger.info("Copying workspace %s -> %s", source_workspace, cache_path)

        # Use cp -r to copy the workspace
        import subprocess

        result = subprocess.run(
            ["cp", "-r", str(source_workspace), str(cache_path)],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        if result.returncode != 0:
            logger.error("Failed to copy workspace: %s", result.stderr)
            return False

        # Create cache metadata
        cache._create_cache_metadata(cache_path, zmk_repo_url, zmk_revision)

        logger.info("Successfully copied workspace to cache: %s", cache_path)
        return True

    except Exception as e:
        logger.error("Failed to copy workspace to cache: %s", e)
        return False


def main() -> int:
    """Main script function."""
    parser = argparse.ArgumentParser(
        description="Generate base dependencies cache from existing ZMK workspace"
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        required=True,
        help="Path to existing ZMK workspace directory",
    )
    parser.add_argument(
        "--zmk-repo",
        type=str,
        help="ZMK repository URL (e.g., 'zmkfirmware/zmk' or 'moergo-sc/zmk'). Auto-detected if not provided.",
    )
    parser.add_argument(
        "--zmk-revision",
        type=str,
        default="main",
        help="ZMK revision/branch (default: main). Auto-detected if not provided.",
    )
    parser.add_argument(
        "--cache-root",
        type=Path,
        help="Custom cache root directory (default: ~/.glovebox/cache/base_deps)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually creating cache",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing cache entry if it exists",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    # Validate workspace path
    if not args.workspace.exists():
        logger.error("Workspace path does not exist: %s", args.workspace)
        return 1

    if not args.workspace.is_dir():
        logger.error("Workspace path is not a directory: %s", args.workspace)
        return 1

    # Validate workspace contents
    if not validate_workspace(args.workspace):
        return 1

    # Determine ZMK repository info
    zmk_repo_url = args.zmk_repo
    zmk_revision = args.zmk_revision

    if not zmk_repo_url:
        detected_info = detect_zmk_info_from_workspace(args.workspace)
        if detected_info:
            zmk_repo_url, detected_revision = detected_info
            if args.zmk_revision == "main":  # Use detected revision if default
                zmk_revision = detected_revision
        else:
            logger.error(
                "Could not detect ZMK repository info. Please specify --zmk-repo"
            )
            return 1

    logger.info("Using ZMK repository: %s@%s", zmk_repo_url, zmk_revision)

    # Create cache instance
    cache = create_base_dependencies_cache(cache_root=args.cache_root)

    # Generate cache key
    cache_key = cache.get_cache_key(zmk_repo_url, zmk_revision)
    cache_path = cache.cache_root / cache_key

    logger.info("Generated cache key: %s", cache_key)
    logger.info("Cache path: %s", cache_path)

    # Check if cache already exists
    if cache_path.exists():
        if not args.force:
            logger.error(
                "Cache entry already exists: %s\nUse --force to overwrite", cache_path
            )
            return 1
        else:
            logger.warning("Overwriting existing cache entry: %s", cache_path)
            import shutil

            shutil.rmtree(cache_path)

    if args.dry_run:
        logger.info("DRY RUN: Would create cache entry:")
        logger.info("  Source: %s", args.workspace)
        logger.info("  Cache Key: %s", cache_key)
        logger.info("  Cache Path: %s", cache_path)
        logger.info("  ZMK Repo: %s@%s", zmk_repo_url, zmk_revision)
        return 0

    # Copy workspace to cache
    if not copy_workspace_to_cache(
        args.workspace, cache, cache_key, zmk_repo_url, zmk_revision
    ):
        return 1

    logger.info("✅ Successfully created base dependencies cache!")
    logger.info("Cache key: %s", cache_key)
    logger.info("Cache path: %s", cache_path)

    # Verify the cache was created properly
    cached_workspace = cache.get_cached_workspace(cache_key)
    if cached_workspace:
        logger.info("✅ Cache verification passed")
    else:
        logger.error("❌ Cache verification failed")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
