# CLI Reference

This is a comprehensive reference for all Glovebox CLI commands, their options, and usage examples.

## Global Options

These options work with all commands:

```bash
--help                    # Show help message
--verbose                 # Enable verbose output  
--quiet                   # Suppress non-essential output
--profile KEYBOARD[/FIRMWARE]  # Override default profile
--version                 # Show version and exit
```

## Command Structure

All Glovebox commands follow this pattern:

```bash
glovebox [GLOBAL_OPTIONS] COMMAND [SUBCOMMAND] [OPTIONS] [ARGUMENTS]
```

---

## Layout Commands

Manage keyboard layouts and convert between formats.

### `glovebox layout compile`

Compile JSON layouts to ZMK keymap and config files.

```bash
glovebox layout compile INPUT OUTPUT [OPTIONS]
```

**Arguments:**
- `INPUT` - Input JSON layout file
- `OUTPUT` - Output directory for generated files

**Options:**
```bash
--profile PROFILE         # Keyboard/firmware profile
--validate / --no-validate  # Validate layout (default: true)
--force                   # Overwrite existing files
--verbose                 # Verbose compilation output
--dry-run                 # Show what would be generated
--format FORMAT           # Output format (zmk, preview)
```

**Examples:**
```bash
# Basic compilation
glovebox layout compile my_layout.json output/ --profile glove80/v25.05

# With validation disabled
glovebox layout compile layout.json output/ --no-validate

# Dry run to preview
glovebox layout compile layout.json output/ --dry-run

# Force overwrite existing files
glovebox layout compile layout.json output/ --force
```

### `glovebox layout validate`

Validate JSON layout files without compilation.

```bash
glovebox layout validate INPUT [OPTIONS]
```

**Options:**
```bash
--profile PROFILE         # Profile for validation context
--verbose                 # Detailed validation output
--format json            # Output validation results as JSON
```

**Examples:**
```bash
# Basic validation
glovebox layout validate my_layout.json

# Verbose validation with profile
glovebox layout validate layout.json --profile glove80/v25.05 --verbose

# JSON output for scripting
glovebox layout validate layout.json --format json
```

### `glovebox layout show`

Display layout information and preview.

```bash
glovebox layout show INPUT [OPTIONS]
```

**Options:**
```bash
--profile PROFILE         # Profile for display context
--mode MODE              # Display mode (grid, list, json)
--verbose                # Show detailed information
--format FORMAT          # Output format (table, json, yaml)
```

**Examples:**
```bash
# Show layout in grid format
glovebox layout show layout.json --mode grid

# Show as JSON
glovebox layout show layout.json --format json

# Verbose layout information
glovebox layout show layout.json --verbose
```

### `glovebox layout edit`

Edit layout files with field operations.

```bash
glovebox layout edit INPUT [OPTIONS]
```

**Field Operations:**
```bash
--get FIELD[,FIELD...]    # Get field values
--set FIELD=VALUE         # Set field value
--unset FIELD             # Remove field
--append FIELD=VALUE      # Append to array field
--merge FIELD=VALUE       # Merge into object field
```

**Layer Operations:**
```bash
--add-layer NAME          # Add new layer
--remove-layer NAME       # Remove layer
--move-layer NAME=POS     # Move layer to position
--copy-layer SRC=DST      # Copy layer
```

**Control Options:**
```bash
--save / --no-save        # Save changes (default: true)
--backup / --no-backup    # Create backup (default: true)
--force                   # Force operations
--interactive             # Interactive editing mode
```

**Examples:**
```bash
# Get field values
glovebox layout edit layout.json --get title,keyboard,version

# Set multiple fields
glovebox layout edit layout.json \
  --set title="My Layout" \
  --set version="2.0" \
  --save

# Add and modify layer
glovebox layout edit layout.json \
  --add-layer "Numbers" \
  --set layers[3].bindings[0]="&kp N1"

# Interactive editing
glovebox layout edit layout.json --interactive
```

### `glovebox layout split`

Split layout into separate component files.

```bash
glovebox layout split INPUT OUTPUT_DIR [OPTIONS]
```

**Options:**
```bash
--format FORMAT          # Output format (json, yaml)
--overwrite              # Overwrite existing files
```

**Examples:**
```bash
# Split into JSON components
glovebox layout split layout.json components/

# Split into YAML format
glovebox layout split layout.json components/ --format yaml
```

### `glovebox layout merge`

Merge component files back into a single layout.

```bash
glovebox layout merge INPUT_DIR OUTPUT [OPTIONS]
```

**Examples:**
```bash
# Merge components into layout
glovebox layout merge components/ merged_layout.json

# Merge with validation
glovebox layout merge components/ layout.json --validate
```

