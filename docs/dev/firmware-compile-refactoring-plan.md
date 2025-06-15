# Firmware Compile Refactoring Plan

## Executive Summary

This document outlines a comprehensive refactoring plan for the firmware compile CLI command, CompilationService, and related configuration systems. The current implementation violates several CLAUDE.md specifications and exceeds complexity limits, requiring systematic refactoring to improve maintainability and align with project conventions.

## Current State Analysis

### Critical Issues Identified

1. **File/Method Size Violations:**
   - `firmware_compile()` CLI command: **315 lines** (violates 50-line method limit)
   - `BaseCompilationService`: **524 lines** (violates 500-line file limit)
   - `ZmkConfigCompilationService`: **381 lines** (approaching 500-line limit)
   - Multiple helper methods exceed 50-line limits

2. **Architecture Complexity:**
   - Over-engineered template method pattern in `BaseCompilationService`
   - Complex parameter objects (`ZmkCompilationParams`, `ZmkConfigGenerationParams`)
   - Tight coupling between CLI, services, and configuration layers
   - Inconsistent factory function usage

3. **CLAUDE.md Convention Violations:**
   - Not following domain-driven design principles effectively
   - Over-complex for a 2-3 developer team
   - Missing clear service boundaries
   - Inconsistent naming conventions

4. **Code Quality Issues:**
   - Long parameter lists
   - Deeply nested conditional logic
   - Repetitive configuration setup
   - Complex workspace management

## Refactoring Strategy

### Phase 1: CLI Command Decomposition & Option Cleanup

**Objective:** Break down the massive `firmware_compile()` function and remove over-engineered CLI options.

#### Critical Finding: Massive CLI Option Bloat
**Analysis reveals that 15+ out of ~20 CLI options are completely unused!**

- **Dead code options:** `output_dir`, `branch`, `repo`, `jobs`, `verbose`, `no_cache`, `clear_cache`, `board_targets`
- **Unused Docker options:** `docker_uid`, `docker_gid`, `docker_username`, `docker_home`, `docker_container_home`, `no_docker_user_mapping`
- **Unused workspace options:** `workspace_dir`, `preserve_workspace`, `force_cleanup`, `build_matrix`

#### Simplified CLI Interface:
```python
# firmware.py (target: <100 lines total)
@firmware_app.command(name="compile")
@handle_errors
@with_profile()
def firmware_compile(
    ctx: typer.Context,
    keymap_file: Annotated[Path, typer.Argument(help="Path to keymap (.keymap) file")],
    kconfig_file: Annotated[Path, typer.Argument(help="Path to kconfig (.conf) file")],
    profile: ProfileOption = None,
    strategy: Annotated[str | None, typer.Option("--strategy", help="Compilation strategy")] = None,
    output_format: OutputFormatOption = "text",
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose output")] = False,
    debug: Annotated[bool, typer.Option("--debug", help="Enable debug mode")] = False,
) -> None:
    """Build ZMK firmware from keymap and config files (target: <25 lines)."""
    # 1. Get profile and create compile request
    keyboard_profile = get_keyboard_profile_from_context(ctx)
    request = CompileRequest(
        keymap_file=keymap_file,
        config_file=kconfig_file,
        keyboard_profile=keyboard_profile,
        strategy=strategy,
        verbose=verbose,
        debug=debug
    )
    
    # 2. Execute compilation
    service = create_compilation_service(request.resolved_strategy)
    result = service.compile(request)
    
    # 3. Format output
    _format_compilation_output(result, output_format)

def _format_compilation_output(result: BuildResult, format: str) -> None:
    """Format and display compilation results (target: <20 lines)."""
    pass
```

#### Configuration Migration Strategy:
Move complex options to appropriate configuration files:

```yaml
# ~/.config/glovebox/config.yaml (user settings)
compilation:
  default_jobs: 4
  cache_enabled: true
  workspace_cleanup: true
  docker:
    user_mapping: true
    auto_detect_user: true

# keyboards/glove80.yaml (keyboard profile)
compile_methods:
  - strategy: zmk_config
    image: zmkfirmware/zmk-build-arm:stable
    repository: zmkfirmware/zmk
    branch: main
    board_targets: [glove80_lh, glove80_rh]
    workspace:
      preserve_on_failure: false
      build_matrix: build.yaml
```

#### Benefits:
- **Reduced CLI complexity:** From 20+ options to 6 essential options
- **Better UX:** Simple, focused interface for common use cases
- **Configuration-driven:** Complex settings in appropriate config files
- **Maintainable:** Drastically reduced parameter handling code
- **CLAUDE.md compliant:** Eliminates over-engineering for small team

#### CLI Option Cleanup Decision Matrix:

