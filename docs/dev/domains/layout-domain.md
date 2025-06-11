# Layout Domain Documentation

The Layout domain handles keyboard layout processing, transforming JSON layouts from keyboard editors into ZMK Device Tree Source Interface (DTSI) files.

## Overview

The Layout domain is responsible for:
- **JSON→DTSI Conversion**: Transform human-readable layouts into ZMK firmware code
- **Component Management**: Extract and merge layout layers for modular editing
- **Behavior Processing**: Handle macros, hold-taps, combos, and custom behaviors
- **Layout Visualization**: Display keyboard layouts in terminal
- **Validation**: Ensure layout integrity and ZMK compatibility

## Domain Structure

```
glovebox/layout/
├── __init__.py              # Domain exports and factory functions
├── models.py               # Layout data models
├── service.py              # Main layout service
├── component_service.py    # Layer extraction/merging
├── display_service.py      # Layout visualization  
├── zmk_generator.py        # ZMK file content generation
├── formatting.py           # Layout formatting utilities
├── utils.py               # Layout utility functions
└── behavior/              # Behavior processing subdomain
    ├── __init__.py
    ├── models.py          # Behavior data models
    ├── service.py         # Behavior registry and management
    ├── formatter.py       # Behavior code formatting
    └── analysis.py        # Behavior analysis utilities
```

## Core Models

### LayoutData
The main model representing a complete keyboard layout:

```python
from glovebox.layout.models import LayoutData

class LayoutData(BaseModel):
    """Complete keyboard layout with all components."""
    metadata: LayoutMetadata
    layers: list[LayoutLayer]
    behaviors: BehaviorList
    config: ConfigParamList
    includes: list[str]
    custom_dtsi: Optional[str] = None
    custom_behaviors: Optional[str] = None
```

### LayoutLayer
Represents a single keyboard layer:

```python
class LayoutLayer(BaseModel):
    """Single keyboard layer with bindings."""
    name: str
    bindings: list[LayoutBinding]
    index: LayerIndex
```

### LayoutBinding
Represents a key binding within a layer:

```python
class LayoutBinding(BaseModel):
    """Key binding for a specific position."""
    key: int                    # Physical key position
    binding: str               # ZMK binding code
    layer: LayerIndex          # Layer index
    # Additional metadata fields...
```

### Behavior Models
The domain includes specialized models for ZMK behaviors:

```python
class MacroBehavior(BaseModel):
    """Macro behavior definition."""
    name: str
    sequence: list[str]
    wait_time: Optional[int] = None

class HoldTapBehavior(BaseModel):
    """Hold-tap behavior definition."""
    name: str
    tap_action: str
    hold_action: str
    tapping_term: Optional[int] = None

class ComboBehavior(BaseModel):
    """Combo behavior definition."""
    name: str
    keys: list[int]
    action: str
    timeout: Optional[int] = None
```

## Services

### LayoutService
The main service providing layout operations:

```python
from glovebox.layout import create_layout_service

# Create service
layout_service = create_layout_service()

# Generate ZMK files from layout
result = layout_service.generate(
    profile=keyboard_profile,
    layout_data=layout_data,
    output_prefix="output/my_layout"
)

# Validate layout
validation_result = layout_service.validate(layout_data)

# Get layout info
info = layout_service.get_layout_info(layout_data)
```

**Key Methods**:
- `generate()`: Convert layout to ZMK files
- `validate()`: Check layout integrity
- `get_layout_info()`: Extract layout metadata

### LayoutComponentService
Service for modular layout management:

```python
from glovebox.layout import create_layout_component_service

component_service = create_layout_component_service()

# Extract components (decompose)
decompose_result = component_service.decompose_components(
    layout_data=layout_data,
    output_dir=Path("components/")
)

# Merge components (compose)
layout_data = component_service.compose_components(
    metadata_file=Path("components/metadata.json"),
    layers_dir=Path("components/layers/")
)
```

**Component Structure**:
```
components/
├── metadata.json       # Layout metadata and configuration
├── device.dtsi         # Custom device tree (if present)
├── keymap.dtsi         # Custom behaviors (if present)
└── layers/
    ├── DEFAULT.json    # Individual layer files
    ├── LOWER.json
    ├── RAISE.json
    └── ...
```

### LayoutDisplayService
Service for layout visualization:

