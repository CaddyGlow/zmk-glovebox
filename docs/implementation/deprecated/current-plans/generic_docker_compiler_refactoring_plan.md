# Generic Docker Compiler Refactoring Plan

## Executive Summary

The current `glovebox/firmware/compile/generic_docker_compiler.py` file has grown to **1558 lines** and violates multiple CLAUDE.md conventions including:
- **CRITICAL**: File exceeds 500-line maximum by 211%
- **CRITICAL**: Multiple methods exceed 50-line maximum  
- **CRITICAL**: Monolithic design violating domain-driven architecture
- **CRITICAL**: Poor separation of concerns mixing compilation, caching, workspace management
- **CRITICAL**: ZMK config mode doesn't implement proper GitHub Actions workflow pattern

This refactoring plan restructures the code following CLAUDE.md design patterns while implementing a proper ZMK config strategy based on the official ZMK GitHub Actions workflow.

## Current Violations Analysis

### File Size Violations
- **Current**: 1558 lines
- **Limit**: 500 lines  
- **Violation**: 211% over limit

### Method Size Violations
- `_execute_west_strategy()`: ~120 lines (140% over 50-line limit)
- `_execute_zmk_config_strategy()`: ~155 lines (210% over 50-line limit)  
- `_initialize_west_workspace()`: ~80 lines (60% over limit)
- `_initialize_zmk_config_workspace()`: ~95 lines (90% over limit)
- Multiple cache management methods: 50-70 lines each

### Architecture Violations
- **Single Responsibility**: One class handles compilation, caching, workspace management, volume preparation
- **Domain Boundaries**: Mixed firmware compilation concerns with infrastructure concerns
- **Service Layer**: Missing proper service abstractions
- **Protocol Implementation**: Incomplete protocol-based design

## Refactoring Strategy

### 1. New Directory Structure

Instead of crowding `glovebox/firmware/compile/`, create a dedicated compilation domain:

```
glovebox/compilation/                 # New compilation domain
├── __init__.py                      # Domain exports and factory functions
├── models/                          # Compilation-specific models
│   ├── __init__.py
│   ├── build_matrix.py             # BuildTarget, BuildMatrix models
│   ├── workspace_config.py         # Workspace configuration models  
│   ├── cache_metadata.py           # Cache metadata models
│   └── compilation_result.py       # Enhanced compilation results
├── services/                       # Compilation services
│   ├── __init__.py
│   ├── base_compilation_service.py # Base service class
│   ├── compilation_coordinator.py  # Main compilation orchestration
│   ├── west_compilation_service.py # West-specific compilation
│   ├── zmk_config_service.py       # ZMK config compilation
│   └── cmake_compilation_service.py # CMake compilation
├── workspace/                      # Workspace management
│   ├── __init__.py
│   ├── workspace_manager.py        # Base workspace management
│   ├── west_workspace_manager.py   # West workspace operations
│   ├── zmk_config_workspace_manager.py # ZMK config workspace
│   └── cache_manager.py            # Workspace caching
├── configuration/                  # Build configuration
│   ├── __init__.py
│   ├── build_matrix_resolver.py    # Parse and resolve build.yaml
│   ├── volume_manager.py           # Docker volume configuration
│   └── environment_manager.py      # Environment variable setup
├── artifacts/                      # Artifact management
│   ├── __init__.py
│   ├── collector.py                # Artifact collection
│   ├── firmware_scanner.py         # Firmware file detection
│   └── validator.py                # Build output validation
└── protocols/                      # Compilation-specific protocols
    ├── __init__.py
    ├── compilation_protocols.py    # Service protocols
    ├── workspace_protocols.py      # Workspace protocols
    └── artifact_protocols.py       # Artifact protocols
```

### 2. Updated Firmware Structure

Keep minimal interface in original location:

```
glovebox/firmware/compile/
├── __init__.py                     # Re-export from compilation domain
├── generic_docker_compiler.py     # Simplified adapter/facade (< 200 lines)
└── methods.py                      # Keep existing method registry
```

### 3. Domain-Driven Service Architecture

#### A. Compilation Services (`glovebox/compilation/services/`)

**Base Service Pattern**
```python
# glovebox/compilation/services/base_compilation_service.py
from glovebox.services.base_service import BaseService
from glovebox.compilation.protocols.compilation_protocols import CompilationServiceProtocol

class BaseCompilationService(BaseService):
    """Base service for all compilation strategies."""
    
    def __init__(self, name: str, version: str):
        super().__init__(name, version)
        
    def validate_configuration(self, config: CompileConfig) -> bool:
        """Validate compilation configuration."""
        # < 50 lines
        
    def prepare_build_environment(self, config: CompileConfig) -> dict[str, str]:
        """Prepare build environment variables."""
        # < 50 lines
```

**ZMK Config Service (GitHub Actions Pattern)**
```python
# glovebox/compilation/services/zmk_config_service.py
class ZmkConfigCompilationService(BaseCompilationService):
    """ZMK config compilation service following GitHub Actions workflow pattern."""
    
    def __init__(self, 
                 workspace_manager: ZmkConfigWorkspaceManagerProtocol,
                 build_matrix_resolver: BuildMatrixResolverProtocol,
                 artifact_collector: ArtifactCollectorProtocol):
        super().__init__("zmk_config_compilation", "1.0.0")
        self.workspace_manager = workspace_manager
        self.build_matrix_resolver = build_matrix_resolver
        self.artifact_collector = artifact_collector
        
    def compile(self, keymap_file: Path, config_file: Path, 
                output_dir: Path, config: GenericDockerCompileConfig) -> BuildResult:
        """Execute ZMK config compilation using GitHub Actions pattern."""
        # < 50 lines - delegate to specialized methods
```

#### B. Workspace Management (`glovebox/compilation/workspace/`)

**ZMK Config Workspace Manager**
```python
# glovebox/compilation/workspace/zmk_config_workspace_manager.py
class ZmkConfigWorkspaceManager:
    """Manage ZMK config repository workspaces following GitHub Actions pattern."""
    
    def initialize_workspace(self, config: ZmkConfigRepoConfig) -> bool:
        """Initialize ZMK config workspace with west integration."""
        # < 50 lines
        
    def clone_config_repository(self, config: ZmkConfigRepoConfig) -> bool:
        """Clone ZMK config repository."""
        # < 30 lines
        
    def initialize_west_workspace(self, workspace_path: Path) -> bool:
        """Initialize west workspace in config repository."""
        # < 40 lines
```

#### C. Build Configuration (`glovebox/compilation/configuration/`)

**Build Matrix Resolver**
```python
# glovebox/compilation/configuration/build_matrix_resolver.py
@dataclass
class BuildTarget:
    """Individual build target from build.yaml."""
    board: str
    shield: str | None = None
    cmake_args: list[str] = field(default_factory=list)
    snippet: str | None = None
    artifact_name: str | None = None

@dataclass  
class BuildMatrix:
    """Complete build matrix resolved from build.yaml."""
    targets: list[BuildTarget]
    board_defaults: list[str]
    shield_defaults: list[str]
    
class BuildMatrixResolver:
    """Resolve build matrix from build.yaml following GitHub Actions pattern."""
    
    def resolve_from_build_yaml(self, build_yaml_path: Path) -> BuildMatrix:
        """Parse build.yaml and create build matrix."""
        # < 50 lines
```

### 4. ZMK Config Mode Implementation (GitHub Actions Pattern)

