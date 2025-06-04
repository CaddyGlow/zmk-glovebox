# Keymap File Format and Processing

This document explains the keymap file format, processing flow, and the relationships between different file types in the Glovebox system.

## Keymap File Types

Glovebox works with several file types throughout the keymap processing and firmware build flow:

### JSON Keymap File (`.json`)

The primary source format for keyboard layouts, typically created with the [Glove80 Layout Editor](https://my.glove80.com/#/edit) or exported from a keyboard.

- **Content**: Complete keyboard layout definition including:
  - Layers and key bindings
  - Behaviors (hold-taps, macros, combos)
  - Custom devicetree code
  - Kconfig options
  - Layout metadata

- **Purpose**: Human-readable, shareable format that contains all necessary information for generating ZMK firmware files.

- **Generation**: Created by either:
  - The web-based [Glove80 Layout Editor](https://my.glove80.com/#/edit)
  - Exported from a physical keyboard
  - Created manually by advanced users

### ZMK Keymap File (`.keymap`)

ZMK Device Tree format file describing keyboard behavior.

- **Content**: Device Tree Source code containing:
  - Layer definitions
  - Key bindings
  - Behaviors (hold-taps, combos)
  - Macros
  - Other ZMK-specific nodes

- **Purpose**: Used by the ZMK build system to incorporate keyboard behavior into firmware

- **Generation**: Created by Glovebox's keymap compiler from the JSON keymap file

### ZMK Config File (`.conf`)

ZMK Kconfig options defining feature settings.

- **Content**: Key-value pairs controlling firmware features:
  - Bluetooth settings
  - Keyboard name
  - Display options
  - Power management settings
  - Other ZMK configuration options

- **Purpose**: Configures firmware features during the build process

- **Generation**: Created by Glovebox's keymap compiler from the JSON keymap file

### Firmware File (`.uf2`)

The compiled firmware binary in UF2 format.

- **Content**: Binary firmware image that can be flashed to a keyboard's microcontroller

- **Purpose**: Installed on the physical keyboard to update its behavior

- **Generation**: Created by the ZMK build system (through Glovebox's firmware build command)

## Processing Flow

The complete flow from editing to flashing:

1. **Design**: Create or modify a keyboard layout in the [Glove80 Layout Editor](https://my.glove80.com/#/edit)

2. **Export**: Download the JSON keymap file from the editor

3. **Compile Keymap**: Process the JSON into ZMK-compatible files
   ```bash
   glovebox keymap compile layout.json output/my_keymap --profile glove80/v25.05
   ```
   This creates:
   - `output/my_keymap.keymap` (ZMK devicetree source)
   - `output/my_keymap.conf` (ZMK config options)
   - `output/my_keymap.json` (Copy of the processed JSON)

4. **Build Firmware**: Compile these files into firmware
   ```bash
   glovebox firmware compile output/my_keymap.keymap output/my_keymap.conf --profile glove80/v25.05
   ```
   This creates:
   - `build/.../*.uf2` (Firmware binary file)

5. **Flash Firmware**: Transfer the firmware to the keyboard
   ```bash
   glovebox firmware flash build/.../glove80.uf2 --profile glove80/v25.05
   ```

## Component Management

For easier maintenance of complex layouts, Glovebox allows splitting and merging keymap components:

### Split Keymap

Split a complete keymap into manageable components:

```bash
glovebox keymap split my_layout.json my_layout/
```

This creates:
```
my_layout/
├── base.json           # Base configuration 
├── device.dtsi         # Custom device tree (if present)
├── keymap.dtsi         # Custom behaviors (if present)
└── layers/
    ├── DEFAULT.json    # Individual layer files
    ├── LOWER.json
    └── ...
```

### Merge Layers

Combine split components back into a complete keymap:

```bash
glovebox keymap merge my_layout/ --output new_layout.json
```

This approach enables:
- Version control of individual layers
- Mixing and matching layers between different keyboards
- Collaborative editing of keyboard layouts
- Simplified maintenance of complex layouts

## Keymap Components

The JSON keymap file contains several specialized components that define keyboard behavior:

### Macros

A macro behavior defines a sequence of actions (e.g., pressing keys, holding modifiers) that are grouped together, which can be assigned to a key or a combo to automate complex tasks on your keyboard.

### Hold-Taps

A hold-tap behavior allows a key to perform two different actions depending on how long you press it. If you tap the key briefly, it performs one action (e.g., typing a letter), and if you hold the key longer, it performs a different action (e.g., holding a modifier like Shift). This allows you to maximize your keyboard's functionality with the same key, depending on how you press it.

### Combos

Combos define rules which let you trigger a specific action when you press multiple keys at the same time. Instead of each key doing its usual function, the combo activates a new action only when the keys are pressed together within a short time interval.

### Input Listeners

An input listener watches for actions, like moving the mouse or clicking, and then sends those actions to the host after making any needed adjustments. This allows you to change how things like your mouse pointer behave by setting up special rules for the listener to follow.

### Custom Defined Behaviors

This is an advanced feature that allows a layout designer to inject text into the keymap DTSI file. It is very powerful and also requires a good understanding of the ZMK DTSI keymap file.

### Custom Device Tree

This is an advanced feature that allows you to specify additional ZMK configuration in the form of Device-Tree (DTSI) configuration. It is very powerful and also requires good understanding of ZMK Device-Tree configuration.

### KConfig Flags

These settings allow users to fine-tune various aspects of their ZMK firmware. Modifying these options requires a solid understanding of how the firmware works, as changes may impact system stability or performance. Making changes to these settings may also require a Factory Reset of the keyboard.