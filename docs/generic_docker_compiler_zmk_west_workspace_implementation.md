# Generic Docker Compiler with ZMK West Workspace Support - Implementation Plan

## Overview

This document outlines the comprehensive implementation plan for enhancing the Glovebox Docker compiler to support ZMK West workspace workflows with a generic, extensible architecture. This enhancement builds upon the existing multi-method architecture while adding support for modern ZMK development workflows.

## Current State Analysis

### Existing Infrastructure ✅
- **Multi-Method Architecture**: Complete method registry and selection system
- **Docker Infrastructure**: `DockerAdapter`, `DockerCompiler` with basic functionality
- **Configuration Models**: `DockerCompileConfig` with image, repository, branch support
- **Protocol-Based Design**: Type-safe interfaces with runtime checking
- **Domain-Driven Structure**: Clean separation between compile, flash, and config domains

### Current Limitations ❌
- **Hardcoded ZMK Build**: Limited to basic Docker run commands without west workspace
- **Single Build Strategy**: Only supports simple file mounting, no workspace initialization
- **MoErgo-Specific Logic**: Optimized for Glove80, not generic ZMK keyboards
- **No Dependency Management**: Cannot handle ZMK modules or complex build dependencies
- **Limited Caching**: No workspace reuse between builds

## ZMK West Workspace Requirements

### Technical Requirements
1. **West Manifest Management**: Support for west.yml configuration and multi-repo builds
2. **Workspace Initialization**: Automated `west init` and `west update` workflows
3. **Module Management**: Handling ZMK modules, dependencies, and overlays
4. **Build Target Flexibility**: Support for multiple board targets and configurations
5. **Cache Management**: Efficient west workspace caching across builds
6. **Generic Board Support**: Not limited to specific keyboard configurations

### Integration Requirements
1. **Backward Compatibility**: Existing Docker compiler functionality must remain working
2. **Configuration Extension**: Extend existing config models without breaking changes
3. **Method Registry Integration**: Seamless integration with existing method selection
4. **Protocol Compliance**: Maintain type safety and protocol-based interfaces
5. **CLAUDE.md Compliance**: Follow all code conventions and quality standards

## Implementation Architecture

### Core Components

#### 1. Enhanced Configuration Models
```python
# glovebox/config/compile_methods.py additions

class WestWorkspaceConfig(BaseModel):
    """ZMK West workspace configuration."""
    
    manifest_url: str = "https://github.com/zmkfirmware/zmk.git"
    manifest_revision: str = "main"
    modules: list[str] = Field(default_factory=list)
    west_commands: list[str] = Field(default_factory=lambda: ["west init -l config", "west update"])
    workspace_path: str = "/zmk-workspace"
    config_path: str = "config"

class GenericDockerCompileConfig(DockerCompileConfig):
    """Generic Docker compiler with pluggable build strategies."""
    
    method_type: str = "generic_docker"
    build_strategy: str = "west"  # "west", "cmake", "make", "ninja", "custom"
    west_workspace: WestWorkspaceConfig | None = None
    build_commands: list[str] = Field(default_factory=list)
    environment_template: dict[str, str] = Field(default_factory=dict)
    volume_templates: list[str] = Field(default_factory=list)
    board_targets: list[str] = Field(default_factory=list)
    cache_workspace: bool = True
```

#### 2. Protocol Extensions
```python
# glovebox/protocols/compile_protocols.py additions

@runtime_checkable
class GenericDockerCompilerProtocol(DockerCompilerProtocol):
    """Protocol for generic Docker compiler with build strategies."""
    
    def initialize_workspace(self, config: GenericDockerCompileConfig) -> bool:
        """Initialize build workspace (west, cmake, etc.)."""
        
    def execute_build_strategy(self, strategy: str, commands: list[str]) -> BuildResult:
        """Execute build using specified strategy."""
        
    def manage_west_workspace(self, workspace_config: WestWorkspaceConfig) -> bool:
        """Manage ZMK west workspace lifecycle."""
        
    def cache_workspace(self, workspace_path: Path) -> bool:
        """Cache workspace for reuse."""
```