#### GitHub Actions Workflow Integration
```python
# glovebox/compilation/configuration/github_actions_builder.py
class GitHubActionsBuilder:
    """Build configuration following ZMK GitHub Actions workflow pattern."""
    
    def create_build_matrix_from_yaml(self, build_yaml_path: Path) -> BuildMatrix:
        """Create build matrix matching GitHub Actions workflow."""
        # < 40 lines
        
    def resolve_board_shield_combinations(self, build_config: dict) -> list[BuildTarget]:
        """Resolve board/shield combinations like GitHub Actions."""
        # < 30 lines
        
    def generate_artifact_names(self, target: BuildTarget) -> str:
        """Generate artifact names matching GitHub Actions pattern."""
        # < 20 lines
```

### 5. Factory Function Patterns

#### Domain Factory Functions
```python
# glovebox/compilation/__init__.py
def create_compilation_coordinator() -> CompilationCoordinatorProtocol:
    """Create main compilation coordinator with all dependencies."""
    workspace_manager = create_workspace_manager()
    zmk_config_service = create_zmk_config_service()
    west_service = create_west_service()
    cmake_service = create_cmake_service()
    
    return CompilationCoordinator(
        compilation_services={
            "west": west_service,
            "zmk_config": zmk_config_service, 
            "cmake": cmake_service
        },
        workspace_manager=workspace_manager
    )

def create_zmk_config_service() -> ZmkConfigCompilationServiceProtocol:
    """Create ZMK config compilation service."""
    workspace_manager = create_zmk_config_workspace_manager()
    build_matrix_resolver = create_build_matrix_resolver()
    artifact_collector = create_artifact_collector()
    
    return ZmkConfigCompilationService(
        workspace_manager=workspace_manager,
        build_matrix_resolver=build_matrix_resolver,
        artifact_collector=artifact_collector
    )
```

### 6. Simplified Generic Docker Compiler

```python
# glovebox/firmware/compile/generic_docker_compiler.py (Refactored to < 200 lines)
from glovebox.compilation import create_compilation_coordinator
from glovebox.compilation.protocols.compilation_protocols import CompilationCoordinatorProtocol

class GenericDockerCompiler:
    """Generic Docker compiler facade - delegates to compilation domain."""
    
    def __init__(self,
                 compilation_coordinator: CompilationCoordinatorProtocol | None = None,
                 docker_adapter: DockerAdapterProtocol | None = None,
                 file_adapter: FileAdapterProtocol | None = None):
        """Initialize with compilation coordinator."""
        self.compilation_coordinator = compilation_coordinator or create_compilation_coordinator()
        self.docker_adapter = docker_adapter or create_docker_adapter()
        self.file_adapter = file_adapter or create_file_adapter()
        
    def compile(self, keymap_file: Path, config_file: Path,
               output_dir: Path, config: GenericDockerCompileConfig) -> BuildResult:
        """Compile firmware using specified build strategy."""
        # < 30 lines - delegate to compilation coordinator
        return self.compilation_coordinator.compile(keymap_file, config_file, output_dir, config)
        
    def validate_config(self, config: GenericDockerCompileConfig) -> bool:
        """Validate compilation configuration."""
        # < 20 lines - delegate to coordinator
        return self.compilation_coordinator.validate_config(config)
        
    def check_available(self) -> bool:
        """Check if Docker compiler is available."""
        # < 10 lines
        return self.docker_adapter.is_available()
```

## Implementation Phases with Mandatory Linting and Testing

### **CRITICAL: Validation Requirements for Each Step**

Every implementation step MUST include:

1. **Pre-Implementation Validation**:
   ```bash
   # BEFORE starting any code changes
   ruff check . --fix
   ruff format .
   mypy glovebox/
   pytest
   ```

2. **Post-Implementation Validation**:
   ```bash
   # AFTER completing each step
   ruff check . --fix          # Fix any linting issues
   ruff format .               # Format all code
   mypy glovebox/              # Type checking must pass
   pytest --cov=glovebox       # All tests must pass with coverage
   pre-commit run --all-files  # Pre-commit hooks must pass
   ```

