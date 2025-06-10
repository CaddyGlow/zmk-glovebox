# Generic Docker Compiler Usage Guide

## Overview

The Generic Docker Compiler provides flexible, multi-strategy firmware compilation with modern west workspace support, intelligent caching, and extensible build systems.

**Important**: This compiler is designed for projects with proper west manifest repositories. For ZMK keyboard firmware builds, use the traditional Docker compiler instead, as ZMK repositories don't contain west.yml manifest files.

## When to Use

### Use Generic Docker Compiler for:
- Projects with west manifest files (west.yml)
- Custom Zephyr-based firmware projects
- Multi-repository projects managed by west
- Projects requiring custom build strategies (cmake, make, ninja)

### Use Traditional Docker Compiler for:
- ZMK keyboard firmware builds
- Single-repository projects without west manifests
- Projects using established Docker build patterns

## Key Features

### Build Strategies
- **west**: West workspace builds for projects with west manifests
- **cmake**: Direct CMake builds for custom projects
- **make**: Traditional make builds
- **ninja**: Ninja build system for fast compilation
- **custom**: User-defined build commands

### Performance Features
- **Workspace Caching**: 50%+ faster builds through intelligent workspace reuse
- **Cache Invalidation**: Automatic cache invalidation on configuration changes
- **Parallel Builds**: Multi-core compilation support
- **Optimized Volumes**: Efficient Docker volume mounting

### Configuration Flexibility
- **Profile Integration**: Full keyboard profile support
- **CLI Overrides**: Command-line parameter overrides for all options
- **Template System**: Configurable volume templates and environment variables
- **Board Targets**: Split keyboard support with multiple board targets

## Basic Usage

### ZMK West Workspace Build (Recommended)

```bash
# Basic ZMK build
glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05

# With workspace caching for faster subsequent builds
glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 --cache-workspace

# Split keyboard with specific board targets
glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 --board-targets glove80_lh,glove80_rh
```

### Alternative Build Strategies

```bash
# CMake build strategy
glovebox firmware compile keymap.keymap config.conf --profile custom/board --build-strategy cmake

# Make build strategy  
glovebox firmware compile keymap.keymap config.conf --profile custom/board --build-strategy make

# Ninja build strategy
glovebox firmware compile keymap.keymap config.conf --profile custom/board --build-strategy ninja
```

### CLI Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `--build-strategy` | Build strategy selection | `--build-strategy west` |
| `--cache-workspace` | Enable workspace caching | `--cache-workspace` |
| `--no-cache-workspace` | Disable workspace caching | `--no-cache-workspace` |
| `--board-targets` | Split keyboard targets | `--board-targets glove80_lh,glove80_rh` |
| `--verbose` | Verbose build output | `--verbose` |
| `--jobs` | Parallel job count | `--jobs 4` |

## Configuration

### Keyboard Profile Configuration

Add generic docker compiler configuration to your keyboard profile:

```yaml
# keyboards/my_keyboard.yaml
keyboard: my_keyboard
description: My Custom Keyboard
vendor: Custom Vendor
key_count: 36

build:
  methods:
    - method_type: generic_docker
      image: zmkfirmware/zmk-build-arm:stable
      build_strategy: west
      cache_workspace: true
      west_workspace:
        manifest_url: https://github.com/zmkfirmware/zmk.git
        manifest_revision: main
        workspace_path: /zmk-workspace
        config_path: config
        west_commands:
          - "west init -l config"
          - "west update"
      board_targets:
        - my_keyboard_left
        - my_keyboard_right
      environment_template:
        ZEPHYR_TOOLCHAIN_VARIANT: zephyr
        CMAKE_BUILD_TYPE: Release
      volume_templates:
        - "/host/path:/container/path:rw"
```

### West Workspace Configuration

For ZMK builds, configure the west workspace:

