# Layout JSON Format Specification

This document provides the complete specification for Glovebox's layout JSON format, including schema definitions, validation rules, field descriptions, and version management features.

## Overview

The layout JSON format is the primary data interchange format for keyboard layouts in Glovebox. It supports:
- **Complete layout definition** with layers, behaviors, and metadata
- **Template processing** with Jinja2 syntax and variable resolution
- **Version management** with master layout tracking and upgrade capabilities
- **Behavior definitions** including hold-taps, combos, macros, and custom behaviors
- **Validation and type safety** through Pydantic models
- **API compatibility** with MoErgo service field names and aliases

## Schema Overview

The layout format follows a structured hierarchy:

```
Layout JSON
├── Metadata (keyboard, version, author, etc.)
├── Variables (template variables for processing)
├── Structure (layer names, config parameters)
├── Behaviors (hold-taps, combos, macros, custom)
├── Layers (key bindings organized by layer)
└── Custom Code (additional device tree and behaviors)
```

## Complete Schema Definition

### Root Level Fields

```json
{
  "$schema": "https://glovebox.dev/schema/layout/v1.json",
  
  // Template variables (MUST be first for proper resolution)
  "variables": {
    "type": "object",
    "description": "Template variables for Jinja2 processing"
  },
  
  // Core identification
  "keyboard": {
    "type": "string",
    "description": "Target keyboard identifier",
    "examples": ["glove80", "moonlander", "ergodox_ez"]
  },
  
  "firmwareApiVersion": {
    "type": "string", 
    "default": "1",
    "description": "Firmware API version compatibility"
  },
  
  "locale": {
    "type": "string",
    "default": "en-US", 
    "description": "Locale for key mappings and templates"
  },
  
  "uuid": {
    "type": "string",
    "format": "uuid",
    "description": "Unique identifier for this layout"
  },
  
  "parentUuid": {
    "type": ["string", "null"],
    "format": "uuid",
    "description": "UUID of parent layout (for derivatives)"
  },
  
  "date": {
    "type": ["integer", "string"],
    "description": "Creation/modification date (Unix timestamp or ISO string)"
  },
  
  "creator": {
    "type": "string",
    "description": "Layout creator/author name"
  },
  
  "title": {
    "type": "string",
    "description": "Human-readable layout title"
  },
  
  "notes": {
    "type": "string", 
    "description": "Layout description and notes"
  },
  
  "tags": {
    "type": "array",
    "items": {"type": "string"},
    "description": "Categorization tags"
  },
  
  // Version management (added for keymap master feature)
  "version": {
    "type": ["string", "null"],
    "description": "Layout version identifier"
  },
  
  "baseVersion": {
    "type": ["string", "null"], 
    "description": "Base master version this layout derives from"
  },
  
  "baseLayout": {
    "type": ["string", "null"],
    "description": "Base master layout identifier"
  },
  
  "lastFirmwareBuild": {
    "type": ["object", "null"],
    "description": "Metadata about last firmware build"
  },
  
  // Layout structure
  "layerNames": {
    "type": "array",
    "items": {"type": "string"},
    "description": "Ordered list of layer names"
  },
  
  "configParameters": {
    "type": "array", 
    "items": {"$ref": "#/definitions/ConfigParameter"},
    "description": "Layout configuration parameters"
  },
  
  // Behavior definitions
  "holdTaps": {
    "type": "array",
    "items": {"$ref": "#/definitions/HoldTapBehavior"},
    "description": "Hold-tap behavior definitions"
  },
  
  "combos": {
    "type": "array",
    "items": {"$ref": "#/definitions/ComboBehavior"}, 
    "description": "Combo behavior definitions"
  },
  
  "macros": {
    "type": "array",
    "items": {"$ref": "#/definitions/MacroBehavior"},
    "description": "Macro behavior definitions"
  },
  
  "inputListeners": {
    "type": ["array", "null"],
    "items": {"$ref": "#/definitions/InputListener"},
    "description": "Input listener definitions"
  },
  
  // Key bindings
  "layers": {
    "type": "array",
    "items": {
      "type": "array", 
      "items": {"$ref": "#/definitions/LayoutBinding"}
    },
    "description": "Layer bindings (array of arrays)"
  },
  
  // Custom code
  "custom_defined_behaviors": {
    "type": "string",
    "description": "Custom behavior definitions in ZMK syntax"
  },
  
  "custom_devicetree": {
    "type": "string", 
    "description": "Custom device tree code"
  }
}
```

