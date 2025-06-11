# Generic Docker Compiler Usage Guide

## Overview

The Generic Docker Compiler provides flexible, multi-strategy firmware compilation with modern west workspace support, intelligent caching, and extensible build systems.

**Important**: This compiler supports both ZMK config template repositories (recommended) and traditional west manifest projects. Use this compiler for modern ZMK builds with `config/west.yml` and `build.yaml` files.

## When to Use

### Use Generic Docker Compiler for:
- **ZMK Config Repositories** - Projects using the ZMK config template pattern with `config/west.yml` and `build.yaml`
- **Traditional West Workspaces** - Projects with west manifest files (west.yml)
- **Custom Zephyr-based firmware projects** - Multi-repository projects managed by west
- **Alternative Build Systems** - Projects requiring custom build strategies (cmake, make, ninja)

### Use Traditional Docker Compiler for:
- **Legacy ZMK builds** - Direct ZMK repository builds without config repositories
- **Simple single-repository projects** - Projects without west manifests
- **Established Docker workflows** - Projects using established Docker build patterns

## Key Features

### Build Strategies
- **zmk_config**: ZMK config repository builds with `config/west.yml` and `build.yaml` (recommended for ZMK)
- **west**: Traditional west workspace builds for projects with west manifests
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

### ZMK Config Repository Build (Recommended for ZMK)

```bash
# Using ZMK config repository pattern
glovebox firmware compile keymap.keymap config.conf --profile corne/main

# With workspace caching for faster subsequent builds
glovebox firmware compile keymap.keymap config.conf --profile corne/main --cache-workspace

# Force specific build strategy
glovebox firmware compile keymap.keymap config.conf --profile corne/main --build-strategy zmk_config
```

### ZMK West Workspace Build (Traditional)

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

## ZMK Config Repository Configuration

The Generic Docker Compiler now supports the modern ZMK config repository pattern, which is the recommended approach for ZMK keyboard builds.

### What is a ZMK Config Repository?

A ZMK config repository is a standalone repository that:
- Contains a `config/west.yml` manifest file that references the main ZMK firmware
- Includes a `build.yaml` file that defines which boards and shields to build
- Uses `west init -l config` to initialize from the local manifest
- Automatically generates build commands based on `build.yaml` targets

### ZMK Config Repository Structure

```
my-zmk-config/
├── config/
│   ├── west.yml          # West manifest pointing to ZMK firmware
│   ├── keymap.keymap     # Your custom keymap
│   └── config.conf       # ZMK configuration options
├── build.yaml            # Build targets configuration
└── README.md
```

### Example ZMK Config Repository Configuration

```yaml
# keyboards/corne.yaml
compile_methods:
  - method_type: generic_docker
    image: zmkfirmware/zmk-build-arm:stable
    build_strategy: zmk_config
    cache_workspace: true
    zmk_config_repo:
      config_repo_url: "https://github.com/example/corne-zmk-config.git"
      config_repo_revision: "main"
      workspace_path: "/zmk-config-workspace"
      config_path: "config"
      build_yaml_path: "build.yaml"
      west_commands:
        - "west init -l config"
        - "west update"
    environment_template:
      ZEPHYR_TOOLCHAIN_VARIANT: "zephyr"
    # Build commands auto-generated from build.yaml
    build_commands: []
    # Volume mappings auto-generated
    volume_templates: []
```

### Example build.yaml File

```yaml
# build.yaml in your ZMK config repository
board: ["nice_nano_v2"]
shield: ["corne_left", "corne_right"]
include:
  - board: nice_nano_v2
    shield: corne_left
    cmake-args: ["-DEXTRA_CONFIG=left"]
    artifact-name: corne_left
  - board: nice_nano_v2  
    shield: corne_right
    cmake-args: ["-DEXTRA_CONFIG=right"]
    artifact-name: corne_right
```

### Example config/west.yml File

```yaml
# config/west.yml in your ZMK config repository
manifest:
  remotes:
    - name: zmkfirmware
      url-base: https://github.com/zmkfirmware
  projects:
    - name: zmk
      remote: zmkfirmware
      revision: main
      import: app/west.yml
  self:
    path: config
```

### Benefits of ZMK Config Repository Pattern

1. **Automatic Build Generation**: Build commands are automatically generated from `build.yaml`
2. **Modern ZMK Support**: Uses the latest ZMK config repository pattern
3. **Simplified Configuration**: Less manual configuration required
4. **Board Target Management**: Automatic handling of multiple board/shield combinations
5. **Workspace Caching**: Full support for intelligent workspace caching
6. **GitHub Actions Integration**: Compatible with ZMK's unified config template

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

1. **Use ZMK Config Strategy**: Recommended for all modern ZMK keyboards using config repositories
2. **Enable Caching**: Always use `--cache-workspace` for development builds
3. **Profile Configuration**: Define build strategy in keyboard profiles for consistency
4. **Build.yaml Targets**: Use `build.yaml` to define board/shield combinations automatically
5. **Environment Variables**: Use path expansion (`$HOME`, `~`) in workspace paths
6. **Verbose Output**: Use `--verbose` for debugging build issues
7. **Resource Management**: Use `--jobs` to control CPU usage during compilation

## Support

For issues or questions:
1. Check this usage guide
2. Review the implementation plan: `docs/generic_docker_compiler_zmk_west_workspace_implementation.md`
3. Enable debug mode: `glovebox --debug firmware compile ...`
4. Check Docker and build environment setup
5. Validate keyboard profile configuration