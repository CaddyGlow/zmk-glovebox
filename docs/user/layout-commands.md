# Layout Commands Guide

This guide covers all layout-related operations in Glovebox, from basic compilation to advanced editing and version management.

## Overview

Layout commands handle the transformation of keyboard layouts from JSON files to ZMK keymap and configuration files. They also provide tools for editing, validating, and managing layout files.

## Basic Layout Operations

### Compiling Layouts

The most common operation is converting JSON layouts to ZMK files:

```bash
# Basic compilation
glovebox layout compile my_layout.json output/ --profile glove80/v25.05

# With validation (default)
glovebox layout compile layout.json output/ --profile glove80/v25.05 --validate

# Skip validation for faster compilation
glovebox layout compile layout.json output/ --no-validate

# Force overwrite existing files
glovebox layout compile layout.json output/ --force
```

**Output files:**
- `output/my_layout.keymap` - ZMK keymap file
- `output/my_layout.conf` - ZMK configuration file

### Validating Layouts

Validate layouts without generating files:

```bash
# Basic validation
glovebox layout validate my_layout.json --profile glove80/v25.05

# Verbose validation with detailed output
glovebox layout validate layout.json --profile glove80/v25.05 --verbose

# JSON output for scripting
glovebox layout validate layout.json --format json
```

### Displaying Layouts

Preview and inspect layout content:

```bash
# Show layout in grid format
glovebox layout show layout.json --mode grid

# Show as structured list
glovebox layout show layout.json --mode list

# Show raw JSON data
glovebox layout show layout.json --format json

# Verbose layout information
glovebox layout show layout.json --verbose
```

## Layout Editing

### Field Operations

Edit specific fields in layout files:

```bash
# Get field values
glovebox layout edit layout.json --get title
glovebox layout edit layout.json --get title,keyboard,version

# Set field values
glovebox layout edit layout.json --set title="My Custom Layout"
glovebox layout edit layout.json --set version="2.0" --set creator="User"

# Multiple operations in one command
glovebox layout edit layout.json \
  --get title,version \
  --set title="Updated Layout" \
  --set version="2.1" \
  --save
```

### Working with Arrays

Manipulate array fields like layers and bindings:

```bash
# Get array elements
glovebox layout edit layout.json --get layers[0].name
glovebox layout edit layout.json --get layers[1].bindings[0]

# Set array elements
glovebox layout edit layout.json --set layers[0].name="Base"
glovebox layout edit layout.json --set layers[1].bindings[5]="&kp ESC"

# Append to arrays
glovebox layout edit layout.json --append config_includes="custom_config.conf"
```

### Object Field Operations

Work with nested object fields:

```bash
# Get nested values
glovebox layout edit layout.json --get metadata.description
glovebox layout edit layout.json --get author.name

# Set nested values
glovebox layout edit layout.json --set metadata.description="Gaming layout"
glovebox layout edit layout.json --set author.name="John Doe"

# Merge object values
glovebox layout edit layout.json --merge metadata='{"tags": ["gaming", "custom"]}'
```

### Advanced Field Paths

Use complex field paths for precise editing:

```bash
# Layer-specific operations
glovebox layout edit layout.json --get layers[0].bindings[10]
glovebox layout edit layout.json --set layers[2].bindings[0]="&mo 3"

# Behavior modifications
glovebox layout edit layout.json --get behaviors.ht.properties
glovebox layout edit layout.json --set behaviors.ht.properties.tapping_term_ms=200

# Config parameter editing
glovebox layout edit layout.json --set config.CONFIG_ZMK_KEYBOARD_NAME="my_keyboard"
```

## Layer Management

### Adding Layers

Create new layers in your layout:

```bash
# Add layer at the end
glovebox layout edit layout.json --add-layer "Numbers"

# Add layer at specific position
glovebox layout edit layout.json --add-layer "Symbols" --position 3

# Add layer with bindings from another layout
glovebox layout edit layout.json \
  --add-layer "Gaming" \
  --import-from gaming_layer.json
```

### Removing Layers

Remove layers from your layout:

```bash
# Remove layer by name
glovebox layout edit layout.json --remove-layer "Unused"

# Remove layer by index
glovebox layout edit layout.json --remove-layer 4
```

### Moving and Copying Layers

Reorganize layer structure:

```bash
# Move layer to new position
glovebox layout edit layout.json --move-layer "Numbers" --position 2

# Copy layer within layout
glovebox layout edit layout.json --copy-layer "Base" "Base_Backup"

# Export layer to separate file
glovebox layout edit layout.json --export-layer "Gaming" gaming_layer.json
```

### Layer Import/Export

Work with individual layers:

```bash
# Export layer as bindings only
glovebox layout edit layout.json \
  --export-layer "Symbols" symbols.json \
  --format bindings

# Export complete layer object
glovebox layout edit layout.json \
  --export-layer "Numbers" numbers.json \
  --format layer

# Import layer from file
glovebox layout edit layout.json \
  --add-layer "Imported" \
  --import-from external_layer.json
```

## Layout Comparison and Diffing

### Basic Comparison

Compare two layout files:

```bash
# Basic diff
glovebox layout diff old_layout.json new_layout.json

# Include DTSI content comparison
glovebox layout diff layout1.json layout2.json --include-dtsi

# Unified diff format
glovebox layout diff layout1.json layout2.json --unified

# More context lines
glovebox layout diff layout1.json layout2.json --context 5
```

### Output Formats

Get diff results in different formats:

```bash
# JSON output for scripting
glovebox layout diff layout1.json layout2.json --format json

# YAML output
glovebox layout diff layout1.json layout2.json --format yaml

# Structured comparison
glovebox layout diff layout1.json layout2.json --format structured
```

### Patch Operations

Create and apply patches:

```bash
# Create patch file
glovebox layout diff old_layout.json new_layout.json \
  --format patch > changes.patch

# Apply patch
glovebox layout patch old_layout.json changes.patch updated_layout.json

# Preview patch without applying
glovebox layout patch layout.json changes.patch output.json --dry-run
```

## File Operations

### Splitting Layouts

Break layouts into component files:

```bash
# Split into JSON components
glovebox layout split layout.json components/

# Split into YAML format
glovebox layout split layout.json components/ --format yaml

# Overwrite existing components
glovebox layout split layout.json components/ --overwrite
```

**Split output structure:**
```
components/
├── metadata.json      # Layout metadata
├── layers/           # Individual layer files
│   ├── base.json
│   ├── symbols.json
│   └── numbers.json
├── behaviors.json    # Custom behaviors
└── config.json      # Configuration parameters
```

### Merging Layouts

Combine component files back into a layout:

```bash
# Merge components
glovebox layout merge components/ merged_layout.json

# Merge with validation
glovebox layout merge components/ layout.json --validate

# Force merge even with conflicts
glovebox layout merge components/ layout.json --force
```

## Advanced Layout Operations

### Interactive Editing

Use interactive mode for complex edits:

```bash
# Interactive editing session
glovebox layout edit layout.json --interactive

# Interactive field editor
glovebox layout edit layout.json --interactive --focus fields

# Interactive layer editor
glovebox layout edit layout.json --interactive --focus layers
```

### Batch Operations

Perform multiple operations efficiently:

```bash
# Multiple field operations
glovebox layout edit layout.json \
  --set title="Updated Layout" \
  --set version="2.0" \
  --set creator="John Doe" \
  --add-layer "Gaming" \
  --move-layer "Symbols" --position 2 \
  --save
```

### Template Variable Resolution

Work with layout templates:

```bash
# Compile with variable resolution
glovebox layout compile template_layout.json output/ \
  --profile glove80/v25.05 \
  --resolve-variables

# Skip variable resolution
glovebox layout compile template_layout.json output/ \
  --profile glove80/v25.05 \
  --no-resolve-variables
```

### Library Integration

Use layouts from libraries:

```bash
# Compile library layout directly
glovebox layout compile @12345678-1234-1234-1234-123456789abc output/ \
  --profile glove80/v25.05

# Edit library layout
glovebox layout edit @uuid --set title="Customized Library Layout"
```

## Validation and Quality Assurance

### Comprehensive Validation

Ensure layout quality:

```bash
# Full validation with all checks
glovebox layout validate layout.json \
  --profile glove80/v25.05 \
  --verbose \
  --check-behaviors \
  --check-includes

# Schema validation only
glovebox layout validate layout.json --schema-only

# ZMK compatibility check
glovebox layout validate layout.json \
  --profile glove80/v25.05 \
  --zmk-compatibility
```

### Pre-compilation Checks

Validate before building:

```bash
# Validate then compile
glovebox layout validate layout.json --profile glove80/v25.05 && \
glovebox layout compile layout.json output/ --profile glove80/v25.05

# Compile with extra validation
glovebox layout compile layout.json output/ \
  --profile glove80/v25.05 \
  --validate \
  --strict
```

## Working with Profiles

### Profile-Specific Operations

Different keyboards may need different handling:

```bash
# Glove80 specific compilation
glovebox layout compile layout.json output/ --profile glove80/v25.05

# Corne keyboard compilation
glovebox layout compile layout.json output/ --profile corne/main

# Generic ZMK keyboard
glovebox layout compile layout.json output/ --profile planck/main
```

### Profile Validation

Ensure layout compatibility:

```bash
# Validate for specific profile
glovebox layout validate layout.json --profile glove80/v25.05

# Check multiple profiles
glovebox layout validate layout.json --profile glove80/v25.05
glovebox layout validate layout.json --profile corne/main
```