```python
from glovebox.layout import create_layout_display_service

display_service = create_layout_display_service()

# Show layout in terminal
display_service.show_layout(
    layout_data=layout_data,
    layer_name="DEFAULT",
    key_width=10
)

# Format layout for display
formatted = display_service.format_layout_for_display(
    layout_data=layout_data,
    options=display_options
)
```

## ZMK File Generation

### ZmkFileContentGenerator
Generates ZMK-compatible file content:

```python
from glovebox.layout.zmk_generator import create_zmk_file_generator

generator = create_zmk_file_generator()

# Generate keymap content
keymap_content = generator.generate_keymap_content(
    profile=profile,
    layout_data=layout_data
)

# Generate config content  
config_content = generator.generate_config_content(
    profile=profile,
    layout_data=layout_data
)
```

**Generated Files**:
- **`.keymap`**: ZMK Device Tree Source with layers and behaviors
- **`.conf`**: ZMK Kconfig options for firmware features

### Template Context Building
The generator builds rich template contexts:

```python
from glovebox.layout.utils import build_template_context

context = build_template_context(
    profile=profile,
    layout_data=layout_data,
    options=generation_options
)

# Context includes:
# - resolved_includes: ZMK include statements
# - keymap_node: Device tree keymap node
# - behaviors: Formatted behavior definitions
# - layers: Formatted layer definitions
# - kconfig_options: Configuration options
```

## Behavior Processing

### Behavior Types
The domain handles several ZMK behavior types:

1. **Macros**: Sequences of key presses and releases
2. **Hold-Taps**: Dual-function keys (tap vs hold)
3. **Combos**: Multi-key combinations that trigger actions
4. **Input Listeners**: Mouse and input processing
5. **Custom Behaviors**: User-defined DTSI behaviors

### BehaviorFormatter
Formats behaviors for DTSI output:

```python
from glovebox.layout.behavior.formatter import BehaviorFormatterImpl

formatter = BehaviorFormatterImpl()

# Format macro behavior
macro_dtsi = formatter.format_macro(macro_behavior)

# Format hold-tap behavior
hold_tap_dtsi = formatter.format_hold_tap(hold_tap_behavior)

# Format combo behavior
combo_dtsi = formatter.format_combo(combo_behavior)
```

### Behavior Analysis
Extracts behavior information from layouts:

```python
from glovebox.layout.behavior.analysis import (
    extract_behavior_codes_from_layout,
    get_required_includes_for_layout
)

# Extract all behavior codes used
behavior_codes = extract_behavior_codes_from_layout(layout_data)

# Get required include statements
includes = get_required_includes_for_layout(layout_data, profile)
```

## Layout Utilities

### Template Context Functions
Utility functions for template generation:

```python
from glovebox.layout.utils import (
    generate_keymap_file,
    generate_config_file,
    generate_kconfig_conf
)

# Generate complete keymap file
keymap_content = generate_keymap_file(
    profile=profile,
    layout_data=layout_data
)

# Generate config file
config_content = generate_config_file(
    profile=profile, 
    layout_data=layout_data
)

# Generate kconfig configuration
kconfig_content = generate_kconfig_conf(
    options=kconfig_options
)
```

### Validation Functions
Layout validation utilities:

```python
from glovebox.layout.utils import (
    validate_layout_structure,
    validate_behavior_references,
    validate_layer_consistency
)

# Validate overall structure
is_valid = validate_layout_structure(layout_data)

# Check behavior references
behavior_issues = validate_behavior_references(layout_data)

# Verify layer consistency
layer_issues = validate_layer_consistency(layout_data)
```

## Usage Patterns

### Basic Layout Generation

```python
from glovebox.layout import create_layout_service
from glovebox.layout.models import LayoutData
from glovebox.config import create_keyboard_profile
from pathlib import Path

# Create services
layout_service = create_layout_service()
profile = create_keyboard_profile("glove80", "v25.05")

# Load layout data
with Path("my_layout.json").open() as f:
    layout_data = LayoutData.model_validate_json(f.read())

# Generate ZMK files
result = layout_service.generate(
    profile=profile,
    layout_data=layout_data,
    output_prefix="output/my_layout"
)

print(f"Generated: {result.keymap_path}, {result.conf_path}")
```

### Component-Based Workflow