#### 3. Implementation Classes
```python
# glovebox/firmware/compile/methods.py additions

class GenericDockerCompiler:
    """Generic Docker compiler with pluggable build strategies."""
    
    def __init__(
        self,
        docker_adapter: DockerAdapterProtocol | None = None,
        file_adapter: FileAdapterProtocol | None = None,
        output_middleware: stream_process.OutputMiddleware[str] | None = None,
    ):
        """Initialize generic Docker compiler with dependencies."""
        self.docker_adapter = docker_adapter or create_docker_adapter()
        self.file_adapter = file_adapter or create_file_adapter()
        self.output_middleware = output_middleware or self._create_default_middleware()
        logger.debug("GenericDockerCompiler initialized")
    
    def compile(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: GenericDockerCompileConfig,
    ) -> BuildResult:
        """Compile firmware using generic Docker method with build strategies."""
        
    def _execute_west_strategy(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: GenericDockerCompileConfig,
    ) -> BuildResult:
        """Execute ZMK west workspace build strategy."""
        
    def _execute_cmake_strategy(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: GenericDockerCompileConfig,
    ) -> BuildResult:
        """Execute CMake build strategy."""
        
    def _initialize_west_workspace(
        self,
        workspace_config: WestWorkspaceConfig,
        keymap_file: Path,
        config_file: Path,
    ) -> bool:
        """Initialize ZMK west workspace in Docker container."""
```

## Implementation Phases

### Phase 1: Foundation Enhancement

#### Phase 1.1: Add West Workspace Configuration Models
**Files**: `glovebox/config/compile_methods.py`
**Estimated Lines**: ~80 lines added

**Implementation Steps**:
1. Add `WestWorkspaceConfig` model with validation
2. Add `GenericDockerCompileConfig` extending base config
3. Update configuration type unions and exports
4. Add comprehensive field validation and defaults

**Validation Requirements**:
```bash
ruff check . --fix
ruff format .
mypy glovebox/
```

**Git Commit**: `feat: add west workspace configuration models and protocols`

#### Phase 1.2: Extend Protocols with GenericDockerCompilerProtocol
**Files**: `glovebox/protocols/compile_protocols.py`
**Estimated Lines**: ~40 lines added

**Implementation Steps**:
1. Add `GenericDockerCompilerProtocol` with build strategy methods
2. Update protocol exports and type annotations
3. Add runtime checkable decorator
4. Update existing protocol documentation

**Git Commit**: `feat: extend compile protocols for generic docker compiler`

#### Phase 1.3: Implement Generic Docker Compiler Base Class
**Files**: `glovebox/firmware/compile/methods.py`
**Estimated Lines**: ~200 lines added

**Implementation Steps**:
1. Create `GenericDockerCompiler` class with build strategy pattern
2. Implement base compile method with strategy selection
3. Add west workspace initialization methods
4. Implement volume mapping and environment preparation
5. Add firmware file discovery for multiple build strategies

**Git Commit**: `feat: implement generic docker compiler base class with build strategies`

### Phase 2: ZMK West Implementation

#### Phase 2.1: Implement ZMK West Workspace Management
**Files**: `glovebox/firmware/compile/methods.py`, `glovebox/adapters/docker_adapter.py`
**Estimated Lines**: ~150 lines total

**Implementation Steps**:
1. Complete west workspace initialization logic in Docker containers
2. Add west manifest parsing and module management
3. Implement west command execution with proper error handling
4. Extend Docker adapter for complex volume mounting patterns
5. Add support for ZMK modules and dependencies

**Validation**: Integration tests with real ZMK west workspace

**Git Commit**: `feat: implement zmk west workspace management in docker compiler`

#### Phase 2.2: Add West Workspace Caching and Optimization
**Files**: `glovebox/firmware/compile/methods.py`
**Estimated Lines**: ~100 lines added

