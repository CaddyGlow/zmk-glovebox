# Simplified Docker Volume Strategy - Feature Plan

## Overview

Simplify the Docker compilation workflow by using a single workspace volume, then extracting artifacts post-execution. This eliminates complex Docker volume mounting issues and provides better control over workspace management and artifact collection.

## Current Problems

### Docker Volume Complexity
- Multiple volume mounts (workspace + output) create confusion
- Host path vs named volume ambiguity (e.g., `build:/output` vs `/path/to/build:/output`)
- Different compilation strategies have different artifact locations
- Artifact collection must scan multiple locations

### Workspace Management Issues
- Workspaces left in current directory by default
- No user control over workspace location
- No configurable cleanup policy
- Workspace paths not predictable

### Artifact Collection Complexity
- Over-engineered scanner with complex pattern matching
- Multiple directory structure strategies (west, zmk_config, legacy)
- Validator and complex search patterns that are hard to maintain
- Doesn't follow ZMK GitHub Actions conventions

## Proposed Solution

### Single Volume Strategy
1. **One Volume Only**: Mount only the workspace volume to Docker container
2. **Post-Execution Extraction**: After Docker build completes, scan workspace for artifacts
3. **Controlled Copy**: Copy found artifacts to desired output location
4. **Configurable Cleanup**: Optionally remove workspace based on user settings

### Configurable Workspace Management
1. **Default Workspace Location**: `/tmp/glovebox-workspaces/` (Linux/macOS), system temp (Windows)
2. **Random Workspace Names**: Use UUID or timestamp for unique workspace directories
3. **User-Configurable Defaults**: Allow users to set preferred workspace root in config
4. **CLI Overrides**: Support `--workspace-dir` flag for specific builds
5. **Profile Overrides**: Allow keyboard profiles to specify workspace preferences

### Simplified Artifact Collection (MAJOR CHANGE)
**Remove entire complex artifact collection system** and replace with simple, ZMK GitHub Actions-based approach:

1. **Delete Complex System**: Remove `glovebox/compilation/artifacts/` (validator, scanner patterns, etc.)
2. **Delete Related Tests**: Remove pytest tests for complex artifact scanning
3. **Use Build Matrix**: Leverage `build.yaml` matrix for artifact naming and location
4. **Follow ZMK Conventions**: Use ZMK GitHub Actions naming pattern

## Implementation Plan

### Phase 1: Configuration System Enhancement

#### User Configuration Schema
```yaml
# ~/.config/glovebox/config.yaml
compilation:
  workspace:
    # Base directory for temporary workspaces (default: system temp)
    root_directory: "/tmp/glovebox-workspaces"
    # Whether to remove workspace after compilation (default: true)
    cleanup_after_build: true
    # Whether to preserve workspace on build failure for debugging (default: false)
    preserve_on_failure: false
    # Maximum number of old workspaces to keep (default: 5)
    max_preserved_workspaces: 5
  artifacts:
    # Artifact naming strategy (default: zmk_github_actions)
    naming_strategy: "zmk_github_actions"  # zmk_github_actions, descriptive, preserve
```

#### CLI Parameter Support
```bash
# Override workspace root for this build
glovebox firmware compile keymap.keymap config.conf --workspace-dir /custom/workspace/root

# Preserve workspace for debugging
glovebox firmware compile keymap.keymap config.conf --preserve-workspace

# Force cleanup even if preserve_on_failure is set
glovebox firmware compile keymap.keymap config.conf --force-cleanup
```

#### Keyboard Profile Schema
```yaml
# keyboards/glove80.yaml
compile_methods:
  - method_type: generic_docker
    strategy: zmk_config
    workspace:
      # Optional: override default workspace root for this keyboard
      root_directory: "/tmp/glove80-builds"
      # Optional: preserve workspaces for this keyboard (useful for development)
      cleanup_after_build: false
```

### Phase 2: Workspace Manager Refactoring

