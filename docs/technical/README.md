# Technical Reference Documentation

This directory contains technical reference documentation, specifications, and API documentation for Glovebox.

## Contents

### Core Specifications
- **[Keymap File Format](keymap_file_format.md)** - Complete specification of keymap JSON format and ZMK DTSI generation
- **[Configuration System](configuration-system.md)** - Configuration file formats, validation, and precedence rules
- **[Protocol Definitions](protocol-definitions.md)** - All protocol interfaces and contracts

### Reference Materials
- **[Resources](resources/)** - Example configurations, reference implementations, and data files
  - **[Glove80](resources/glove80/)** - Glove80-specific reference materials
  - **[Keymap JSON](resources/keymap_json.md)** - JSON schema and format documentation

### Build Systems
- **[Docker Integration](docker-integration.md)** - Docker container management and build processes
- **[Compilation Strategies](compilation-strategies.md)** - ZMK compilation methods and workspace management

## Documentation Standards

### API Documentation
All public APIs are documented with:
- **Function signatures** with full type annotations
- **Parameter descriptions** including types and constraints
- **Return value documentation** with possible states
- **Example usage** with realistic scenarios
- **Error conditions** and exception handling

### Protocol Documentation
Protocol interfaces include:
- **Method signatures** with protocol compliance
- **Behavior contracts** defining expected behavior
- **Implementation guidelines** for concrete implementations
- **Testing strategies** for protocol compliance

### Configuration Reference
Configuration documentation provides:
- **Schema definitions** with validation rules
- **Example configurations** for common scenarios
- **Default values** and fallback behavior
- **Precedence rules** for multi-source configuration
- **Validation messages** and error handling

## Cross-References

For implementation details, see:
- **[Developer Documentation](../dev/)** - Architecture and implementation guides
- **[User Documentation](../user/)** - End-user guides and tutorials
- **[Implementation Plans](../implementation/)** - Current development and completed features

## Maintenance

Technical documentation is maintained alongside code changes:
- **API changes** require corresponding documentation updates
- **Protocol modifications** must update interface documentation
- **Configuration schema changes** require reference updates
- **Examples** must remain current with latest features