# Common Workflows

This guide provides step-by-step workflows for common Glovebox tasks, from basic layout compilation to advanced development and deployment scenarios.

## Basic Workflows

### First-Time Setup

Complete setup for new Glovebox installations:

```bash
# 1. Install and verify Glovebox
glovebox --version
glovebox status

# 2. Set default profile for your keyboard
glovebox profile list
glovebox config edit --set profile=glove80/v25.05

# 3. Test basic functionality
glovebox profile show glove80/v25.05
glovebox firmware devices

# 4. Download example layout
curl -O https://example.com/basic_layout.json

# 5. Test complete workflow
glovebox layout validate basic_layout.json
glovebox firmware compile basic_layout.json test_firmware/
glovebox firmware flash test_firmware/glove80_lh.uf2 --dry-run
```

### Simple Layout Compilation

Basic layout to firmware workflow:

```bash
# 1. Start with a layout file (JSON from Layout Editor)
# my_layout.json

# 2. Validate the layout
glovebox layout validate my_layout.json --profile glove80/v25.05

# 3. Compile to firmware
glovebox firmware compile my_layout.json firmware/ --profile glove80/v25.05

# 4. Flash to keyboard
glovebox firmware flash firmware/glove80_lh.uf2 --profile glove80
glovebox firmware flash firmware/glove80_rh.uf2 --profile glove80
```

### Layout Editing and Testing

Iterative layout development:

```bash
# 1. Make backup
cp my_layout.json backups/my_layout_$(date +%Y%m%d).json

# 2. Edit layout
glovebox layout edit my_layout.json \
  --set title="Gaming Layout v2" \
  --set version="2.0"

# 3. Test changes
glovebox layout validate my_layout.json --profile glove80/v25.05

# 4. Preview keymap
glovebox layout show my_layout.json --mode grid

# 5. Compile and test
glovebox firmware compile my_layout.json test_firmware/ --profile glove80/v25.05

# 6. Flash if satisfied
glovebox firmware flash test_firmware/glove80_lh.uf2 --profile glove80
```

## Development Workflows

### Layout Development Cycle

Professional layout development workflow:

```bash
# Project setup
mkdir my_keyboard_project
cd my_keyboard_project
mkdir layouts firmware backups logs

# Initialize with base layout
glovebox library fetch @base-layout-uuid layouts/base.json

# Development cycle
while true; do
  # Edit layout
  glovebox layout edit layouts/current.json --interactive
  
  # Validate changes
  if glovebox layout validate layouts/current.json --profile glove80/v25.05; then
    # Create backup
    cp layouts/current.json "backups/current_$(date +%Y%m%d_%H%M%S).json"
    
    # Build firmware
    glovebox firmware compile layouts/current.json firmware/ \
      --profile glove80/v25.05 \
      --verbose 2>&1 | tee "logs/build_$(date +%Y%m%d_%H%M%S).log"
    
    # Test on keyboard
    echo "Ready to flash firmware/glove80_*.uf2"
    break
  else
    echo "Validation failed, fix errors and try again"
  fi
done
```

### Multi-Keyboard Development

Develop layouts for multiple keyboards:

```bash
# Project structure
mkdir multi_keyboard_layout
cd multi_keyboard_layout
mkdir -p {glove80,corne,lily58}/{layouts,firmware}

# Base layout
cp base_layout.json glove80/layouts/layout.json
cp base_layout.json corne/layouts/layout.json  
cp base_layout.json lily58/layouts/layout.json

# Customize for each keyboard
glovebox layout edit glove80/layouts/layout.json \
  --set keyboard="glove80" \
  --set title="Glove80 Layout"

glovebox layout edit corne/layouts/layout.json \
  --set keyboard="corne" \
  --set title="Corne Layout" \
  --remove-layer "Unused"  # Corne has fewer keys

glovebox layout edit lily58/layouts/layout.json \
  --set keyboard="lily58" \
  --set title="Lily58 Layout"

# Validate all layouts
for keyboard in glove80 corne lily58; do
  echo "Validating $keyboard..."
  glovebox layout validate "$keyboard/layouts/layout.json" \
    --profile "$keyboard/main"
done

# Build all firmware
for keyboard in glove80 corne lily58; do
  echo "Building firmware for $keyboard..."
  glovebox firmware compile \
    "$keyboard/layouts/layout.json" \
    "$keyboard/firmware/" \
    --profile "$keyboard/main"
done
```

### Version Control Integration

Git workflow for layout management:

