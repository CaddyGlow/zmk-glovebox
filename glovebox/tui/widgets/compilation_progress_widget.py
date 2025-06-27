"""Compilation progress widget for firmware build operations."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from .progress_widget import ProgressWidget


class CompilationProgressWidget(ProgressWidget[Any]):
    """Specialized progress widget for compilation operations.

    This widget extends ProgressWidget with compilation-specific display elements
    for firmware building operations, including:
    - Compilation phases (initialization, cache_restoration, west_update, building, cache_saving)
    - Repository and branch information
    - Multi-board build progress tracking
    - Build statistics and timing information
    - Visual indicators for different compilation phases
    """

    def __init__(
        self,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        """Initialize the compilation progress widget.

        Args:
            name: The name of the widget
            id: The ID of the widget
            classes: CSS classes for styling
            disabled: Whether the widget is disabled
        """
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)

        # Compilation-specific state
        self.compilation_phase = "initialization"
        self.current_repository = ""
        self.current_board = ""
        self.repositories_downloaded = 0
        self.total_repositories = 0
        self.boards_completed = 0
        self.total_boards = 0
        self.bytes_downloaded = 0
        self.total_bytes = 0
        self.overall_progress_percent = 0

    def compose(self) -> ComposeResult:
        """Compose the compilation progress widget layout."""
        with Vertical():
            # Status and phase information
            yield Static(self.status_text, id="status-text", classes="status")

            # Repository and phase info
            with Horizontal(classes="repo-info"):
                yield Static("⚙️", id="phase-icon", classes="icon")
                yield Static("", id="current-repo", classes="current-repo")
                yield Static("", id="phase-info", classes="phase")

            # Board information (for multi-board builds)
            with Horizontal(classes="board-info"):
                yield Static("🔨", id="board-icon", classes="icon")
                yield Static("", id="current-board", classes="current-board")
                yield Static("", id="board-progress", classes="board-progress")

            # Progress bars
            yield Static("", id="progress-info", classes="progress-info")
            from textual.widgets import ProgressBar

            yield ProgressBar(
                total=self.progress_total,
                show_eta=True,
                show_percentage=True,
                id="progress-bar",
            )

            # Build statistics
            with Horizontal(classes="build-stats"):
                yield Static("", id="repo-stats", classes="stats")
                yield Static("", id="download-stats", classes="stats")

            # Description and additional info
            yield Static(self.description, id="description", classes="description")

    def on_mount(self) -> None:
        """Initialize the compilation progress widget when mounted."""
        super().on_mount()

        # Get references to compilation-specific widgets
        self.phase_icon = self.query_one("#phase-icon", Static)
        self.current_repo_widget = self.query_one("#current-repo", Static)
        self.phase_info_widget = self.query_one("#phase-info", Static)
        self.board_icon = self.query_one("#board-icon", Static)
        self.current_board_widget = self.query_one("#current-board", Static)
        self.board_progress_widget = self.query_one("#board-progress", Static)
        self.progress_info_widget = self.query_one("#progress-info", Static)
        self.repo_stats_widget = self.query_one("#repo-stats", Static)
        self.download_stats_widget = self.query_one("#download-stats", Static)

    def _update_from_progress_data(self, progress_data: Any) -> None:
        """Update widget state from compilation progress data.

        Args:
            progress_data: Compilation progress data object
        """
        # Handle compilation-specific progress updates
        if hasattr(progress_data, "compilation_phase"):
            self.compilation_phase = progress_data.compilation_phase

            if hasattr(progress_data, "current_repository"):
                self.current_repository = progress_data.current_repository
                self._update_repo_display()

            # Update phase-specific information
            if self.compilation_phase == "initialization":
                self._handle_initialization_phase(progress_data)
            elif self.compilation_phase == "cache_restoration":
                self._handle_cache_restoration_phase(progress_data)
            elif self.compilation_phase == "workspace_setup":
                self._handle_workspace_setup_phase(progress_data)
            elif self.compilation_phase == "west_update":
                self._handle_west_update_phase(progress_data)
            elif self.compilation_phase == "building":
                self._handle_building_phase(progress_data)
            elif self.compilation_phase == "cache_saving":
                self._handle_cache_saving_phase(progress_data)
            else:
                self._handle_unknown_phase(progress_data)

        else:
            # Fallback for non-compilation progress data
            super()._update_from_progress_data(progress_data)

    def _handle_initialization_phase(self, progress_data: Any) -> None:
        """Handle initialization phase updates."""
        self.phase_icon.update("⚙️")
        self.status_text = f"⚙️ Setup: {self.current_repository}"
        self.phase_info_widget.update("(initialization)")

        if hasattr(progress_data, "repositories_downloaded") and hasattr(
            progress_data, "total_repositories"
        ):
            self.repositories_downloaded = progress_data.repositories_downloaded
            self.total_repositories = progress_data.total_repositories
            self.progress_current = self.repositories_downloaded
            self.progress_total = self.total_repositories
            self.description = f"Initializing ({self.compilation_phase})"
            self._update_repo_stats()

    def _handle_cache_restoration_phase(self, progress_data: Any) -> None:
        """Handle cache restoration phase updates."""
        self.phase_icon.update("💾")
        self.status_text = f"💾 Cache: {self.current_repository}"
        self.phase_info_widget.update("(cache restoration)")

        # Prefer bytes progress for cache restoration
        if hasattr(progress_data, "total_bytes") and progress_data.total_bytes > 0:
            if hasattr(progress_data, "bytes_downloaded"):
                self.bytes_downloaded = progress_data.bytes_downloaded
                self.total_bytes = progress_data.total_bytes
                self.progress_current = self.bytes_downloaded
                self.progress_total = self.total_bytes
                self.description = f"Restoring Cache ({self.compilation_phase})"
                self._update_download_stats()
        else:
            # Fallback to repository-based progress
            if hasattr(progress_data, "repositories_downloaded") and hasattr(
                progress_data, "total_repositories"
            ):
                self.repositories_downloaded = progress_data.repositories_downloaded
                self.total_repositories = progress_data.total_repositories
                self.progress_current = self.repositories_downloaded
                self.progress_total = self.total_repositories
                self.description = f"Restoring Cache ({self.compilation_phase})"
                self._update_repo_stats()

    def _handle_workspace_setup_phase(self, progress_data: Any) -> None:
        """Handle workspace setup phase updates."""
        self.phase_icon.update("🗂️")
        self.status_text = f"🗂️ Workspace: {self.current_repository}"
        self.phase_info_widget.update("(workspace setup)")

        # Use bytes progress if available
        if hasattr(progress_data, "total_bytes") and progress_data.total_bytes > 0:
            if hasattr(progress_data, "bytes_downloaded"):
                self.bytes_downloaded = progress_data.bytes_downloaded or 0
                self.total_bytes = progress_data.total_bytes
                self.progress_current = self.bytes_downloaded
                self.progress_total = self.total_bytes
                self.description = f"Setting up Workspace ({self.compilation_phase})"
                self._update_download_stats()
        else:
            # Arbitrary progress for workspace setup
            self.progress_current = 50
            self.progress_total = 100
            self.description = f"Setting up Workspace ({self.compilation_phase})"

    def _handle_west_update_phase(self, progress_data: Any) -> None:
        """Handle west update phase updates."""
        self.phase_icon.update("📦")
        self.status_text = f"📦 Downloading: {self.current_repository}"
        self.phase_info_widget.update("(west update)")

        if hasattr(progress_data, "repositories_downloaded") and hasattr(
            progress_data, "total_repositories"
        ):
            self.repositories_downloaded = progress_data.repositories_downloaded
            self.total_repositories = progress_data.total_repositories
            self.progress_current = self.repositories_downloaded
            self.progress_total = self.total_repositories
            self.description = f"West Update ({self.compilation_phase})"
            self._update_repo_stats()

    def _handle_building_phase(self, progress_data: Any) -> None:
        """Handle building phase updates."""
        self.phase_icon.update("🔨")
        self.phase_info_widget.update("(building)")

        # Enhanced building display with board information
        if hasattr(progress_data, "total_boards") and progress_data.total_boards > 1:
            # Multi-board display
            if hasattr(progress_data, "boards_completed"):
                self.boards_completed = progress_data.boards_completed
                self.total_boards = progress_data.total_boards
                board_info = f"({self.boards_completed + 1}/{self.total_boards})"

            if hasattr(progress_data, "current_board") and progress_data.current_board:
                self.current_board = progress_data.current_board
                self.status_text = f"🔨 Building: {self.current_board} {board_info if 'board_info' in locals() else ''}"
                self.current_board_widget.update(self.current_board)
            else:
                self.status_text = f"🔨 Building: {self.current_repository}"
                self.current_board_widget.update("")

            # Use overall progress for multi-board builds
            if hasattr(progress_data, "overall_progress_percent"):
                self.overall_progress_percent = progress_data.overall_progress_percent
                self.progress_current = self.overall_progress_percent
                self.progress_total = 100
                self.description = (
                    f"Building {board_info if 'board_info' in locals() else ''}"
                )
                self._update_board_progress()
        else:
            # Single board display
            self.status_text = f"🔨 Building: {self.current_repository}"
            self.current_board_widget.update("")

            if hasattr(progress_data, "overall_progress_percent"):
                self.overall_progress_percent = progress_data.overall_progress_percent
                self.progress_current = self.overall_progress_percent
                self.progress_total = 100
                self.description = f"Compiling ({self.compilation_phase})"

    def _handle_cache_saving_phase(self, progress_data: Any) -> None:
        """Handle cache saving phase updates."""
        self.phase_icon.update("💾")
        self.status_text = f"💾 Cache: {self.current_repository}"
        self.phase_info_widget.update("(cache saving)")

        if hasattr(progress_data, "overall_progress_percent"):
            self.overall_progress_percent = progress_data.overall_progress_percent
            self.progress_current = self.overall_progress_percent
            self.progress_total = 100
            self.description = f"Saving Build Cache ({self.compilation_phase})"

    def _handle_unknown_phase(self, progress_data: Any) -> None:
        """Handle unknown compilation phases."""
        self.phase_icon.update("⚙️")
        self.status_text = f"⚙️ {self.current_repository}"
        self.phase_info_widget.update(f"({self.compilation_phase})")

    def _update_repo_display(self) -> None:
        """Update the repository display with proper truncation."""
        if not self.current_repository:
            self.current_repo_widget.update("")
            return

        # Truncate long repository names for display
        max_length = 40
        repo_name = self.current_repository
        if len(repo_name) > max_length:
            repo_name = f"{repo_name[: max_length - 3]}..."

        self.current_repo_widget.update(repo_name)

    def _update_repo_stats(self) -> None:
        """Update repository statistics display."""
        if self.total_repositories > 0:
            self.repo_stats_widget.update(
                f"Repos: {self.repositories_downloaded}/{self.total_repositories}"
            )
        else:
            self.repo_stats_widget.update("")

    def _update_download_stats(self) -> None:
        """Update download statistics display."""
        if self.total_bytes > 0:
            # Format bytes in human-readable format
            def format_bytes(bytes_val: int) -> str:
                for unit in ["B", "KB", "MB", "GB"]:
                    if bytes_val < 1024:
                        return f"{bytes_val:.1f} {unit}"
                    bytes_val /= 1024
                return f"{bytes_val:.1f} TB"

            downloaded_str = format_bytes(self.bytes_downloaded)
            total_str = format_bytes(self.total_bytes)
            self.download_stats_widget.update(
                f"Downloaded: {downloaded_str}/{total_str}"
            )
        else:
            self.download_stats_widget.update("")

    def _update_board_progress(self) -> None:
        """Update board progress display."""
        if self.total_boards > 1:
            self.board_progress_widget.update(
                f"Board {self.boards_completed + 1}/{self.total_boards}"
            )
        else:
            self.board_progress_widget.update("")

    def _update_progress_info(self) -> None:
        """Update the progress information display."""
        if self.compilation_phase == "building" and self.total_boards > 1:
            # Multi-board progress
            board_percentage = (
                (self.boards_completed + (self.overall_progress_percent / 100))
                / self.total_boards
            ) * 100
            self.progress_info_widget.update(f"Overall: {board_percentage:.1f}%")
        elif self.overall_progress_percent > 0:
            # Single progress
            self.progress_info_widget.update(
                f"Progress: {self.overall_progress_percent:.1f}%"
            )
        elif self.total_repositories > 0:
            # Repository-based progress
            percentage = (self.repositories_downloaded / self.total_repositories) * 100
            self.progress_info_widget.update(f"Progress: {percentage:.1f}%")
        else:
            self.progress_info_widget.update("")

    # Override reactive watchers to update compilation-specific displays
    def watch_progress_current(self, progress_current: int) -> None:
        """React to progress current changes."""
        super().watch_progress_current(progress_current)
        self._update_progress_info()

    def watch_progress_total(self, progress_total: int) -> None:
        """React to progress total changes."""
        super().watch_progress_total(progress_total)
        self._update_progress_info()

    def complete_progress(self, result: Any = None) -> None:
        """Mark the compilation operation as completed.

        Args:
            result: Optional result data to store
        """
        super().complete_progress(result)

        # Update compilation-specific completion display
        self.phase_icon.update("✅")
        self.current_repo_widget.update("Build completed")
        self.phase_info_widget.update("(finished)")

        if self.total_boards > 1:
            self.board_progress_widget.update(f"✅ All {self.total_boards} boards")
        else:
            self.board_progress_widget.update("✅ Build complete")

        if self.total_repositories > 0:
            self.repo_stats_widget.update(
                f"✅ Processed: {self.total_repositories} repos"
            )

        # Clear current board display
        self.current_board_widget.update("")


def create_compilation_progress_widget(**kwargs: Any) -> CompilationProgressWidget:
    """Factory function to create a compilation progress widget.

    Args:
        **kwargs: Keyword arguments for the widget

    Returns:
        A new CompilationProgressWidget instance
    """
    return CompilationProgressWidget(**kwargs)
