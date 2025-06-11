# Compilation Domain Simplification Plan

## Overview

This plan addresses the architectural complexity and code duplication in the compilation domain by eliminating unnecessary layers, removing code duplication, and simplifying the service structure while maintaining functionality and extensibility. It also includes refactoring the cache system to be more generic and reusable across the entire codebase.

## Current Problems

### 1. **Architectural Bloat**
- **Triple-layer complexity**: BuildService → CompilationCoordinator → StrategyService → Docker
- **Unnecessary delegation**: GenericDockerCompiler that only delegates to CompilationCoordinator
- **Method selection complexity**: Complex fallback logic for simple strategy selection

### 2. **Massive Code Duplication**
- **zmk_config_service.py** (1,097 lines) and **west_compilation_service.py** (550 lines) share 95% identical code
- **Docker execution logic** duplicated across all services
- **Validation, error handling, artifact collection** duplicated in every service
- **Constructor patterns** nearly identical across services

### 3. **Configuration Explosion**
- **5+ different config types** for the same Docker operations:
  - `DockerCompileConfig` (old)
  - `GenericDockerCompileConfig` (facade)
  - `ZmkConfigRepoConfig` (compilation domain)
  - `WestWorkspaceConfig` (compilation domain)
  - `FirmwareDockerConfig` (user settings)

### 4. **Unnecessary Service Layers**
- **BuildService**: Front service that does nothing but delegate
- **CompilationCoordinator**: Strategy selection that could be done directly
- **GenericDockerCompiler**: Facade that adds no value

### 5. **Cache System Issues**
- **Domain-specific caches**: `base_dependencies_cache.py`, `keyboard_config_cache.py` only work for compilation
- **No reusability**: Cache logic tied to specific compilation use cases
- **Missing generic patterns**: No common cache interface for other domains

## Solution Architecture

### Target Architecture
```
CLI Command
├── create_compilation_service(strategy)  # Simple factory
├── ZmkConfigService                      # Strategy implementation  
│   └── BaseCompilationService           # Common Docker logic
├── WestService                          # Strategy implementation
│   └── BaseCompilationService           # Common Docker logic  
└── CMakeService                         # Strategy implementation
    └── BaseCompilationService           # Common Docker logic

Generic Cache System (NEW)
├── CacheManager                         # Generic cache interface
├── FilesystemCache                      # File-based caching
├── MemoryCache                          # In-memory caching
└── CompilationCache                     # Compilation-specific cache
```

### Key Principles
1. **Extract ALL common logic** to BaseCompilationService
2. **Keep separate services** for different strategies (Single Responsibility)
3. **Direct service usage** - eliminate coordinator complexity
4. **User-driven strategy selection** via CLI
5. **Unified configuration** with strategy-specific extensions
6. **Generic cache system** reusable across all domains

## Implementation Plan

### Phase 1: Extract Common Docker Logic to Base Service

**Goal**: Move ALL duplicate code to BaseCompilationService to eliminate 95% code duplication.

#### Step 1.1: Enhance BaseCompilationService with Common Logic
- **File**: `glovebox/compilation/services/base_compilation_service.py`
- **Changes**:
  - Add common Docker execution method
  - Add common artifact collection with fallback
  - Add common validation logic
  - Add common error handling
  - Add common dependency injection
  - Add template method pattern for compile flow

**Expected file size**: ~400 lines (absorbs common logic from all services)

#### Step 1.2: Extract Common Constructor Dependencies
- **Files**: All compilation services
- **Changes**:
  - Move ALL common dependencies to base class
  - Use dependency injection pattern
  - Initialize common dependencies in base constructor

#### Step 1.3: Create Template Method for Compilation Flow
- **File**: `glovebox/compilation/services/base_compilation_service.py`
- **Changes**:
  - Implement template method `compile()` with common flow
  - Define abstract methods for strategy-specific parts:
    - `_setup_workspace()`
    - `_build_compilation_command()`

**Deliverable**: Enhanced BaseCompilationService with all common logic

**Testing**: 
- Run existing tests to ensure no regression
- Add unit tests for new common methods in base class

