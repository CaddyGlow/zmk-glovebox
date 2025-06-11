# Keyboard Configuration Management System

## Overview

The Keyboard Configuration Management System extends Glovebox with powerful capabilities for installing, managing, and sharing keyboard configurations. This feature enables users to easily discover, install, and validate community keyboard configurations while maintaining the existing robust configuration architecture.

## Motivation

Currently, Glovebox ships with built-in keyboard configurations (like Glove80) and supports user-defined configurations through manual file placement. However, there's no systematic way to:

- **Install community keyboard configurations** from external sources
- **Validate custom configurations** before use
- **Share keyboard configurations** between users and projects
- **Manage configuration versions** and updates
- **Create new configurations** from templates

This system addresses these gaps while building on Glovebox's existing solid configuration foundation.

## Current State Analysis

### ✅ Existing Strengths

**Multi-Source Configuration Discovery:**
- Built-in configs in `keyboards/` directory
- User configs in `~/.config/glovebox/keyboards`
- Environment variable support (`GLOVEBOX_KEYBOARD_PATH`)
- User-defined paths in configuration files

**Robust CLI Interface:**
- `glovebox config list` - List available keyboards
- `glovebox config show-keyboard <name>` - Show keyboard details
- `glovebox config firmwares <keyboard>` - List firmware versions
- `glovebox config firmware <keyboard> <firmware>` - Show firmware details

**Type-Safe Configuration:**
- Pydantic models with comprehensive validation
- Structured YAML configuration format
- Caching system for performance
- Support for both `.yaml` and `.yml` extensions

**Flexible Profile System:**
- Keyboard + firmware combinations
- Keyboard-only profiles for minimal configurations
- Runtime profile creation and caching

### ❌ Missing Capabilities

**Installation and Management:**
- No installation commands for external configurations
- No validation of custom configurations
- No removal/uninstall functionality
- No backup/restore capabilities

**Development and Sharing:**
- No templates for creating new keyboard configs
- No validation tools for config developers
- No standardized sharing mechanisms
- No version management or update system

**Registry and Discovery:**
- No community marketplace or registry
- No search and discovery of configurations
- No remote repository management

## Architecture Design

### Core Components

```
glovebox/config/
├── installation.py        # Installation service
├── validation.py          # Configuration validation
├── templates.py           # Template generation
└── registry.py            # Future: Registry integration

glovebox/cli/commands/
├── config.py              # Extended with install commands
└── config_install.py      # Installation-specific commands

glovebox/models/
└── installation.py        # Installation metadata models
```

### Configuration Search Hierarchy

The system maintains the existing search hierarchy while adding installation tracking:

```
1. Built-in configurations     # Package keyboards/ directory
2. User-installed configs      # ~/.config/glovebox/keyboards/
3. Environment paths           # GLOVEBOX_KEYBOARD_PATH
4. User-defined paths          # From config files
```

### Installation Metadata

```yaml
# ~/.config/glovebox/installed.json
{
  "keyboards": {
    "corne-v3": {
      "source": {
        "type": "url",
        "path": "https://raw.githubusercontent.com/user/repo/corne-v3.yaml",
        "version": "1.2.0"
      },
      "installed_at": "2025-01-09T10:30:00Z",
      "is_builtin": false
    }
  },
  "last_updated": "2025-01-09T10:30:00Z"
}
```

## Implementation Phases

### Phase 1: Core Installation System

**Target: Basic install/remove/validate functionality**

#### New CLI Commands

```bash
# Install from local file
glovebox config install ./my_keyboard.yaml

# Install from URL
glovebox config install https://raw.githubusercontent.com/user/repo/keyboard.yaml

# Install with custom name
glovebox config install ./keyboard.yaml --name my_custom_board

# Validate configuration
glovebox config validate ./keyboard.yaml

# Remove installed configuration
glovebox config remove my_custom_board

# List with installation status
glovebox config list --installed
glovebox config list --available
glovebox config list --all
```

#### Core Services

**Installation Service (`glovebox/config/installation.py`):**
- Download configurations from URLs
- Install local configuration files
- Track installation metadata
- Handle naming conflicts
- Provide installation status reporting

