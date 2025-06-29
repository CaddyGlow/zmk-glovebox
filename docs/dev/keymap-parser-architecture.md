# Keymap Parser Architecture

This document describes the architecture and design patterns of the ZMK keymap parser system in Glovebox, focusing on the processor-based design and type safety improvements.

## Overview

The keymap parser is responsible for reverse-engineering ZMK keymap files (`.keymap`) back into Glovebox JSON layout format. The system uses a modular, processor-based architecture that supports multiple parsing strategies while maintaining strong type safety.

## Architecture Components

### Core Parser (`keymap_parser.py`)

The main `ZmkKeymapParser` class serves as the orchestrator, delegating actual parsing work to specialized processors:

```python
from glovebox.layout.parsers.keymap_parser import create_zmk_keymap_parser, ParsingMode

parser = create_zmk_keymap_parser()
result = parser.parse_keymap(
    keymap_file=Path("my_keymap.keymap"),
    mode=ParsingMode.TEMPLATE_AWARE,
    keyboard_profile="glove80"
)
```

**Key Features:**
- **Processor delegation**: Uses strategy pattern with specialized processors
- **Protocol-based typing**: Strong type safety with runtime-checkable protocols
- **Factory function pattern**: Follows CLAUDE.md conventions
- **Error handling**: Debug-aware exception logging

### Parsing Modes

#### `ParsingMode.FULL`
- Parses complete standalone keymap files
- Uses AST parsing for comprehensive extraction
- Ideal for reverse-engineering complete keymaps

#### `ParsingMode.TEMPLATE_AWARE`
- Uses keyboard profile templates to extract only user-defined data
- Avoids parsing template-generated content
- More efficient for keymaps generated from Glovebox templates

### Processor Architecture (`keymap_processors.py`)

The processor system implements the Strategy pattern for different parsing approaches:

```python
# Processors are automatically created and injected
processors = {
    ParsingMode.FULL: create_full_keymap_processor(),
    ParsingMode.TEMPLATE_AWARE: create_template_aware_processor(),
}
```

#### `FullKeymapProcessor`
- **Purpose**: Complete keymap file parsing using AST
- **Use case**: Standalone keymaps without template awareness
- **Approach**: Parse entire file into AST, extract all components

#### `TemplateAwareProcessor`
- **Purpose**: Template-aware parsing using keyboard profiles
- **Use case**: Keymaps generated from Glovebox templates
- **Approach**: Use profile templates + section extraction for user data only

### Section Extraction (`section_extractor.py`)

Handles extraction of specific sections from keymap content using configurable delimiters:

```python
# Comment-based section extraction
configs = [
    ExtractionConfig(
        tpl_ctx_name="user_behaviors_dtsi",
        type="behavior",
        layer_data_name="behaviors", 
        delimiter=[
            r"/\*\s*Automatically\s+generated\s+behavior\s+definitions\s*\*/",
            r"/\*\s*(?:Automatically\s+generated\s+combos|$)"
        ]
    )
]

sections = extractor.extract_sections(content, configs)
processed = extractor.process_extracted_sections(sections, context)
```

**Capabilities:**
- **Regex-based extraction**: Uses comment delimiters to find sections
- **AST processing**: Parses extracted sections as device tree AST
- **Type-specific handling**: Different processing for behaviors, macros, combos, layers

### Data Models (`parsing_models.py`)

Type-safe data models for parsing operations:

```python
@dataclass
class ExtractionConfig(GloveboxBaseModel):
    tpl_ctx_name: str  # Template context name
    type: Literal["dtsi", "behavior", "macro", "combo", "keymap", "input_listener"]
    layer_data_name: str  # Target field name in layout
    delimiter: list[str]  # Regex patterns for section boundaries

@dataclass  
class ParsingContext(GloveboxBaseModel):
    keymap_content: str
    template_vars: list[str] = []
    keyboard_profile_name: str | None = None
    extraction_config: list[ExtractionConfig] = []
    errors: list[str] = []
    warnings: list[str] = []
```