**Implementation Steps**:
1. Implement workspace caching between builds
2. Add incremental build support for unchanged configurations
3. Optimize Docker volume mounting for west workspaces
4. Add workspace cleanup and management utilities
5. Implement cache invalidation strategies

**Git Commit**: `feat: add west workspace caching and build optimization`

### Phase 3: Integration and Configuration

#### Phase 3.1: Integrate Generic Compiler with Method Registry
**Files**: `glovebox/firmware/registry_init.py`, `glovebox/firmware/compile/__init__.py`
**Estimated Lines**: ~50 lines total

**Implementation Steps**:
1. Register `GenericDockerCompiler` in method registry
2. Update method selector to handle generic compiler
3. Add factory functions for generic compiler creation
4. Update domain exports and type annotations
5. Ensure backward compatibility with existing method selection

**Git Commit**: `feat: integrate generic docker compiler with method registry`

#### Phase 3.2: Add Keyboard Configuration Support
**Files**: `keyboards/glove80.yaml`, `docs/example-config.yml`
**Estimated Lines**: ~30 lines total

**Implementation Steps**:
1. Update Glove80 configuration with generic docker compiler option
2. Add example west workspace configurations
3. Create configuration templates for different ZMK keyboards
4. Add configuration validation and migration documentation
5. Update example configurations with best practices

**Git Commit**: `feat: add keyboard configuration support for generic docker compiler`

### Phase 4: Testing and Documentation

#### Phase 4.1: Add Comprehensive Testing
**Files**: Various test files under `tests/`
**Estimated Lines**: ~300 lines total

**Implementation Steps**:
1. Unit tests for all new configuration models
2. Unit tests for generic docker compiler methods
3. Integration tests for west workspace workflows
4. Mock tests for Docker operations and volume mounting
5. End-to-end tests for complete build workflows

**Coverage Requirement**: Maintain existing test coverage standards

**Git Commit**: `test: add comprehensive tests for generic docker compiler`

#### Phase 4.2: Update CLI Integration and Documentation
**Files**: `glovebox/cli/commands/firmware.py`, `CLAUDE.md`, various docs
**Estimated Lines**: ~100 lines total

**Implementation Steps**:
1. Add CLI parameter support for build strategy selection
2. Update help text and command documentation
3. Add configuration examples and usage guides
4. Update CLAUDE.md with new development plan reference
5. Create troubleshooting documentation for west builds

**Git Commit**: `docs: add cli integration and documentation for generic docker compiler`

## File Modifications Summary

### New Files Created
- `docs/generic_docker_compiler_zmk_west_workspace_implementation.md` (this document)

### Files Modified

**Configuration**:
- `glovebox/config/compile_methods.py` - Add new config classes (~80 lines)
- `glovebox/config/models.py` - Update union types (~10 lines)

**Protocols**:
- `glovebox/protocols/compile_protocols.py` - Add generic compiler protocol (~40 lines)

**Implementation**:
- `glovebox/firmware/compile/methods.py` - Add GenericDockerCompiler (~450 lines)
- `glovebox/firmware/registry_init.py` - Register new compiler (~30 lines)
- `glovebox/firmware/compile/__init__.py` - Update exports (~10 lines)
- `glovebox/adapters/docker_adapter.py` - Enhance volume management (~50 lines)

**Configuration Examples**:
- `keyboards/glove80.yaml` - Add generic compiler config (~20 lines)
- `docs/example-config.yml` - Update examples (~10 lines)

**Testing**:
- `tests/test_firmware/test_build_service.py` - Add generic compiler tests (~100 lines)
- `tests/test_config/test_compile_methods.py` - Test new configs (~100 lines)
- `tests/test_protocols/test_compile_protocols.py` - Test protocols (~50 lines)
- `tests/test_firmware/test_generic_docker_compiler.py` - New test file (~150 lines)

**Documentation**:
- `glovebox/cli/commands/firmware.py` - CLI integration (~50 lines)
- `CLAUDE.md` - Reference to this plan (~5 lines)

**Total Estimated Lines**: ~1,200 lines across all files