#### New WorkspaceManager Interface
```python
class WorkspaceManager:
    def create_workspace(
        self, 
        keyboard_name: str,
        strategy: str,
        root_dir: Path | None = None
    ) -> WorkspaceContext:
        """Create temporary workspace with unique name."""
        
    def cleanup_workspace(self, workspace: WorkspaceContext) -> bool:
        """Remove workspace directory and contents."""
        
    def preserve_workspace(self, workspace: WorkspaceContext, reason: str) -> Path:
        """Move workspace to preservation location with metadata."""
```

#### WorkspaceContext Class
```python
@dataclass
class WorkspaceContext:
    path: Path
    keyboard_name: str
    strategy: str
    created_at: datetime
    should_cleanup: bool
    preserved: bool = False
    
    def __enter__(self) -> Path:
        """Context manager entry - returns workspace path."""
        
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - handles cleanup based on settings."""
```

### Phase 3: Compilation Service Simplification

#### Simplified Docker Volume Strategy
```python
class BaseCompilationService:
    def _prepare_build_volumes(self, workspace_path: Path) -> list[tuple[str, str]]:
        """Prepare Docker volumes - ONLY workspace volume."""
        return [(str(workspace_path.resolve()), "/workspace")]
        
    def _execute_compilation(self, workspace_context: WorkspaceContext, config: CompilationConfig) -> BuildResult:
        """Execute compilation with simplified volume strategy."""
        # 1. Run Docker with only workspace volume
        # 2. Extract artifacts from workspace using build matrix
        # 3. Copy to output directory with ZMK naming
        # 4. Cleanup workspace based on settings
```

### Phase 4: Simple Artifact Collection System

#### Complete Removal of Complex System
**Files to Delete:**
- `glovebox/compilation/artifacts/collector.py`
- `glovebox/compilation/artifacts/firmware_scanner.py`
- `glovebox/compilation/artifacts/validator.py`
- `tests/test_compilation/test_artifacts/` (entire directory)
- All related complex scanning logic

#### New Simple Artifact Collector
```python
class SimpleArtifactCollector:
    """Simple artifact collector using ZMK GitHub Actions conventions."""
    
    def collect_from_workspace(
        self, 
        workspace_path: Path,
        build_matrix: BuildMatrix
    ) -> dict[str, Path]:
        """Collect artifacts using build matrix for naming and location."""
        artifacts = {}
        
        for entry in build_matrix.include:
            # Generate expected artifact name using ZMK pattern
            artifact_name = self._generate_zmk_artifact_name(entry)
            
            # Look for .uf2 file in expected build location
            build_dir = self._get_build_directory(workspace_path, entry)
            uf2_file = build_dir / "zephyr" / "zmk.uf2"
            
            if uf2_file.exists():
                artifacts[artifact_name] = uf2_file
                self.logger.info("Found artifact: %s -> %s", artifact_name, uf2_file)
            else:
                self.logger.warning("Expected artifact not found: %s at %s", artifact_name, uf2_file)
        
        return artifacts
    
    def _generate_zmk_artifact_name(self, matrix_entry: BuildMatrixEntry) -> str:
        """Generate artifact name using ZMK GitHub Actions pattern.
        
        Based on: artifact_name=${artifact_name:-${shield:+$shield-}${board}-zmk}
        """
        if matrix_entry.artifact_name:
            return f"{matrix_entry.artifact_name}.uf2"
        
        shield_prefix = f"{matrix_entry.shield}-" if matrix_entry.shield else ""
        return f"{shield_prefix}{matrix_entry.board}-zmk.uf2"
    
    def _get_build_directory(self, workspace_path: Path, entry: BuildMatrixEntry) -> Path:
        """Get expected build directory for matrix entry."""
        if entry.shield:
            # Split keyboard builds use separate directories
            return workspace_path / f"build_{entry.shield}"
        else:
            # Single board builds use build directory
            return workspace_path / "build"
    
    def copy_to_output(
        self,
        artifacts: dict[str, Path], 
        output_dir: Path
    ) -> dict[str, Path]:
        """Copy artifacts to output directory preserving ZMK names."""
        copied_artifacts = {}
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for artifact_name, source_path in artifacts.items():
            dest_path = output_dir / artifact_name
            shutil.copy2(source_path, dest_path)
            copied_artifacts[artifact_name] = dest_path
            self.logger.info("Copied artifact: %s -> %s", source_path, dest_path)
            
        return copied_artifacts
```

