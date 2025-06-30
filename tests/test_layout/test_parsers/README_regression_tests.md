# Parser Regression Tests

This directory contains regression tests for critical parser fixes implemented to resolve ZMK keymap parsing issues.

## Test Files

### `test_regression_fixes_simple.py`
**Primary regression test file** - Comprehensive tests for the core parser fixes, focusing on the actual API and working implementations:

#### 1. #binding-cells Parsing Fix (`TestBindingCellsParsingFix`)
- **Issue**: `#binding-cells = <1>` was incorrectly tokenized as preprocessor directive
- **Fix**: Updated tokenizer patterns to distinguish properties from preprocessor directives
- **Tests**:
  - `test_binding_cells_tokenization_fix`: Verifies `#binding-cells` is tokenized as IDENTIFIER
  - `test_binding_cells_lark_parsing_fix`: Verifies Lark parser correctly handles hash properties
  - `test_extract_int_from_array_property_fix`: Tests integer extraction from ARRAY type values
  - `test_extract_int_handles_malformed_array`: Tests graceful handling of malformed arrays

#### 2. Multi-line Comment Extraction Fix (`TestCommentExtractionFix`)
- **Issue**: Only first comment line was captured for macro descriptions
- **Fix**: Enhanced comment-to-node association and multi-line extraction
- **Tests**:
  - `test_single_comment_extraction`: Single comment line extraction
  - `test_multi_line_comment_extraction`: Multiple consecutive comment lines
  - `test_multi_line_with_empty_lines`: Preserving empty lines for formatting
  - `test_comment_prefix_removal`: Proper removal of `//` prefixes
  - `test_empty_comments_handling`: Handling nodes with no comments
  - `test_excessive_whitespace_cleanup`: Cleaning up multiple empty lines

#### 3. Section Extraction Fix (`TestSectionExtractionFix`)
- **Issue**: Full section structures `/ { macros { ... } };` couldn't be parsed by Lark
- **Fix**: Extract inner block content before parsing
- **Tests**:
  - `test_extract_macro_inner_content_fix`: Extract inner macro block content
  - `test_extract_behavior_inner_content_fix`: Extract inner behavior block content
  - `test_brace_counting_accuracy_fix`: Correct nested brace handling
  - `test_unknown_block_type_fallback`: Fallback for unknown block types
  - `test_missing_block_fallback`: Fallback when target block not found

#### 4. Integration Tests (`TestIntegrationRegression`)
- **Purpose**: Verify all fixes work together correctly
- **Tests**:
  - `test_binding_cells_in_parsed_macro`: Full macro parsing with `#binding-cells`
  - `test_preprocessor_directives_still_work`: Preprocessor directives still handled
  - `test_hash_properties_vs_preprocessor_distinction`: Proper classification of both types

## Original Issues Addressed

### 1. AS_v1_TKZ Macro Parameter Issue
- **Problem**: Macro should have 1 parameter but was inferred as 2 due to missing `#binding-cells`
- **Root Cause**: `#binding-cells = <1>` was tokenized as preprocessor, not parsed as property
- **Solution**: Fixed tokenizer patterns and added ARRAY type handling in integer extraction

### 2. Multi-line Comment Description Issue
- **Problem**: Comments like:
  ```
  // mod_tab_switcher - TailorKey
  //
  // mod_tab_v1_TKZ: Additional description
  ```
  Only captured "mod_tab_switcher - TailorKey"
- **Root Cause**: Comments not associated with nodes, only first line extracted
- **Solution**: Implemented comment-to-node association and multi-line extraction

### 3. Section Parsing Issue
- **Problem**: Full section structures caused Lark parser errors
- **Root Cause**: Device tree grammar couldn't handle full `/{ sections { ... } };` format
- **Solution**: Extract inner block content before parsing

## Test Coverage

The regression tests provide comprehensive coverage for:
- ✅ Tokenizer pattern fixes
- ✅ Lark parser property handling
- ✅ AST behavior converter integer extraction
- ✅ Comment-to-node association
- ✅ Multi-line description extraction  
- ✅ Section extraction with inner content
- ✅ Integration between all fixes
- ✅ Backward compatibility with preprocessor directives

## Running the Tests

```bash
# Run all regression tests
python -m pytest tests/test_layout/test_parsers/test_regression_fixes_simple.py -v

# Run specific test class
python -m pytest tests/test_layout/test_parsers/test_regression_fixes_simple.py::TestBindingCellsParsingFix -v

# Run with coverage
python -m pytest tests/test_layout/test_parsers/test_regression_fixes_simple.py --cov=glovebox.layout.parsers
```

## Maintenance

These tests should be run whenever:
- Parser code is modified
- Tokenizer patterns are updated
- AST node structures change
- Comment handling logic is altered
- Section extraction logic is modified

The tests are designed to catch regressions early and ensure the specific fixes for ZMK keymap parsing continue to work correctly.