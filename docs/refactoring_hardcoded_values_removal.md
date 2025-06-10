# Hardcoded Values Removal & Multi-File Configuration Refactoring Plan

## Overview

This document outlines the comprehensive refactoring plan to remove all hardcoded values from the `glovebox/layout/` directory and implement a robust multi-file configuration system. This refactoring builds on the existing excellent configuration infrastructure while eliminating hardcoded values and enabling support for multiple keyboard types.

## Current System Analysis

### Strengths to Preserve
- ✅ **Excellent Pydantic-based models** with validation
- ✅ **Robust KeyboardProfile factory functions** 
- ✅ **Modern method system** (compile_methods/flash_methods)
- ✅ **Comprehensive test coverage** for keyboard-only profiles
- ✅ **ConfigFileAdapter** with search paths and caching
- ✅ **Rich behavioral configuration** already in glove80.yaml

### Identified Hardcoded Values

#### 1. Behavior Configuration (`glovebox/layout/behavior/formatter.py`)
- **Lines 161-183**: Behavior class mappings (`&none`, `&kp`, `&lt`, etc.)
- **Lines 100-114, 132-141**: Modifier key mappings (LA/LALT, etc.)
- **Line 363**: Magic behavior constants
- **Line 223**: Reset behavior mapping

#### 2. Layout Structure (`glovebox/layout/formatting.py`, `display_service.py`)
- **Lines 299-309**: Hardcoded Glove80 layout structure (9 rows)
- **Lines 161-171**: Display service layout mappings
- **Lines 87, 91**: Default key count (80) and padding values

#### 3. ZMK Constants (`glovebox/layout/zmk_generator.py`)
- **Lines 143-148**: Hold-tap flavor values
- **Lines 217-224**: ZMK compatible strings
- **Lines 121-122, 248-250**: DTSI node names and patterns

#### 4. Display & Formatting Constants
- Header width (80), key display widths, special characters
- File extensions (`.keymap`, `.conf`, `.dtsi`, `.json`)
- Validation limits (layer counts, parameter counts)

## Refactoring Strategy

### Phase-Based Approach
1. **Clean Legacy**: Remove backward compatibility code
2. **Extend Models**: Add new configuration sections
3. **Multi-File Support**: Implement directory-based configurations
4. **Update Layout Domain**: Replace hardcoded values with config lookup
5. **Enhance Tests**: Comprehensive test coverage
6. **Migrate Keyboards**: Convert existing keyboards to new structure

### Design Pattern Adherence
- **Factory Functions**: All services use `create_*()` functions
- **Protocol-Based Interfaces**: New config protocols with `@runtime_checkable`
- **Pydantic Models**: Comprehensive validation for all new configuration
- **Domain Ownership**: Config domain owns models, layout domain consumes
- **Type Safety**: Full mypy compliance throughout

## Phase 1: Remove Legacy Compatibility & Clean Models

### Step 1.1: Remove Legacy Fields from KeyboardConfig
**Files Modified:**
- `glovebox/config/models.py`

**Changes:**
- Remove `flash: FlashConfig | None = None`
- Remove `build: BuildConfig | None = None`
- Remove related legacy classes: `FlashConfig`, `BuildConfig`
- Update validation to require new method system

**Tests Updated:**
- `tests/test_config/test_models.py`
- `tests/test_config/test_keyboard_only_profiles.py`

**Validation Commands:**
```bash
uv run make format && uv run make lint
pytest tests/test_config/test_models.py
```

**Commit Message:**
```
refactor: remove legacy flash/build configuration fields

- Remove deprecated flash and build fields from KeyboardConfig
- Update validation to require modern method system only
- Clean up legacy test cases and validation logic
```

### Step 1.2: Clean Up Legacy Method References
**Files Modified:**
- `glovebox/config/keyboard_profile.py`
- `glovebox/firmware/method_selector.py`
- CLI commands using legacy fields

**Changes:**
- Remove fallback logic to legacy fields
- Update error messages to reference new method system
- Remove legacy compatibility in profile creation

**Tests Updated:**
- Method selector tests
- CLI integration tests

