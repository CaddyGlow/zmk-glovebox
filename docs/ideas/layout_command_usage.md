## **Current Issues:**
- Too many single-purpose commands (19+ commands!)
- Inconsistent naming (`get-field` vs `set-field` vs just `show`)
- Related operations scattered across different commands
- Some commands do very similar things (`decompose`/`compose` vs `export-layer`/`import-layer`)

## **Redesigned Structure:**

### **Core Operations (Essential)**
```bash
# Main workflow commands
glovebox layout compile input.json output/  [--profile glove80/v25.05]
glovebox layout validate input.json         [--profile glove80/v25.05] 
glovebox layout show input.json            [--layer 0] [--compact]
```

### **Unified Edit Command**
```bash
# Replace get-field, set-field, add-layer, remove-layer, move-layer
glovebox layout edit layout.json [OPTIONS]

# Examples:
glovebox layout edit layout.json --get title
glovebox layout edit layout.json --set title="New Title"
glovebox layout edit layout.json --add-layer "NewLayer" --position 3
glovebox layout edit layout.json --remove-layer "OldLayer"
glovebox layout edit layout.json --move-layer "Symbol" --to-position 0
glovebox layout edit layout.json --copy-layer "Base" --as "NewBase"

# Batch operations:
glovebox layout edit layout.json \
  --set title="My Layout" \
  --add-layer "Gaming" \
  --remove-layer "Unused"

# Basic import another layer or layout json file we should support completion after the `:`
glovebox layout edit layout.json --add-layer "SuperLayer" --from a-layer-file.json
glovebox layout edit layout.json --add-layer "ImportedSymbol" --from other_layout.json:Symbol

# Batch operations still work
glovebox layout edit layout.json \
  --add-layer "SuperLayer" --from a-layer-file.json \
  --add-layer "ImportedSymbol" --from other_layout.json:Symbol \
  --set title="Updated Layout"
```

We should support json path for `set` and `add-layer`.
We should have support for tab completion event in the xpath with some caching.

This a example not all the field are valid bellow. That just so we ahve some example.
They are sort from by priority and complexity
```
# Import entire layer file (simple case)
glovebox layout edit layout.json --add-layer "SuperLayer" --from a-layer-file.json

# Import specific layer using JSON path (since we don't have the name in layers we should do some magic to match it layer_names list)
glovebox layout edit layout.json --add-layer "ImportedSymbol" --from "other_layout.json$.layers[?(@.name=='Symbol')]"

# Or simpler syntax with layer name (same here)
glovebox layout edit layout.json --add-layer "ImportedSymbol" --from "other_layout.json$.layers.Symbol"

# Import multiple layers at once
glovebox layout edit layout.json --add-layers --from "other_layout.json$.layers[0:2]"


# Import custom behaviors
glovebox layout edit layout.json --set "custom_defined_behaviors" --from "other_layout.json$.custom_defined_behaviors"

# Import metadata
glovebox layout edit layout.json --set "author" --from "other_layout.json$.author" 

# Short aliases for common patterns
--from "file.json:layername"           # shortcut for $.layers.layername
--from "file.json:behaviors"           # shortcut for $.custom_defined_behaviors
--from "file.json:meta"               # shortcut for $.author,$.description,etc

# Smart Completion

# Completion knows what you're trying to import
glovebox layout edit layout.json --add-layer "Test" --from "other.json$.<TAB>
# Prioritizes: layers (since you're adding a layer)

glovebox layout edit layout.json --set "custom_defined_behaviors" --from "other.json$.<TAB>
# Prioritizes: custom_defined_behaviors (since that's what you're setting)

# Array index completion with previews
glovebox layout edit layout.json --add-layer "Test" --from "other.json$.layers[<TAB>
# Shows:
# 0    (Base - QWERTY base layer)
# 1    (Symbol - Special characters)  
# 2    (Number - Numeric keypad)

# File completion first
glovebox layout edit layout.json --add-layer "Test" --from ~/layouts/<TAB>
# Shows: my-layout.json, gaming.json, work.json...

# Then JSON path completion
glovebox layout edit layout.json --add-layer "Test" --from ~/layouts/gaming.json$.<TAB>
# Parses the file and shows its structure

# Advance completion fetures
# Function/filter completion
glovebox layout edit layout.json --from "other.json$.layers[?(@.<TAB>
# Shows: name, type, bindings... (available fields for filtering)

# Value completion for filters
glovebox layout edit layout.json --from "other.json$.layers[?(@.name=='<TAB>
# Shows actual layer names: Base, Symbol, Number...

# Slice completion with hints
glovebox layout edit layout.json --from "other.json$.layers.Base.bindings[<TAB>
# Shows: 0:10 (first row), 10:20 (second row), 20:30 (third row)...
```

### **File Operations**
```bash
# Replace decompose, compose, export-layer, import operations
glovebox layout split layout.json --output-dir ./layers/     # was decompose
glovebox layout merge ./layers/ --output combined.json      # was compose  
glovebox layout export layout.json "LayerName" layer.json   # was export-layer
glovebox layout import base.json --add-from other.json      # combine imports
```

### **Version Management (Simplified)**
```bash
glovebox layout versions list [glove80]                     # was list-masters
glovebox layout versions import master-v42.json v42        # was import-master  
glovebox layout upgrade my-layout.json --to v42            # simplified upgrade
```

### **Comparison**
```bash
glovebox layout diff layout1.json layout2.json [--format json]
glovebox layout patch source.json changes.json --output result.json
```

### **Cloud Integration**
```bash
glovebox layout cloud upload/download/list/delete [args]   # was glove80 subcommands
```

## **Benefits:**
- **19 commands → 8 commands** (60% reduction)
- **Consistent patterns** - `edit` for modifications, `versions` for version ops
- **Batch operations** possible with unified `edit`
- **Logical grouping** - related operations under same command
- **Easier to learn** - fewer commands to remember

# Edit enhancement 
#
#
