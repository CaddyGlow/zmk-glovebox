# KConfig type definitions
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BuildServiceCompileOpts:
    """Options for building firmware with BuildService.

    Contains all the necessary configuration parameters for a firmware build.
    Used to provide type-safe configuration to the BuildService compile method.
    """

    keymap_path: Path
    """Path to the keymap (.keymap) file for the firmware build"""

    kconfig_path: Path
    """Path to the KConfig (.conf) file containing configuration options"""

    output_dir: Path
    """Directory where build artifacts will be stored"""

    branch: str = "main"
    """Git branch to use for the ZMK firmware repository (defaults to 'main')"""

    repo: str = "moergo-sc/zmk"
    """Git repository to use for the ZMK firmware (defaults to 'moergo-sc/zmk')"""

    jobs: int | None = None
    """Number of parallel jobs for compilation (None uses CPU count)"""

    verbose: bool = False
    """Enable verbose build output for debugging"""
