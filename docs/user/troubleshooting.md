# Troubleshooting

This guide helps you diagnose and resolve common issues with Glovebox.

## Quick Diagnosis

### System Status Check

```bash
# Check overall system health
glovebox status

# Detailed diagnostics
glovebox status --verbose

# Profile-specific diagnostics
glovebox status --profile glove80/v25.05 --verbose

# JSON output for automated checks
glovebox status --format json
```

### Debug Mode

Enable debug mode for detailed information:

```bash
# Global debug mode
glovebox --debug [command]

# Environment variable
export GLOVEBOX_DEBUG=1
glovebox [command]

# Verbose logging levels
glovebox -v [command]    # Info level
glovebox -vv [command]   # Debug level with stack traces
```

## Common Issues

### Installation and Setup

#### Command Not Found

**Problem:** `glovebox: command not found`

**Solutions:**
```bash
# Check if installed
which glovebox

# Install via pip
pip install glovebox

# Install in development mode
pip install -e .

# Check PATH
echo $PATH

# Add to PATH if needed
export PATH="$HOME/.local/bin:$PATH"
```

#### Permission Issues

**Problem:** Permission denied errors

**Solutions:**
```bash
# Check file permissions
ls -la ~/.glovebox/

# Fix permissions
chmod 755 ~/.glovebox/
chmod 644 ~/.glovebox/config.yml

# Docker permission issues
sudo usermod -aG docker $USER
# Then log out and back in

# USB device permissions
sudo usermod -aG dialout $USER
```

#### Missing Dependencies

**Problem:** Missing Python packages or system dependencies

**Solutions:**
```bash
# Check Python version (requires 3.8+)
python --version

# Install missing dependencies
pip install -r requirements.txt

# System dependencies (Ubuntu/Debian)
sudo apt update
sudo apt install git python3-pip docker.io

# System dependencies (macOS)
brew install git python docker

# System dependencies (Arch Linux)
sudo pacman -S git python docker
```

### Configuration Issues

#### Invalid Configuration

**Problem:** Configuration file errors

**Solutions:**
```bash
# Validate configuration
glovebox config validate

# Check configuration syntax
glovebox config list --format json

# Reset to defaults
mv ~/.glovebox/config.yml ~/.glovebox/config.yml.backup
glovebox config list  # Creates new default config

# Import known good configuration
glovebox config import backup-config.yml
```

#### Profile Not Found

**Problem:** `Profile 'xxx' not found`

**Solutions:**
```bash
# List available keyboards
glovebox keyboard list

# List firmware versions
glovebox keyboard firmwares glove80

# Check profile format
# Correct: glove80/v25.05
# Incorrect: glove80-v25.05, glove80_v25.05

# Set valid default profile
glovebox config edit --set default_profile=glove80/v25.05
```

#### Auto-Detection Failure

**Problem:** Cannot auto-detect keyboard profile

**Solutions:**
```bash
# Check JSON keyboard field
jq '.keyboard' layout.json

# Disable auto-detection
glovebox layout compile layout.json --no-auto --profile glove80/v25.05

# Fix JSON keyboard field
glovebox layout edit layout.json --set keyboard=glove80

# Set environment variable
export GLOVEBOX_PROFILE=glove80/v25.05
```

### Layout Issues

#### Invalid Layout File

**Problem:** Layout validation errors

**Solutions:**
```bash
# Validate layout
glovebox layout validate layout.json

# Check JSON syntax
jq '.' layout.json

# Get detailed validation info
glovebox layout validate layout.json --format json

# Common fixes for layout issues:

# Missing required fields
glovebox layout edit layout.json --set keyboard=glove80

# Invalid layer structure
glovebox layout edit layout.json --list-layers

# Corrupted JSON
cp layout.json layout.json.backup
jq '.' layout.json.backup > layout.json
```

#### Compilation Errors

**Problem:** Layout compilation fails

**Solutions:**
```bash
# Debug compilation
glovebox --debug layout compile layout.json --profile glove80/v25.05

# Check profile validity
glovebox status --profile glove80/v25.05

# Try different firmware version
glovebox layout compile layout.json --profile glove80/main

# Clear cache and retry
glovebox cache clear --tag compilation
glovebox layout compile layout.json --profile glove80/v25.05

# Force rebuild
glovebox layout compile layout.json --profile glove80/v25.05 --force
```

#### Behavior Errors

**Problem:** Unknown behaviors or invalid behavior configurations