```bash
# Initialize repository
git init keyboard_layouts
cd keyboard_layouts

# Structure
mkdir -p {layouts,firmware,docs,scripts}
echo "firmware/" >> .gitignore
echo "*.log" >> .gitignore

# Add layouts to version control
git add layouts/
git commit -m "Initial layout commit"

# Development branch workflow
git checkout -b feature/gaming-layer

# Make changes
glovebox layout edit layouts/main.json --add-layer "Gaming"

# Test changes
glovebox layout validate layouts/main.json --profile glove80/v25.05
glovebox firmware compile layouts/main.json firmware/ --profile glove80/v25.05

# Commit changes
git add layouts/main.json
git commit -m "Add gaming layer with WASD bindings"

# Create build script
cat > scripts/build.sh << 'EOF'
#!/bin/bash
set -e

LAYOUT="layouts/main.json"
PROFILE="glove80/v25.05"
OUTPUT="firmware"

echo "Building firmware from $LAYOUT..."

glovebox layout validate "$LAYOUT" --profile "$PROFILE"
glovebox firmware compile "$LAYOUT" "$OUTPUT" --profile "$PROFILE" --verbose

echo "Firmware built successfully:"
ls -la "$OUTPUT"/*.uf2
EOF

chmod +x scripts/build.sh
git add scripts/build.sh
git commit -m "Add build script"

# Tag releases
git tag v1.0
```

## Production Workflows

### Release Preparation

Prepare layouts for release:

```bash
# Release workflow
RELEASE_VERSION="v2.1.0"
RELEASE_DIR="releases/$RELEASE_VERSION"

mkdir -p "$RELEASE_DIR"/{layouts,firmware,docs}

# Finalize layout
glovebox layout edit layouts/main.json \
  --set version="$RELEASE_VERSION" \
  --set release_date="$(date -I)"

# Comprehensive validation
echo "Validating layout..."
glovebox layout validate layouts/main.json \
  --profile glove80/v25.05 \
  --verbose \
  --check-behaviors \
  --check-features

# Build release firmware
echo "Building release firmware..."
glovebox firmware compile layouts/main.json "$RELEASE_DIR/firmware/" \
  --profile glove80/v25.05 \
  --mode release \
  --verbose 2>&1 | tee "$RELEASE_DIR/build.log"

# Copy artifacts
cp layouts/main.json "$RELEASE_DIR/layouts/"
glovebox layout show layouts/main.json --format json > "$RELEASE_DIR/layout_info.json"

# Generate documentation
echo "# Release $RELEASE_VERSION" > "$RELEASE_DIR/README.md"
echo "Built on $(date)" >> "$RELEASE_DIR/README.md"
echo "" >> "$RELEASE_DIR/README.md"
echo "## Files" >> "$RELEASE_DIR/README.md"
echo "- \`layouts/main.json\` - Layout file" >> "$RELEASE_DIR/README.md"
echo "- \`firmware/glove80_*.uf2\` - Firmware files" >> "$RELEASE_DIR/README.md"

# Create release archive
tar -czf "releases/glovebox-layout-$RELEASE_VERSION.tar.gz" -C "$RELEASE_DIR" .

echo "Release $RELEASE_VERSION prepared in $RELEASE_DIR"
```

### Batch Processing

Process multiple layouts efficiently:

```bash
# Batch layout processing
LAYOUTS_DIR="input_layouts"
OUTPUT_DIR="processed_layouts"
PROFILE="glove80/v25.05"

mkdir -p "$OUTPUT_DIR"/{layouts,firmware,logs}

# Process all JSON files
for layout_file in "$LAYOUTS_DIR"/*.json; do
  filename=$(basename "$layout_file" .json)
  echo "Processing $filename..."
  
  # Create output directory
  mkdir -p "$OUTPUT_DIR/firmware/$filename"
  
  # Validate layout
  if glovebox layout validate "$layout_file" --profile "$PROFILE"; then
    echo "✓ $filename validated"
    
    # Compile firmware
    if glovebox firmware compile "$layout_file" \
       "$OUTPUT_DIR/firmware/$filename/" \
       --profile "$PROFILE" \
       --verbose 2>&1 | tee "$OUTPUT_DIR/logs/$filename.log"; then
      echo "✓ $filename compiled"
      
      # Copy layout file
      cp "$layout_file" "$OUTPUT_DIR/layouts/"
    else
      echo "✗ $filename compilation failed"
    fi
  else
    echo "✗ $filename validation failed"
  fi
done

# Generate summary
echo "Batch processing complete:"
ls -la "$OUTPUT_DIR/firmware/"*/
```