3. **Commit Requirements**:
   - Each step gets its own commit following conventional commit format
   - Commit message format: `refactor(compilation): [step description]`
   - All linting and tests MUST pass before commit
   - Include test coverage metrics in commit message

4. **Unit Test Requirements**:
   - **Minimum 85% test coverage** for all new code
   - **Integration tests** for service interactions
   - **Mock all external dependencies** (Docker, filesystem)
   - **Test error conditions** and edge cases
   - **Performance tests** for caching mechanisms

### Phase 1: Domain Structure Setup (Week 1)

#### Step 1.1: Create Domain Directory Structure
**Deliverables**:
- [ ] Create `glovebox/compilation/` directory structure
- [ ] Add all `__init__.py` files with proper exports
- [ ] Create basic protocol definitions
- [ ] Add factory function stubs

**Validation**:
```bash
# After completion
ruff check . --fix
mypy glovebox/
pytest glovebox/compilation/
```

**Tests Required**:
- [ ] Test all imports work correctly
- [ ] Test factory functions return correct types
- [ ] Test protocol definitions are runtime checkable

#### Step 1.2: Extract Base Models
**Deliverables**:
- [ ] Create `glovebox/compilation/models/build_matrix.py`
- [ ] Create `glovebox/compilation/models/workspace_config.py`
- [ ] Create `glovebox/compilation/models/cache_metadata.py`
- [ ] Move existing models to new structure

**Validation**:
```bash
ruff check . --fix
mypy glovebox/compilation/models/
pytest tests/test_compilation/test_models/
```

**Tests Required**:
- [ ] Unit tests for all model validation
- [ ] Test model serialization/deserialization
- [ ] Test model field validation and defaults

#### Step 1.3: Create Base Service Classes
**Deliverables**:
- [ ] Create `BaseCompilationService` class
- [ ] Create service protocols
- [ ] Add basic validation methods

**Validation**:
```bash
ruff check . --fix
mypy glovebox/compilation/services/
pytest tests/test_compilation/test_services/test_base_service.py -v
```

**Tests Required**:
- [ ] Test base service initialization
- [ ] Test configuration validation logic
- [ ] Test service lifecycle methods

### Phase 2: Build Matrix and Configuration (Week 1-2)

#### Step 2.1: Extract Build Matrix Resolver
**Deliverables**:
- [ ] Create `BuildMatrixResolver` class
- [ ] Implement GitHub Actions workflow pattern
- [ ] Add build.yaml parsing logic

**Validation**:
```bash
ruff check . --fix
mypy glovebox/compilation/configuration/
pytest tests/test_compilation/test_configuration/test_build_matrix_resolver.py -v --cov=glovebox.compilation.configuration.build_matrix_resolver
```

**Tests Required**:
- [ ] Test build.yaml parsing with various configurations
- [ ] Test artifact name generation
- [ ] Test board/shield combination resolution
- [ ] Test error handling for invalid build.yaml
- [ ] Integration test with real ZMK build.yaml files

#### Step 2.2: Extract Volume and Environment Managers
**Deliverables**:
- [ ] Create `VolumeManager` class
- [ ] Create `EnvironmentManager` class
- [ ] Extract volume template parsing logic

**Validation**:
```bash
ruff check . --fix
mypy glovebox/compilation/configuration/
pytest tests/test_compilation/test_configuration/ -v --cov=glovebox.compilation.configuration
```

**Tests Required**:
- [ ] Test Docker volume preparation for all strategies
- [ ] Test environment variable expansion
- [ ] Test volume template parsing
- [ ] Test caching volume optimizations

### Phase 3: Workspace Management (Week 2)

#### Step 3.1: Extract Base Workspace Manager
**Deliverables**:
- [ ] Create `WorkspaceManager` base class
- [ ] Create workspace protocols
- [ ] Add workspace validation logic

**Validation**:
```bash
ruff check . --fix
mypy glovebox/compilation/workspace/
pytest tests/test_compilation/test_workspace/test_workspace_manager.py -v
```

