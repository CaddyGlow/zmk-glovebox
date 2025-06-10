# Refactoring Quick Reference Guide

## Overview

Quick reference for developers working on the hardcoded values removal and multi-file configuration refactoring. This guide provides before/after examples, migration patterns, and essential commands.

## Before vs After Examples

### Configuration Structure

#### Before (Single File)
```yaml
# keyboards/glove80.yaml (1,080+ lines)
keyboard: "glove80"
description: "MoErgo Glove80 split ergonomic keyboard"
# ... 1,000+ lines of configuration
```

#### After (Multi-File)
```yaml
# keyboards/glove80/keyboard.yaml (80 lines)
keyboard: "glove80"
description: "MoErgo Glove80 split ergonomic keyboard"
includes:
  behaviors: "./behaviors.yaml"
  display: "./display.yaml"
  zmk: "./zmk.yaml"
```

### Behavior Configuration

#### Before (Hardcoded)
```python
# glovebox/layout/behavior/formatter.py
self._behavior_classes = {
    "&none": SimpleBehavior,
    "&trans": SimpleBehavior,
    "&kp": KPBehavior,
    # ... hardcoded mappings
}
```

#### After (Configurable)
```python
# Access from configuration
behavior_mappings = profile.keyboard_config.behavior_config.behavior_mappings
for mapping in behavior_mappings:
    self._behavior_classes[mapping.behavior_name] = getattr(behaviors_module, mapping.behavior_class)
```

### Layout Structure

#### Before (Hardcoded)
```python
# glovebox/layout/formatting.py
row_structure = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],  # Hardcoded Glove80
    [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21],
    # ... hardcoded rows
]
```

#### After (Configurable)
```python
# Load from configuration
layout_config = profile.keyboard_config.display_config.layout_structure
if layout_config and layout_config.rows:
    row_structure = list(layout_config.rows.values())
```

### ZMK Constants

#### Before (Hardcoded)
```python
# glovebox/layout/zmk_generator.py
compatible = "zmk,behavior-macro"  # Hardcoded
hold_tap_flavors = ["tap-preferred", "hold-preferred"]  # Hardcoded
```

#### After (Configurable)
```python
# Load from configuration
zmk_config = profile.keyboard_config.zmk_config
compatible = zmk_config.compatible_strings.macro
hold_tap_flavors = zmk_config.hold_tap_flavors
```

## Configuration File Examples

### Main Keyboard Configuration
```yaml
# keyboards/glove80/keyboard.yaml
keyboard: "glove80"
description: "MoErgo Glove80 split ergonomic keyboard"
vendor: "MoErgo"
key_count: 80

# Method configurations
compile_methods:
  - method_type: "docker"
    image: "zmkfirmware/zmk-build-arm:stable"
    # ... method config

flash_methods:
  - method_type: "usb"
    mount_timeout: 10
    # ... method config

# Firmware configurations
firmwares:
  v25.05:
    version: "v25.05"
    description: "Stable release"
    # ... firmware config

# Includes for modular configuration
includes:
  behaviors: "./behaviors.yaml"
  display: "./display.yaml"
  zmk: "./zmk.yaml"
```

### Behavior Configuration
```yaml
# keyboards/glove80/behaviors.yaml
behavior_mappings:
  - behavior_name: "&none"
    behavior_class: "SimpleBehavior"
  - behavior_name: "&trans"
    behavior_class: "SimpleBehavior"
  - behavior_name: "&kp"
    behavior_class: "KPBehavior"
  - behavior_name: "&lt"
    behavior_class: "LayerTapBehavior"

modifier_mappings:
  - long_form: "LALT"
    short_form: "LA"
  - long_form: "LCTL"
    short_form: "LC"

magic_layer_command: "&magic LAYER_Magic 0"
reset_behavior_alias: "&sys_reset"
```