### `glovebox layout diff`

Compare two layout files and show differences.

```bash
glovebox layout diff LAYOUT1 LAYOUT2 [OPTIONS]
```

**Options:**
```bash
--include-dtsi           # Include DTSI content comparison
--format FORMAT          # Output format (text, json, yaml)
--context LINES          # Context lines for diff (default: 3)
--unified                # Unified diff format
```

**Examples:**
```bash
# Basic diff
glovebox layout diff old_layout.json new_layout.json

# Include DTSI comparison
glovebox layout diff layout1.json layout2.json --include-dtsi

# JSON output
glovebox layout diff layout1.json layout2.json --format json

# Unified diff with more context
glovebox layout diff layout1.json layout2.json --unified --context 5
```

### `glovebox layout patch`

Apply patch file to layout.

```bash
glovebox layout patch INPUT PATCH_FILE OUTPUT [OPTIONS]
```

**Options:**
```bash
--dry-run                # Preview patch without applying
--force                  # Force patch application
```

**Examples:**
```bash
# Apply patch
glovebox layout patch layout.json changes.patch patched_layout.json

# Preview patch
glovebox layout patch layout.json changes.patch output.json --dry-run
```

---

## Firmware Commands

Build and flash keyboard firmware.

### `glovebox firmware compile`

Compile layouts or ZMK files into firmware.

```bash
glovebox firmware compile INPUT OUTPUT [OPTIONS]
```

**Input Types:**
- JSON layout file
- ZMK keymap file (with config file)
- Directory containing ZMK files

**Options:**
```bash
--profile PROFILE         # Keyboard/firmware profile (required)
--config CONFIG_FILE      # Additional config file
--verbose                 # Verbose build output
--clean                   # Clean build (no cache)
--dry-run                 # Show build plan without executing
--timeout SECONDS         # Build timeout (default: 300)
```

**Examples:**
```bash
# Compile from JSON layout
glovebox firmware compile layout.json firmware/ --profile glove80/v25.05

# Compile from ZMK files
glovebox firmware compile keymap.keymap firmware/ \
  --profile glove80/v25.05 \
  --config config.conf

# Clean build with verbose output
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --clean --verbose

# Extended timeout for large builds
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --timeout 600
```

### `glovebox firmware flash`

Flash firmware to connected keyboards.

```bash
glovebox firmware flash FIRMWARE [OPTIONS]
```

**Options:**
```bash
--profile PROFILE         # Keyboard profile for device detection
--device DEVICE           # Specific device to flash
--wait                    # Wait for device to appear
--timeout SECONDS         # Flash timeout (default: 30)
--dry-run                 # Show flash plan without executing
--force                   # Force flash without verification
```

**Examples:**
```bash
# Flash firmware (auto-detect device)
glovebox firmware flash firmware.uf2 --profile glove80

# Flash to specific device
glovebox firmware flash firmware.uf2 --device /dev/ttyACM0

# Wait for device and flash
glovebox firmware flash firmware.uf2 --profile glove80 --wait

# Flash with extended timeout
glovebox firmware flash firmware.uf2 --profile glove80 --timeout 60
```

### `glovebox firmware devices`

List available devices for firmware flashing.

```bash
glovebox firmware devices [OPTIONS]
```

Detects and displays USB devices that can be used for flashing firmware.
Shows device information including name, vendor, mount status, and connection
details. Supports filtering by device query string and multiple output formats.

**Options:**
```bash
--profile PROFILE         # Keyboard profile for device detection
--query/-q QUERY          # Device query string for filtering
--all/-a                  # Show all devices (bypass default removable=true filtering)
--output-format FORMAT    # Output format (text, table, json)
```

**Device Filtering Behavior:**
- **Default**: Shows only removable devices (`removable=true` filter)
- **With --all/-a**: Shows all devices including non-removable ones
- **With --query/-q**: Uses custom query string to filter devices
- **Profile-based**: Uses device query from keyboard profile if available

**Query String Format:**
Device queries support attribute matching with operators:
- `vendor=Adafruit` - Exact vendor match
- `serial~=GLV80-.*` - Serial regex pattern match  
- `removable=true` - Boolean attribute match
- `name:Nice` - Name contains text
- Combined: `vendor=Adafruit and serial~=GLV80-.*`

**Device Information Displayed:**
- Device name and vendor identification
- Mount point and connection status  
- Device serial number and path
- Removable device status
- Compatibility with keyboard profile flash methods

