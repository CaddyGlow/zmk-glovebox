# Template-Edit Regression Testing

This document outlines the comprehensive test suite that prevents regressions in template functionality when edit operations are performed.

## Overview

The template-edit regression tests ensure that:
1. **Edit operations preserve template syntax** in unmodified fields
2. **Template processing works correctly** after edits
3. **Complex template features** (conditionals, filters, nested variables) remain functional
4. **CLI edit commands** don't interfere with templating
5. **End-to-end workflows** (edit → compile) function properly

## Test Files

### 1. Core Regression Tests
**File**: `tests/test_layout/test_template_edit_regression.py`

**Coverage**:
- Template preservation during field edits
- Variable editing preserves template references  
- Layer operations preserve templates
- Template processing after edits
- Complex Jinja2 expressions with edits
- Error handling and recovery

**Key Tests**:
- `test_field_edit_preserves_templates()` - Basic field editing
- `test_template_processing_after_field_edits()` - End-to-end processing
- `test_load_with_templates_after_edits()` - Main entry point testing
- `test_to_flattened_dict_after_edits()` - Compilation output testing

### 2. Template Service Integration  
**File**: `tests/test_layout/test_template_service_edit_integration.py`

**Coverage**:
- Deep template service integration with edits
- Complex nested variable handling
- Multi-stage template resolution after edits
- Template error recovery
- Multiple edit cycle stability

**Key Tests**:
- `test_template_processing_before_edit()` - Baseline functionality
- `test_template_processing_after_edits()` - Post-edit processing
- `test_multiple_edit_cycles_stability()` - Stress testing
- `test_load_with_templates_edit_roundtrip()` - Roundtrip testing

### 3. CLI Integration Tests
**File**: `tests/test_cli/test_template_edit_integration.py`

**Coverage**:
- CLI edit commands preserve templates
- End-to-end CLI workflows
- Template compilation integration
- Error handling in CLI context

**Key Tests**:
- `test_cli_set_field_preserves_templates()` - CLI field editing
- `test_cli_edit_then_compile_workflow()` - Complete CLI workflow
- `test_cli_multiple_operations_preserve_templates()` - Batch operations

### 4. Comprehensive Regression Suite
**File**: `tests/test_template_edit_regression_suite.py`

**Coverage**:
- Complete regression test suite
- All critical paths in one place
- Easy-to-run verification
- Multiple template complexity levels

**Key Tests**:
- `test_basic_template_preservation()` - Foundation testing
- `test_template_processing_after_edits()` - Core functionality
- `test_complex_conditional_logic()` - Advanced features
- `test_compilation_workflow_integration()` - End-to-end validation

## Template Features Tested

### Basic Template Syntax
- Variable substitution: `{{ variables.user_name }}`
- Nested variables: `{{ variables.timing.fast }}`
- Filters: `{{ variables.user_name|lower }}`

### Advanced Template Features  
- Conditionals: `{% if variables.features.combos %}`
- Loops: `{% for item in variables.list %}`
- Complex expressions with multiple variables
- Multi-line templates with whitespace control

### Template Processing Contexts
- Basic fields (title, creator, notes)
- Behavior definitions (holdTaps, combos, macros)
- Custom code (custom_defined_behaviors)
- Layer content (limited support)

## Edit Operations Tested

### Field Operations
- Setting simple fields: `version`, `keyboard`
- Setting nested variables: `variables.user_name`, `variables.timing.fast`
- Adding new variables and template expressions
- Complex nested object editing

### Layer Operations
- Adding layers: `--add-layer`
- Copying layers: `--copy-layer`
- Removing layers: `--remove-layer`
- Moving layers: `--move-layer`

### Batch Operations
- Multiple edits in single command
- Mixed field and layer operations
- Variable updates with template additions

## Critical Workflows Tested

### Edit → Template Processing
1. **Load layout** with templates (unprocessed)
2. **Edit fields/variables** via CLI or programmatically
3. **Process templates** via `LayoutData.load_with_templates()`
4. **Verify** templates resolved with edited values

### Edit → Compile
1. **Edit layout** with template variables
2. **Compile layout** via `glovebox layout compile`
3. **Verify** generated files have processed templates

### Roundtrip Editing
1. **Process templates** in layout
2. **Edit processed layout** 
3. **Process templates again**
4. **Verify** continued functionality

## Running the Tests

### Quick Verification
```bash
# Run comprehensive regression suite
pytest tests/test_template_edit_regression_suite.py -v

# Run specific test category
pytest tests/test_layout/test_template_edit_regression.py -v
```

### Complete Coverage
```bash
# Run all template-edit related tests
pytest tests/test_layout/test_template_edit_regression.py \
       tests/test_layout/test_template_service_edit_integration.py \
       tests/test_cli/test_template_edit_integration.py \
       tests/test_template_edit_regression_suite.py -v
```

### CI Integration
```bash
# Minimal regression check for CI
pytest tests/test_template_edit_regression_suite.py::TestTemplateEditRegressionSuite::test_basic_template_preservation \
       tests/test_template_edit_regression_suite.py::TestTemplateEditRegressionSuite::test_template_processing_after_edits \
       tests/test_template_edit_regression_suite.py::TestTemplateEditRegressionSuite::test_compilation_workflow_integration
```

## Test Scenarios Covered

### Normal Operations
- ✅ Field edits preserve templates
- ✅ Variable edits preserve template references
- ✅ Templates process correctly after edits
- ✅ Layer operations don't interfere with templates
- ✅ CLI commands preserve template functionality

### Edge Cases
- ✅ Multiple edit cycles maintain stability
- ✅ Complex conditional logic works after edits
- ✅ Error recovery when templates have issues
- ✅ Roundtrip edit → template → edit workflows
- ✅ Template variable deletion handling

### Integration Points
- ✅ `LayoutData.load_with_templates()` entry point
- ✅ `LayoutData.process_templates()` explicit processing
- ✅ `LayoutData.to_flattened_dict()` compilation output
- ✅ CLI compilation workflow with templates
- ✅ Template service multi-stage processing

## Regression Prevention Strategy

### Automated Testing
- All tests run in CI/CD pipeline
- Tests cover critical user workflows
- Tests verify both preservation and processing
- Tests include error scenarios

### Test Maintenance  
- Update tests when adding new template features
- Extend tests when adding new edit operations
- Keep tests synchronized with CLI command changes
- Document new test scenarios as they arise

### Performance Monitoring
- Track test execution time for performance regressions
- Monitor template processing performance after edits
- Verify no memory leaks in edit → template cycles

## Future Enhancements

### Additional Test Coverage
- More complex layer template scenarios
- Advanced Jinja2 feature testing (macros, inheritance)
- Template performance with large layouts
- Concurrent edit operation testing

### Tooling Improvements
- Automated test generation for new templates
- Visual diff verification for compiled outputs
- Template syntax validation testing
- CLI command fuzzing with templates

## Summary

The template-edit regression test suite provides comprehensive coverage of the critical interaction between template functionality and edit operations. This ensures that users can safely edit layouts containing templates without losing template functionality or experiencing unexpected behavior during compilation.

Key success metrics:
- ✅ **Template Preservation**: Edit operations never modify template syntax
- ✅ **Processing Integrity**: Templates process correctly with edited values  
- ✅ **Workflow Continuity**: Complete edit → compile workflows function properly
- ✅ **Error Resilience**: Graceful handling of template-related errors
- ✅ **CLI Compatibility**: All CLI edit commands work with templates