### Continuous Integration

GitHub Actions workflow for layout validation:

```yaml
# .github/workflows/validate-layouts.yml
name: Validate Layouts

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  validate:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install Glovebox
      run: |
        python -m pip install --upgrade pip
        pip install glovebox
    
    - name: Set up Docker
      uses: docker/setup-buildx-action@v2
    
    - name: Validate layouts
      run: |
        for layout in layouts/*.json; do
          echo "Validating $layout..."
          glovebox layout validate "$layout" --profile glove80/v25.05
        done
    
    - name: Build test firmware
      run: |
        mkdir -p test_firmware
        glovebox firmware compile layouts/main.json test_firmware/ \
          --profile glove80/v25.05 \
          --verbose
    
    - name: Upload firmware artifacts
      uses: actions/upload-artifact@v3
      with:
        name: test-firmware
        path: test_firmware/*.uf2
```

## Maintenance Workflows

### System Maintenance

Regular Glovebox maintenance:

```bash
#!/bin/bash
# maintenance.sh - Regular Glovebox maintenance

echo "Glovebox Maintenance $(date)"
echo "================================"

# Check system status
echo "Checking system status..."
glovebox status --verbose

# Update profile cache
echo "Updating profiles..."
glovebox profile update

# Check for updates
echo "Checking for updates..."
glovebox config check-updates

# Clean old cache entries
echo "Cleaning cache..."
glovebox cache clear --older-than 7d

# Show cache status
echo "Cache status:"
glovebox cache show

# Clean old workspaces
echo "Cleaning workspaces..."
glovebox cache workspace cleanup

# Docker maintenance
echo "Docker maintenance..."
docker system prune -f

echo "Maintenance complete!"
```

### Backup and Restore

Backup Glovebox configuration and layouts:

```bash
# Backup script
BACKUP_DIR="glovebox_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup configuration
echo "Backing up configuration..."
cp -r ~/.config/glovebox/ "$BACKUP_DIR/config/"

# Backup layouts
echo "Backing up layouts..."
glovebox library list --format json > "$BACKUP_DIR/library_inventory.json"

# Backup custom profiles
if glovebox config show | grep -q profiles_paths; then
  echo "Backing up custom profiles..."
  mkdir -p "$BACKUP_DIR/profiles/"
  # Copy custom profile directories
fi

# Create archive
echo "Creating backup archive..."
tar -czf "$BACKUP_DIR.tar.gz" "$BACKUP_DIR"
rm -rf "$BACKUP_DIR"

echo "Backup created: $BACKUP_DIR.tar.gz"

# Restore script (example)
restore_backup() {
  BACKUP_FILE="$1"
  
  echo "Restoring from $BACKUP_FILE..."
  
  # Extract backup
  tar -xzf "$BACKUP_FILE"
  BACKUP_DIR="${BACKUP_FILE%.tar.gz}"
  
  # Restore configuration
  cp -r "$BACKUP_DIR/config/" ~/.config/glovebox/
  
  # Verify restoration
  glovebox status
  
  echo "Restore complete!"
}
```

### Health Monitoring

Monitor Glovebox health and performance:

```bash
#!/bin/bash
# health_check.sh - Monitor Glovebox health

LOG_FILE="glovebox_health.log"

log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG_FILE"
}

# System status check
if glovebox status --quiet; then
  log "STATUS: OK"
else
  log "STATUS: ERROR - System check failed"
fi

# Docker connectivity
if docker run --rm hello-world >/dev/null 2>&1; then
  log "DOCKER: OK"
else
  log "DOCKER: ERROR - Docker connectivity failed"
fi

# Cache performance
CACHE_SIZE=$(glovebox cache show --format json | jq -r '.total_size // "unknown"')
log "CACHE: Size: $CACHE_SIZE"

# Profile availability
PROFILE_COUNT=$(glovebox profile list --format json | jq '. | length')
log "PROFILES: Count: $PROFILE_COUNT"

# Test layout validation
if echo '{"version": 1, "keyboard": "test", "layers": []}' | \
   glovebox layout validate - --profile glove80/v25.05 >/dev/null 2>&1; then
  log "VALIDATION: OK"
else
  log "VALIDATION: ERROR - Basic validation failed"
fi

# Disk space check
DISK_USAGE=$(df -h ~/.cache/glovebox 2>/dev/null | awk 'NR==2 {print $5}' || echo "unknown")
log "DISK: Cache usage: $DISK_USAGE"

echo "Health check complete - see $LOG_FILE for details"
```

