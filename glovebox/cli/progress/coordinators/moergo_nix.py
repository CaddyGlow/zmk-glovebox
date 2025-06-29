"""MoErgo Nix progress coordinator with workspace integration."""

from __future__ import annotations

from glovebox.cli.progress.coordinators.base import BaseProgressCoordinator
from glovebox.cli.progress.models import ProgressContext, WorkspaceOperation
from glovebox.compilation.models import CompilationProgress


class MoergoNixProgressCoordinator(BaseProgressCoordinator):
    """Progress coordinator for MoErgo Nix compilation strategy."""

    def __init__(self, context: ProgressContext) -> None:
        """Initialize MoErgo Nix coordinator."""
        super().__init__(context)
        self._setup_moergo_phases()

    def _setup_moergo_phases(self) -> None:
        """Setup MoErgo Nix-specific compilation phases."""
        moergo_phases = [
            "workspace_setup",
            "nix_setup",
            "dependency_fetch",
            "compilation",
            "post_processing",
        ]

        if not self.context.progress.total_stages:
            self.context.progress.total_stages = len(moergo_phases)

        self.context.strategy_data["phases"] = moergo_phases

    def update_progress(self, progress: CompilationProgress) -> None:
        """Update progress with MoErgo Nix-specific handling."""
        self._detect_moergo_phase(progress)
        super().update_progress(progress)

    def _detect_moergo_phase(self, progress: CompilationProgress) -> None:
        """Detect current MoErgo compilation phase from progress."""
        description = progress.description.lower() if progress.description else ""

        # Map common MoErgo Nix output to workspace operations
        if "nix" in description and "setup" in description:
            self.update_workspace(WorkspaceOperation.WORKSPACE_INIT)
        elif "fetching" in description or "downloading" in description:
            # Try to extract what's being fetched
            component = self._extract_fetch_target(description)
            self.update_workspace(WorkspaceOperation.COMPONENT_COPY, component)
        elif "restoring" in description and "cache" in description:
            self.update_workspace(WorkspaceOperation.CACHE_RESTORE)

    def _extract_fetch_target(self, description: str) -> str | None:
        """Extract what's being fetched from Nix output."""
        # Common Nix fetch patterns
        if "zmk" in description:
            return "zmk"
        elif "zephyr" in description:
            return "zephyr"
        elif "toolchain" in description:
            return "toolchain"
        elif "dependencies" in description:
            return "dependencies"

        return None

    def handle_phase_change(self, old_phase: str, new_phase: str) -> None:
        """Handle MoErgo Nix-specific phase changes."""
        super().handle_phase_change(old_phase, new_phase)

        # Update stage counter for staged display
        phases = self.context.strategy_data.get("phases", [])
        if new_phase in phases:
            stage_index = phases.index(new_phase)
            self.context.progress.current_stage = stage_index + 1

    def get_estimated_duration(self, phase: str) -> float:
        """Get estimated duration for MoErgo Nix phases."""
        # Rough estimates based on typical Nix compilation times
        phase_durations = {
            "workspace_setup": 5.0,
            "nix_setup": 15.0,
            "dependency_fetch": 60.0,
            "compilation": 180.0,  # Nix can be slower
            "post_processing": 5.0,
        }
        return phase_durations.get(phase, 15.0)