## Output Customization

### Custom Output Paths

Control where files are generated:

```bash
# Custom keymap filename
glovebox layout compile layout.json output/ \
  --profile glove80/v25.05 \
  --keymap-name custom_keymap

# Custom config filename
glovebox layout compile layout.json output/ \
  --profile glove80/v25.05 \
  --config-name custom_config

# Output to stdout
glovebox layout compile layout.json --output-stdout --profile glove80/v25.05
```

### Template Customization

Use custom templates:

```bash
# Custom keymap template
glovebox layout compile layout.json output/ \
  --profile glove80/v25.05 \
  --keymap-template custom_keymap.j2

# Custom config template
glovebox layout compile layout.json output/ \
  --profile glove80/v25.05 \
  --config-template custom_config.j2
```

## Error Handling and Debugging

### Verbose Output

Get detailed information about operations:

```bash
# Verbose compilation
glovebox layout compile layout.json output/ \
  --profile glove80/v25.05 \
  --verbose

# Debug-level output
glovebox layout compile layout.json output/ \
  --profile glove80/v25.05 \
  --debug

# Quiet mode (minimal output)
glovebox layout compile layout.json output/ \
  --profile glove80/v25.05 \
  --quiet
```

### Dry Run Operations

Preview operations without executing:

```bash
# Preview compilation
glovebox layout compile layout.json output/ \
  --profile glove80/v25.05 \
  --dry-run

# Preview edit operations
glovebox layout edit layout.json \
  --set title="New Title" \
  --dry-run
```

### Error Recovery

Handle common issues:

```bash
# Force operations past warnings
glovebox layout compile layout.json output/ \
  --profile glove80/v25.05 \
  --force

# Skip validation for problematic layouts
glovebox layout compile layout.json output/ \
  --profile glove80/v25.05 \
  --no-validate

# Continue on errors
glovebox layout compile layout.json output/ \
  --profile glove80/v25.05 \
  --continue-on-error
```

## Performance Optimization

### Caching

Use caching for faster operations:

```bash
# Enable aggressive caching
glovebox layout compile layout.json output/ \
  --profile glove80/v25.05 \
  --cache-aggressive

# Disable caching for debugging
glovebox layout compile layout.json output/ \
  --profile glove80/v25.05 \
  --no-cache

# Warm up cache
glovebox layout compile layout.json /dev/null \
  --profile glove80/v25.05 \
  --cache-only
```

### Parallel Operations

Process multiple layouts:

```bash
# Batch compile multiple layouts
for layout in *.json; do
  glovebox layout compile "$layout" "output/${layout%.json}/" \
    --profile glove80/v25.05 &
done
wait
```

## Common Workflows

### Development Workflow

Typical development cycle:

```bash
# 1. Validate layout
glovebox layout validate my_layout.json --profile glove80/v25.05

# 2. Edit if needed
glovebox layout edit my_layout.json --set version="1.1" --save

# 3. Compile to files
glovebox layout compile my_layout.json build/ --profile glove80/v25.05

# 4. Review generated files
glovebox layout show build/my_layout.keymap --format preview
```

### Testing Workflow

Test layouts across profiles:

```bash
# Test compilation for multiple keyboards
for profile in glove80/v25.05 corne/main lily58/main; do
  echo "Testing $profile..."
  glovebox layout validate my_layout.json --profile "$profile"
done
```

### Backup and Version Control

Manage layout versions:

```bash
# Create backup before editing
cp my_layout.json "backups/my_layout_$(date +%Y%m%d_%H%M%S).json"

# Edit layout
glovebox layout edit my_layout.json --set version="2.0" --save

# Compare versions
glovebox layout diff backups/my_layout_20240101_120000.json my_layout.json
```

## Best Practices

### 1. Always Validate Before Compiling
```bash
glovebox layout validate layout.json --profile glove80/v25.05 && \
glovebox layout compile layout.json output/ --profile glove80/v25.05
```

### 2. Use Descriptive Filenames
```bash
glovebox layout compile layout.json output/ \
  --keymap-name "gaming_layout_v2" \
  --config-name "gaming_config_v2"
```

### 3. Keep Backups
```bash
# Automatic backup before editing
glovebox layout edit layout.json --backup --set title="New Title"
```

### 4. Use Version Fields
```bash
glovebox layout edit layout.json \
  --set version="1.0" \
  --set creator="$(whoami)" \
  --set date="$(date -I)"
```

### 5. Test Multiple Profiles
```bash
# Ensure cross-compatibility
glovebox layout validate layout.json --profile glove80/v25.05
glovebox layout validate layout.json --profile corne/main
```

---

*Layout commands are the core of Glovebox functionality. Master these commands to efficiently manage and build your keyboard layouts.*