```python
from glovebox.layout import (
    create_layout_service,
    create_layout_component_service
)

layout_service = create_layout_service()
component_service = create_layout_component_service()

# Decompose layout into components
decompose_result = component_service.decompose_components(
    layout_data=original_layout,
    output_dir=Path("components/")
)

# Edit individual layer files...
# components/layers/DEFAULT.json
# components/layers/LOWER.json

# Compose back into complete layout
modified_layout = component_service.compose_components(
    metadata_file=Path("components/metadata.json"),
    layers_dir=Path("components/layers/")
)

# Generate ZMK files from modified layout
result = layout_service.generate(
    profile=profile,
    layout_data=modified_layout,
    output_prefix="output/modified_layout"
)
```

### Custom Behavior Integration

```python
from glovebox.layout.models import MacroBehavior, HoldTapBehavior

# Define custom behaviors
macro = MacroBehavior(
    name="email_macro",
    sequence=["user", "@", "example.com"],
    wait_time=10
)

hold_tap = HoldTapBehavior(
    name="ctrl_a",
    tap_action="&kp A",
    hold_action="&kp LCTRL",
    tapping_term=200
)

# Add to layout
layout_data.behaviors.macros.append(macro)
layout_data.behaviors.hold_taps.append(hold_tap)

# Generate with custom behaviors
result = layout_service.generate(
    profile=profile,
    layout_data=layout_data,
    output_prefix="output/custom_layout"
)
```

## Testing

### Unit Tests
Test individual components:

```python
def test_layout_data_validation():
    """Test LayoutData model validation."""
    valid_data = {...}
    layout = LayoutData.model_validate(valid_data)
    assert layout.metadata.name == "test_layout"

def test_behavior_formatting():
    """Test behavior DTSI formatting."""
    macro = MacroBehavior(name="test", sequence=["a", "b"])
    formatter = BehaviorFormatterImpl()
    dtsi = formatter.format_macro(macro)
    assert "test" in dtsi
```

### Integration Tests
Test service interactions:

```python
def test_layout_generation_flow():
    """Test complete layout generation."""
    service = create_layout_service()
    profile = create_keyboard_profile("test", "main")
    layout = create_test_layout()
    
    result = service.generate(profile, layout, "test_output")
    
    assert result.success
    assert result.keymap_path.exists()
    assert result.conf_path.exists()
```

### CLI Tests
Test command-line interface:

```python
def test_layout_compile_command():
    """Test layout compile CLI command."""
    result = runner.invoke(app, [
        "layout", "compile", 
        "test_layout.json", "output/test",
        "--profile", "glove80/v25.05"
    ])
    
    assert result.exit_code == 0
    assert "Generated successfully" in result.output
```

## Performance Considerations

### Caching
- **Template caching**: Jinja2 templates cached after first load
- **Behavior registry**: System behaviors cached per profile
- **Validation caching**: Layout validation results cached

### Memory Management
- **Lazy loading**: Large layouts processed in chunks
- **Streaming**: Component processing uses generators
- **Resource cleanup**: Temporary files cleaned automatically

### Optimization
- **Parallel processing**: Multiple layers processed concurrently
- **Incremental updates**: Only changed components regenerated
- **Efficient parsing**: JSON parsing optimized for large layouts

## Error Handling

### Layout Validation Errors
```python
from glovebox.core.errors import LayoutValidationError

try:
    layout_data = LayoutData.model_validate(json_data)
except ValidationError as e:
    raise LayoutValidationError(
        "Invalid layout structure",
        validation_errors=e.errors()
    ) from e
```

### Behavior Processing Errors
```python
from glovebox.core.errors import BehaviorProcessingError

try:
    formatted_behavior = formatter.format_macro(macro)
except Exception as e:
    raise BehaviorProcessingError(
        f"Failed to format macro '{macro.name}'",
        behavior_name=macro.name,
        behavior_type="macro"
    ) from e
```

## Future Enhancements

### Planned Features
- **Layout validation**: Enhanced validation with ZMK compatibility checks
- **Behavior templates**: Pre-defined behavior templates for common patterns
- **Layout optimization**: Automatic layout optimization suggestions
- **Visual editor**: Web-based layout editor integration

### Extension Points
- **Custom formatters**: Support for alternative output formats
- **Behavior plugins**: Plugin system for custom behavior types
- **Layout transformers**: Pipeline for layout transformations
- **Export formats**: Support for multiple keyboard firmware formats