**Validation Service (`glovebox/config/validation.py`):**
- Validate Pydantic model compliance
- Check required configuration sections
- Validate firmware configurations
- Verify keyboard metadata completeness
- Lint YAML formatting and structure

#### File Structure

```
~/.config/glovebox/
├── keyboards/              # Installed keyboard configs
│   ├── corne-v3.yaml
│   ├── lily58.yaml
│   └── custom_board.yaml
├── installed.json          # Installation metadata
└── config.yaml            # User configuration
```

### Phase 2: Advanced Management

**Target: Templates, backup/restore, updates**

#### Template System

```bash
# Generate keyboard config template
glovebox config template basic --output my_keyboard.yaml

# Generate from existing keyboard
glovebox config template --from glove80 --output glove80_custom.yaml

# List available templates
glovebox config template --list
```

#### Backup and Restore

```bash
# Backup all configurations
glovebox config backup

# Restore from backup
glovebox config restore 2025-01-09

# List available backups
glovebox config backup --list
```

#### Update Management

```bash
# Update specific configuration
glovebox config update corne-v3

# Update all configurations
glovebox config update --all

# Check for updates
glovebox config update --check
```

### Phase 3: Registry and Marketplace (Future)

**Target: Community sharing and discovery**

#### Registry Integration

```bash
# Search registry
glovebox config search "split keyboard"

# Install from registry
glovebox config install --registry corne-v3@latest

# Publish to registry
glovebox config publish ./my_keyboard.yaml

# Show registry information
glovebox config info --registry corne-v3
```

## Configuration Schema

### Enhanced Keyboard Configuration

```yaml
# Keyboard metadata
keyboard: "my_custom_board"
description: "Custom split ergonomic keyboard"
vendor: "Community"
key_count: 52
version: "1.0.0"              # New: Version field
homepage: "https://..."       # New: Documentation URL
repository: "https://..."     # New: Source repository
license: "MIT"               # New: License information

# Hardware configuration
flash:
  method: "mass_storage"
  query: "vendor=Custom and removable=true"
  usb_vid: "0x1234"
  usb_pid: "0x5678"

build:
  method: "docker"
  docker_image: "zmk-build"
  repository: "zmkfirmware/zmk"
  branch: "main"

# Firmware configurations
firmwares:
  stable:
    version: "stable"
    description: "Stable firmware build"
    build_options:
      repository: "zmkfirmware/zmk"
      branch: "main"

# Keymap configuration
keymap:
  includes:
    - "#include <behaviors.dtsi>"
    - "#include <dt-bindings/zmk/keys.h>"
  formatting:
    default_key_width: 8
    key_gap: "  "
    rows: [...]
  kconfig_options: {...}
  system_behaviors: [...]
```

### Installation Source Types

```python
class InstallationSource(BaseModel):
    type: Literal["file", "url", "git", "registry"]
    path: str
    version: Optional[str] = None
    branch: Optional[str] = None      # For git sources
    tag: Optional[str] = None         # For git sources
    checksum: Optional[str] = None    # For integrity verification

class InstalledKeyboard(BaseModel):
    name: str
    source: InstallationSource
    installed_at: datetime
    version: Optional[str] = None
    is_builtin: bool = False
    config_path: Path
```

## CLI Command Reference

### Extended `glovebox config` Commands

```bash
# Existing commands (enhanced)
glovebox config list [--installed|--available|--all] [--format json|text]
glovebox config show-keyboard <name> [--format json|text]
glovebox config firmwares <keyboard> [--format json|text]
glovebox config firmware <keyboard> <firmware> [--format json|text]

# New installation commands
glovebox config install <source> [--name <name>] [--force] [--validate]
glovebox config remove <name> [--force]
glovebox config validate <file> [--strict]

# New management commands
glovebox config template [<type>] [--output <file>] [--from <keyboard>]
glovebox config backup [--restore <id>] [--list]
glovebox config update [<name>|--all] [--check] [--dry-run]

# Future registry commands
glovebox config search <query> [--limit <n>]
glovebox config publish <file> [--registry <url>]
glovebox config info <name> [--registry]
```

### Command Examples

#### Installation