**Validation Commands:**
```bash
uv run make format && uv run make lint
pytest tests/test_config/ tests/test_firmware/test_method_selector.py
```

**Commit Message:**
```
refactor: remove legacy method compatibility

- Remove fallback logic to deprecated flash/build fields
- Update error messages to guide users to new method system
- Clean up profile creation and method selection logic
```

## Phase 2: Extend Configuration Models for New Sections

### Step 2.1: Add Behavior Configuration Section
**Files Modified:**
- `glovebox/config/models.py`

**New Models:**
```python
class BehaviorMapping(BaseModel):
    """Individual behavior class mapping."""
    behavior_name: str = Field(description="ZMK behavior name (e.g., '&kp')")
    behavior_class: str = Field(description="Python class name (e.g., 'KPBehavior')")
    
class ModifierMapping(BaseModel):
    """Modifier key mapping configuration."""
    long_form: str = Field(description="Long modifier name (e.g., 'LALT')")
    short_form: str = Field(description="Short modifier name (e.g., 'LA')")

class BehaviorConfig(BaseModel):
    """Behavior system configuration."""
    behavior_mappings: list[BehaviorMapping] = Field(default_factory=list)
    modifier_mappings: list[ModifierMapping] = Field(default_factory=list)
    magic_layer_command: str = Field(default="&magic LAYER_Magic 0")
    reset_behavior_alias: str = Field(default="&sys_reset")
```

**Tests Created:**
- `tests/test_config/test_behavior_config.py`

**Validation Commands:**
```bash
uv run make format && uv run make lint
pytest tests/test_config/test_behavior_config.py
```

**Commit Message:**
```
feat: add BehaviorConfig section to configuration model

- Add BehaviorMapping and ModifierMapping models
- Add BehaviorConfig with behavior mappings and defaults
- Include comprehensive validation and type safety
```

### Step 2.2: Add Display Configuration Section
**Files Modified:**
- `glovebox/config/models.py`

**New Models:**
```python
class LayoutStructure(BaseModel):
    """Physical layout structure for display."""
    rows: dict[str, list[list[int]]] = Field(description="Row-wise key position mapping")
    
    @field_validator('rows')
    def validate_row_structure(cls, v):
        """Validate row structure contains valid key positions."""
        return v

class DisplayFormatting(BaseModel):
    """Display formatting configuration."""
    header_width: int = Field(default=80, gt=0)
    none_display: str = Field(default="&none")
    trans_display: str = Field(default="▽")
    key_width: int = Field(default=8, gt=0)
    center_small_rows: bool = Field(default=True)
    horizontal_spacer: str = Field(default=" | ")

class DisplayConfig(BaseModel):
    """Complete display configuration."""
    layout_structure: LayoutStructure | None = None
    formatting: DisplayFormatting = Field(default_factory=DisplayFormatting)
```

**Tests Created:**
- `tests/test_config/test_display_config.py`

**Validation Commands:**
```bash
uv run make format && uv run make lint
pytest tests/test_config/test_display_config.py
```

**Commit Message:**
```
feat: add DisplayConfig section for layout structure

- Add LayoutStructure model for keyboard layout definitions
- Add DisplayFormatting for visual display configuration
- Include validation for row structures and key positions
```

### Step 2.3: Add ZMK Configuration Section
**Files Modified:**
- `glovebox/config/models.py`

**New Models:**
```python
class ZmkCompatibleStrings(BaseModel):
    """ZMK compatible string constants."""
    macro: str = Field(default="zmk,behavior-macro")
    hold_tap: str = Field(default="zmk,behavior-hold-tap")
    combos: str = Field(default="zmk,combos")

class ZmkPatterns(BaseModel):
    """ZMK naming and pattern configuration."""
    layer_define: str = Field(default="LAYER_{}")
    node_name_sanitize: str = Field(default="[^A-Z0-9_]")

class FileExtensions(BaseModel):
    """File extension configuration."""
    keymap: str = Field(default=".keymap")
    conf: str = Field(default=".conf")
    dtsi: str = Field(default=".dtsi")
    metadata: str = Field(default=".json")

class ValidationLimits(BaseModel):
    """Validation limits and thresholds."""
    max_layers: int = Field(default=10, gt=0)
    max_macro_params: int = Field(default=2, gt=0)
    required_holdtap_bindings: int = Field(default=2, gt=0)
    warn_many_layers_threshold: int = Field(default=10, gt=0)

class ZmkConfig(BaseModel):
    """ZMK-specific configuration and constants."""
    compatible_strings: ZmkCompatibleStrings = Field(default_factory=ZmkCompatibleStrings)
    hold_tap_flavors: list[str] = Field(default=["tap-preferred", "hold-preferred", "balanced", "tap-unless-interrupted"])
    patterns: ZmkPatterns = Field(default_factory=ZmkPatterns)
    file_extensions: FileExtensions = Field(default_factory=FileExtensions)
    validation_limits: ValidationLimits = Field(default_factory=ValidationLimits)
```