### Display Configuration
```yaml
# keyboards/glove80/display.yaml
layout_structure:
  rows:
    row0: [[0, 1, 2, 3, 4], [5, 6, 7, 8, 9]]
    row1: [[10, 11, 12, 13, 14, 15], [16, 17, 18, 19, 20, 21]]
    row2: [[22, 23, 24, 25, 26, 27], [28, 29, 30, 31, 32, 33]]
    row3: [[34, 35, 36, 37, 38, 39], [40, 41, 42, 43, 44, 45]]
    row4: [[46, 47, 48, 49, 50, 51], [58, 59, 60, 61, 62, 63]]
    row5: [[64, 65, 66, 67, 68], [75, 76, 77, 78, 79]]
    thumb1: [[69, 52], [57, 74]]
    thumb2: [[70, 53], [56, 73]]
    thumb3: [[71, 54], [55, 72]]

formatting:
  header_width: 80
  none_display: "&none"
  trans_display: "▽"
  key_width: 8
  center_small_rows: true
  horizontal_spacer: " | "
```

### ZMK Configuration
```yaml
# keyboards/glove80/zmk.yaml
compatible_strings:
  macro: "zmk,behavior-macro"
  hold_tap: "zmk,behavior-hold-tap"
  combos: "zmk,combos"

hold_tap_flavors:
  - "tap-preferred"
  - "hold-preferred"
  - "balanced"
  - "tap-unless-interrupted"

patterns:
  layer_define: "LAYER_{}"
  node_name_sanitize: "[^A-Z0-9_]"

file_extensions:
  keymap: ".keymap"
  conf: ".conf"
  dtsi: ".dtsi"
  metadata: ".json"

validation_limits:
  max_layers: 10
  max_macro_params: 2
  required_holdtap_bindings: 2
  warn_many_layers_threshold: 10
```

## Migration Patterns

### Pattern 1: Replace Hardcoded Dictionary
```python
# Before
hardcoded_dict = {
    "key1": "value1",
    "key2": "value2"
}

# After
config_items = profile.keyboard_config.section.items
configured_dict = {item.key: item.value for item in config_items}
```

### Pattern 2: Replace Hardcoded Constants
```python
# Before
HARDCODED_CONSTANT = "value"

# After
config_value = profile.keyboard_config.section.field
```

### Pattern 3: Add Configuration Fallbacks
```python
# Configuration with fallback
def get_config_value(profile, default_value):
    try:
        return profile.keyboard_config.section.field
    except AttributeError:
        logger.warning("Configuration missing, using default: %s", default_value)
        return default_value
```

## Code Access Patterns

### Accessing Configuration in Layout Domain
```python
def format_layout(profile: KeyboardProfile, layout_data: LayoutData):
    # Access behavior configuration
    behavior_config = profile.keyboard_config.behavior_config
    
    # Access display configuration
    display_config = profile.keyboard_config.display_config
    
    # Access ZMK configuration
    zmk_config = profile.keyboard_config.zmk_config
    
    # Use configuration values
    header_width = display_config.formatting.header_width
    compatible_string = zmk_config.compatible_strings.macro
```

### Configuration Validation
```python
# Validate configuration before use
def validate_keyboard_config(config: KeyboardConfig) -> list[str]:
    errors = []
    
    if config.display_config.layout_structure:
        # Validate layout structure matches key count
        total_keys = sum(len(row) for rows in config.display_config.layout_structure.rows.values() for row in rows)
        if total_keys != config.key_count:
            errors.append(f"Layout structure has {total_keys} keys but key_count is {config.key_count}")
    
    return errors
```

## Essential Commands

### Development Commands
```bash
# Format and lint (run after every change)
uv run make format && uv run make lint

# Run specific test files
pytest tests/test_config/test_models.py
pytest tests/test_layout/test_behavior_formatter.py

# Run tests with coverage
pytest --cov=glovebox tests/test_config/

# Run mypy type checking
mypy glovebox/

# Test core functionality
glovebox status --profile glove80/v25.05
glovebox layout compile tests_data/v42pre.json /tmp/test --profile glove80/v25.05
```