**Solutions:**
```bash
# Check available behaviors for profile
glovebox keyboard show glove80 --verbose

# Validate behavior syntax
glovebox layout validate layout.json --verbose

# Check behavior documentation
glovebox keyboard show glove80 --format json | jq '.behaviors'

# Common behavior fixes:
# Use correct behavior names (&kp, &mo, &lt, etc.)
# Check parameter counts and types
# Verify custom behavior definitions
```

### Docker Issues

#### Docker Not Running

**Problem:** Cannot connect to Docker daemon

**Solutions:**
```bash
# Check Docker status
docker version
docker info

# Start Docker service
sudo systemctl start docker     # Linux
brew services start docker      # macOS
# Windows: Start Docker Desktop

# Test Docker access
docker run hello-world

# Fix permissions
sudo usermod -aG docker $USER
# Log out and back in
```

#### Docker Image Issues

**Problem:** Cannot pull or run Docker images

**Solutions:**
```bash
# Pull ZMK image manually
docker pull zmkfirmware/zmk-build-arm:stable

# Check available images
docker images

# Clean up Docker
docker system prune

# Use alternative registry
glovebox config edit --set docker.registry=ghcr.io

# Check Docker storage space
docker system df
```

#### Build Container Failures

**Problem:** Docker build container exits with errors

**Solutions:**
```bash
# Check Docker logs
glovebox --debug layout compile layout.json --profile glove80/v25.05

# Increase build timeout
glovebox config edit --set docker.build_timeout=3600

# Try different build strategy
glovebox config edit --set compilation.strategy=moergo_nix

# Clear Docker cache
docker builder prune

# Check available disk space
df -h
```

### Firmware Issues

#### Device Not Found

**Problem:** Cannot detect keyboard device for flashing

**Solutions:**
```bash
# Check connected devices
lsblk                    # Linux
diskutil list           # macOS
wmic logicaldisk list   # Windows

# Put keyboard in bootloader mode:
# - Press reset button
# - Hold boot button while plugging in
# - Use firmware key combination

# Wait for device detection
glovebox firmware flash firmware.uf2 --profile glove80 --timeout 60

# Manual device specification
glovebox firmware flash firmware.uf2 --device /dev/sdb

# Check device patterns
glovebox keyboard show glove80
```

#### Flash Permission Errors

**Problem:** Permission denied when flashing

**Solutions:**
```bash
# Add user to dialout group (Linux)
sudo usermod -aG dialout $USER

# Use sudo for specific flash operation
sudo glovebox firmware flash firmware.uf2 --profile glove80

# Check device permissions
ls -la /dev/disk/by-label/

# Fix USB permissions (Linux)
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="1d50", ATTRS{idProduct}=="615e", MODE="0666"' | sudo tee /etc/udev/rules.d/99-glovebox.rules
sudo udevadm control --reload-rules
```

#### Firmware Build Failures

**Problem:** Firmware compilation fails

**Solutions:**
```bash
# Debug firmware build
glovebox --debug firmware compile layout.keymap config.conf --profile glove80/v25.05

# Check keymap syntax
# Common issues:
# - Missing semicolons
# - Invalid behavior references
# - Syntax errors in custom behaviors

# Validate with upstream tools
# Use ZMK's validation tools if available

# Try minimal configuration
# Start with basic keymap and add complexity gradually
```

### Cache Issues

#### Cache Corruption

**Problem:** Cache-related errors or inconsistent behavior

**Solutions:**
```bash
# Clear all cache
glovebox cache clear --all

# Clear specific cache tags
glovebox cache clear --tag compilation
glovebox cache clear --tag layout

# Check cache statistics
glovebox cache stats

# Disable cache temporarily
glovebox config edit --set cache_strategy=disabled

# Reset cache directory
rm -rf ~/.cache/glovebox/
glovebox cache stats  # Recreates cache
```

#### Out of Disk Space

**Problem:** Cache fills up disk space

**Solutions:**
```bash
# Check cache size
glovebox cache stats

# Clear old cache entries
glovebox cache clear --older-than 7

# Reduce cache size limit
glovebox config edit --set max_cache_size_gb=1

# Move cache to different location
glovebox config edit --set cache_dir=/path/to/larger/disk

# Clean up Docker cache too
docker system prune
```

### Performance Issues

#### Slow Compilation

**Problem:** Layout/firmware compilation takes too long