**Validation**:
```bash
# Test and lint requirements
pytest tests/test_compilation/test_services/test_base_compilation_service.py
ruff check . --fix
ruff format .
mypy glovebox/
```

**Commit**: "refactor: extract common Docker compilation logic to base service"

---

### Phase 2: Refactor Cache System to Generic Components

**Goal**: Transform domain-specific caches into generic, reusable cache system.

#### Step 2.1: Create Generic Cache Framework
- **New Files**:
  - `glovebox/core/cache/cache_manager.py` - Generic cache interface
  - `glovebox/core/cache/filesystem_cache.py` - File-based cache implementation
  - `glovebox/core/cache/memory_cache.py` - In-memory cache implementation
  - `glovebox/core/cache/models.py` - Cache data models
  - `glovebox/core/cache/__init__.py` - Cache factory functions

**Generic Cache Interface**:
```python
# glovebox/core/cache/cache_manager.py
class CacheManager(Protocol):
    def get(self, key: str, default: Any = None) -> Any
    def set(self, key: str, value: Any, ttl: int | None = None) -> None
    def delete(self, key: str) -> bool
    def clear(self) -> None
    def exists(self, key: str) -> bool
    def get_metadata(self, key: str) -> CacheMetadata | None
```

#### Step 2.2: Migrate Existing Caches to Generic System
- **Files to Refactor**:
  - `glovebox/compilation/cache/base_dependencies_cache.py` → Use generic FilesystemCache
  - `glovebox/compilation/cache/keyboard_config_cache.py` → Use generic FilesystemCache

**Changes**:
- Extract cache-specific logic from compilation domain
- Use generic cache interfaces
- Keep compilation-specific cache logic as thin wrapper

#### Step 2.3: Create Compilation-Specific Cache Service
- **New File**: `glovebox/compilation/cache/compilation_cache.py`
- **Purpose**: Thin wrapper around generic cache for compilation-specific operations
- **Size**: ~100 lines (was distributed across 1000+ lines)

**Example**:
```python
# glovebox/compilation/cache/compilation_cache.py
class CompilationCache:
    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
    
    def get_zmk_dependencies(self, key: str) -> ZmkDependencies | None:
        """Compilation-specific cache operation using generic cache."""
        return self.cache.get(f"zmk_deps:{key}")
    
    def cache_keyboard_config(self, keyboard: str, config: KeyboardConfig):
        """Compilation-specific cache operation using generic cache."""
        self.cache.set(f"keyboard:{keyboard}", config, ttl=3600)
```

**Deliverable**: Generic cache system with compilation-specific wrapper

**Testing**:
- Test generic cache implementations
- Test migration of existing cache usage
- Verify cache performance

**Validation**:
```bash
# Test and lint requirements
pytest tests/test_core/test_cache/
pytest tests/test_compilation/test_cache/
ruff check . --fix
ruff format .
mypy glovebox/
```

**Commit**: "refactor: create generic cache system and migrate compilation caches"

---

### Phase 3: Simplify Individual Compilation Services

**Goal**: Reduce service implementations to strategy-specific logic only.

#### Step 3.1: Refactor ZmkConfigService
- **File**: `glovebox/compilation/services/zmk_config_service.py`
- **Changes**:
  - Remove ALL duplicate methods (validate_config, check_available, set_docker_adapter, etc.)
  - Implement only strategy-specific methods:
    - `_setup_workspace()` - ZMK config workspace setup
    - `_build_compilation_command()` - ZMK config command building
  - Remove duplicate constructor dependencies
  - Use base class template method
  - Use generic cache system via CompilationCache

**Expected file size**: ~80 lines (was 1,097 lines - **92% reduction**)

#### Step 3.2: Refactor WestCompilationService
- **File**: `glovebox/compilation/services/west_compilation_service.py`
- **Changes**:
  - Remove ALL duplicate methods
  - Implement only strategy-specific methods:
    - `_setup_workspace()` - West workspace setup
    - `_build_compilation_command()` - West command building
  - Remove duplicate constructor dependencies
  - Use base class template method
  - Use generic cache system via CompilationCache

**Expected file size**: ~60 lines (was 550 lines - **89% reduction**)