**Tests Required**:
- [ ] Test workspace initialization
- [ ] Test workspace validation
- [ ] Test workspace cleanup
- [ ] Mock all filesystem operations

#### Step 3.2: Extract ZMK Config Workspace Manager
**Deliverables**:
- [ ] Create `ZmkConfigWorkspaceManager` class
- [ ] Implement GitHub Actions workspace pattern
- [ ] Add config repository cloning logic

**Validation**:
```bash
ruff check . --fix
mypy glovebox/compilation/workspace/
pytest tests/test_compilation/test_workspace/test_zmk_config_workspace_manager.py -v --cov=glovebox.compilation.workspace.zmk_config_workspace_manager
```

**Tests Required**:
- [ ] Test ZMK config repository cloning
- [ ] Test west workspace initialization
- [ ] Test user configuration copying
- [ ] Test error handling for Git operations
- [ ] Integration test with real ZMK config repos

#### Step 3.3: Extract Cache Manager
**Deliverables**:
- [ ] Create `CacheManager` class
- [ ] Implement intelligent cache invalidation
- [ ] Add cache cleanup automation

**Validation**:
```bash
ruff check . --fix
mypy glovebox/compilation/workspace/
pytest tests/test_compilation/test_workspace/test_cache_manager.py -v --cov=glovebox.compilation.workspace.cache_manager
```

**Tests Required**:
- [ ] Test cache validity checking
- [ ] Test cache metadata generation
- [ ] Test cache cleanup with age limits
- [ ] Test cache invalidation scenarios
- [ ] Performance tests for cache operations

### Phase 4: Compilation Services (Week 2-3)

#### Step 4.1: Extract ZMK Config Compilation Service
**Deliverables**:
- [ ] Create `ZmkConfigCompilationService` class
- [ ] Implement GitHub Actions build workflow
- [ ] Add build matrix execution logic

**Validation**:
```bash
ruff check . --fix
mypy glovebox/compilation/services/
pytest tests/test_compilation/test_services/test_zmk_config_service.py -v --cov=glovebox.compilation.services.zmk_config_service
```

**Tests Required**:
- [ ] Test compilation with build matrix
- [ ] Test GitHub Actions workflow integration
- [ ] Test artifact collection
- [ ] Test error handling for build failures
- [ ] Integration test with Docker containers

#### Step 4.2: Extract West Compilation Service
**Deliverables**:
- [ ] Create `WestCompilationService` class
- [ ] Extract west-specific logic
- [ ] Add west workspace integration

**Validation**:
```bash
ruff check . --fix
mypy glovebox/compilation/services/
pytest tests/test_compilation/test_services/test_west_compilation_service.py -v --cov=glovebox.compilation.services.west_compilation_service
```

**Tests Required**:
- [ ] Test west build command generation
- [ ] Test west workspace management
- [ ] Test board target compilation
- [ ] Test custom build commands
- [ ] Mock Docker adapter interactions

#### Step 4.3: Extract Compilation Coordinator
**Deliverables**:
- [ ] Create `CompilationCoordinator` class
- [ ] Implement strategy selection logic
- [ ] Add service orchestration

**Validation**:
```bash
ruff check . --fix
mypy glovebox/compilation/services/
pytest tests/test_compilation/test_services/test_compilation_coordinator.py -v --cov=glovebox.compilation.services.compilation_coordinator
```

**Tests Required**:
- [ ] Test strategy selection based on configuration
- [ ] Test service coordination
- [ ] Test error propagation
- [ ] Test service lifecycle management
- [ ] Integration tests with all compilation strategies

### Phase 5: Artifact Management (Week 3)

#### Step 5.1: Extract Artifact Collector
**Deliverables**:
- [ ] Create `ArtifactCollector` class
- [ ] Extract firmware file detection logic
- [ ] Add artifact validation