**Tests Created:**
- `tests/test_config/test_zmk_config.py`

**Validation Commands:**
```bash
uv run make format && uv run make lint
pytest tests/test_config/test_zmk_config.py
```

**Commit Message:**
```
feat: add ZmkConfig section for ZMK constants

- Add ZmkCompatibleStrings for ZMK behavior types
- Add ZmkPatterns for naming conventions
- Add FileExtensions and ValidationLimits configuration
- Include comprehensive validation and sensible defaults
```

### Step 2.4: Integrate New Sections into KeyboardConfig
**Files Modified:**
- `glovebox/config/models.py`

**Changes:**
```python
class KeyboardConfig(BaseModel):
    # ... existing fields ...
    
    # New configuration sections
    behavior_config: BehaviorConfig = Field(default_factory=BehaviorConfig)
    display_config: DisplayConfig = Field(default_factory=DisplayConfig)
    zmk_config: ZmkConfig = Field(default_factory=ZmkConfig)
```

**Tests Updated:**
- `tests/test_config/test_models.py`
- `tests/test_config/test_keyboard_only_profiles.py`

**Validation Commands:**
```bash
uv run make format && uv run make lint
pytest tests/test_config/test_models.py tests/test_config/test_keyboard_only_profiles.py
```

**Commit Message:**
```
feat: integrate new configuration sections into KeyboardConfig

- Add behavior_config, display_config, zmk_config fields
- Maintain backward compatibility with default factories
- Update comprehensive model validation tests
```

## Phase 3: Implement Multi-File Configuration Loading

### Step 3.1: Extend ConfigFileAdapter for Multi-File Support
**Files Modified:**
- `glovebox/adapters/config_file_adapter.py`
- `glovebox/protocols/config_file_adapter_protocol.py`

**New Methods:**
```python
def load_config_directory(self, config_dir: Path, main_config: str = "keyboard.yaml") -> dict[str, Any]:
    """Load configuration from directory with multiple files."""
    
def resolve_includes(self, config_data: dict[str, Any], base_path: Path) -> dict[str, Any]:
    """Resolve include directives in configuration."""
```

**Tests Created:**
- `tests/test_adapters/test_config_file_adapter_multifile.py`

**Validation Commands:**
```bash
uv run make format && uv run make lint
pytest tests/test_adapters/test_config_file_adapter_multifile.py
```

**Commit Message:**
```
feat: add multi-file configuration loading support

- Extend ConfigFileAdapter with directory loading capability
- Add include resolution for modular configurations
- Maintain backward compatibility with single-file configs
```

### Step 3.2: Update KeyboardProfile Loading
**Files Modified:**
- `glovebox/config/keyboard_profile.py`

**Changes:**
- Add support for loading from `{keyboard_name}/` directories
- Implement include resolution in configuration data
- Maintain search path compatibility

**Tests Updated:**
- `tests/test_config/test_keyboard_only_profiles.py`

**Validation Commands:**
```bash
uv run make format && uv run make lint
pytest tests/test_config/test_keyboard_only_profiles.py
```

**Commit Message:**
```
feat: add directory-based keyboard profile loading

- Support loading keyboards from {name}/ directories
- Implement include directive resolution
- Maintain full backward compatibility with single files
```

## Phase 4: Update Layout Domain to Use Configuration