#### Step 3.3: Update Factory Functions
- **Files**: Individual service factory functions
- **Changes**:
  - Inject common dependencies into base class
  - Inject CompilationCache instead of domain-specific caches
  - Simplify service creation
  - Update imports

**Deliverable**: Simplified services with only strategy-specific logic

**Testing**:
- Run full test suite for compilation services
- Verify all existing functionality works with generic cache
- Add strategy-specific tests

**Validation**:
```bash
# Test and lint requirements
pytest tests/test_compilation/test_services/
ruff check . --fix
ruff format .
mypy glovebox/
```

**Commit**: "refactor: simplify compilation services to strategy-specific logic only"

---

### Phase 4: Eliminate Unnecessary Service Layers

**Goal**: Remove delegation-only services and simplify service creation.

#### Step 4.1: Remove GenericDockerCompiler
- **Files to DELETE**:
  - `glovebox/firmware/compile/generic_docker_compiler.py` (245 lines)
  - `glovebox/firmware/compile/methods.py` (333 lines)
  - `glovebox/firmware/method_selector.py` (100+ lines)

#### Step 4.2: Remove CompilationCoordinator
- **File to DELETE**: `glovebox/compilation/services/compilation_coordinator.py` (301 lines)
- **Reason**: User selects strategy via CLI, no need for automatic coordination

#### Step 4.3: Simplify BuildService
- **File**: `glovebox/firmware/build_service.py`
- **Changes**:
  - Remove method selection complexity
  - Direct service instantiation based on user choice
  - Simplified configuration creation
  - Use generic cache system

**Expected file size**: ~40 lines (was 200+ lines)

#### Step 4.4: Update Compilation Domain Factory
- **File**: `glovebox/compilation/__init__.py`
- **Changes**:
  - Remove coordinator factory
  - Add simple service factory: `create_compilation_service(strategy)`
  - Update exports
  - Add cache factory integration

**Deliverable**: Eliminated unnecessary service layers

**Testing**:
- Update tests to use direct service creation
- Verify CLI integration works
- Test all compilation strategies with generic cache

**Validation**:
```bash
# Test and lint requirements
pytest tests/test_compilation/
pytest tests/test_firmware/
ruff check . --fix
ruff format .
mypy glovebox/
```

**Commit**: "refactor: eliminate unnecessary service coordination layers"

---

### Phase 5: Unify Configuration Models

**Goal**: Replace multiple config types with unified, clean configuration.

#### Step 5.1: Create Unified Configuration Model
- **File**: `glovebox/config/compile_methods.py`
- **Changes**:
  - Create single `CompilationConfig` model
  - Merge common fields from all existing config types
  - Keep strategy-specific configs as optional fields
  - Remove redundant config classes
  - Add cache configuration options

#### Step 5.2: Update Services to Use Unified Config
- **Files**: All compilation services
- **Changes**:
  - Update method signatures to use `CompilationConfig`
  - Handle strategy-specific config extraction
  - Remove old config type handling
  - Integrate cache configuration

#### Step 5.3: Update Factory Functions and CLI
- **Files**: Service factories and CLI commands
- **Changes**:
  - Create `CompilationConfig` from CLI parameters
  - Remove old config type creation
  - Update all factory function signatures
  - Include cache configuration

**Deliverable**: Unified configuration system

**Testing**:
- Test configuration creation from CLI parameters
- Verify all compilation strategies work with new config
- Test configuration validation including cache settings

**Validation**:
```bash
# Test and lint requirements
pytest tests/test_config/
pytest tests/test_compilation/
ruff check . --fix
ruff format .
mypy glovebox/
```

**Commit**: "refactor: unify compilation configuration models"

---

### Phase 6: CLI Integration and Direct Service Usage

**Goal**: Enable direct service selection via CLI without coordination complexity.

#### Step 6.1: Update CLI Commands
- **Files**: CLI firmware compile commands
- **Changes**:
  - Add `--strategy` option for direct strategy selection
  - Use `create_compilation_service(strategy)` factory
  - Remove method selection logic
  - Add cache control options (`--no-cache`, `--clear-cache`)

#### Step 6.2: Update BuildService for Direct Usage
- **File**: `glovebox/firmware/build_service.py`
- **Changes**:
  - Implement direct service factory method
  - Remove coordinator dependency
  - Simplify compilation flow
  - Integrate generic cache system