### Model Conversion (`keymap_converters.py`)

Factory utilities for creating layout model instances:

```python
factory = ModelFactory()
comment = factory.create_comment(comment_dict)
include = factory.create_include(include_dict)
directive = factory.create_directive(directive_dict)
```

## Type Safety Architecture

### Protocol-Based Design

The system uses Protocol classes for strong typing with dependency injection:

```python
class ProcessorProtocol(Protocol):
    def process(self, context: ParsingContext) -> LayoutData | None: ...

class SectionExtractorProtocol(Protocol):
    def extract_sections(self, content: str, configs: list) -> dict: ...
    def process_extracted_sections(self, sections: dict, context) -> dict: ...

class ModelConverterProtocol(Protocol):
    def convert_behaviors(self, behaviors_dict: dict) -> dict: ...
```

**Benefits:**
- **Runtime type checking**: Protocols are runtime-checkable
- **Dependency injection**: Clean interfaces for testing and modularity
- **IDE support**: Full autocomplete and type checking
- **No `Any` types**: Eliminated all `Any` annotations for better safety

### Factory Function Pattern

All components follow CLAUDE.md factory function conventions:

```python
# Clean factory functions with dependency injection
def create_zmk_keymap_parser(
    template_adapter: TemplateAdapterProtocol | None = None,
    processors: dict[ParsingMode, ProcessorProtocol] | None = None,
) -> ZmkKeymapParser:
    return ZmkKeymapParser(template_adapter, processors)

def create_full_keymap_processor(
    section_extractor: SectionExtractorProtocol | None = None,
    template_adapter: TemplateAdapterProtocol | None = None,
) -> FullKeymapProcessor:
    return FullKeymapProcessor(section_extractor, template_adapter)
```

## Configuration System

### Profile-Based Extraction

Keyboard profiles can define custom extraction configurations:

```yaml
# keyboards/glove80.yaml
keymap_extraction:
  sections:
    - tpl_ctx_name: "custom_behaviors"
      type: "behavior"
      layer_data_name: "behaviors"
      delimiter:
        - "/\\*\\s*Custom\\s+Behaviors\\s*\\*/"
        - "/\\*\\s*Generated\\s+Keymap\\s*\\*/"
```

### Default Extraction Patterns

The system provides sensible defaults for common ZMK keymap structures:

```python
def get_default_extraction_config() -> list[ExtractionConfig]:
    return [
        # Custom device tree code
        ExtractionConfig(
            tpl_ctx_name="custom_devicetree",
            type="dtsi",
            layer_data_name="custom_devicetree",
            delimiter=[
                r"/\*\s*Custom\s+Device-tree\s*\*/",
                r"/\*\s*Input\s+Listeners\s*\*/",
            ]
        ),
        # User-defined behaviors
        ExtractionConfig(
            tpl_ctx_name="user_behaviors_dtsi", 
            type="behavior",
            layer_data_name="behaviors",
            delimiter=[
                r"/\*\s*Automatically\s+generated\s+behavior\s+definitions\s*\*/",
                r"/\*\s*(?:Automatically\s+generated\s+combos|$)"
            ]
        ),
        # ... more default configs
    ]
```

## Usage Patterns

### Basic Parsing

```python
from glovebox.layout.parsers.keymap_parser import create_zmk_keymap_parser
from pathlib import Path

parser = create_zmk_keymap_parser()
result = parser.parse_keymap(
    keymap_file=Path("glove80.keymap"),
    mode=ParsingMode.TEMPLATE_AWARE,
    keyboard_profile="glove80"
)

if result.success:
    layout_data = result.layout_data
    print(f"Parsed {len(layout_data.layers)} layers")
else:
    print(f"Errors: {result.errors}")
```

### Custom Processors