**Validation**:
```bash
ruff check . --fix
mypy glovebox/compilation/artifacts/
pytest tests/test_compilation/test_artifacts/test_collector.py -v --cov=glovebox.compilation.artifacts.collector
```

**Tests Required**:
- [ ] Test firmware file scanning in various directory structures
- [ ] Test artifact validation
- [ ] Test multiple artifact handling
- [ ] Test error handling for missing artifacts

### Phase 6: Integration and Cleanup (Week 3-4)

#### Step 6.1: Refactor Generic Docker Compiler
**Deliverables**:
- [ ] Simplify `GenericDockerCompiler` to facade pattern
- [ ] Update all imports to use compilation domain
- [ ] Add backward compatibility layer

**Validation**:
```bash
ruff check . --fix
mypy glovebox/
pytest tests/test_firmware/test_generic_docker_compiler.py -v
pytest tests/test_compilation/ -v --cov=glovebox.compilation
```

**Tests Required**:
- [ ] Test backward compatibility with existing code
- [ ] Test facade delegates properly to compilation coordinator
- [ ] Test all existing functionality still works
- [ ] Integration tests with CLI commands

#### Step 6.2: Update Import Patterns
**Deliverables**:
- [ ] Update all imports following CLAUDE.md patterns
- [ ] Remove old code and unused imports
- [ ] Update CLI integration

**Validation**:
```bash
ruff check . --fix
mypy glovebox/
pytest --cov=glovebox
```

**Tests Required**:
- [ ] Test all imports work correctly
- [ ] Test CLI commands still function
- [ ] Test backward compatibility
- [ ] End-to-end integration tests

#### Step 6.3: Performance and Optimization Testing
**Deliverables**:
- [ ] Performance regression testing
- [ ] Memory usage optimization
- [ ] Build time optimization validation

**Validation**:
```bash
ruff check . --fix
pytest --cov=glovebox --durations=10
pytest tests/performance/ -v
```

**Tests Required**:
- [ ] Performance benchmarks vs old implementation
- [ ] Memory usage tests
- [ ] Build time measurements
- [ ] Cache effectiveness tests

## Success Metrics with Validation Requirements

### Code Quality Metrics (Validated Each Step)
- [ ] All files under 500 lines (enforced by ruff)
- [ ] All methods under 50 lines (enforced by ruff) 
- [ ] Zero CLAUDE.md convention violations (enforced by pre-commit)
- [ ] >85% test coverage for all new code (enforced by pytest)
- [ ] Zero mypy type checking errors (enforced by CI)

### Performance Metrics (Measured Each Phase)
- [ ] 30% reduction in memory usage during compilation
- [ ] 50% improvement in cached build times  
- [ ] 20% reduction in Docker image pull times
- [ ] <5% performance regression for cold builds

### Architecture Metrics (Validated at Integration)
- [ ] Clear domain boundaries (validated by import analysis)
- [ ] Protocol compliance (validated by runtime checks)
- [ ] Service isolation (validated by unit tests)
- [ ] Factory function consistency (validated by integration tests)

## Risk Mitigation with Continuous Validation

### Continuous Integration Requirements
```yaml
# Required CI checks for each commit
- name: Lint and Format
  run: |
    ruff check . --fix
    ruff format .
    
- name: Type Check  
  run: mypy glovebox/
  
- name: Test with Coverage
  run: |
    pytest --cov=glovebox --cov-report=xml
    coverage report --fail-under=85
    
- name: Pre-commit Hooks
  run: pre-commit run --all-files
```

### Rollback Strategy
- [ ] Feature flags for old vs new implementation
- [ ] Comprehensive integration tests before each merge
- [ ] Performance monitoring with automatic rollback triggers
- [ ] User feedback collection at each phase

This refactoring plan ensures **every single step** is validated with linting, type checking, and comprehensive testing, while organizing the code into a clean domain-driven architecture that fully complies with CLAUDE.md conventions.