**Examples:**
```bash
# List available devices (default: only removable devices)
glovebox firmware devices

# Show all devices including non-removable ones
glovebox firmware devices --all

# Filter devices by vendor
glovebox firmware devices --query "vendor=Adafruit"

# Filter by serial pattern
glovebox firmware devices --query "serial~=GLV80-.*"

# Complex query with multiple conditions
glovebox firmware devices --query "vendor=Adafruit and removable=true"

# Use with keyboard profile
glovebox firmware devices --profile glove80

# Enhanced table output
glovebox firmware devices --output-format table

# JSON output for scripting
glovebox firmware devices --output-format json

# Bypass all filtering to see everything
glovebox firmware devices --query ""
```

**Output Formats:**
- **text** (default): Simple list with device details
- **table**: Enhanced Rich table with formatted columns
- **json**: Machine-readable JSON for automation/scripting

---

## Profile Commands

Manage keyboard and firmware profiles.

### `glovebox profile list`

List available profiles.

```bash
glovebox profile list [OPTIONS]
```

**Options:**
```bash
--keyboards-only         # Show only keyboard names
--verbose                # Show detailed profile information
--format FORMAT          # Output format (table, json, yaml)
```

**Examples:**
```bash
# List all profiles
glovebox profile list

# Show only keyboards
glovebox profile list --keyboards-only

# Verbose profile information
glovebox profile list --verbose

# JSON output
glovebox profile list --format json
```

### `glovebox profile show`

Show detailed profile information.

```bash
glovebox profile show PROFILE [OPTIONS]
```

**Options:**
```bash
--verbose                # Show all configuration details
--format FORMAT          # Output format (table, json, yaml)
```

**Examples:**
```bash
# Show profile details
glovebox profile show glove80/v25.05

# Show keyboard-only profile
glovebox profile show glove80

# Verbose profile information
glovebox profile show glove80/v25.05 --verbose

# JSON output
glovebox profile show glove80/v25.05 --format json
```

### `glovebox profile edit`

Edit profile configurations.

```bash
glovebox profile edit PROFILE [OPTIONS]
```

**Options:**
```bash
--get KEY                # Get configuration value
--set KEY=VALUE          # Set configuration value
--interactive            # Interactive editing mode
```

**Examples:**
```bash
# Get profile value
glovebox profile edit glove80/v25.05 --get build_timeout

# Set profile value
glovebox profile edit glove80/v25.05 --set build_timeout=600

# Interactive editing
glovebox profile edit glove80/v25.05 --interactive
```

### `glovebox profile firmwares`

List firmware versions for a keyboard.

```bash
glovebox profile firmwares KEYBOARD [OPTIONS]
```

**Options:**
```bash
--format FORMAT          # Output format (table, json, yaml)
```

**Examples:**
```bash
# List Glove80 firmware versions
glovebox profile firmwares glove80

# JSON output
glovebox profile firmwares glove80 --format json
```

### `glovebox profile firmware`

Show specific firmware version details.

```bash
glovebox profile firmware KEYBOARD FIRMWARE [OPTIONS]
```

**Examples:**
```bash
# Show firmware details
glovebox profile firmware glove80 v25.05
```

---

## Configuration Commands

Manage Glovebox configuration settings.

### `glovebox config edit`

Edit configuration values.

```bash
glovebox config edit [OPTIONS]
```

**Field Operations:**
```bash
--get FIELD[,FIELD...]    # Get configuration values
--set FIELD=VALUE         # Set configuration value
--unset FIELD             # Remove configuration field
--add FIELD=VALUE         # Add to list configuration
--remove FIELD=VALUE      # Remove from list configuration
```

**Control Options:**
```bash
--save / --no-save        # Save changes (default: true)
--interactive             # Interactive configuration editor
```

**Examples:**
```bash
# Get configuration values
glovebox config edit --get profile,cache_strategy

# Set configuration values
glovebox config edit \
  --set profile=glove80/v25.05 \
  --set cache_strategy=shared \
  --set icon_mode=text

# Add to list configuration
glovebox config edit --add profiles_paths=/path/to/custom/profiles

# Interactive configuration
glovebox config edit --interactive
```

### `glovebox config show`

Display current configuration.

```bash
glovebox config show [OPTIONS]
```

**Options:**
```bash
--defaults               # Show default values
--descriptions           # Show field descriptions
--sources                # Show configuration sources
--format FORMAT          # Output format (table, json, yaml)
```

**Examples:**
```bash
# Show current configuration
glovebox config show

# Show with defaults and descriptions
glovebox config show --defaults --descriptions

# Show all information
glovebox config show --defaults --descriptions --sources

# JSON output
glovebox config show --format json
```

### `glovebox config check-updates`