```yaml
west_workspace:
  manifest_url: https://github.com/zmkfirmware/zmk.git
  manifest_revision: main  # or specific tag/branch
  modules:
    - zephyr
    - zmk
  west_commands:
    # Additional commands after workspace initialization (optional)
    # Note: "west init" and "west update" are handled automatically
    - "west config build.board-dir /zmk-workspace/boards"
  workspace_path: /zmk-workspace
  config_path: config
```

## Performance Optimization

### Workspace Caching

Enable workspace caching for significantly faster builds:

```bash
# Enable caching (recommended)
glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 --cache-workspace
```

**Benefits:**
- 50-70% faster build times on subsequent builds
- Automatic cache invalidation on configuration changes
- Intelligent cache management with automatic cleanup
- Workspace reuse across similar configurations

### Cache Management

Cache locations and management:

```bash
# Cache location: /tmp/glovebox_cache/workspaces/
# Automatic cleanup after 7 days
# Cache validation checks:
#   - Manifest hash changes
#   - Configuration file changes  
#   - Cache age (24 hour limit)
#   - Cache version compatibility
```

## Troubleshooting

### Common Issues

**Docker not available:**
```bash
# Check Docker status
docker --version
docker info

# Start Docker service
sudo systemctl start docker
```

**Build failures:**
```bash
# Enable verbose output for debugging
glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 --verbose

# Clear workspace cache
rm -rf /tmp/glovebox_cache/workspaces/
```

**Permission issues:**
```bash
# Check Docker permissions
docker run hello-world

# Add user to docker group (requires logout/login)
sudo usermod -aG docker $USER
```

### Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
glovebox --debug firmware compile keymap.keymap config.conf --profile glove80/v25.05
```

### Build Strategy Validation

Verify your configuration supports the chosen build strategy:

```bash
# Check profile configuration
glovebox config show --profile my_keyboard/v1.0

# Validate build method availability
glovebox firmware compile --help
```

## Advanced Usage

### Custom Build Commands

Configure custom build commands for specialized workflows:

```yaml
build_strategy: custom
build_commands:
  - "mkdir -p /build"
  - "cd /zmk-workspace && west build -b my_board -d /build"
  - "cp /build/zephyr/zmk.uf2 /output/"
```

### Environment Templates

Customize the build environment:

```yaml
environment_template:
  ZEPHYR_TOOLCHAIN_VARIANT: zephyr
  CMAKE_BUILD_TYPE: Release
  BOARD_ROOT: /zmk-workspace/boards
  DTC_OVERLAY_FILE: /zmk-workspace/config/my_board.overlay
```

### Volume Templates

Configure custom volume mounting:

```yaml
volume_templates:
  - "/host/boards:/zmk-workspace/boards:ro"
  - "/host/modules:/zmk-workspace/modules:ro"
  - "/host/cache:/zmk-workspace/.cache:rw"
```

## Migration from Docker Compiler

The Generic Docker Compiler is fully backward compatible:

```bash
# Old docker compiler (still works)
glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05

# New generic docker compiler (same command, enhanced features)
glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 --cache-workspace
```

**Migration benefits:**
- Faster builds with workspace caching
- Modern ZMK west workspace support
- Multi-strategy build support
- Enhanced configuration flexibility
- Better error handling and diagnostics

## Best Practices

1. **Use West Strategy**: Recommended for all ZMK keyboards
2. **Enable Caching**: Always use `--cache-workspace` for development
3. **Profile Configuration**: Define build strategy in keyboard profiles
4. **Board Targets**: Specify explicit board targets for split keyboards
5. **Verbose Output**: Use `--verbose` for debugging build issues
6. **Resource Management**: Use `--jobs` to control CPU usage

## Support

For issues or questions:
1. Check this usage guide
2. Review the implementation plan: `docs/generic_docker_compiler_zmk_west_workspace_implementation.md`
3. Enable debug mode: `glovebox --debug firmware compile ...`
4. Check Docker and build environment setup
5. Validate keyboard profile configuration