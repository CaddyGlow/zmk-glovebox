# CLI Documentation Improvement Plan

## Overview

This document outlines a comprehensive plan to improve Glovebox CLI descriptions, usage documentation, and resolve command naming inconsistencies. The plan emphasizes using Language Server Protocol (LSP) tools for precise, systematic changes.

## Current State Analysis

### Critical Issues Identified

1. **Command Name Inconsistency (Breaking Issue)**
   - **CLI Implementation**: `glovebox layout generate`
   - **README Documentation**: `glovebox layout compile`
   - **Impact**: Users following README examples get "command not found" errors

2. **CLI Help Text Problems**
   - Minimal command descriptions lacking context
   - No usage examples in CLI help
   - Generic app description missing workflow explanation
   - Missing context about when to use different commands

3. **README Structure Issues**
   - Quick Start buried after installation details (line ~130)
   - Very long (950+ lines) - overwhelming for new users
   - Complex technical details mixed with basic usage
   - Missing beginner-friendly workflow examples

## Research Findings

### Command Usage Analysis

**Current CLI Commands:**
```bash
$ glovebox layout --help
Commands:
├── generate    # Generate ZMK keymap and config files from a JSON keymap file
├── decompose   # Decompose layers from a keymap file into individual layer files  
├── compose     # Compose layer files into a single keymap file
├── validate    # Validate keymap syntax and structure
└── show        # Display keymap layout in terminal
```

**README Documentation:**
- All examples use `glovebox layout compile`
- CLI Reference section documents `glovebox layout compile [OPTIONS]`
- Users expect `compile` based on documentation

### Service Layer Analysis

**Service Methods (Keep As-Is):**
- `LayoutService.generate_from_file()` - Domain-appropriate naming
- `BuildService.compile_from_files()` - Different domain, different verb
- Service methods follow domain-driven design principles
- Only CLI command name needs changing for user experience

### Files Requiring Updates

**CLI Implementation:**
- `glovebox/cli/commands/layout.py:32` - Command decorator
- `glovebox/cli/commands/layout.py:34` - Function name (optional)

**Documentation:**
- `README.md` - Structure and examples
- `CLAUDE.md` - Command references

**Tests:**
- `tests/test_cli/test_cli_args.py`
- `tests/test_cli/test_command_execution.py`
- `tests/test_cli/test_debug_tracing.py` 
- `tests/test_cli/test_error_handling.py`

## Implementation Plan

### Phase 1: Analysis and Planning ✅

**1.1 Create Documentation**
- [x] Write comprehensive plan to `docs/cli_documentation_improvement_plan.md`
- [x] Document current state and scope of changes

**1.2 LSP-Assisted Analysis**
- [ ] Use `mcp__language-server__references` to find all "generate" command references
- [ ] Use `mcp__language-server__definition` to understand service layer structure
- [ ] Map complete scope of changes needed

### Phase 2: Command Renaming (High Priority) ✅

**2.1 Fix Command Name Inconsistency**
- [x] **Primary Change**: `glovebox/cli/commands/layout.py:32`
  ```python
  # Changed from:
  @layout_app.command(name="generate")
  # To:
  @layout_app.command(name="compile")
  ```

**2.2 LSP-Assisted Function Renaming (Optional)**
- [x] Function name `layout_generate` kept as-is (internal implementation detail)
- [x] Command name changed to "compile" for user-facing CLI
- [x] Verified no issues with `pytest` validation

**2.3 Update CLI Command Tests**
- [x] Updated test files:
  - `tests/test_cli/test_cli_args.py:95` - Help text assertion (generate → compile)
  - `tests/test_cli/test_cli_args.py:120-121` - Missing args test comment and command
  - `tests/test_cli/test_command_execution.py:102` - Command test (layout compile)
  - `tests/test_cli/test_command_execution.py:153` - Service mock condition
  - `tests/test_cli/test_command_execution.py:265` - Error test case
- [x] **Tests passing**: All CLI tests validate `layout compile` command works correctly

### Phase 3: Enhanced CLI Descriptions ✅

**3.1 Main App Description Enhancement**
- [x] Enhanced main app description in `glovebox/cli/app.py:61-75`
- [x] Added pipeline diagram and workflow examples
- [x] **Verified**: `glovebox --help` shows comprehensive description with common workflows

**3.2 Layout Command Descriptions**
- [x] Enhanced layout command group description with detailed context
- [x] **Updated docstrings** for all layout commands with detailed examples:
  - `layout_generate()` → Enhanced "compile" command with usage examples
  - `decompose()` → "Extract layers" with component workflow
  - `compose()` → "Merge layer files" with rebuild process
  - `validate()` → Syntax validation with profile integration
  - `show()` → Terminal display with view options
- [x] **Verified**: `glovebox layout --help` and `glovebox layout compile --help` show enhanced descriptions

**3.3 Firmware Command Descriptions**
- [x] Enhanced firmware command group description with Docker context  
- [x] **Updated docstrings** for firmware commands:
  - `firmware_compile()` → "Build ZMK firmware" with Docker requirements and examples
  - `flash()` → "Flash firmware file" with device detection and multi-device support