| Option | Current Status | Decision | Rationale |
|--------|----------------|----------|-----------|
| `keymap_file` | ✅ Used | **Keep** | Essential argument |
| `kconfig_file` | ✅ Used | **Keep** | Essential argument |
| `profile` | ✅ Used | **Keep** | Core functionality |
| `strategy` | ✅ Used | **Keep** | Essential for multi-strategy support |
| `output_format` | ✅ Used | **Keep** | Essential for automation |
| `output_dir` | ❌ Ignored | **Remove** | Hardcoded to 'build' anyway |
| `branch` | ❌ Unused | **Remove** | Use profile configuration |
| `repo` | ❌ Unused | **Remove** | Use profile configuration |
| `jobs` | ❌ Unused | **Remove** | Move to user config |
| `verbose` | ❌ Unused | **Add & Implement** | Useful for debugging |
| `no_cache` | ❌ Unused | **Remove** | Move to user config |
| `clear_cache` | ❌ Unused | **Remove** | Move to user config |
| `board_targets` | ❌ Unused | **Remove** | Move to profile config |
| All Docker options | ❌ Unused | **Remove** | Move to user config |
| All Workspace options | ❌ Unused | **Remove** | Move to user config |

**Result: 20+ options → 6 essential options (70% reduction)**

#### Essential Options to Keep & Implement:

```python
def firmware_compile(
    ctx: typer.Context,
    keymap_file: Path,                    # ✅ Essential: Input file
    kconfig_file: Path,                   # ✅ Essential: Input file  
    profile: ProfileOption = None,        # ✅ Essential: Configuration source
    strategy: str | None = None,          # ✅ Essential: Multi-strategy support
    output_format: OutputFormatOption = "text",  # ✅ Essential: JSON/text output
    verbose: bool = False,                # ✅ Add: Actually implement for debugging
) -> None:
```

#### Configuration-First Approach:
Instead of CLI options, use configuration files for complex settings:

```yaml
# User Config (~/.config/glovebox/config.yaml)
compilation:
  docker:
    user_mapping: true
    auto_detect_user: true
    uid: 1000  # Optional override
    gid: 1000  # Optional override
  workspace:
    cleanup_after_build: true
    preserve_on_failure: false
    base_directory: "~/.cache/glovebox/workspaces"
  cache:
    enabled: true
    max_age_hours: 24
  build:
    parallel_jobs: 4
    timeout_minutes: 30
```

This eliminates the need for 15+ CLI options while providing the same functionality through proper configuration management.

### Phase 2: Service Layer Simplification

**Objective:** Simplify the compilation service architecture by removing over-engineered patterns and focusing on pragmatic solutions.

#### Current Issues:
- `BaseCompilationService` uses complex template method pattern
- Abstract methods create unnecessary complexity
- Too many configuration managers and dependency injection

#### Target Architecture:
```python
# Simple, focused compilation services
class ZmkConfigCompilationService:
    """ZMK config compilation service (target: <200 lines)."""
    
    def __init__(self, docker_adapter: DockerAdapterProtocol):
        """Simple constructor with minimal dependencies."""
        self.docker_adapter = docker_adapter
        self.logger = logging.getLogger(__name__)
    
    def compile(self, request: CompileRequest) -> BuildResult:
        """Main compilation method (target: <40 lines)."""
        # 1. Setup workspace
        workspace = self._setup_workspace(request)
        
        # 2. Execute docker build
        result = self._execute_docker_build(workspace, request)
        
        # 3. Collect artifacts
        artifacts = self._collect_artifacts(workspace, request.output_dir)
        
        return BuildResult(success=True, output_files=artifacts)
    
    def _setup_workspace(self, request: CompileRequest) -> WorkspacePath:
        """Setup compilation workspace (target: <25 lines)."""
        pass
    
    def _execute_docker_build(self, workspace: WorkspacePath, request: CompileRequest) -> None:
        """Execute Docker compilation (target: <30 lines)."""
        pass
    
    def _collect_artifacts(self, workspace: WorkspacePath, output_dir: Path) -> list[Path]:
        """Collect compilation artifacts (target: <20 lines)."""
        pass
```

#### Key Changes:
- Remove `BaseCompilationService` template method complexity
- Use simple, direct method calls instead of abstract method patterns
- Eliminate complex parameter objects
- Focus on essential functionality only

### Phase 3: Configuration System Streamlining

**Objective:** Simplify the configuration system to reduce complexity while maintaining functionality.

#### Current Issues:
- Too many configuration classes with overlapping responsibilities
- Complex parameter objects that obscure simple data passing
- Over-engineered workspace configuration

#### Target Structure:
```python
# Simplified configuration models
@dataclass
class CompileRequest:
    """Simple compilation request (replaces complex parameter objects)."""
    keymap_file: Path
    config_file: Path
    output_dir: Path
    keyboard_profile: KeyboardProfile
    docker_image: str
    workspace_config: WorkspaceConfig
    build_options: BuildOptions

@dataclass
class WorkspaceConfig:
    """Simplified workspace configuration."""
    workspace_dir: Path
    config_dir: Path
    build_dir: Path
    cleanup_after_build: bool = True

@dataclass
class BuildOptions:
    """Build-specific options."""
    repository: str
    branch: str
    board_targets: list[str]
    verbose: bool = False
```

#### Benefits:
- Simple, clear data structures
- Easy to understand and modify
- Reduced cognitive load
- Better testability

