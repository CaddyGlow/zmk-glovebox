"""ZMK West progress coordinator with workspace integration."""

from __future__ import annotations

from glovebox.cli.progress.coordinators.base import BaseProgressCoordinator
from glovebox.cli.progress.models import ProgressContext, WorkspaceOperation
from glovebox.compilation.models import CompilationProgress, CompilationState


class ZmkWestProgressCoordinator(BaseProgressCoordinator):
    """Progress coordinator for ZMK West compilation strategy."""

    def __init__(self, context: ProgressContext) -> None:
        """Initialize ZMK West coordinator."""
        super().__init__(context)
        self._setup_zmk_phases()

    def _setup_zmk_phases(self) -> None:
        """Setup ZMK-specific compilation phases."""
        zmk_phases = [
            "workspace_setup",
            "west_init",
            "west_update",
            "compilation",
            "post_processing",
        ]

        if not self.context.progress.total_stages:
            self.context.progress.total_stages = len(zmk_phases)

        self.context.strategy_data["phases"] = zmk_phases

    def update_progress(self, progress: CompilationProgress) -> None:
        """Update progress with ZMK West-specific handling."""
        # Enhanced phase detection for ZMK West
        self._detect_zmk_phase(progress)
        super().update_progress(progress)

    def _detect_zmk_phase(self, progress: CompilationProgress) -> None:
        """Detect current ZMK compilation phase from progress."""
        description = progress.description.lower() if progress.description else ""

        # Map common ZMK West output to workspace operations
        if "west init" in description:
            self.update_workspace(WorkspaceOperation.WEST_INIT)
        elif "west update" in description:
            self.update_workspace(WorkspaceOperation.WEST_UPDATE)
        elif "restoring" in description and "cache" in description:
            self.update_workspace(WorkspaceOperation.CACHE_RESTORE)
        elif "copying" in description:
            # Try to extract component name from description
            component = self._extract_component_name(description)
            self.update_workspace(WorkspaceOperation.COMPONENT_COPY, component)

    def _extract_component_name(self, description: str) -> str | None:
        """Extract component name from compilation output."""
        # Common ZMK component patterns
        components = ["zmk", "zephyr", "modules", ".west"]

        for component in components:
            if component in description:
                return component

        return None

    def handle_phase_change(self, old_phase: str, new_phase: str) -> None:
        """Handle ZMK West-specific phase changes."""
        super().handle_phase_change(old_phase, new_phase)

        # Update stage counter for staged display
        phases = self.context.strategy_data.get("phases", [])
        if new_phase in phases:
            stage_index = phases.index(new_phase)
            self.context.progress.current_stage = stage_index + 1

    def get_estimated_duration(self, phase: str) -> float:
        """Get estimated duration for ZMK West phases."""
        # Rough estimates based on typical ZMK compilation times
        phase_durations = {
            "workspace_setup": 10.0,
            "west_init": 5.0,
            "west_update": 30.0,
            "compilation": 120.0,
            "post_processing": 5.0,
        }
        return phase_durations.get(phase, 10.0)
