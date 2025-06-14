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

## Benefits of This Structure

1. **Easy to Copy**: Entire glove80/ directory can be copied as a unit
2. **Modular**: Individual components can be modified independently
3. **Reusable**: Components can be shared between different keyboard variants
4. **Maintainable**: Easier to update specific aspects (e.g., just firmwares or behaviors)
5. **Clean Separation**: Hardware vs firmware vs strategy concerns are separated

## Usage

### Using the Modular Configs

Use the new modular configurations:

```bash
# ZMK Config strategy
glovebox layout compile my_layout.json output/ --profile glove80_modular/v25.05

# MoErgo Docker strategy  
glovebox layout compile my_layout.json output/ --profile glove80_moergo_modular/v25.05
```

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

## Migration Path

The original monolithic configs still exist:
- `glove80.yaml` (1,087 lines)
- `glove80_moergo.yaml` (1,087 lines)

New modular configs:
- `glove80_modular.yaml` (uses this modular structure)
- `glove80_moergo_modular.yaml` (uses this modular structure)

The modular approach reduces duplication and makes maintenance much easier.