## Field Definitions

### ConfigParameter

Configuration parameters for layout customization.

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "description": "Parameter name"
    },
    "value": {
      "type": ["string", "integer", "boolean"],
      "description": "Parameter value"
    },
    "type": {
      "type": "string", 
      "enum": ["string", "int", "bool"],
      "description": "Parameter type"
    }
  },
  "required": ["name", "value"],
  "additionalProperties": false
}
```

### LayoutBinding

Individual key binding definition with support for nested parameters.

```json
{
  "type": "object",
  "properties": {
    "value": {
      "type": "string",
      "description": "Behavior code (e.g., '&kp', '&mt', '&trans')",
      "pattern": "^&[a-zA-Z0-9_]+$"
    },
    "params": {
      "type": "array",
      "items": {"$ref": "#/definitions/LayoutParam"},
      "description": "Behavior parameters (may be nested)"
    }
  },
  "required": ["value"],
  "additionalProperties": false
}
```

**Examples:**
```json
// Simple key press
{"value": "&kp", "params": [{"value": "Q"}]}

// Mod-tap behavior
{"value": "&mt", "params": [{"value": "LCTRL"}, {"value": "A"}]}

// Nested parameter (modifier with key)
{"value": "&kp", "params": [{"value": "LC", "params": [{"value": "X"}]}]}

// Transparent key
{"value": "&trans"}
```

### LayoutParam

Parameter definition supporting nested parameters for complex behaviors.

```json
{
  "type": "object", 
  "properties": {
    "value": {
      "type": ["string", "integer"],
      "description": "Parameter value"
    },
    "params": {
      "type": "array",
      "items": {"$ref": "#/definitions/LayoutParam"},
      "description": "Nested parameters for complex behaviors"
    }
  },
  "required": ["value"],
  "additionalProperties": false
}
```

### HoldTapBehavior

Hold-tap behavior configuration for modifier keys.

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "description": "Behavior name (must be unique)"
    },
    "tap": {
      "type": "string", 
      "description": "Tap behavior (e.g., 'Q', 'SPACE')"
    },
    "hold": {
      "type": "string",
      "description": "Hold behavior (e.g., 'LCTRL', 'LALT')"
    },
    "tapping-term-ms": {
      "type": "integer",
      "minimum": 1,
      "maximum": 5000,
      "default": 200,
      "description": "Tapping term in milliseconds"
    },
    "quick-tap-ms": {
      "type": "integer", 
      "minimum": 0,
      "maximum": 1000,
      "default": 0,
      "description": "Quick tap threshold in milliseconds"
    },
    "require-prior-idle-ms": {
      "type": "integer",
      "minimum": 0, 
      "maximum": 1000,
      "default": 0,
      "description": "Required idle time before activation"
    },
    "flavor": {
      "type": "string",
      "enum": ["tap-preferred", "hold-preferred", "balanced"],
      "default": "tap-preferred",
      "description": "Hold-tap behavior flavor"
    },
    "hold-trigger-key-positions": {
      "type": "array",
      "items": {
        "type": "integer",
        "minimum": 0
      },
      "description": "Key positions that trigger hold behavior"
    },
    "hold-trigger-on-release": {
      "type": "boolean",
      "default": false,
      "description": "Trigger hold behavior on key release"
    }
  },
  "required": ["name", "tap", "hold"],
  "additionalProperties": false
}
```

**Example:**
```json
{
  "name": "hrm_ctrl",
  "tap": "A", 
  "hold": "LCTRL",
  "tapping-term-ms": 200,
  "flavor": "tap-preferred",
  "hold-trigger-key-positions": [5, 6, 7, 8, 9, 10]
}
```

### ComboBehavior