```python
# Create parser with custom processors
custom_processors = {
    ParsingMode.FULL: create_full_keymap_processor(
        section_extractor=my_custom_extractor
    ),
    ParsingMode.TEMPLATE_AWARE: create_template_aware_processor(
        template_adapter=my_custom_adapter
    )
}

parser = create_zmk_keymap_parser(processors=custom_processors)
```

### Testing with Mocks

```python
from unittest.mock import Mock

# Mock protocols for testing
mock_processor = Mock(spec=ProcessorProtocol)
mock_processor.process.return_value = LayoutData(keyboard="test")

test_processors = {ParsingMode.FULL: mock_processor}
parser = create_zmk_keymap_parser(processors=test_processors)
```

## Performance Considerations

### Template-Aware Optimization

- **Selective parsing**: Only parses user-defined sections, not template content
- **Section extraction**: Uses regex to identify relevant sections before AST parsing
- **Profile caching**: Template metadata cached for repeated operations

### AST Processing

- **Lazy evaluation**: AST nodes created only when accessed
- **Focused extraction**: Extracts only needed components from AST
- **Error recovery**: Continues processing even if some sections fail

## Error Handling

### Debug-Aware Logging

Following CLAUDE.md conventions, all exception handling includes debug-aware stack traces:

```python
try:
    # Processing logic
    pass
except Exception as e:
    exc_info = self.logger.isEnabledFor(logging.DEBUG)
    self.logger.error("Processing failed: %s", e, exc_info=exc_info)
    context.errors.append(f"Processing failed: {e}")
```

### Graceful Degradation

- **Section failures**: Individual section failures don't stop entire parsing
- **Partial results**: Returns partial data when some components fail
- **Warning collection**: Non-fatal issues collected as warnings

## Migration Notes

### From Previous Architecture

The parser was refactored from a monolithic 1461-line file to a modular system:

**Before:**
- Single large parser class with multiple responsibilities
- `Any` types throughout for generic handling
- Hardcoded parsing strategies

**After:**
- **455-line main parser** (68% reduction) with clear responsibilities
- **Protocol-based typing** with zero `Any` types
- **Strategy pattern** with pluggable processors
- **Configuration-driven** section extraction

### Breaking Changes

None - the public API remains fully backward compatible:

```python
# This still works exactly the same
parser = create_zmk_keymap_parser()
result = parser.parse_keymap(keymap_file, mode, profile)
```

## Future Extensions

### Custom Parsing Strategies

Add new parsing modes by implementing `ProcessorProtocol`:

```python
class CustomProcessor(BaseKeymapProcessor):
    def process(self, context: ParsingContext) -> LayoutData | None:
        # Custom parsing logic
        return layout_data

# Register with parser
custom_processors = {
    ParsingMode.CUSTOM: CustomProcessor(),
    **default_processors
}
```

### Profile-Specific Processors

Extend keyboard profiles to specify custom processors:

```yaml
# Future enhancement
parsing:
  processor_class: "my_package.CustomGlove80Processor"
  processor_config:
    enable_macro_analysis: true
```

## Best Practices

### Type Safety

1. **Use Protocol interfaces** for all dependencies
2. **Avoid `Any` types** - use specific types or `object` for truly generic data
3. **Runtime type checking** with Protocol-based validation

### Testing

1. **Mock Protocol interfaces** for isolated unit tests
2. **Use factory functions** with dependency injection for testability
3. **Test both parsing modes** for comprehensive coverage

### Performance

1. **Choose appropriate parsing mode** based on keymap source
2. **Profile-specific optimization** through custom extraction configs
3. **Cache template metadata** for repeated operations

### Error Handling

1. **Debug-aware logging** for all exceptions
2. **Collect warnings** for non-fatal issues
3. **Graceful degradation** when possible

## Related Documentation

- [CLAUDE.md](../CLAUDE.md) - Project coding conventions
- [Testing Guidelines](testing.md) - Testing standards and methodology
- [Layout Domain Architecture](layout-domain.md) - Overall layout system design
- [Configuration System](configuration.md) - Keyboard profile configuration