#### Build Matrix Integration
```python
@dataclass
class BuildMatrixEntry:
    board: str
    shield: str | None = None
    artifact_name: str | None = None
    snippet: str | None = None
    cmake_args: list[str] = field(default_factory=list)

class BuildMatrix:
    """Represents ZMK build.yaml matrix configuration."""
    include: list[BuildMatrixEntry]
    
    @classmethod
    def from_yaml_file(cls, yaml_file: Path) -> "BuildMatrix":
        """Load build matrix from build.yaml file."""
        with yaml_file.open() as f:
            data = yaml.safe_load(f)
        
        entries = []
        for item in data.get("include", []):
            entries.append(BuildMatrixEntry(**item))
        
        return cls(include=entries)
```

### Phase 5: ZMK GitHub Actions Environment Variables

#### Environment Variable Generation
```python
def generate_zmk_env_vars(matrix_entry: BuildMatrixEntry) -> dict[str, str]:
    """Generate environment variables following ZMK GitHub Actions pattern."""
    env_vars = {
        "board": matrix_entry.board,
        "display_name": f"{matrix_entry.shield + ' - ' if matrix_entry.shield else ''}{matrix_entry.board}",
    }
    
    if matrix_entry.shield:
        env_vars["shield"] = matrix_entry.shield
        
    if matrix_entry.artifact_name:
        env_vars["artifact_name"] = matrix_entry.artifact_name
    else:
        shield_prefix = f"{matrix_entry.shield}-" if matrix_entry.shield else ""
        env_vars["artifact_name"] = f"{shield_prefix}{matrix_entry.board}-zmk"
    
    if matrix_entry.snippet:
        env_vars["snippet"] = matrix_entry.snippet
        env_vars["extra_west_args"] = f'-S "{matrix_entry.snippet}"'
    
    # Generate cmake args
    cmake_args = []
    if matrix_entry.shield:
        cmake_args.append(f'-DSHIELD="{matrix_entry.shield}"')
    cmake_args.extend(matrix_entry.cmake_args)
    
    if cmake_args:
        env_vars["extra_cmake_args"] = " ".join(cmake_args)
    
    return env_vars
```

### Phase 6: Configuration Integration

#### CompilationConfig Updates
```python
@dataclass
class CompilationConfig:
    # ... existing fields ...
    
    # Workspace configuration
    workspace_root: Path | None = None
    cleanup_workspace: bool = True
    preserve_on_failure: bool = False
    
    # Artifact handling
    artifact_naming: str = "zmk_github_actions"  # zmk_github_actions, descriptive, preserve
    build_matrix_file: Path | None = None  # Path to build.yaml
```

#### CLI Integration
```python
@firmware_app.command(name="compile")
def firmware_compile(
    # ... existing parameters ...
    
    workspace_dir: Annotated[
        Path | None,
        typer.Option("--workspace-dir", help="Custom workspace root directory")
    ] = None,
    preserve_workspace: Annotated[
        bool,
        typer.Option("--preserve-workspace", help="Don't delete workspace after build")
    ] = False,
    force_cleanup: Annotated[
        bool, 
        typer.Option("--force-cleanup", help="Force workspace cleanup even on failure")
    ] = False,
    build_matrix: Annotated[
        Path | None,
        typer.Option("--build-matrix", help="Path to build.yaml file (auto-detected if not specified)")
    ] = None,
):
```

## Benefits

### Simplified Architecture
- **Single Volume**: Only workspace volume mounted to Docker
- **Matrix-Based**: Use build.yaml matrix for deterministic artifact handling
- **ZMK Standard**: Follow established ZMK GitHub Actions conventions
- **Debuggable**: Option to preserve workspaces for troubleshooting