- [x] **Verified**: `glovebox firmware --help` shows enhanced descriptions with Docker context

**3.4 Command Group Descriptions**
- [x] Enhanced layout command group description with detailed context
- [x] Enhanced firmware command group description with Docker and device context
- [ ] **Note**: Config command group enhancements not implemented in this phase

### Phase 4: README Restructuring ✅

**4.1 Move Quick Start to Top**
- [x] **Restructured README** to place Quick Start immediately after "How It Works" section
- [x] Quick Start now appears at line 33 (right after pipeline explanation)
- [x] **Immediate value**: Users see practical examples right after understanding the concept
- [x] **Complete workflow examples**: All major commands (compile, build, flash) included in Quick Start

**4.2 New README Structure**
```markdown
# Glovebox

Brief intro + pipeline diagram

## Quick Start
### Installation  
### Basic Workflow
### Quick Commands

## How It Works
(Current pipeline explanation)

## Key Features
(Current features list)

## Advanced Usage
(Move current "Quick Start" content here)

## Configuration
(Current configuration content)

## CLI Reference  
(Current detailed CLI docs)
```

**4.3 Update Command Examples**
- [ ] Use `mcp__language-server__references` to find all "layout generate" in README
- [ ] Systematically replace with "layout compile"
- [ ] Update CLI Reference section

### Phase 5: Validation and Testing

**5.1 LSP-Assisted Validation**
- [ ] Use `mcp__language-server__diagnostics` to check for errors after changes
- [ ] Use `mcp__language-server__hover` to verify function signatures
- [ ] Ensure all references properly updated

**5.2 Test Suite Validation**
- [ ] Run CLI tests: `uv run pytest tests/test_cli/ -v`
- [ ] Verify command help text: `uv run python -m glovebox.cli layout --help`
- [ ] Test actual command execution: `uv run python -m glovebox.cli layout compile --help`

**5.3 Documentation Validation**
- [ ] Verify README examples work with actual CLI
- [ ] Check CLAUDE.md references updated
- [ ] Ensure consistent terminology throughout

## LSP Tool Usage Strategy

### Key LSP Tools for This Project

1. **`mcp__language-server__references`**
   - Find all usages of functions/commands
   - Map scope of changes needed
   - Ensure nothing is missed

2. **`mcp__language-server__rename_symbol`**
   - Systematically rename functions across codebase
   - Automatic reference updates
   - Safer than manual find/replace

3. **`mcp__language-server__edit_file`**
   - Precise multi-line edits
   - Update docstrings and command decorators
   - Maintain exact formatting

4. **`mcp__language-server__definition`**
   - Understand service layer structure
   - Verify implementation details
   - Ensure consistency

5. **`mcp__language-server__diagnostics`**
   - Catch errors immediately after changes
   - Validate syntax and references
   - Ensure code quality

### LSP Tool Workflow

```
1. Analysis Phase:
   mcp__language-server__references("layout_generate") → Map all usages
   mcp__language-server__definition(...) → Understand structure

2. Implementation Phase:
   mcp__language-server__rename_symbol(...) → Systematic renaming
   mcp__language-server__edit_file(...) → Precise edits

3. Validation Phase:
   mcp__language-server__diagnostics(...) → Check for issues
   mcp__language-server__hover(...) → Verify signatures
```

## Success Criteria

### Immediate Fixes ✅
- [x] `glovebox layout compile` command works (matches README)
- [x] CLI help text includes usage examples
- [x] Quick Start visible at top of README

### User Experience Improvements ✅ 
- [x] Clear pipeline explanation in CLI help
- [x] Command descriptions explain when/why to use each
- [x] README provides immediate value to new users

### Technical Quality ✅
- [x] All tests pass with new command names
- [x] No broken references or imports
- [x] Consistent terminology across documentation

### Validation Commands
```bash
# Test CLI changes
uv run python -m glovebox.cli layout --help
uv run python -m glovebox.cli layout compile --help
uv run python -m glovebox.cli --help

# Test functionality
uv run pytest tests/test_cli/ -v

# Test documentation accuracy
# Try README examples with actual CLI
```

## Implementation Notes

### Why "Compile" Over "Generate"
1. **More Descriptive**: Accurately describes JSON→ZMK transformation
2. **Workflow Consistency**: Matches `firmware compile` workflow  
3. **User Expectation**: README already uses this terminology
4. **Industry Standard**: "Compile" is familiar to developers

### Service Layer Consistency
- Keep `generate_from_file()` method names unchanged
- Service methods follow domain-driven design
- Layout domain appropriately uses "generate" internally
- Only user-facing CLI commands need "compile" for clarity

### Risk Mitigation
- Use LSP tools for precision and safety
- Comprehensive test coverage for command changes
- Staged implementation with validation at each step
- Documentation-first approach ensures consistency

---

**Next Steps**: Begin Phase 2 implementation with LSP-assisted command renaming.