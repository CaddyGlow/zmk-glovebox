# Technical Reference Documentation

This directory contains comprehensive technical reference documentation for the Glovebox keyboard firmware management system.

## Overview

Glovebox is a domain-driven application that transforms keyboard layouts through a multi-stage pipeline:

```
Layout Editor → JSON File → ZMK Files → Firmware → Flash
  (Design)    →  (.json)  → (.keymap + .conf) → (.uf2) → (Keyboard)
```

## Documentation Structure

### Core References
- **[API Reference](api-reference.md)** - Complete API documentation for all public interfaces
- **[Data Models](data-models.md)** - Comprehensive Pydantic model schemas and validation rules
- **[Configuration System](configuration-system.md)** - Configuration file formats and type-safe profile management
- **[Protocol Definitions](protocol-definitions.md)** - All protocol interfaces and behavioral contracts
- **[Error Handling](error-handling.md)** - Error codes, exception hierarchy, and debugging guidelines

### Domain-Specific Documentation
- **[Layout System](layout-system.md)** - Layout processing, JSON→DTSI conversion, and version management
- **[Firmware Domain](firmware-domain.md)** - Compilation strategies, build systems, and flashing operations
- **[Cache Architecture](cache-architecture.md)** - Shared cache coordination and performance optimization
- **[CLI Framework](cli-framework.md)** - Command structure, parameter handling, and theming system

### Integration Guides
- **[ZMK Integration](zmk-integration.md)** - ZMK firmware compilation and workspace management
- **[MoErgo Integration](moergo-integration.md)** - MoErgo service API client and authentication
- **[Docker Integration](docker-integration.md)** - Container management and build processes
- **[USB Device Handling](usb-device-handling.md)** - Cross-platform USB device detection and flashing

### File Format Specifications
- **[Layout JSON Format](layout-json-format.md)** - Complete layout file format specification
- **[Keymap DTSI Format](keymap-dtsi-format.md)** - ZMK Device Tree Source Interface generation
- **[Configuration YAML Format](configuration-yaml-format.md)** - Modular configuration file structure
- **[Behavior Definitions](behavior-definitions.md)** - ZMK behavior syntax and custom behaviors

### Performance and Optimization
- **[Performance Considerations](performance-considerations.md)** - Optimization strategies and benchmarks
- **[Memory Management](memory-management.md)** - Cache strategies and resource optimization
- **[Build Optimization](build-optimization.md)** - Compilation caching and workspace management

## Technical Standards

### Type Safety
All APIs use comprehensive type annotations with Pydantic v2 models:
- **Runtime validation** with automatic type coercion
- **JSON Schema generation** for external integrations
- **Alias support** for API compatibility
- **Custom validators** for domain-specific rules

### Error Handling
Structured error handling with:
- **Domain-specific exceptions** with clear inheritance hierarchy
- **Debug-aware logging** with stack traces only in debug mode
- **User-friendly messages** with actionable error information
- **Contextual error reporting** with file paths and line numbers

### Protocol Design
All interfaces defined as runtime-checkable protocols:
- **Behavioral contracts** defining expected behavior
- **Implementation guidelines** for concrete implementations
- **Testing strategies** for protocol compliance
- **Adapter patterns** for external system integration

### Documentation Standards
Technical documentation includes:
- **Complete function signatures** with type annotations
- **Parameter descriptions** with types, constraints, and examples
- **Return value documentation** with all possible states
- **Example usage** with realistic scenarios
- **Error conditions** and exception handling patterns

## Cross-References

For implementation details and architecture:
- **[Developer Documentation](../dev/)** - Implementation guides and coding standards
- **[User Documentation](../user/)** - End-user guides and tutorials
- **[Implementation Plans](../implementation/)** - Development roadmap and completed features

## Maintenance Guidelines

Technical documentation is maintained alongside code changes:
- **API changes** require corresponding documentation updates
- **Protocol modifications** must update interface documentation
- **Configuration schema changes** require reference updates
- **Examples** must remain current with latest features
- **Error codes** must be documented and categorized

## Quick Reference

### Factory Functions
All services are created through factory functions following consistent patterns:
```python
# Domain service creation
layout_service = create_layout_service()
flash_service = create_flash_service()
compilation_service = create_compilation_service("zmk_west")

# Configuration creation
keyboard_profile = create_keyboard_profile("glove80", "v25.05")
user_config = create_user_config()

# Adapter creation
docker_adapter = create_docker_adapter()
file_adapter = create_file_adapter()
```

### Base Model Usage
All data models inherit from `GloveboxBaseModel`:
```python
# Proper serialization
data = model.model_dump(by_alias=True, mode="json")
# or use convenience method
data = model.to_dict()

# Proper validation
model = MyModel.model_validate(data, mode="json")
```

### Protocol Implementation
All protocols are runtime-checkable:
```python
@runtime_checkable
class MyServiceProtocol(Protocol):
    def my_method(self, param: str) -> str: ...

# Implementation validation
assert isinstance(my_service, MyServiceProtocol)
```