### User Experience Improvements
- **Familiar Naming**: Artifacts named like ZMK GitHub Actions builds
- **Predictable**: Always know what artifacts to expect from build matrix
- **Configurable Defaults**: Set workspace preferences once in config
- **CLI Flexibility**: Override settings per build as needed

### Developer Benefits
- **Much Simpler Code**: Remove thousands of lines of complex scanning logic
- **Maintainable**: Follow established patterns instead of custom complexity
- **Testable**: Simple, predictable artifact collection logic
- **Standards-Based**: Use same conventions as official ZMK builds

## Migration Strategy

### Phase 1: Configuration Layer (Week 1)
1. Add workspace configuration to user config schema
2. Add CLI parameters for workspace control
3. Add keyboard profile workspace overrides
4. Add build matrix configuration support

### Phase 2: Artifact System Removal (Week 2)
1. **DELETE** complex artifact collection system
2. **DELETE** related pytest tests
3. **DELETE** validator and complex scanner classes
4. Update imports and references

### Phase 3: Simple Artifact Collector (Week 3)
1. Implement SimpleArtifactCollector with ZMK naming
2. Add BuildMatrix and BuildMatrixEntry classes
3. Implement ZMK environment variable generation
4. Add build matrix YAML loading

### Phase 4: Workspace Management (Week 4)
1. Implement WorkspaceManager and WorkspaceContext
2. Add workspace creation with unique naming
3. Implement configurable cleanup logic
4. Add workspace preservation for debugging

### Phase 5: Volume Strategy Simplification (Week 5)
1. Remove output volume from Docker mounts
2. Update all compilation services to use single workspace volume
3. Implement post-execution artifact extraction using build matrix
4. Add matrix-based artifact collection

### Phase 6: Testing and Documentation (Week 6)
1. Comprehensive testing with simplified system
2. Update user documentation
3. Add troubleshooting guides for workspace management
4. Performance testing and optimization

## Configuration Examples

### Basic User Config
```yaml
compilation:
  workspace:
    root_directory: "~/tmp/glovebox"
    cleanup_after_build: true
    preserve_on_failure: true
  artifacts:
    naming_strategy: "zmk_github_actions"
```

### Development Setup
```yaml
compilation:
  workspace:
    root_directory: "/dev/glovebox-workspaces"
    cleanup_after_build: false  # Keep for debugging
    max_preserved_workspaces: 20
```

### ZMK Build Matrix Example
```yaml
# build.yaml (automatically generated or user-provided)
include:
  - board: nice_nano_v2
    shield: corne_left
  - board: nice_nano_v2
    shield: corne_right
  - board: glove80_lh
    shield: glove80_left
    artifact-name: glove80-left-custom
  - board: glove80_rh  
    shield: glove80_right
    artifact-name: glove80-right-custom
```

**Expected Artifacts:**
- `corne_left-nice_nano_v2-zmk.uf2`
- `corne_right-nice_nano_v2-zmk.uf2`
- `glove80-left-custom.uf2`
- `glove80-right-custom.uf2`

## Future Enhancements

### Advanced Matrix Features
- Support for ZMK snippets and cmake arguments
- Matrix expansion for multiple board/shield combinations
- Conditional matrix entries based on keyboard features

### Workspace Caching
- Cache common dependencies between builds
- Share base ZMK repositories across workspaces
- Implement workspace templates for faster initialization

### Build Artifacts Management
- Archive successful builds with metadata
- Implement build artifact tagging and retrieval
- Add build reproducibility tracking

## Conclusion

This simplified approach removes significant complexity while aligning with ZMK ecosystem standards. By removing the over-engineered artifact collection system and using the established `build.yaml` matrix pattern, we achieve:

1. **Massive code reduction** - Remove thousands of lines of complex logic
2. **Standards compliance** - Follow ZMK GitHub Actions conventions exactly
3. **Predictable behavior** - Use matrix entries to know exactly what to expect
4. **Simplified maintenance** - Much less code to maintain and debug
5. **Better user experience** - Familiar naming and patterns for ZMK users

The single-volume Docker strategy combined with matrix-based artifact collection provides a clean, maintainable, and user-friendly compilation system.