Combo behavior for simultaneous key presses.

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "description": "Combo name (must be unique)"
    },
    "key-positions": {
      "type": "array",
      "items": {
        "type": "integer", 
        "minimum": 0
      },
      "minItems": 2,
      "description": "Key positions that form the combo"
    },
    "bindings": {
      "type": "array",
      "items": {"type": "string"},
      "minItems": 1,
      "description": "Behaviors to execute when combo is triggered"
    },
    "timeout-ms": {
      "type": "integer",
      "minimum": 1,
      "maximum": 1000, 
      "default": 50,
      "description": "Combo timeout in milliseconds"
    },
    "require-prior-idle-ms": {
      "type": "integer",
      "minimum": 0,
      "maximum": 1000,
      "default": 0,
      "description": "Required idle time before combo"
    },
    "layers": {
      "type": "array",
      "items": {
        "type": "integer",
        "minimum": 0
      },
      "description": "Layers where combo is active (empty = all layers)"
    }
  },
  "required": ["name", "key-positions", "bindings"],
  "additionalProperties": false
}
```

**Example:**
```json
{
  "name": "escape_combo",
  "key-positions": [0, 1],
  "bindings": ["&kp ESC"],
  "timeout-ms": 50,
  "layers": [0, 1, 2]
}
```

### MacroBehavior

Macro behavior for sequences of actions.

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "description": "Macro name (must be unique)"
    },
    "bindings": {
      "type": "array",
      "items": {"type": "string"},
      "minItems": 1,
      "description": "Sequence of behaviors to execute"
    },
    "wait-ms": {
      "type": "integer",
      "minimum": 0,
      "maximum": 5000,
      "default": 0,
      "description": "Wait time between bindings"
    },
    "tap-ms": {
      "type": "integer", 
      "minimum": 0,
      "maximum": 1000,
      "default": 0,
      "description": "Key tap duration"
    }
  },
  "required": ["name", "bindings"],
  "additionalProperties": false
}
```

**Example:**
```json
{
  "name": "email_macro",
  "bindings": [
    "&kp H", "&kp E", "&kp L", "&kp L", "&kp O",
    "&kp AT", "&kp E", "&kp X", "&kp A", "&kp M", "&kp P", "&kp L", "&kp E",
    "&kp DOT", "&kp C", "&kp O", "&kp M"
  ],
  "wait-ms": 10
}
```

### InputListener

Input listener for advanced input processing.

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "description": "Listener name"
    },
    "device": {
      "type": "string", 
      "description": "Input device reference"
    },
    "processors": {
      "type": "array",
      "items": {"$ref": "#/definitions/InputProcessor"},
      "description": "Input processors"
    }
  },
  "required": ["name", "device"],
  "additionalProperties": false
}
```

### InputProcessor

Input processor for custom input handling.

```json
{
  "type": "object",
  "properties": {
    "type": {
      "type": "string",
      "description": "Processor type"
    },
    "config": {
      "type": "object",
      "description": "Processor configuration"
    }
  },
  "required": ["type"],
  "additionalProperties": true
}
```

## Template Processing

### Variables Section

The `variables` section enables template processing with Jinja2 syntax:

```json
{
  "variables": {
    "mod_key": "LCTRL",
    "layer_count": 5,
    "enable_rgb": true,
    "custom_keys": ["F13", "F14", "F15"]
  },
  
  "holdTaps": [
    {
      "name": "hrm_mod",
      "tap": "A",
      "hold": "{{ mod_key }}",
      "tapping-term-ms": 200
    }
  ],
  
  "layers": [
    // Template usage in layer bindings
    [
      {"value": "&kp", "params": [{"value": "{{ mod_key }}"}]},
      {"value": "&to", "params": [{"value": "{{ layer_count - 1 }}"}]}
    ]
  ]
}
```

### Template Syntax Support

**Variable substitution:**
```json
"title": "{{ username }}'s Custom Layout"
```

**Conditional rendering:**
```json
{%- if enable_rgb %}
"custom_devicetree": "#define ZMK_RGB_UNDERGLOW 1"
{%- endif %}
```

**Loops for repeated content:**
```json
"macros": [
  {%- for i in range(1, 4) %}
  {
    "name": "macro_{{ i }}",
    "bindings": ["&kp F{{ i + 12 }}"]
  }{{ "," if not loop.last }}
  {%- endfor %}
]
```

**Complex expressions:**
```json
"layers": [
  {%- for layer_idx in range(layer_count) %}
  [
    {%- for key_idx in range(80) %}
    {
      "value": "&trans"
    }{{ "," if not loop.last }}
    {%- endfor %}
  ]{{ "," if not loop.last }}
  {%- endfor %}
]
```

### Template Processing API

```python
from glovebox.layout.models import LayoutData

