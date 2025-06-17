# Keymap Version Management Implementation Plan

**Status: ✅ COMPLETED** - Implementation finished and documented

## Overview

Users need to upgrade their customized keymaps when new master versions are released (e.g., v41 → v42-pre) while preserving their customizations. This document details a pragmatic implementation that follows CLAUDE.md principles: simple, clear, and focused.

## User Workflow

### Current Manual Process (8+ steps)
1. Download new master version from Layout Editor
2. Manually clean filename
3. Decompose old master, new master, and custom version
4. Manually diff directories
5. Copy and edit files
6. Compose new version
7. Compile and test
8. Rollback if issues

### New Simplified Process (3 steps)
```bash
# 1. Import new master version
glovebox layout import-master ~/Downloads/glorious-v42-pre.json --name v42-pre

# 2. Upgrade custom layout  
glovebox layout upgrade my-custom-v41.json --to-master v42-pre

# 3. Test (existing commands)
glovebox firmware compile my-custom-v42-pre.json --profile glove80/v25.05
```

## Implementation Details

### Phase 1: Core Commands (MVP)

#### 1.1 Import Master Command
```python
# glovebox/cli/commands/layout.py - Add to existing layout_app

@layout_app.command()
def import_master(
    json_file: Path,
    name: str,
    force: bool = False
) -> None:
    """Import a master layout version for future upgrades."""
    # Store in: ~/.glovebox/masters/{keyboard}/{name}.json
    # Extract metadata: version, date, creator
    # Validate it's a complete layout
```

**Storage Structure:**
```
~/.glovebox/
└── masters/
    └── glove80/
        ├── v41.json
        ├── v42-pre.json
        └── versions.yaml  # Metadata tracking
```

#### 1.2 Upgrade Command
```python
@layout_app.command()
def upgrade(
    custom_layout: Path,
    to_master: str,
    output: Path = None,  # Default: {input}-{to_master}.json
    strategy: str = "preserve-custom"  # Simple strategy only
) -> None:
    """Upgrade custom layout to new master version preserving customizations."""
    # 1. Load custom layout and identify its base version
    # 2. Load old master and new master  
    # 3. Detect customizations (diff old master vs custom)
    # 4. Apply customizations to new master
    # 5. Save result with updated metadata
```

**Simple Merge Strategy:**
- Preserve all custom layers (by name)
- Preserve all custom behaviors (hold-taps, combos, macros)
- Update only non-customized layers from new master
- Keep custom config parameters
- Log what was preserved vs updated

### Phase 2: Firmware Tracking

#### 2.1 Enhanced Metadata Model
```python
# glovebox/layout/models.py - Extend existing LayoutMetadata

class LayoutMetadata(BaseModel):
    # Existing fields...
    
    # Version tracking (new)
    version: str = Field(default="1.0.0")
    base_version: str = Field(default="")  # Master version this is based on
    base_layout: str = Field(default="")   # e.g., "glorious-engrammer"
    
    # Firmware tracking (new)
    last_firmware_build: dict[str, Any] = Field(default_factory=dict)
    # Structure: {
    #     "date": "2024-01-15T10:30:00Z",
    #     "profile": "glove80/v25.05",
    #     "firmware_path": "firmware/my-layout-v42.uf2",
    #     "firmware_hash": "sha256:abc123...",
    #     "build_id": "8984a4e0-v25.05-598b0350"
    # }
```

#### 2.2 Update Firmware Compile
```python
# glovebox/cli/commands/firmware.py - Enhance existing compile command

# After successful compilation:
# 1. Calculate firmware hash
# 2. Update layout's metadata with build info
# 3. Save updated layout file (preserves firmware link)
```

### Phase 3: Simple Diff/Compare

#### 3.1 Diff Command  
```python
@layout_app.command()
def diff(
    layout1: Path,
    layout2: Path,
    output_format: str = "summary"  # summary or detailed
) -> None:
    """Compare two layouts showing differences."""
    # Simple text-based diff output
    # Focus on: layers changed, behaviors added/removed
    # No interactive UI - just clear text output
```

### Implementation Priority

1. **Week 1**: Import-master and basic version tracking
2. **Week 2**: Upgrade command with simple merge
3. **Week 3**: Firmware tracking integration  
4. **Week 4**: Diff command and testing

### File Organization

Keep it simple - use existing patterns:

```
# User's working directory
my-keymaps/
├── my-custom-v41.json          # Current version
├── my-custom-v42-pre.json      # Upgraded version
└── firmware/
    ├── my-custom-v41.uf2       # Previous firmware
    └── my-custom-v42-pre.uf2   # New firmware

# Glovebox managed
~/.glovebox/
└── masters/
    └── glove80/
        ├── v41.json
        └── v42-pre.json
```

### Code Reuse Strategy

1. **Use existing services:**
   - `LayoutService` for decompose/compose operations
   - `FileAdapter` for file operations
   - Existing validation from layout commands

2. **Minimal new code:**
   - One new file: `glovebox/layout/version_manager.py`
   - Extend existing CLI commands, don't create new module
   - Reuse existing models with minimal additions

3. **No new dependencies:**
   - Use Python's difflib for comparisons
   - Use existing pathlib for file operations
   - Keep metadata in existing JSON structure

### Error Handling

- Clear error messages when master version not found
- Warn about potential conflicts, don't block
- Always create backup before upgrade
- Log all operations for debugging

### Testing Strategy

1. **Unit tests**: Version detection, merge logic
2. **Integration tests**: Full upgrade workflow
3. **Test data**: Use existing test layouts in tests_data/

### Success Metrics

- Reduce upgrade time from 30+ minutes to <5 minutes
- Zero data loss (all customizations preserved)
- Clear audit trail (what changed and why)
- Works with existing glovebox commands

## Next Steps

1. Review and approve this plan
2. Create `version_manager.py` with core logic
3. Add CLI commands to existing `layout.py`
4. Update models with version fields
5. Write tests
6. Update user documentation

## Non-Goals (Avoiding Over-Engineering)

- ❌ No GUI/web interface
- ❌ No complex merge algorithms  
- ❌ No automatic conflict resolution
- ❌ No version control system (use git separately)
- ❌ No cloud sync or sharing features
- ❌ No automatic updates

Keep it simple, make it work, help users upgrade their keymaps efficiently.