Check for version updates.

```bash
glovebox config check-updates [OPTIONS]
```

**Options:**
```bash
--include-prereleases    # Include pre-release versions
```

**Examples:**
```bash
# Check for updates
glovebox config check-updates

# Include pre-releases
glovebox config check-updates --include-prereleases
```

---

## Library Commands

Manage layout libraries and repositories.

### `glovebox library fetch`

Download layouts from libraries.

```bash
glovebox library fetch SOURCE [OUTPUT] [OPTIONS]
```

**Sources:**
- MoErgo layout UUID or URL
- GitHub repository URL
- Local library reference

**Examples:**
```bash
# Fetch from MoErgo by UUID
glovebox library fetch @12345678-1234-1234-1234-123456789abc

# Fetch from URL
glovebox library fetch https://github.com/user/layout layout.json

# Fetch to specific file
glovebox library fetch @uuid my_layout.json
```

### `glovebox library search`

Search layout libraries.

```bash
glovebox library search QUERY [OPTIONS]
```

**Options:**
```bash
--limit LIMIT            # Limit number of results
--format FORMAT          # Output format (table, json)
```

**Examples:**
```bash
# Search layouts
glovebox library search "gaming layout"

# Limited results
glovebox library search colemak --limit 5

# JSON output
glovebox library search dvorak --format json
```

### `glovebox library list`

List local library layouts.

```bash
glovebox library list [OPTIONS]
```

**Options:**
```bash
--format FORMAT          # Output format (table, json, yaml)
--verbose                # Show detailed information
```

**Examples:**
```bash
# List local layouts
glovebox library list

# Verbose listing
glovebox library list --verbose

# JSON output
glovebox library list --format json
```

### `glovebox library info`

Show layout information.

```bash
glovebox library info LAYOUT [OPTIONS]
```

**Examples:**
```bash
# Show layout info
glovebox library info my_layout

# Detailed information
glovebox library info my_layout --verbose
```

### `glovebox library remove`

Remove layouts from local library.

```bash
glovebox library remove LAYOUT [OPTIONS]
```

**Options:**
```bash
--force                  # Force removal without confirmation
```

**Examples:**
```bash
# Remove layout
glovebox library remove old_layout

# Force removal
glovebox library remove old_layout --force
```

### `glovebox library export`

Export layouts to files.

```bash
glovebox library export LAYOUT OUTPUT [OPTIONS]
```

**Examples:**
```bash
# Export layout
glovebox library export my_layout exported_layout.json
```

### `glovebox library copy`

Copy layouts within library.

```bash
glovebox library copy SOURCE DEST [OPTIONS]
```

**Examples:**
```bash
# Copy layout
glovebox library copy base_layout custom_layout
```

---

## Cache Commands

Manage build caches and workspaces.

### `glovebox cache show`

Display cache information.

```bash
glovebox cache show [OPTIONS]
```

**Options:**
```bash
--verbose                # Show detailed cache information
--format FORMAT          # Output format (table, json)
```

**Examples:**
```bash
# Show cache status
glovebox cache show

# Verbose cache information
glovebox cache show --verbose

# JSON output
glovebox cache show --format json
```

### `glovebox cache clear`

Clear cache data.

```bash
glovebox cache clear [OPTIONS]
```

**Options:**
```bash
--tag TAG                # Clear specific cache tag
--force                  # Force clear without confirmation
```

**Examples:**
```bash
# Clear all caches
glovebox cache clear

# Clear specific cache
glovebox cache clear --tag compilation

# Force clear
glovebox cache clear --force
```

### `glovebox cache keys`

List cache keys.

```bash
glovebox cache keys [OPTIONS]
```

**Options:**
```bash
--tag TAG                # Filter by cache tag
--format FORMAT          # Output format (table, json)
```

**Examples:**
```bash
# List all cache keys
glovebox cache keys

# Filter by tag
glovebox cache keys --tag compilation
```

### `glovebox cache delete`

Delete specific cache entries.

```bash
glovebox cache delete KEY [OPTIONS]
```

**Examples:**
```bash
# Delete cache entry
glovebox cache delete specific_cache_key
```

### `glovebox cache debug`

Debug cache operations.

```bash
glovebox cache debug [OPTIONS]
```

**Examples:**
```bash
# Debug cache
glovebox cache debug
```

### `glovebox cache workspace`

Manage build workspaces.

```bash
glovebox cache workspace COMMAND [OPTIONS]
```

**Subcommands:**
- `show` - Show workspace information
- `create` - Create new workspace
- `delete` - Delete workspace
- `cleanup` - Clean up old workspaces
- `add` - Add files to workspace
- `export` - Export workspace
- `update` - Update workspace