### Git Workflow Commands
```bash
# Create feature branch
git checkout -b refactor/remove-hardcoded-values

# Commit with proper message format
git add .
git commit -m "refactor: remove hardcoded behavior mappings

- Replace hardcoded behavior classes with config lookup
- Add graceful fallbacks for missing configuration
- Update tests for configurable behavior system"

# Bypass pre-commit hooks if needed (for unrelated errors)
git commit --no-verify -m "commit message"
```

### Testing Validation Commands
```bash
# Validate specific phase completion
pytest tests/test_config/test_behavior_config.py -v
pytest tests/test_layout/test_configurable_display.py -v

# Full test suite validation
pytest --tb=short

# Test specific keyboard functionality
glovebox status --profile glove80/v25.05 --debug
```

## Troubleshooting

### Common Issues

#### Configuration Loading Errors
```python
# Problem: Configuration section missing
# Solution: Add default factory and graceful fallback

class SomeConfig(BaseModel):
    new_field: NewConfigSection = Field(default_factory=NewConfigSection)

# In code
def get_config_safely(profile):
    try:
        return profile.keyboard_config.new_section
    except AttributeError:
        return DefaultConfigSection()
```

#### Type Validation Errors
```python
# Problem: Pydantic validation fails
# Solution: Add proper field validation

class ConfigSection(BaseModel):
    field: int = Field(gt=0, description="Must be positive")
    
    @field_validator('field')
    def validate_field(cls, v):
        if v < 1:
            raise ValueError("Field must be positive")
        return v
```

#### Multi-File Loading Issues
```python
# Problem: Include directive not found
# Solution: Check file paths and add proper error handling

def load_with_includes(config_path: Path):
    try:
        return adapter.load_config_directory(config_path)
    except FileNotFoundError as e:
        logger.error("Include file not found: %s", e)
        raise ConfigurationError(f"Missing include file: {e}")
```

### Debug Configuration Loading
```python
# Add debug logging for configuration issues
import logging
logger = logging.getLogger(__name__)

def debug_config_loading(profile: KeyboardProfile):
    logger.debug("Keyboard config: %s", profile.keyboard_config.keyboard)
    logger.debug("Behavior config: %s", profile.keyboard_config.behavior_config)
    logger.debug("Display config: %s", profile.keyboard_config.display_config)
```

## Validation Checklist

### Before Each Commit
- [ ] `uv run make format && uv run make lint` passes
- [ ] Relevant tests pass: `pytest tests/test_[domain]/`
- [ ] No mypy errors in modified files
- [ ] Core functionality tested manually
- [ ] Progress tracker updated

### Phase Completion Validation
- [ ] All hardcoded values in scope removed
- [ ] Configuration models created and validated
- [ ] Tests updated and passing
- [ ] Backward compatibility maintained
- [ ] Documentation updated

### Final Validation
- [ ] Complete test suite passes: `pytest`
- [ ] No lint/format errors: `uv run make lint`
- [ ] Core commands work: `glovebox status --profile glove80/v25.05`
- [ ] Layout compilation works: `glovebox layout compile [test] [output] --profile glove80/v25.05`
- [ ] Multi-file configuration loads correctly

## Performance Considerations

### Configuration Caching
- Multi-file configurations are cached after first load
- Profile creation uses module-level caching
- Include resolution is cached per configuration directory

### Optimization Tips
- Load configuration once per operation, not per function call
- Use lazy loading for optional configuration sections
- Cache computed configuration values when expensive

## Next Steps After Refactoring

### Follow-up Improvements
1. **Additional Keyboard Types**: Add configurations for more keyboard layouts
2. **Configuration Validation Tools**: CLI commands to validate keyboard configurations
3. **Configuration Templates**: Templates for creating new keyboard configurations
4. **User Configuration**: Allow users to override keyboard configurations locally
5. **Configuration Documentation**: Auto-generated documentation from Pydantic models

### Monitoring and Maintenance
- Monitor for configuration-related issues in user reports
- Add configuration validation to CI/CD pipeline
- Maintain backward compatibility for configuration format changes
- Document configuration format changes in release notes