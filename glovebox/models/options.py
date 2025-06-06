# KConfig type definitions
from dataclasses import dataclass
from pathlib import Path


@dataclass
class BuildServiceCompileOpts:
    keymap_path: Path
    kconfig_path: Path
    output_dir: Path
    branch: str
    repo: str
    jobs: int
    verbose: bool
