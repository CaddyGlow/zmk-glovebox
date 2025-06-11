# Refactoring Recommendations

This document summarizes all the recommended improvements to the Glovebox codebase, organized by focus area.

## 1. Protocol Validation Improvements

### Replace Custom Runtime Protocol Validator with Standard mypy

The current custom protocol validator in `glovebox/utils/protocol_validator.py` should be replaced with the existing mypy configuration, which is already quite strict:

- **Current Strengths**: The project already has excellent mypy configuration with `strict = true`
- **Remove Custom Code**: Eliminate the custom protocol validator and rely on mypy
- **@runtime_checkable**: Apply to all Protocols to enable `isinstance()` checks
- **Test with isinstance()**: Replace validation calls with simple `isinstance()` checks in tests

See [Protocol Validation Refactoring](./refactoring_protocol_validation.md) for the detailed plan.

## 2. Service Layer Improvements

### Move CLI Logic to Services

Move validation and data conversion logic from CLI commands to appropriate service methods:

- **File-Based Service Methods**: Create methods that accept file paths rather than pre-parsed data
- **Data Validation in Services**: Move all validation logic to service layer
- **CLI as Thin Layer**: Reduce CLI code to only parameter handling and output formatting

### Enforce Strict Dependency Injection

Improve the dependency injection pattern:

- **Explicit Dependencies**: Make all dependencies explicit in constructors
- **Enhanced Factory Functions**: Create comprehensive factory functions for all services
- **Consistent Patterns**: Use the same DI pattern across all services

### Make Behavior Registration Explicit

Improve the behavior registration mechanism:

- **Dedicated Registration Service**: Create a service specifically for behavior registration
- **Immutable After Setup**: Make the behavior registry immutable after initial setup
- **Clear Responsibility**: Define clear ownership of registration processes

See [Service Layer Improvements](./service_layer_improvements.md) for detailed recommendations.

## 3. Naming Improvements

Several names in the codebase could be improved for clarity:

### Class and Interface Naming

- Use **consistent suffixes**: `-Protocol` for interfaces, `-Impl` for implementations only when necessary
- Make **clear distinctions** between adapters and protocols

### Method and Parameter Naming

- Use **more descriptive names** for methods and parameters
- Avoid **abbreviations** that aren't immediately clear
- Ensure parameter names **indicate their purpose**

### File Naming

- Rename files to better reflect their primary purpose
- Use consistent naming patterns across the codebase

See [Naming Improvements](./naming_improvements.md) for the complete list of suggested changes.

## 4. Implementation Strategy

### Phased Approach

1. **Initial Phase**: Remove custom protocol validator
   - Remove `protocol_validator.py` and `validate_adapters.py`
   - Update Protocol definitions with `@runtime_checkable` where needed
   - Update tests to use `isinstance()` instead of custom validators

2. **Service Layer Phase**: Restructure service layer
   - Move logic from CLI to services
   - Implement strict dependency injection

3. **Cleanup Phase**: Update names and documentation
   - Improve naming for clarity
   - Update documentation

### Milestones and Pull Requests

Create PRs for each focused change:

1. **PR #1**: Remove custom protocol validator
2. **PR #2**: Move CLI logic to service layer
3. **PR #3**: Implement strict dependency injection
4. **PR #4**: Make behavior registration explicit
5. **PR #5**: Rename classes, methods, and files for clarity

## 5. Benefits of These Changes

### Improved Code Quality

- **Simplified Code**: Removes custom validation logic
- **Standard Patterns**: Uses Python's built-in typing features
- **Clearer Responsibilities**: Better separation of concerns

### Better Developer Experience

- **IDE Support**: Better code completion and error detection
- **Reduced Learning Curve**: More conventional patterns
- **Clearer Naming**: Immediate understanding of purpose

### Maintainability

- **Less Custom Code**: Fewer special patterns to learn
- **Better Testability**: Clearer dependencies make testing easier
- **Improved Documentation**: Better names reduce need for comments

## 6. Getting Started

The highest impact items to start with:

1. Remove the custom protocol validator
2. Create file-based service methods to move logic from CLI
3. Implement strict dependency injection in one service as an example

These three changes will demonstrate the value of the approach while minimizing disruption to the existing codebase.