# Load layout with template processing
layout = LayoutData.load_with_templates(json_data)

# Manual template processing
layout = LayoutData.model_validate(json_data)
resolved_layout = layout.process_templates()

# Export without variables section (resolved templates)
flattened_data = layout.to_flattened_dict()
```

## Version Management

### Master Layout Tracking

Layouts can track their relationship to master versions:

```json
{
  "version": "custom-v1.2",
  "baseVersion": "v42",
  "baseLayout": "master",
  "lastFirmwareBuild": {
    "timestamp": 1672531200,
    "profile": "glove80/v25.05",
    "buildId": "build-abc123",
    "firmwareHash": "sha256:def456..."
  }
}
```

### Version Upgrade Process

The version management system enables safe upgrades while preserving customizations:

1. **Import Master**: Store versioned master layouts
2. **Track Derivation**: Link custom layouts to master versions  
3. **Intelligent Merge**: Upgrade with customization preservation
4. **Validation**: Verify compatibility and resolve conflicts

```python
from glovebox.layout.version_manager import create_version_manager

version_manager = create_version_manager(user_config)

# Import master layout
version_manager.import_master(
    layout_file=Path("master-v42.json"),
    version="v42", 
    keyboard="glove80"
)

# Upgrade custom layout
version_manager.upgrade_layout(
    layout_file=Path("my-custom.json"),
    to_master="v42",
    from_master="v41"  # Auto-detect if None
)
```

## Validation Rules

### Required Fields

**Minimum required fields for valid layout:**
```json
{
  "keyboard": "glove80",
  "layerNames": ["Base"],
  "layers": [
    [
      // Must have bindings for all key positions
      {"value": "&kp", "params": [{"value": "Q"}]},
      // ... more bindings
    ]
  ]
}
```

### Layer Validation

```python
# Layer count must match layer names
len(layout.layers) == len(layout.layer_names)

# Each layer must have correct number of bindings for keyboard
for i, layer in enumerate(layout.layers):
    assert len(layer) == keyboard.key_count, f"Layer {i} has wrong key count"

# All bindings must have valid behavior values
for layer_idx, layer in enumerate(layout.layers):
    for key_idx, binding in enumerate(layer):
        assert binding.value.startswith("&"), f"Invalid behavior at [{layer_idx}][{key_idx}]"
```

### Behavior Validation

```python
# Behavior names must be unique
behavior_names = [ht.name for ht in layout.hold_taps]
assert len(behavior_names) == len(set(behavior_names)), "Duplicate hold-tap names"

# Key positions must be valid for keyboard  
for combo in layout.combos:
    for pos in combo.key_positions:
        assert 0 <= pos < keyboard.key_count, f"Invalid key position: {pos}"

# References must exist
for layer in layout.layers:
    for binding in layer:
        if binding.value in ["&hrm_ctrl", "&my_macro"]:
            # Verify behavior is defined
            assert any(ht.name == binding.value[1:] for ht in layout.hold_taps + layout.macros)
```

### Template Validation

```python
# Variables section must be valid JSON object
assert isinstance(layout.variables, dict)

# Template syntax must be valid Jinja2
template_service.validate_template(json.dumps(layout.model_dump()))

# Resolved templates must produce valid layout
resolved_layout = layout.process_templates()
validate_layout_structure(resolved_layout)
```

## Field Aliases and Compatibility

### MoErgo API Compatibility

The format maintains compatibility with MoErgo service APIs through field aliases:

```json
{
  // Pydantic field name -> JSON alias
  "firmware_api_version": "firmwareApiVersion",
  "layer_names": "layerNames", 
  "config_parameters": "configParameters",
  "hold_taps": "holdTaps",
  "input_listeners": "inputListeners",
  "parent_uuid": "parentUuid",
  "base_version": "baseVersion",
  "base_layout": "baseLayout",
  "last_firmware_build": "lastFirmwareBuild"
}
```

### Serialization Behavior

```python
# Proper serialization with aliases
data = layout.model_dump(by_alias=True, mode="json")