### Step 4.1: Update Behavior Formatter
**Files Modified:**
- `glovebox/layout/behavior/formatter.py`

**Changes:**
- Replace hardcoded `_behavior_classes` with `profile.keyboard_config.behavior_config.behavior_mappings`
- Replace hardcoded modifier mappings with config lookup
- Add graceful fallbacks for missing configuration

**Tests Updated:**
- `tests/test_layout/test_layout_behavior_formatter.py`

**Validation Commands:**
```bash
uv run make format && uv run make lint
pytest tests/test_layout/test_layout_behavior_formatter.py
```

**Commit Message:**
```
refactor: use configuration for behavior mappings

- Replace hardcoded behavior classes with config lookup
- Use configurable modifier mappings
- Add graceful fallbacks for missing behavior configuration
```

### Step 4.2: Update Layout Formatting and Display
**Files Modified:**
- `glovebox/layout/formatting.py`
- `glovebox/layout/display_service.py`

**Changes:**
- Replace hardcoded layout structures with `profile.keyboard_config.display_config.layout_structure`
- Use configurable display formatting options
- Remove Glove80-specific hardcoded layout

**Tests Updated:**
- `tests/test_layout/test_display_service.py`

**Validation Commands:**
```bash
uv run make format && uv run make lint
pytest tests/test_layout/test_display_service.py
```

**Commit Message:**
```
refactor: use configurable layout structures

- Replace hardcoded Glove80 layout with configuration
- Use configurable display formatting options
- Support multiple keyboard layout types through config
```

### Step 4.3: Update ZMK Generator
**Files Modified:**
- `glovebox/layout/zmk_generator.py`

**Changes:**
- Replace hardcoded ZMK constants with `profile.keyboard_config.zmk_config`
- Use configurable compatible strings and patterns
- Apply configurable validation limits

**Tests Updated:**
- `tests/test_layout/test_zmk_generator.py`

**Validation Commands:**
```bash
uv run make format && uv run make lint
pytest tests/test_layout/test_zmk_generator.py
```

**Commit Message:**
```
refactor: use configurable ZMK constants

- Replace hardcoded ZMK compatible strings with config
- Use configurable patterns and validation limits
- Support customizable ZMK generation through configuration
```

### Step 4.4: Update Layout Utilities
**Files Modified:**
- `glovebox/layout/utils.py`

**Changes:**
- Use configurable file extensions
- Apply configurable validation limits
- Use configurable default values

**Tests Updated:**
- `tests/test_layout/test_layout_utils.py`

**Validation Commands:**
```bash
uv run make format && uv run make lint
pytest tests/test_layout/test_layout_utils.py
```

**Commit Message:**
```
refactor: use configurable utilities and defaults

- Use configurable file extensions and patterns
- Apply configurable validation limits from config
- Remove hardcoded utility constants
```

## Phase 5: Update and Enhance Test Coverage

### Step 5.1: Write Comprehensive Configuration Tests
**New Test Files:**
- `tests/test_config/test_multi_file_loading.py`
- `tests/test_config/test_configuration_integration.py`
- `tests/test_layout/test_configurable_behavior.py`
- `tests/test_layout/test_configurable_display.py`

**Validation Commands:**
```bash
uv run make format && uv run make lint
pytest tests/test_config/test_multi_file_loading.py tests/test_config/test_configuration_integration.py
pytest tests/test_layout/test_configurable_behavior.py tests/test_layout/test_configurable_display.py
```

**Commit Message:**
```
test: add comprehensive configuration test coverage

- Add multi-file configuration loading tests
- Add end-to-end configuration integration tests
- Add layout domain tests with configurable options
- Ensure full test coverage for new functionality
```

### Step 5.2: Update Existing Tests for New Configuration
**Files Updated:**
- `tests/test_config/test_models.py`
- `tests/test_services/test_layout_service.py`
- `tests/test_cli/test_*.py`

**Validation Commands:**
```bash
uv run make format && uv run make lint
pytest tests/test_config/ tests/test_services/ tests/test_cli/
```

**Commit Message:**
```
test: update existing tests for new configuration system

- Update model tests for new configuration sections
- Update service tests for configurable behavior
- Update CLI tests for new configuration options
```