## Testing Workflows

### Layout Testing

Comprehensive layout testing:

```bash
# test_layout.sh - Comprehensive layout testing
LAYOUT_FILE="$1"
PROFILE="${2:-glove80/v25.05}"

if [ ! -f "$LAYOUT_FILE" ]; then
  echo "Usage: $0 <layout_file> [profile]"
  exit 1
fi

echo "Testing layout: $LAYOUT_FILE with profile: $PROFILE"

# Validation tests
echo "1. Basic validation..."
glovebox layout validate "$LAYOUT_FILE" --profile "$PROFILE"

echo "2. Behavior validation..."
glovebox layout validate "$LAYOUT_FILE" --profile "$PROFILE" --check-behaviors

echo "3. Feature compatibility..."
glovebox layout validate "$LAYOUT_FILE" --profile "$PROFILE" --check-features

# Compilation tests
echo "4. ZMK file generation..."
glovebox layout compile "$LAYOUT_FILE" test_output/ --profile "$PROFILE"

echo "5. Firmware compilation..."
glovebox firmware compile "$LAYOUT_FILE" test_firmware/ --profile "$PROFILE"

# Format tests
echo "6. JSON format validation..."
python -m json.tool "$LAYOUT_FILE" >/dev/null

echo "7. Layout display test..."
glovebox layout show "$LAYOUT_FILE" --mode grid

# Cleanup
rm -rf test_output/ test_firmware/

echo "All tests passed for $LAYOUT_FILE"
```

### Performance Testing

Test build performance and optimization:

```bash
# performance_test.sh - Test build performance
LAYOUT_FILE="$1"
PROFILE="glove80/v25.05"
ITERATIONS=5

echo "Performance testing: $LAYOUT_FILE"

# Cold build (no cache)
echo "Cold build test..."
glovebox cache clear --quiet
time glovebox firmware compile "$LAYOUT_FILE" /tmp/test_firmware1/ \
  --profile "$PROFILE" --quiet

# Warm build (with cache)
echo "Warm build test..."
for i in $(seq 1 $ITERATIONS); do
  echo "Iteration $i..."
  time glovebox firmware compile "$LAYOUT_FILE" "/tmp/test_firmware$i/" \
    --profile "$PROFILE" --quiet
done

# Cache efficiency
echo "Cache statistics:"
glovebox cache show --stats

# Cleanup
rm -rf /tmp/test_firmware*/
```

## Best Practices

### Workflow Organization

```bash
# Recommended project structure
my_keyboard_project/
├── layouts/
│   ├── main.json
│   ├── gaming.json
│   └── work.json
├── firmware/           # Generated, not in git
├── backups/
├── scripts/
│   ├── build.sh
│   ├── test.sh
│   └── maintenance.sh
├── docs/
│   └── README.md
└── .gitignore
```

### Error Handling

```bash
# Robust error handling in scripts
build_layout() {
  local layout="$1"
  local profile="$2"
  local output="$3"
  
  # Validate first
  if ! glovebox layout validate "$layout" --profile "$profile"; then
    echo "ERROR: Layout validation failed for $layout"
    return 1
  fi
  
  # Build with retry
  for attempt in 1 2 3; do
    if glovebox firmware compile "$layout" "$output" --profile "$profile"; then
      echo "SUCCESS: Built $layout on attempt $attempt"
      return 0
    fi
    
    echo "RETRY: Attempt $attempt failed, cleaning cache..."
    glovebox cache clear --tag compilation
  done
  
  echo "ERROR: Failed to build $layout after 3 attempts"
  return 1
}
```

### Documentation

```bash
# Document your workflows
cat > docs/workflow.md << 'EOF'
# My Keyboard Workflow

## Daily Development
1. Edit layouts with `glovebox layout edit`
2. Validate with `glovebox layout validate`
3. Test build with `glovebox firmware compile`
4. Flash with `glovebox firmware flash`

## Release Process
1. Update version numbers
2. Run full test suite
3. Build release firmware
4. Tag in git
5. Archive release files

## Maintenance
- Weekly: Run maintenance script
- Monthly: Update profiles and check for updates
- As needed: Clean cache and workspaces
EOF
```

---

*These workflows provide proven patterns for common Glovebox tasks. Adapt them to your specific needs and keyboard setups.*