# Technical Debt and Future Refactoring

This document tracks technical debt and future refactoring tasks identified during development.

## Type Safety in Service Interfaces

### Issue: Inconsistent Use of KeymapData

**Current State:**
The codebase currently mixes the use of `KeymapData` (a Pydantic model) and raw dictionaries (`dict[str, Any]`) for keymap operations. The KeymapService uses `KeymapData` in its public methods, but then converts to dictionaries when calling component services.

**Impact:**
- Type safety is lost at service boundaries
- Interface contracts are less clear
- Risk of inconsistency when converting between types
- Missing potential benefits of Pydantic validation

**Refactoring Needed:**
1. Update all service interfaces to accept `KeymapData` objects directly:
   - KeymapComponentService
   - LayoutDisplayService
   - ConfigGenerator
   - TemplateContextBuilder
   - DTSIGenerator

2. Leverage Pydantic's validation throughout the service chain
3. Remove redundant `model_dump()` calls in KeymapService
4. Update tests to use KeymapData objects directly

**Priority:** Medium

**Estimated Effort:** 1-2 days

## Service Registration Methods

### Issue: Duplicate Behavior Registration Logic

**Current State:**
The codebase contains two ways to register behaviors:
1. Using KeyboardProfile's `register_behaviors()` method
2. Using KeymapService's `_register_system_behaviors()` method (now removed)

**Impact:**
- Risk of inconsistent behavior registration
- Potential confusion about the proper way to register behaviors

**Refactoring Needed:**
1. Review all behavior registration flows
2. Standardize on the profile-based approach
3. Update any remaining code that uses the service-based approach

**Priority:** Low

**Estimated Effort:** 2-4 hours

## Component Dependencies

### Issue: Direct Instantiation vs. Dependency Injection

**Current State:**
The codebase has a mix of dependency injection patterns:
- Some components are directly instantiated within service constructors
- Others are passed via optional parameters with factory function fallbacks

**Impact:**
- Potential difficulties in testing
- Inconsistent service initialization patterns

**Refactoring Needed:**
1. Apply consistent dependency injection pattern across all services
2. Consider using a dependency injection container for managing service creation
3. Improve testing support by making all dependencies injectable

**Priority:** Low

**Estimated Effort:** 1 day