#### Step 6.3: Update Documentation
- **Files**: CLI help and user documentation
- **Changes**:
  - Document new `--strategy` option
  - Update examples for direct strategy usage
  - Remove references to automatic method selection
  - Document cache options

**Deliverable**: Direct CLI-driven service selection

**Testing**:
- Test all CLI commands with different strategies
- Verify backward compatibility where needed
- Integration tests for full compilation flow
- Test cache functionality via CLI

**Validation**:
```bash
# Test and lint requirements
pytest tests/test_cli/
pytest tests/test_firmware/
# Manual CLI testing
glovebox firmware compile --strategy zmk_config test.keymap test.conf output/
glovebox firmware compile --strategy west test.keymap test.conf output/
glovebox firmware compile --no-cache test.keymap test.conf output/
ruff check . --fix
ruff format .
mypy glovebox/
```

**Commit**: "feat: add direct compilation strategy selection via CLI"

---

### Phase 7: Extend Generic Cache to Other Domains

**Goal**: Demonstrate cache reusability by integrating into other domains.

#### Step 7.1: Integrate Cache into Layout Domain
- **Files**: `glovebox/layout/` services
- **Changes**:
  - Use generic cache for layout parsing results
  - Cache component decomposition results
  - Cache behavior analysis results

#### Step 7.2: Integrate Cache into Configuration Domain
- **Files**: `glovebox/config/` services
- **Changes**:
  - Cache keyboard profile loading
  - Cache configuration validation results
  - Cache include file processing

#### Step 7.3: Add Cache Management CLI Commands
- **New CLI Commands**:
  - `glovebox cache status` - Show cache usage and statistics
  - `glovebox cache clear [domain]` - Clear specific or all caches
  - `glovebox cache info` - Display cache configuration

**Deliverable**: Generic cache system used across multiple domains

**Testing**:
- Test cache integration in other domains
- Test cache management CLI commands
- Verify cache performance benefits

**Validation**:
```bash
# Test and lint requirements
pytest tests/test_layout/
pytest tests/test_config/
pytest tests/test_cli/
# Manual CLI testing
glovebox cache status
glovebox cache clear compilation
ruff check . --fix
ruff format .
mypy glovebox/
```

**Commit**: "feat: extend generic cache system to layout and config domains"

---

### Phase 8: Cleanup and Optimization

**Goal**: Final cleanup, documentation, and performance optimization.

#### Step 8.1: Remove Dead Code
- **Files**: Various
- **Changes**:
  - Remove unused imports
  - Remove unused configuration classes
  - Remove old cache implementations
  - Remove unused protocols if any
  - Clean up test files

#### Step 8.2: Update Documentation
- **Files**: Architecture documentation
- **Changes**:
  - Update domain documentation
  - Update architecture diagrams
  - Document new simplified flow
  - Update factory function documentation
  - Document generic cache system
  - Add cache performance guidelines

#### Step 8.3: Performance Optimization
- **Files**: Compilation services and cache system
- **Changes**:
  - Optimize common Docker execution
  - Optimize cache key generation and lookup
  - Profile compilation performance with caching
  - Implement cache prewarming strategies

**Deliverable**: Clean, optimized compilation domain with generic cache system

**Testing**:
- Full regression test suite
- Performance benchmarks (with and without cache)
- Documentation validation
- Cache performance tests

**Validation**:
```bash
# Complete test and lint requirements
pytest
coverage run -m pytest
coverage report --show-missing
ruff check . --fix
ruff format .
mypy glovebox/
pre-commit run --all-files
```

**Commit**: "refactor: finalize compilation domain simplification and cache optimization"

---

## Expected Outcomes

### Code Reduction Summary
- **zmk_config_service.py**: 1,097 → ~80 lines (**92% reduction**)
- **west_compilation_service.py**: 550 → ~60 lines (**89% reduction**)
- **base_compilation_service.py**: 119 → ~400 lines (absorbs common logic)
- **Cache files**: 1,000+ lines → ~300 lines total (generic + wrapper)
- **Eliminated files**: ~650 lines (**100% elimination**)
- **Total reduction**: **~1,800 lines of redundant code eliminated**

