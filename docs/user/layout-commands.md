# Layout Commands

This guide covers all Glovebox layout commands with their harmonized parameters and usage examples.

## Quick Reference

| Command | Purpose | Key Parameters |
|---------|---------|----------------|
| [`diff`](#diff-command) | Compare two layouts | `--output`, `--detailed`, `--include-dtsi` |
| [`patch`](#patch-command) | Apply diff patches | `--output`, `--exclude-dtsi` |
| [`compile`](#compile-command) | Generate ZMK files | `--output`, `--profile` |
| [`validate`](#validate-command) | Validate layout files | `--profile` |
| [`show`](#show-command) | Display layout content | `--layer`, `--output-format` |
| [`edit`](#edit-command) | Modify layout fields | `--get`, `--set`, `--output` |
| [`split`](#split-command) | Split layout into components | `output_dir`, `--profile` |
| [`merge`](#merge-command) | Merge components into layout | `input_dir`, `output_file` |

## Common Parameters

All layout commands share these harmonized parameter patterns:

### File Parameters
- **Layout files**: All commands use `JsonFileArgument` which supports the `GLOVEBOX_JSON_FILE` environment variable
- **Output files**: All commands use `--output` (`-o`) for consistent file output handling

### Environment Variables
```bash
# Set once, use everywhere
export GLOVEBOX_JSON_FILE=my-layout.json
export GLOVEBOX_PROFILE=glove80/v25.05

# Now these work without specifying files
glovebox layout validate
glovebox layout show --layer 0
glovebox layout compile --output build/
```

### Output Formats
All commands support the same output formats via `--output-format`:
- `text` (default) - Human-readable text
- `json` - Structured JSON output
- `markdown` - Markdown formatted output
- `table` - Simple table format
- `rich-table` - Rich colored table
- `rich-panel` - Rich panel format
- `rich-grid` - Rich grid layout

### Profile Handling
Commands that need keyboard/firmware profiles use consistent resolution:
1. CLI `--profile` flag (highest priority)
2. Auto-detection from JSON keyboard field (unless `--no-auto`)
3. `GLOVEBOX_PROFILE` environment variable
4. User config default profile
5. Hardcoded fallback profile (lowest priority)

## Command Details

### diff command

Compare two layout files and optionally create patch files for later application.

**Syntax:**
```bash
glovebox layout diff LAYOUT2 [LAYOUT1] [OPTIONS]
```

**Parameters:**
- `layout2` (required) - Second layout file to compare
- `layout1` (optional) - First layout file (uses `GLOVEBOX_JSON_FILE` if not provided)
- `--output`, `-o` - Create LayoutDiff patch file for later application
- `--output-format` - Output format (default: text)
- `--detailed` - Show detailed key changes within layers
- `--include-dtsi` - Include custom DTSI fields in diff output
- `--patch-section` - DTSI section for patch: behaviors, devicetree, or both (default: both)

**Examples:**

Basic comparison:
```bash
# Compare two layout versions
glovebox layout diff my-layout-v42.json my-layout-v41.json

# Use environment variable for first layout
export GLOVEBOX_JSON_FILE=current-layout.json
glovebox layout diff modified-layout.json
```

Detailed analysis:
```bash
# Show individual key differences
glovebox layout diff new.json old.json --detailed

# Include custom DTSI code differences
glovebox layout diff new.json old.json --include-dtsi --detailed
```

Create patch files:
```bash
# Create diff file for later patching
glovebox layout diff new.json old.json --output changes.json

# JSON output for automation
glovebox layout diff layout2.json layout1.json --output-format json

# Complete workflow: detailed comparison with patch creation
glovebox layout diff layout2.json layout1.json \
  --detailed --include-dtsi --output changes.json
```

Master version comparison:
```bash
# Compare your custom layout with a master version
glovebox layout diff my-custom.json \
  ~/.glovebox/masters/glove80/v42-rc3.json --detailed
```

### patch command

Apply a JSON diff patch to transform a layout file.

**Syntax:**
```bash
glovebox layout patch LAYOUT_FILE PATCH_FILE [OPTIONS]
```

**Parameters:**
- `layout_file` (required) - Source layout file to patch
- `patch_file` (required) - JSON diff file from `glovebox layout diff --output`
- `--output`, `-o` - Output path (default: source_layout with -patched suffix)
- `--force` - Overwrite existing files
- `--exclude-dtsi` - Exclude DTSI changes even if present in patch

**Examples:**

Basic patch workflow:
```bash
# Step 1: Generate a diff
glovebox layout diff old.json new.json --output changes.json

# Step 2: Apply the diff to transform another layout
glovebox layout patch my-layout.json changes.json --output patched-layout.json

# Apply diff with auto-generated output name
glovebox layout patch my-layout.json changes.json
```

Advanced options:
```bash
# Force overwrite existing output file
glovebox layout patch base.json changes.json --output result.json --force

# Skip DTSI changes from patch
glovebox layout patch layout.json patch.json --exclude-dtsi
```

### compile command

Compile ZMK keymap and config files from a JSON layout file.

**Syntax:**
```bash
glovebox layout compile [JSON_FILE] [OPTIONS]
```

**Parameters:**
- `json_file` (optional) - Layout JSON file (supports `GLOVEBOX_JSON_FILE`)
- `--output`, `-o` - Output directory and base filename (e.g., 'config/my_glove80')
- `--profile` - Keyboard/firmware profile (e.g., 'glove80/v25.05')
- `--no-auto` - Disable automatic profile detection from JSON keyboard field
- `--force` - Overwrite existing files
- `--output-format` - Output format (default: text)

**Examples:**

Auto-detection (recommended):
```bash
# Auto-detect profile from JSON keyboard field
glovebox layout compile layout.json --output build/my_glove80

# Using environment variable
GLOVEBOX_JSON_FILE=layout.json glovebox layout compile --output build/
```

Explicit profile:
```bash
# Specify profile explicitly
glovebox layout compile layout.json \
  --output output/glove80 --profile glove80/v25.05

# Disable auto-detection
glovebox layout compile layout.json \
  --no-auto --profile glove80/v25.05 --output build/
```

### validate command

Validate a layout JSON file for correctness and completeness.

**Syntax:**
```bash
glovebox layout validate [JSON_FILE] [OPTIONS]
```

**Parameters:**
- `json_file` (optional) - Layout JSON file (supports `GLOVEBOX_JSON_FILE`)
- `--profile` - Keyboard/firmware profile for validation context
- `--no-auto` - Disable automatic profile detection
- `--output-format` - Output format (default: text)

**Examples:**

Basic validation:
```bash
# Validate with auto-detection
glovebox layout validate layout.json

# Use environment variable
GLOVEBOX_JSON_FILE=layout.json glovebox layout validate
```

Advanced validation:
```bash
# Validate with specific profile
glovebox layout validate layout.json --profile glove80/v25.05

# JSON output for CI/CD pipelines
glovebox layout validate layout.json --output-format json

# Disable auto-detection
glovebox layout validate layout.json --no-auto --profile glove80/v25.05
```

### show command

Display layout content in various formats.

**Syntax:**
```bash
glovebox layout show [JSON_FILE] [OPTIONS]
```

**Parameters:**
- `json_file` (optional) - Layout JSON file (supports `GLOVEBOX_JSON_FILE`)
- `--key-width` - Key width for display (default: 10)
- `--view-mode` - View mode for display
- `--layout`, `-l` - Layout name to use for display
- `--layer` - Layer name or index to display
- `--profile` - Keyboard/firmware profile
- `--no-auto` - Disable automatic profile detection
- `--output-format` - Output format (default: text)

**Examples:**

Basic display:
```bash
# Show entire layout
glovebox layout show layout.json

# Use environment variable
GLOVEBOX_JSON_FILE=layout.json glovebox layout show
```

Layer-specific display:
```bash
# Show specific layer by index
glovebox layout show layout.json --layer 0

# Show specific layer by name
glovebox layout show layout.json --layer "Gaming"

# Show layer with custom key width
glovebox layout show layout.json --layer "Base" --key-width 12
```

Rich formatting:
```bash
# Rich table format
glovebox layout show layout.json --output-format rich-table

# Rich panel format
glovebox layout show layout.json --output-format rich-panel

# JSON format for processing
glovebox layout show layout.json --output-format json
```

### edit command

Modify layout fields, layers, and structure with atomic operations.

**Syntax:**
```bash
glovebox layout edit [LAYOUT_FILE] [OPTIONS]
```

**Parameters:**
- `layout_file` (optional) - Layout JSON file (supports `GLOVEBOX_JSON_FILE`)

**Field Operations:**
- `--get` - Get field value(s) using JSON path notation
- `--set` - Set field value using 'key=value' format
- `--unset` - Remove field or dictionary key
- `--merge` - Merge dictionary using 'key=value' or 'key=from:file.json'
- `--append` - Append to array using 'key=value' format

**Layer Operations:**
- `--add-layer` - Add new layer(s)
- `--remove-layer` - Remove layer(s) by name or index
- `--move-layer` - Move layer using 'name:position' syntax
- `--copy-layer` - Copy layer using 'source:target' syntax

**Info Operations:**
- `--list-layers` - List all layers in the layout
- `--list-usage` - Show where each variable is used

**Output Options:**
- `--output`, `-o` - Output file (default: overwrite original)
- `--output-format` - Output format (default: text)
- `--force` - Overwrite existing files
- `--dry-run` - Show what would be done without saving

**Examples:**

Field operations:
```bash
# Get field values
glovebox layout edit layout.json --get title --get version

# Set multiple fields
glovebox layout edit layout.json \
  --set title="My Custom Layout" \
  --set author="Your Name" \
  --set version="2.0"

# Remove fields
glovebox layout edit layout.json --unset notes --unset tags
```

Import from files:
```bash
# Import variables from another file
glovebox layout edit layout.json \
  --set variables=from:vars.json$.variables

# Merge data from file with JSON path
glovebox layout edit layout.json \
  --merge variables=from:other.json:meta.variables
```

Layer management:
```bash
# Add new layers
glovebox layout edit layout.json --add-layer Gaming --add-layer Media

# Remove layers by name or index
glovebox layout edit layout.json --remove-layer 3 --remove-layer "Unused"

# Move layers
glovebox layout edit layout.json --move-layer Symbol:0 --move-layer Gaming:2

# Copy layers
glovebox layout edit layout.json --copy-layer Base:Backup
```

Information and preview:
```bash
# List all layers
glovebox layout edit layout.json --list-layers

# Show variable usage
glovebox layout edit layout.json --list-usage

# Preview changes without saving
glovebox layout edit layout.json --set title="Test" --dry-run

# Save to new file
glovebox layout edit layout.json \
  --set version="2.0" --output modified.json
```

Complex operations:
```bash
# Multiple operations in one command
glovebox layout edit layout.json \
  --set title="Updated Layout" \
  --add-layer Gaming \
  --move-layer Symbol:0 \
  --output updated.json \
  --force
```

### split command

Split a layout file into separate component files for easier management.

**Syntax:**
```bash
glovebox layout split OUTPUT_DIR [LAYOUT_FILE] [OPTIONS]
```

**Parameters:**
- `output_dir` (required) - Directory to save split files
- `layout_file` (optional) - Layout JSON file (supports `GLOVEBOX_JSON_FILE`)
- `--profile` - Keyboard/firmware profile
- `--no-auto` - Disable automatic profile detection
- `--force` - Overwrite existing files
- `--output-format` - Output format (default: text)

**Examples:**

Basic splitting:
```bash
# Split layout into components with auto-profile detection
glovebox layout split layout.json ./components/

# Use environment variable for JSON file
GLOVEBOX_JSON_FILE=layout.json glovebox layout split ./components/
```

Advanced options:
```bash
# Force overwrite existing directory
glovebox layout split layout.json ./output/ --force

# Disable auto-detection and specify profile
glovebox layout split layout.json ./components/ \
  --no-auto --profile glove80/v25.05

# JSON output format
glovebox layout split layout.json ./split/ --output-format json
```

**Output structure:**
```
components/
├── metadata.json       # Layout metadata
├── layers/            # Individual layer files
│   ├── Base.json
│   ├── Lower.json
│   └── Raise.json
├── behaviors/         # Behavior definitions
│   ├── holdTaps.json
│   ├── combos.json
│   └── macros.json
└── dtsi/             # Custom DTSI files
    ├── behaviors.dtsi
    └── devicetree.dtsi
```

### merge command

Merge split component files back into a complete layout file.

**Syntax:**
```bash
glovebox layout merge INPUT_DIR OUTPUT_FILE [OPTIONS]
```

**Parameters:**
- `input_dir` (required) - Directory with metadata.json and component subdirectories
- `output_file` (required) - Output merged layout JSON file path
- `--profile` - Keyboard/firmware profile
- `--force` - Overwrite existing files
- `--output-format` - Output format (default: text)

**Examples:**

Basic merging:
```bash
# Merge components back into layout
glovebox layout merge ./components/ merged-layout.json

# Force overwrite existing output file
glovebox layout merge ./split/ layout.json --force
```

Advanced options:
```bash
# Specify keyboard profile
glovebox layout merge ./components/ layout.json --profile glove80/v25.05

# JSON output format
glovebox layout merge ./components/ layout.json --output-format json
```

## Common Workflows

### Development Workflow

```bash
# 1. Start with environment setup
export GLOVEBOX_JSON_FILE=my-layout.json
export GLOVEBOX_PROFILE=glove80/v25.05

# 2. Validate your layout
glovebox layout validate

# 3. Make modifications
glovebox layout edit --set title="Development Version" --set version="2.1-dev"

# 4. Compile to ZMK files
glovebox layout compile --output build/dev/

# 5. Split for easier management
glovebox layout split ./components/
```

### Version Comparison Workflow

```bash
# Compare with previous version
glovebox layout diff current.json previous.json --detailed --output changes.json

# Apply changes to another layout
glovebox layout patch base-layout.json changes.json --output updated.json

# Validate the result
glovebox layout validate updated.json
```

### Master Version Upgrade Workflow

```bash
# Compare with master version
glovebox layout diff my-custom.json \
  ~/.glovebox/masters/glove80/v42.json \
  --detailed --include-dtsi --output upgrade.json

# Apply master updates while preserving customizations
glovebox layout patch my-custom.json upgrade.json --output upgraded.json

# Validate and compile
glovebox layout validate upgraded.json
glovebox layout compile upgraded.json --output build/upgraded/
```

### Batch Processing Workflow

```bash
# Process multiple layouts
for layout in layouts/*.json; do
  echo "Processing $layout"
  
  # Validate
  glovebox layout validate "$layout" --output-format json > "${layout%.json}.validation.json"
  
  # Update version
  glovebox layout edit "$layout" --set version="2.0" --output "v2/${layout##*/}"
  
  # Compile
  glovebox layout compile "v2/${layout##*/}" --output "build/${layout##*/%.json}/"
done
```

## Error Handling

### Common Issues and Solutions

**File not found:**
```bash
# ❌ Error: File not found
glovebox layout validate nonexistent.json

# ✅ Solution: Use environment variable or full path
export GLOVEBOX_JSON_FILE=my-layout.json
glovebox layout validate
```

**Profile detection failure:**
```bash
# ❌ Error: Cannot detect keyboard profile
glovebox layout compile layout.json

# ✅ Solution: Specify profile explicitly
glovebox layout compile layout.json --profile glove80/v25.05
```

**Validation errors:**
```bash
# ❌ Error: Invalid layout structure
glovebox layout validate layout.json

# ✅ Solution: Check JSON format and required fields
glovebox layout validate layout.json --output-format json | jq '.errors'
```

### Best Practices

1. **Always validate before compiling:**
   ```bash
   glovebox layout validate layout.json && \
   glovebox layout compile layout.json --output build/
   ```

2. **Use environment variables for consistency:**
   ```bash
   export GLOVEBOX_JSON_FILE=my-layout.json
   export GLOVEBOX_PROFILE=glove80/v25.05
   ```

3. **Create backups before major edits:**
   ```bash
   cp layout.json layout.json.backup
   glovebox layout edit layout.json --set version="2.0"
   ```

4. **Use dry-run for preview:**
   ```bash
   glovebox layout edit layout.json --set title="New Title" --dry-run
   ```

5. **Leverage JSON output for automation:**
   ```bash
   glovebox layout validate layout.json --output-format json | \
   jq -r '.valid // false'
   ```

## Integration with Other Commands

### With Configuration Commands

```bash
# Set up profile and JSON file
glovebox config set default_profile=glove80/v25.05
glovebox config set default_json_file=my-layout.json

# Now layout commands use these defaults
glovebox layout validate
glovebox layout compile --output build/
```

### With Firmware Commands

```bash
# Complete workflow: layout to firmware
glovebox layout compile layout.json --output build/firmware/
glovebox firmware flash build/firmware/glove80.uf2 --profile glove80
```

### With Cache Commands

```bash
# Clear layout-related caches
glovebox cache clear --tag layout

# Show cache statistics
glovebox cache stats
```

This completes the comprehensive layout commands documentation. All commands now follow consistent patterns and provide a unified, predictable interface for keyboard layout management.