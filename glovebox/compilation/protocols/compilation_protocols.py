"""Compilation service protocols."""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from glovebox.core.file_operations import CompilationProgressCallback
from glovebox.firmware.models import BuildResult


if TYPE_CHECKING:
    from glovebox.compilation.models import CompilationConfigUnion
    from glovebox.config.profile import KeyboardProfile


@runtime_checkable
class CompilationServiceProtocol(Protocol):
    """Protocol for compilation strategy services."""

    def compile(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: "CompilationConfigUnion",
        keyboard_profile: "KeyboardProfile",
        progress_callback: CompilationProgressCallback | None = None,
        json_file: Path | None = None,
    ) -> BuildResult:
        """Execute compilation using this strategy.

        Args:
            keymap_file: Path to keymap file
            config_file: Path to config file
            output_dir: Output directory for build artifacts
            config: Compilation configuration
            keyboard_profile: Keyboard profile for dynamic generation
            progress_callback: Optional callback for compilation progress updates
            json_file: Optional path to original JSON layout file for metadata

        Returns:
            BuildResult: Results of compilation
        """
        ...

    def compile_from_json(
        self,
        json_file: Path,
        output_dir: Path,
        config: "CompilationConfigUnion",
        keyboard_profile: "KeyboardProfile",
        progress_callback: CompilationProgressCallback | None = None,
    ) -> BuildResult:
        """Execute compilation from JSON layout file.

        Args:
            json_file: Path to JSON layout file
            output_dir: Output directory for build artifacts
            config: Compilation configuration
            keyboard_profile: Keyboard profile for dynamic generation
            progress_callback: Optional callback for compilation progress updates

        Returns:
            BuildResult: Results of compilation
        """
        ...

    def compile_from_data(
        self,
        layout_data: dict[str, Any],
        output_dir: Path,
        config: "CompilationConfigUnion",
        keyboard_profile: "KeyboardProfile",
        progress_callback: CompilationProgressCallback | None = None,
    ) -> BuildResult:
        """Execute compilation from layout data dictionary.

        This is the memory-first method that takes layout data as input
        and returns content in the result object, following the unified
        input/output patterns established in Phase 1/2 refactoring.

        Args:
            layout_data: Layout data dictionary (validated as LayoutData)
            output_dir: Output directory for build artifacts
            config: Compilation configuration
            keyboard_profile: Keyboard profile for dynamic generation
            progress_callback: Optional callback for compilation progress updates

        Returns:
            BuildResult: Results of compilation with generated content
        """
        ...

    def validate_config(self, config: "CompilationConfigUnion") -> bool:
        """Validate configuration for this compilation strategy.

        Args:
            config: Compilation configuration to validate

        Returns:
            bool: True if configuration is valid
        """
        ...

    def check_available(self) -> bool:
        """Check if this compilation strategy is available.

        Returns:
            bool: True if strategy is available
        """
        ...