### Phase 4: Helper Function Refactoring

**Objective:** Break down complex helper functions and eliminate unnecessary abstractions.

#### Target Changes:

1. **zmk_helpers.py Refactoring:**
```python
# Current: Complex parameter objects
def setup_zmk_workspace_paths(params: ZmkCompilationParams) -> None:
    # 47 lines of complex logic

# Refactored: Simple, direct functions
def create_workspace_directories(base_dir: Path) -> WorkspaceDirectories:
    """Create workspace directories (target: <15 lines)."""
    pass

def setup_docker_paths(workspace_dirs: WorkspaceDirectories) -> DockerPathMapping:
    """Setup Docker path mappings (target: <10 lines)."""
    pass
```

2. **Build Command Generation:**
```python
# Current: Complex build matrix resolution
def build_zmk_compilation_commands(build_matrix: BuildMatrix, workspace_params: ZmkWorkspaceParams) -> list[str]:
    # 38 lines of complex logic

# Refactored: Simple, focused functions
def generate_west_build_commands(build_targets: list[str], config_dir: Path, build_dir: Path) -> list[str]:
    """Generate west build commands (target: <20 lines)."""
    pass

def create_build_command(board: str, config_dir: Path, build_dir: Path, shield: str = None) -> str:
    """Create single build command (target: <8 lines)."""
    pass
```

### Phase 5: Factory Function Standardization

**Objective:** Ensure all services follow the factory function pattern consistently as specified in CLAUDE.md.

#### Target Factory Functions:
```python
# compilation/__init__.py
def create_compilation_service(strategy: str) -> CompilationServiceProtocol:
    """Create compilation service for strategy (target: <20 lines)."""
    if strategy == "zmk_config":
        return create_zmk_config_service()
    elif strategy == "moergo":
        return create_moergo_service()
    else:
        raise ValueError(f"Unknown strategy: {strategy}")

def create_zmk_config_service() -> ZmkConfigCompilationService:
    """Create ZMK config service (target: <10 lines)."""
    docker_adapter = create_docker_adapter()
    return ZmkConfigCompilationService(docker_adapter)

def create_moergo_service() -> MoergoCompilationService:
    """Create Moergo service (target: <10 lines)."""
    docker_adapter = create_docker_adapter()
    return MoergoCompilationService(docker_adapter)
```

## Implementation Plan

### Step 1: CLI Option Cleanup & Command Refactoring (Priority: Critical)
- **Timeline:** 1 day
- **Files:** `glovebox/cli/commands/firmware.py`
- **Approach:** 
  1. **Remove dead code options** (immediate 70% complexity reduction)
  2. **Migrate settings to config files** (user config, keyboard profiles)
  3. **Simplify function signature** (20+ params → 6 params)
  4. **Extract helper functions** for the remaining logic
- **Impact:** Massive complexity reduction with minimal risk

### Step 2: Service Simplification (Priority: High)  
- **Timeline:** 2-3 days
- **Files:** `glovebox/compilation/services/`
- **Approach:** Create new simplified services alongside existing ones, then replace

### Step 3: Configuration Streamlining (Priority: Medium)
- **Timeline:** 1-2 days  
- **Files:** `glovebox/config/compile_methods.py`, `glovebox/compilation/models/`
- **Approach:** Create simplified models, update services to use them

### Step 4: Helper Function Refactoring (Priority: Medium)
- **Timeline:** 1 day
- **Files:** `glovebox/compilation/helpers/`
- **Approach:** Break down functions into smaller, focused utilities

### Step 5: Factory Function Cleanup (Priority: Low)
- **Timeline:** 0.5 days
- **Files:** `glovebox/compilation/__init__.py`
- **Approach:** Simplify factory functions to match new service architecture

## Success Criteria

### Quantitative Metrics:
- **All files:** ≤ 500 lines
- **All methods:** ≤ 50 lines  
- **CLI command:** ≤ 30 lines
- **Service methods:** ≤ 40 lines average
- **Helper functions:** ≤ 25 lines average

### Qualitative Improvements:
- Clear separation of concerns
- Simple, testable functions
- Consistent factory function usage
- Reduced cognitive complexity
- Better error handling
- Improved maintainability

## Risk Mitigation

### Testing Strategy:
- Maintain existing integration tests during refactoring
- Add unit tests for new extracted functions
- Test each phase independently
- Keep backward compatibility during transition

### Rollback Plan:
- Keep original implementations alongside new ones during development
- Use feature flags to switch between implementations
- Maintain git branching strategy for safe rollbacks

## Long-term Benefits

1. **Maintainability:** Easier to understand and modify code
2. **Testability:** Smaller functions are easier to test
3. **Reliability:** Simpler code has fewer bugs
4. **Team Productivity:** Faster development cycles for new features
5. **CLAUDE.md Compliance:** Aligns with project conventions and team size

## Conclusion

This refactoring addresses critical complexity issues while maintaining functionality. The phased approach ensures minimal disruption while significantly improving code quality and maintainability. The resulting architecture will be more appropriate for the project's team size and complexity requirements.