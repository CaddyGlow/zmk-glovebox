# Refactoring Plan: Generator Consolidation and Type Safety

This document outlines the plan for refactoring the generator components and improving type safety throughout the codebase.

## Goals

1. Consolidate ConfigGenerator into DTSIGenerator
2. Improve type safety by consistently using KeymapData objects
3. Leverage KeyboardProfile methods for configuration resolution
4. Simplify service interfaces and responsibilities
5. Remove duplication between components

## Non-Goals

1. Backward compatibility with earlier interfaces is NOT required
2. We will update all tests to use the new interfaces

## Plan Details

### 1. Consolidate Generators

- Move ConfigGenerator functionality into DTSIGenerator
- Make DTSIGenerator accept KeymapData objects directly
- Integrate with KeyboardProfile's kconfig resolution methods
- Name the new method `generate_kconfig_conf`
- Remove the config_generator.py file

### 2. Improve KeyboardProfile Methods

- Fix the `resolve_includes` method to properly return the resolved includes
- Enhance `resolve_kconfig_with_user_options` to handle type formatting
- Consider adding a method to extract behavior codes from KeymapData

### 3. Update KeymapService to Use Profile Methods

- Remove redundant kconfig mapping creation in KeymapService
- Use profile methods directly for resolving settings and includes
- Simplify `_generate_config_file` to delegate to DTSIGenerator

### 4. Implement Complete Type Safety

- Update DTSIGenerator to work with KeymapData objects directly
- Remove all remaining `model_dump()` calls in service methods
- Ensure proper error handling with typed objects

### 5. Update Tests

- Update all test fixtures to use KeymapData objects
- Remove any tests relying on ConfigGenerator
- Add tests for the new DTSIGenerator kconfig methods
- Ensure test coverage remains high

### 6. Clean Up After Refactoring

- Remove the now-unused config_generator.py file
- Update all references in imports and factory functions
- Remove any deprecated methods and constants

## Proposed Interface Changes

### For DTSIGenerator:

```python
def generate_kconfig_conf(
    self,
    keymap_data: KeymapData,
    profile: KeyboardProfile,
) -> tuple[str, dict[str, str]]:
    """Generate kconfig content and settings.

    Args:
        keymap_data: Keymap data with configuration parameters
        profile: Keyboard profile with kconfig options

    Returns:
        Tuple of (kconfig_content, kconfig_settings)
    """
```

### For KeyboardProfile:

```python
def resolve_includes(self, behaviors_used: list[str]) -> list[str]:
    """Resolve all necessary includes based on behaviors used.

    Args:
        behaviors_used: List of behavior codes used in the keymap

    Returns:
        List of include statements needed for the behaviors
    """
    # Fix method to return the resolved includes
```

### For KeymapService:

```python
def _generate_config_file(
    self,
    profile: KeyboardProfile,
    keymap_data: KeymapData,
    output_path: Path,
) -> dict[str, str]:
    """Generate configuration file and return settings.

    Args:
        profile: Keyboard profile with configuration options
        keymap_data: Keymap data containing config parameters
        output_path: Path to save the config file

    Returns:
        Dictionary of kconfig settings
    """
    # Simplified to use DTSIGenerator directly
```

## Implementation Tracking

| Task | Status | Notes |
|------|--------|-------|
| Fix KeyboardProfile.resolve_includes | Completed | Added missing return statement |
| Add extract_behavior_codes to KeyboardProfile | Completed | Added new method to extract behavior codes from KeymapData |
| Add kconfig formatting to KeyboardProfile | Completed | Added _format_kconfig_value and generate_kconfig_content methods |
| Add kconfig generation to DTSIGenerator | Completed | Added generate_kconfig_conf method |
| Update KeymapService | Completed | Removed ConfigGenerator dependency and updated _generate_config_file |
| Update tests | Completed | Updated mock_profile fixture with new methods |
| Remove ConfigGenerator | Completed | Removed config_generator.py file |
| Clean up imports | Completed | Removed KConfigMap type alias and ConfigGenerator import |

## Testing Strategy

1. Update test fixtures to use KeymapData objects
2. Write tests for the new DTSIGenerator kconfig methods
3. Ensure KeymapService tests still pass with the updated implementation
4. Verify that the generated config files are identical to the previous implementation

## Success Criteria

1. All tests pass
2. Code is more maintainable and follows consistent patterns
3. Type safety is improved throughout the codebase
4. No functionality is lost compared to the previous implementation