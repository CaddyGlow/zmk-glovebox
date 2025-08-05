# Glove80 Modular Configuration

This directory contains a better organized, modular configuration for the Glove80 keyboard.

## Directory Structure

```
glove80/
├── README.md           # This file
├── main.yaml          # Main config that includes all components
├── hardware.yaml      # Physical keyboard properties
├── firmwares.yaml     # Available firmware versions
├── strategies.yaml    # Compilation strategies
├── kconfig.yaml       # ZMK configuration options
└── behaviors.yaml     # System behaviors (40 total)
```

## Usage

### Component Files

- **hardware.yaml**: Physical properties (key layout, flash methods, build config)
- **firmwares.yaml**: All available firmware versions (v25.05, v25.04-beta.1, etc.)
- **strategies.yaml**: Compilation methods (zmk_config, moergo docker)
- **kconfig.yaml**: ZMK configuration options (64 total options)
- **behaviors.yaml**: System behaviors (40 total behaviors including ZMK core and MoErgo-specific)
- **main.yaml**: Ties everything together with includes

### Extending the Configuration

To add a new firmware version, edit `firmwares.yaml`.
To add new behaviors, edit `behaviors.yaml`.
To modify hardware properties, edit `hardware.yaml`.