**Examples:**
```bash
# Show workspaces
glovebox cache workspace show

# Create workspace
glovebox cache workspace create zmk --profile glove80/v25.05

# Delete workspace
glovebox cache workspace delete old_workspace

# Cleanup old workspaces
glovebox cache workspace cleanup
```

---

## MoErgo Commands

Integrate with MoErgo services.

### `glovebox moergo login`

Login to MoErgo services.

```bash
glovebox moergo login [OPTIONS]
```

**Examples:**
```bash
# Login to MoErgo
glovebox moergo login
```

### `glovebox moergo logout`

Logout from MoErgo services.

```bash
glovebox moergo logout [OPTIONS]
```

**Examples:**
```bash
# Logout from MoErgo
glovebox moergo logout
```

### `glovebox moergo status`

Show MoErgo connection status.

```bash
glovebox moergo status [OPTIONS]
```

**Examples:**
```bash
# Show MoErgo status
glovebox moergo status
```

### `glovebox moergo keystore-info`

Show keystore information.

```bash
glovebox moergo keystore-info [OPTIONS]
```

**Examples:**
```bash
# Show keystore info
glovebox moergo keystore-info
```

---

## Cloud Commands

Manage cloud layout storage.

### `glovebox cloud upload`

Upload layouts to cloud storage.

```bash
glovebox cloud upload INPUT [OPTIONS]
```

**Examples:**
```bash
# Upload layout
glovebox cloud upload my_layout.json
```

### `glovebox cloud download`

Download layouts from cloud storage.

```bash
glovebox cloud download LAYOUT [OUTPUT] [OPTIONS]
```

**Examples:**
```bash
# Download layout
glovebox cloud download remote_layout local_layout.json
```

### `glovebox cloud list`

List cloud layouts.

```bash
glovebox cloud list [OPTIONS]
```

**Examples:**
```bash
# List cloud layouts
glovebox cloud list
```

### `glovebox cloud browse`

Browse cloud layouts interactively.

```bash
glovebox cloud browse [OPTIONS]
```

**Examples:**
```bash
# Browse cloud layouts
glovebox cloud browse
```

### `glovebox cloud delete`

Delete cloud layouts.

```bash
glovebox cloud delete LAYOUT [OPTIONS]
```

**Examples:**
```bash
# Delete cloud layout
glovebox cloud delete old_layout
```

---

## System Commands

### `glovebox status`

Show system status and diagnostics.

```bash
glovebox status [OPTIONS]
```

**Options:**
```bash
--verbose                # Show detailed diagnostics
--format FORMAT          # Output format (table, json)
```

**Examples:**
```bash
# Show system status
glovebox status

# Verbose diagnostics
glovebox status --verbose

# JSON output for scripting
glovebox status --format json
```

### `glovebox metrics`

View session metrics and statistics.

```bash
glovebox metrics COMMAND [OPTIONS]
```

**Subcommands:**
- `list` - List sessions
- `show` - Show session details
- `dump` - Export session data
- `clean` - Clean old sessions

**Examples:**
```bash
# List sessions
glovebox metrics list

# Show session details
glovebox metrics show SESSION_ID

# Clean old sessions
glovebox metrics clean
```

---

## Common Patterns

### Profile Usage
```bash
# Set default profile
glovebox config edit --set profile=glove80/v25.05

# Override for single command
glovebox layout compile layout.json output/ --profile corne/main

# Use keyboard-only profile
glovebox firmware flash firmware.uf2 --profile glove80
```

### Output Formats
```bash
# Table output (default)
glovebox profile list

# JSON for scripting
glovebox profile list --format json

# YAML for configuration
glovebox config show --format yaml
```

### Verbose Operations
```bash
# Verbose compilation
glovebox layout compile layout.json output/ --verbose

# Verbose system diagnostics
glovebox status --verbose

# Quiet mode (minimal output)
glovebox layout compile layout.json output/ --quiet
```

### Dry Run Operations
```bash
# Preview compilation
glovebox layout compile layout.json output/ --dry-run

# Preview firmware flash
glovebox firmware flash firmware.uf2 --dry-run

# Preview cache operations
glovebox cache clear --dry-run
```

---

## Exit Codes

Glovebox uses standard exit codes:

- `0` - Success
- `1` - General error
- `2` - Configuration error
- `3` - Validation error
- `4` - Compilation error
- `5` - Device error
- `6` - Network error
- `130` - Interrupted (Ctrl+C)

---

*This reference covers all available CLI commands. Use `glovebox COMMAND --help` for detailed help on specific commands.*