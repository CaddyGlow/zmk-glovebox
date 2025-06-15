"""Cache management CLI commands."""

import logging
from pathlib import Path
from typing import Annotated

import typer

from glovebox.compilation.cache import inject_base_dependencies_cache_from_workspace


logger = logging.getLogger(__name__)

cache_app = typer.Typer(help="Cache management commands")


@cache_app.command(name="inject-base-deps")
def inject_base_deps_command(
    workspace_path: Annotated[
        Path,
        typer.Argument(help="Path to existing workspace with ZMK dependencies"),
    ],
    zmk_repo_url: Annotated[
        str,
        typer.Option("--zmk-repo", help="ZMK repository URL"),
    ] = "zmkfirmware/zmk",
    zmk_revision: Annotated[
        str,
        typer.Option("--zmk-revision", help="ZMK revision/branch"),
    ] = "main",
    cache_root: Annotated[
        Path | None,
        typer.Option("--cache-root", help="Cache root directory"),
    ] = None,
) -> None:
    """Inject base dependencies cache from existing workspace.

    This command creates a new base dependencies cache entry from an existing
    workspace that already contains ZMK dependencies (zephyr, zmk, modules).

    Args:
        workspace_path: Path to existing workspace with ZMK dependencies
        zmk_repo_url: ZMK repository URL for cache key generation
        zmk_revision: ZMK revision for cache key generation
        cache_root: Root directory for cache storage
    """
    try:
        workspace_path = workspace_path.resolve()

        typer.echo(
            f"Injecting base dependencies cache from workspace: {workspace_path}"
        )
        typer.echo(f"ZMK repository: {zmk_repo_url}@{zmk_revision}")

        if cache_root:
            typer.echo(f"Cache root: {cache_root}")

        cache_key = inject_base_dependencies_cache_from_workspace(
            source_workspace=workspace_path,
            zmk_repo_url=zmk_repo_url,
            zmk_revision=zmk_revision,
            cache_root=cache_root,
        )

        typer.echo("✅ Base dependencies cache injected successfully!")
        typer.echo(f"Cache key: {cache_key}")

    except Exception as e:
        logger.error("Failed to inject base dependencies cache: %s", e)
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1) from e


@cache_app.command(name="list-base-deps")
def list_base_deps_command(
    cache_root: Annotated[
        Path | None,
        typer.Option("--cache-root", help="Cache root directory"),
    ] = None,
) -> None:
    """List base dependencies cache entries."""
    try:
        from glovebox.compilation.cache.base_dependencies_cache import (
            create_base_dependencies_cache,
        )

        base_cache = create_base_dependencies_cache(cache_root=cache_root)

        if not base_cache.cache_root.exists():
            typer.echo("No base dependencies cache found.")
            return

        typer.echo(f"Base dependencies cache location: {base_cache.cache_root}")
        typer.echo()

        cache_entries = list(base_cache.cache_root.iterdir())
        if not cache_entries:
            typer.echo("No cache entries found.")
            return

        typer.echo("Available cache entries:")
        for entry in sorted(cache_entries):
            if entry.is_dir():
                metadata_file = entry / ".glovebox_cache_metadata.json"
                if metadata_file.exists():
                    try:
                        import json

                        metadata = json.loads(metadata_file.read_text())
                        created_at = metadata.get("created_at", "unknown")
                        zmk_repo = metadata.get("zmk_repo_url", "unknown")
                        zmk_revision = metadata.get("zmk_revision", "unknown")

                        typer.echo(f"  📦 {entry.name}")
                        typer.echo(f"     ZMK: {zmk_repo}@{zmk_revision}")
                        typer.echo(f"     Created: {created_at}")
                        typer.echo()
                    except Exception:
                        typer.echo(f"  📦 {entry.name} (metadata unavailable)")
                        typer.echo()
                else:
                    typer.echo(f"  📦 {entry.name} (no metadata)")
                    typer.echo()

    except Exception as e:
        logger.error("Failed to list base dependencies cache: %s", e)
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1) from e


@cache_app.command(name="cleanup")
def cleanup_command(
    max_age_days: Annotated[
        int,
        typer.Option("--max-age", help="Maximum age in days for cache entries"),
    ] = 30,
    cache_root: Annotated[
        Path | None,
        typer.Option("--cache-root", help="Cache root directory"),
    ] = None,
) -> None:
    """Clean up old cache entries."""
    try:
        from glovebox.compilation.cache.base_dependencies_cache import (
            create_base_dependencies_cache,
        )

        base_cache = create_base_dependencies_cache(cache_root=cache_root)

        typer.echo(f"Cleaning up cache entries older than {max_age_days} days...")
        base_cache.cleanup_cache(max_age_days=max_age_days)
        typer.echo("✅ Cache cleanup completed.")

    except Exception as e:
        logger.error("Failed to cleanup cache: %s", e)
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1) from e