**Solutions:**
```bash
# Use shared cache
glovebox config edit --set cache_strategy=shared

# Increase parallel jobs
glovebox config edit --set compilation.parallel_jobs=8

# Use SSD for cache
glovebox config edit --set cache_dir=/path/to/ssd

# Enable Docker BuildKit
glovebox config edit --set docker.buildkit=true

# Check available resources
free -h    # Memory
df -h      # Disk space
nproc      # CPU cores
```

#### Memory Issues

**Problem:** Out of memory errors during builds

**Solutions:**
```bash
# Reduce parallel jobs
glovebox config edit --set compilation.parallel_jobs=2

# Increase Docker memory limit
# Docker Desktop: Settings -> Resources -> Memory

# Check memory usage
free -h
docker stats

# Use swap if available
sudo swapon --show
```

## Advanced Troubleshooting

### Log Analysis

#### Enable Detailed Logging

```bash
# Set log level in configuration
glovebox config edit --set log_level=DEBUG

# Enable file logging
glovebox config edit --set logging.file=~/.glovebox/debug.log

# View logs in real-time
tail -f ~/.glovebox/debug.log
```

#### Common Log Patterns

**Docker connection issues:**
```
ERROR: Cannot connect to the Docker daemon
```
Solution: Start Docker service and check permissions

**Profile resolution failures:**
```
WARNING: Cannot detect keyboard profile from JSON
```
Solution: Set profile explicitly or fix JSON keyboard field

**Cache errors:**
```
ERROR: Cache operation failed
```
Solution: Clear cache and check disk space

### Environment Debugging

#### Check Environment Variables

```bash
# Show all Glovebox environment variables
env | grep GLOVEBOX

# Important variables:
echo $GLOVEBOX_PROFILE
echo $GLOVEBOX_JSON_FILE
echo $GLOVEBOX_CONFIG_FILE
echo $GLOVEBOX_CACHE_DIR
echo $GLOVEBOX_DEBUG
```

#### Path Issues

```bash
# Check if paths exist and are accessible
glovebox config list --format json | jq -r '.keyboard_paths[]' | xargs -I {} test -d {} && echo "OK: {}" || echo "MISSING: {}"

# Check file permissions
stat ~/.glovebox/config.yml
```

### Network Issues

#### Repository Access

**Problem:** Cannot access Git repositories

**Solutions:**
```bash
# Test Git access
git clone https://github.com/zmkfirmware/zmk.git /tmp/zmk-test

# Check proxy settings
echo $HTTP_PROXY
echo $HTTPS_PROXY

# Configure Git proxy if needed
git config --global http.proxy http://proxy.company.com:8080

# Use SSH instead of HTTPS
glovebox config edit --set compilation.west.repository=git@github.com:zmkfirmware/zmk.git
```

#### Docker Registry Issues

**Problem:** Cannot pull Docker images

**Solutions:**
```bash
# Test registry access
docker pull zmkfirmware/zmk-build-arm:stable

# Use different registry
glovebox config edit --set docker.registry=ghcr.io

# Configure registry authentication if needed
docker login ghcr.io
```

## Getting Help

### Collect Diagnostic Information

When reporting issues, collect this information:

```bash
# System information
glovebox status --verbose --format json > glovebox-status.json

# Configuration
glovebox config list --defaults --format yaml > glovebox-config.yml

# Version information
glovebox --version
python --version
docker --version

# Log excerpt (last 100 lines)
tail -n 100 ~/.glovebox/debug.log > recent-logs.txt

# Error reproduction with debug
glovebox --debug [failing-command] 2>&1 | tee error-debug.log
```

### Minimal Reproduction

Create minimal examples to isolate issues:

```bash
# Minimal layout for testing
echo '{
  "keyboard": "glove80",
  "title": "Test Layout",
  "layer_names": ["Base"],
  "layers": [[
    "&kp Q", "&kp W", "&kp E", "&kp R", "&kp T",
    "&kp Y", "&kp U", "&kp I", "&kp O", "&kp P"
  ]]
}' > test-minimal.json

# Test with minimal layout
glovebox layout validate test-minimal.json --profile glove80/v25.05
```

### Support Channels

- **GitHub Issues**: Report bugs and feature requests
- **GitHub Discussions**: Ask questions and get community help
- **Documentation**: Check latest docs for updates
- **Examples**: Working examples in the repository

### Before Reporting Issues

1. **Check existing issues** on GitHub
2. **Update to latest version** of Glovebox
3. **Try with minimal configuration** to isolate the problem
4. **Collect diagnostic information** as shown above
5. **Include reproduction steps** in your report

Most issues can be resolved with the troubleshooting steps in this guide. For persistent problems, the community and maintainers are available to help through the official support channels.