```bash
# Install from GitHub raw URL
glovebox config install https://raw.githubusercontent.com/splitkb/keyboards/main/corne.yaml

# Install local file with custom name
glovebox config install ./my_board.yaml --name experimental_board

# Install and validate
glovebox config install ./keyboard.yaml --validate

# Force reinstall over existing
glovebox config install ./keyboard.yaml --name existing_board --force
```

#### Validation

```bash
# Validate configuration file
glovebox config validate ./my_keyboard.yaml

# Strict validation (all optional fields required)
glovebox config validate ./my_keyboard.yaml --strict

# Validate installed configuration
glovebox config validate --installed corne-v3
```

#### Management

```bash
# List all configurations with installation status
glovebox config list --all --format json

# Show installation details
glovebox config show-keyboard corne-v3

# Remove installed configuration
glovebox config remove corne-v3

# Update configuration from source
glovebox config update corne-v3
```

## Integration with Existing Features

### Profile System Integration

The keyboard configuration management system integrates seamlessly with the existing profile system:

```bash
# Use installed keyboard in profile
glovebox layout compile input.json output/ --profile corne-v3/stable

# Keyboard-only profile with installed keyboard
glovebox status --profile corne-v3

# Flash with installed keyboard profile
glovebox firmware flash firmware.uf2 --profile corne-v3/stable
```

### Configuration Search Integration

Installed keyboards automatically appear in configuration discovery:

```python
# Existing code continues to work
profile = create_keyboard_profile("corne-v3", "stable")
keyboards = get_available_keyboards()  # Includes installed keyboards
```

### User Configuration Integration

Installation preferences integrate with user configuration:

```yaml
# ~/.config/glovebox/config.yaml
keyboard_paths:
  - "/custom/keyboards"
  - "/project/keyboards"

installation:
  auto_validate: true
  backup_before_install: true
  default_install_location: "user"  # user | project | custom
```

## Security Considerations

### Validation and Safety

**Configuration Validation:**
- All installed configurations must pass Pydantic model validation
- Required sections (flash, build) must be present and valid
- Firmware configurations must be complete and consistent
- YAML syntax and structure validation

**Source Verification:**
- Checksum verification for downloaded configurations
- URL source validation and safety checks
- Git repository verification for trusted sources
- User confirmation for external installations

**Isolation and Safety:**
- Installed configurations stored in user directories only
- No system-wide installation capabilities
- Built-in configurations remain immutable
- Backup creation before modifications

### Installation Policies

```yaml
# Security configuration
installation:
  allowed_sources:
    - "file"           # Local files always allowed
    - "url"            # URLs require confirmation
    - "git"            # Git repos require confirmation
  trusted_domains:
    - "github.com"
    - "raw.githubusercontent.com"
  require_checksum: false    # Future: require integrity verification
  backup_before_install: true
```

## Future Enhancements

### Registry and Marketplace

**Community Registry:**
- Centralized keyboard configuration repository
- Version management and dependency tracking
- Community ratings and reviews
- Automated testing and validation

**Publishing Platform:**
- Standardized publishing workflow
- Configuration quality metrics
- Documentation requirements
- License and attribution tracking

### Advanced Features

**Dependency Management:**
- Firmware version compatibility tracking
- Configuration dependencies and conflicts
- Automatic dependency resolution

**Development Tools:**
- Configuration linting and formatting
- Automated testing frameworks
- Configuration diff and comparison tools
- Integration with keyboard design tools

**Ecosystem Integration:**
- QMK configuration converter
- KLE (Keyboard Layout Editor) import
- Via/Vial configuration support
- Hardware vendor integrations

## Implementation Notes

### Backward Compatibility

- All existing configuration discovery continues to work unchanged
- Existing CLI commands maintain their current behavior
- Built-in configurations remain immutable and cached
- User configurations in existing locations continue to work

### Performance Considerations

- Installation metadata cached for fast access
- Configuration validation cached after initial check
- Download operations with progress indication
- Lazy loading of installation metadata

### Testing Strategy

- Unit tests for installation service components
- Integration tests for CLI command functionality
- Validation tests for configuration schemas
- End-to-end tests for installation workflows

This keyboard configuration management system transforms Glovebox from a tool with fixed keyboard support into a platform that can grow with the community's needs while maintaining its architectural integrity and user experience excellence.