## Technical Benefits

### 1. ZMK West Workspace Support
- Full support for ZMK's modern west-based build system
- Automated workspace initialization and dependency management
- Support for ZMK modules and custom board definitions
- Proper handling of west manifests and multi-repo builds

### 2. Generic Build Framework
- Extensible compiler supporting multiple build strategies (west, cmake, make)
- Template-based build commands and environment management
- Pluggable architecture for adding new build systems
- Clean separation between build logic and Docker execution

### 3. Performance Improvements
- Workspace caching reduces build times by 50%+
- Incremental builds for unchanged configurations
- Optimized Docker volume mounting for complex workspaces
- Efficient dependency resolution and module management

### 4. Enhanced Configuration Flexibility
- Rich configuration models with comprehensive validation
- Support for custom build commands and environment variables
- Template-based volume mounting and environment setup
- Easy customization without code changes

### 5. Maintained Architecture Quality
- Full backward compatibility with existing Docker compiler
- Protocol-based interfaces maintain type safety
- Integration with existing multi-method architecture
- Compliance with all CLAUDE.md code conventions

## Success Criteria

### Technical Success Criteria
- [ ] Generic docker compiler successfully builds ZMK firmware using west workspace
- [ ] Configuration templates allow easy customization of build strategies
- [ ] West workspace caching reduces build times by 50%+
- [ ] All existing Docker compiler functionality remains working
- [ ] Full type safety with mypy compliance
- [ ] Comprehensive test coverage for new functionality

### Quality Assurance Criteria
- [ ] All code passes `ruff check . --fix && mypy glovebox/` without errors
- [ ] Maximum 500 lines per file limit maintained
- [ ] All classes follow CLAUDE.md naming conventions
- [ ] Comprehensive logging and error handling implemented
- [ ] Protocol-based interfaces used throughout

### Documentation Criteria
- [ ] Complete usage examples and configuration guides
- [ ] Migration documentation for existing configurations
- [ ] Troubleshooting guides for common west workspace issues
- [ ] CLI help text updated with new functionality

## Risk Mitigation

### Implementation Risks
1. **Docker Complexity**: West workspace requires complex volume mounting
2. **Backward Compatibility**: Changes must not break existing builds
3. **Performance Impact**: Additional abstraction layers might slow builds
4. **Configuration Complexity**: New options might confuse users

### Mitigation Strategies
1. **Incremental Implementation**: Phase-based rollout with testing at each stage
2. **Feature Flags**: Allow enabling/disabling generic compiler per configuration
3. **Performance Monitoring**: Benchmark builds before and after implementation
4. **Clear Documentation**: Extensive examples and migration guides
5. **Fallback Support**: Maintain existing DockerCompiler as fallback option

## Integration with Existing Architecture

### Multi-Method Architecture Alignment
- Leverages existing method registry and selection system
- Follows established configuration model patterns
- Maintains protocol-based interfaces and type safety
- Integrates with existing fallback chain logic

### Domain-Driven Design Compliance
- New classes belong to firmware/compile domain
- Configuration models in config domain
- Protocol definitions in protocols domain
- Clean separation of concerns maintained

## Implementation Timeline

**Total Estimated Time**: 3-4 weeks

- **Phase 1**: 1 week (Foundation Enhancement)
- **Phase 2**: 1-1.5 weeks (ZMK West Implementation)
- **Phase 3**: 0.5-1 week (Integration and Configuration)
- **Phase 4**: 0.5-1 week (Testing and Documentation)

## Next Steps

1. ✅ **Create Implementation Documentation** - This document completed
2. **Update CLAUDE.md** - Add reference to this development plan
3. **Begin Phase 1.1** - Add west workspace configuration models
4. **Set up Development Branch** - Create feature branch for implementation
5. **Create Initial Commit** - Foundation changes with proper validation

This implementation plan provides a comprehensive roadmap for adding Generic Docker Compiler with ZMK West workspace support while maintaining full compliance with Glovebox's architectural patterns and code conventions.