## Phase 6: Migrate Existing Keyboards to New Structure

### Step 6.1: Create Multi-File Structure for Glove80
**New Directory Structure:**
```
keyboards/glove80/
├── keyboard.yaml              # Core configuration
├── behaviors.yaml             # Behavior mappings
├── display.yaml               # Layout structure
├── zmk.yaml                   # ZMK constants
└── templates/                 # Template files
    ├── keymap.dtsi
    └── behaviors.dts
```

**Migration Strategy:**
- Extract sections from current `keyboards/glove80.yaml`
- Maintain all existing functionality
- Add new configuration sections with current hardcoded values

**Validation Commands:**
```bash
uv run make format && uv run make lint
pytest tests/test_config/test_keyboard_only_profiles.py -k glove80
glovebox status --profile glove80/v25.05
```

**Commit Message:**
```
feat: migrate glove80 to multi-file configuration

- Create modular configuration structure for Glove80
- Extract behaviors, display, and ZMK configuration sections
- Maintain full backward compatibility and functionality
```

### Step 6.2: Update Test Data for New Configuration
**Files Updated:**
- `tests/test_config/test_data/keyboards/test_keyboard.yaml`
- Create test keyboard directories with multi-file structure

**Validation Commands:**
```bash
uv run make format && uv run make lint
pytest tests/test_config/
```

**Commit Message:**
```
test: update test data for new configuration structure

- Add new configuration sections to test keyboards
- Create test cases for multi-file keyboard structure
- Ensure comprehensive test coverage
```

## Final Validation and Documentation

### Complete Test Suite Validation
```bash
# Run complete test suite
uv run make format && uv run make lint
pytest

# Test core functionality
glovebox status --profile glove80/v25.05
glovebox layout compile tests_data/v42pre.json /tmp/test_output --profile glove80/v25.05

# Final commit
git add . && git commit -m "refactor: complete hardcoded value removal and multi-file configuration

- Remove all hardcoded values from layout domain
- Implement comprehensive multi-file configuration system
- Maintain full backward compatibility and type safety
- Add extensive test coverage for new functionality

🎯 Generated with Claude Code"
```

## Risk Assessment and Mitigation

### Risk Level: Medium
**Rationale:** Building on excellent existing infrastructure reduces implementation risk.

### Key Risks and Mitigations:
1. **Breaking Changes**: Maintain comprehensive test coverage and validation at each step
2. **Configuration Complexity**: Provide clear migration guides and validation
3. **Performance Impact**: Multi-file loading should be cached and optimized
4. **User Experience**: Maintain backward compatibility for single-file configs

### Rollback Strategy:
Each phase is designed to be independently reversible through git. Critical rollback points:
- After Phase 1: Can restore legacy compatibility
- After Phase 3: Can revert to single-file only
- After Phase 4: Can restore hardcoded values

## Success Criteria

### Functional Requirements:
- ✅ All hardcoded values removed from layout domain
- ✅ Multi-file configuration system operational
- ✅ Backward compatibility maintained for existing keyboards
- ✅ Full test coverage for new functionality
- ✅ Type safety maintained throughout

### Non-Functional Requirements:
- ✅ No regression in existing functionality
- ✅ Performance maintained or improved
- ✅ Clear error messages for configuration issues
- ✅ Comprehensive documentation and examples

### Deliverables:
- ✅ Refactored codebase with configurable layout system
- ✅ Multi-file configuration support
- ✅ Migrated Glove80 configuration
- ✅ Enhanced test suite
- ✅ Updated documentation

## Estimated Timeline

**Total Estimated Time:** 3-5 days
- **Phase 1:** 4-6 hours (Legacy cleanup)
- **Phase 2:** 6-8 hours (Model extensions)
- **Phase 3:** 4-6 hours (Multi-file support)
- **Phase 4:** 8-10 hours (Layout domain updates)
- **Phase 5:** 6-8 hours (Test coverage)
- **Phase 6:** 4-6 hours (Keyboard migration)

**Note:** Timeline assumes familiarity with existing codebase and includes comprehensive testing and validation at each step.