### New Generic Components
- **Generic Cache System**: ~200 lines of reusable cache infrastructure
- **Compilation Cache Wrapper**: ~100 lines of domain-specific cache logic
- **Cache Management CLI**: ~50 lines of cache administration tools

### Architecture Benefits
- **Single source of truth** for Docker compilation logic
- **Generic cache system** reusable across all domains
- **Clean service separation** by compilation strategy
- **Direct service usage** - no coordination complexity
- **User-controlled strategy selection** via CLI
- **Improved performance** through intelligent caching
- **Easier testing** - test common logic once, strategy logic separately
- **Better extensibility** - add new strategies by extending base class

### Cache System Benefits
- **Domain-agnostic** - can be used by layout, config, firmware domains
- **Multiple backends** - filesystem, memory, future: Redis, SQLite
- **TTL support** - automatic cache expiration
- **Metadata tracking** - cache hit rates, performance metrics
- **CLI management** - easy cache administration
- **Performance monitoring** - cache effectiveness tracking

### CLAUDE.md Compliance
- ✅ All files under 500 lines (max file will be ~400 lines)
- ✅ Methods under 50 lines (enforced through refactoring)
- ✅ Maintains existing functionality
- ✅ Follows existing naming conventions
- ✅ Uses modern typing and pathlib
- ✅ Clean imports and domain boundaries

## Validation Requirements

### After Each Phase
1. **Run full test suite**: `pytest`
2. **Fix all linting issues**: `ruff check . --fix && ruff format .`
3. **Pass type checking**: `mypy glovebox/`
4. **Verify functionality**: Manual testing of compilation commands
5. **Test cache functionality**: Verify cache operations work correctly
6. **Commit changes**: Only when all tests pass and lint is clean

### Pre-commit Validation
```bash
# MANDATORY before each commit
pytest                    # All tests must pass
ruff check . --fix       # No linting errors
ruff format .            # Code must be formatted
mypy glovebox/           # No type errors
```

### Final Validation
```bash
# Complete validation before plan completion
pytest                           # Full test suite
coverage run -m pytest          # With coverage
coverage report --show-missing   # Verify coverage
ruff check . --fix              # No linting errors
ruff format .                   # Code formatting
mypy glovebox/                  # Type checking
pre-commit run --all-files      # Pre-commit hooks

# Cache system validation
glovebox cache status           # Verify cache system works
glovebox cache clear            # Test cache management
glovebox firmware compile --strategy zmk_config --no-cache test.keymap test.conf output/
glovebox firmware compile --strategy zmk_config test.keymap test.conf output/  # With cache
```

## Risk Mitigation

### Import Breaking Changes
- **Risk**: Refactoring may break existing imports
- **Mitigation**: Update all imports systematically, use factory functions to maintain API compatibility

### Cache Migration
- **Risk**: Existing cache data may be incompatible
- **Mitigation**: Implement cache migration utilities, provide clear cache strategies

### Test Coverage
- **Risk**: Tests may break during refactoring
- **Mitigation**: Update tests incrementally with each phase, maintain test coverage throughout

### Performance Regression
- **Risk**: Simplification may impact performance
- **Mitigation**: Profile compilation performance before and after, benchmark key operations, optimize caching

### Backward Compatibility
- **Risk**: CLI changes may break user workflows
- **Mitigation**: Maintain default behavior, add new options without removing existing functionality

## Success Criteria

1. **All existing functionality preserved** - no regression in compilation capabilities
2. **Significant code reduction** - target 70%+ reduction in compilation domain code
3. **Generic cache system** - reusable across multiple domains
4. **CLAUDE.md compliance** - all files under 500 lines, methods under 50 lines
5. **Clean architecture** - clear separation of concerns, no code duplication
6. **Maintainable codebase** - easy to understand, test, and extend
7. **Performance maintained or improved** - caching should improve performance
8. **Full test coverage** - all new and refactored code properly tested
9. **Cache effectiveness** - measurable performance improvements from caching

This plan transforms the compilation domain from a complex, duplicated architecture into a clean, maintainable system with a reusable cache infrastructure, while preserving all functionality and following CLAUDE.md guidelines.