# Convenience method
data = layout.to_dict()

# Field ordering (variables first for template resolution)
field_order = [
    "variables", "keyboard", "firmware_api_version",
    "layers", "custom_defined_behaviors"
]
```

## Usage Examples

### Complete Layout Example

```json
{
  "variables": {
    "mod_key": "LCTRL",
    "enable_combos": true
  },
  
  "keyboard": "glove80",
  "firmwareApiVersion": "1",
  "locale": "en-US",
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "date": 1672531200,
  "creator": "John Doe",
  "title": "My Custom Glove80 Layout",
  "notes": "Optimized for programming with Vim bindings",
  "tags": ["programming", "vim", "minimal"],
  
  "version": "v1.0",
  "baseVersion": "v42",
  "baseLayout": "master",
  
  "layerNames": ["Base", "Nav", "Sym"],
  
  "configParameters": [
    {
      "name": "sleep_timeout",
      "value": 30000,
      "type": "int"
    }
  ],
  
  "holdTaps": [
    {
      "name": "hrm_ctrl",
      "tap": "A",
      "hold": "{{ mod_key }}",
      "tapping-term-ms": 200,
      "flavor": "tap-preferred"
    }
  ],
  
  "combos": [
    {%- if enable_combos %}
    {
      "name": "esc_combo",
      "key-positions": [0, 1], 
      "bindings": ["&kp ESC"],
      "timeout-ms": 50
    }
    {%- endif %}
  ],
  
  "macros": [
    {
      "name": "email",
      "bindings": [
        "&kp J", "&kp O", "&kp H", "&kp N",
        "&kp AT", "&kp E", "&kp X", "&kp A", "&kp M", "&kp P", "&kp L", "&kp E",
        "&kp DOT", "&kp C", "&kp O", "&kp M"
      ]
    }
  ],
  
  "layers": [
    // Base layer (80 keys for Glove80)
    [
      {"value": "&kp", "params": [{"value": "Q"}]},
      {"value": "&kp", "params": [{"value": "W"}]},
      {"value": "&hrm_ctrl"},
      {"value": "&lt", "params": [{"value": "1"}, {"value": "SPACE"}]},
      // ... remaining 76 bindings
    ],
    
    // Navigation layer
    [
      {"value": "&kp", "params": [{"value": "HOME"}]},
      {"value": "&kp", "params": [{"value": "UP"}]},
      {"value": "&kp", "params": [{"value": "END"}]},
      {"value": "&trans"},
      // ... remaining bindings
    ],
    
    // Symbol layer  
    [
      {"value": "&kp", "params": [{"value": "EXCL"}]},
      {"value": "&kp", "params": [{"value": "AT"}]},
      {"value": "&kp", "params": [{"value": "HASH"}]},
      {"value": "&trans"},
      // ... remaining bindings
    ]
  ],
  
  "custom_defined_behaviors": "/delete-node/ &caps_word;",
  "custom_devicetree": ""
}
```

### Parsing and Creating Layouts

```python
from glovebox.layout.models import LayoutData

# Load from JSON file
with open("layout.json") as f:
    data = json.load(f)

# Create layout with template processing
layout = LayoutData.load_with_templates(data)

# Access structured data
print(f"Layout: {layout.title}")
print(f"Layers: {len(layout.layers)}")
print(f"Hold-taps: {len(layout.hold_taps)}")

# Modify layout
layout.title = "Updated Layout"
layout.notes = "Added new customizations"

# Export with resolved templates
output_data = layout.to_flattened_dict()

# Save to file
with open("updated_layout.json", "w") as f:
    json.dump(output_data, f, indent=2)
```

This comprehensive format specification enables rich keyboard layout definitions with full template support, version management, and compatibility with external services while maintaining type safety and validation.