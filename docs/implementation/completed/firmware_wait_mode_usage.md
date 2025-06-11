# Firmware Wait Mode Usage Guide

Wait mode enables real-time device detection for firmware flashing operations. Instead of failing immediately when no devices are found, wait mode monitors for device connections and provides live feedback.

## Basic Usage

### Enable Wait Mode via CLI
```bash
# Wait for devices with default settings
glovebox firmware flash firmware.uf2 --wait

# Custom timeout and polling
glovebox firmware flash firmware.uf2 --wait --timeout 120 --poll-interval 1.0

# Wait for multiple devices
glovebox firmware flash firmware.uf2 --wait --count 3 --timeout 180
```

### Configure via User Config
```yaml
# ~/.config/glovebox/config.yaml
firmware:
  flash:
    wait: true
    timeout: 120
    poll_interval: 0.5
    show_progress: true
    count: 2
```

## Configuration Options

| Setting | CLI Flag | Environment Variable | Default | Description |
|---------|----------|---------------------|---------|-------------|
| wait | `--wait/--no-wait` | `GLOVEBOX_FIRMWARE__FLASH__WAIT` | false | Enable device waiting |
| poll_interval | `--poll-interval` | `GLOVEBOX_FIRMWARE__FLASH__POLL_INTERVAL` | 0.5 | Polling interval (0.1-5.0s) |
| show_progress | `--show-progress/--no-show-progress` | `GLOVEBOX_FIRMWARE__FLASH__SHOW_PROGRESS` | true | Show progress updates |

## User Experience

### Without Wait Mode (Default)
```
$ glovebox firmware flash firmware.uf2
Found 0 compatible device(s)
❌ Flash operation failed: No compatible devices found
```

### With Wait Mode
```
$ glovebox firmware flash firmware.uf2 --wait --count 2
Waiting for 2 device(s)... (timeout: 60s)
Found device: GLV80-1234 [1/2]
Found device: GLV80-5678 [2/2]
✓ Starting flash operation...
✓ Successfully flashed 2 device(s)
```

## Precedence Rules

Configuration values are applied in this order (highest to lowest precedence):

1. **CLI flags** - `--wait`, `--poll-interval`, etc.
2. **Environment variables** - `GLOVEBOX_FIRMWARE__FLASH__WAIT=true`
3. **Config files** - `~/.config/glovebox/config.yaml`
4. **Defaults** - Built-in default values

## Tips

- Use wait mode when flashing multiple keyboards sequentially
- Set `poll_interval` higher (1.0-2.0) for slower systems
- Disable `show_progress` for automated scripts
- Configure persistent settings in user config for regular use