# Troubleshooting Guide

This guide helps you diagnose and fix common issues with Glovebox. Start with the system diagnostics, then check the specific sections for your problem.

## Quick Diagnostics

### System Status Check

Always start here when encountering issues:

```bash
# Comprehensive system check
glovebox status --verbose

# Check specific components
glovebox status --docker --usb --config
```

This command checks:
- **Configuration**: Valid settings and profiles
- **Docker**: Installation and connectivity  
- **USB**: Device access and permissions
- **Cache**: Cache system and workspace status
- **Profiles**: Available keyboards and firmware versions

### Configuration Validation

Check your configuration:

```bash
# Show current configuration
glovebox config show

# Validate configuration
glovebox config show --validate

# Reset problematic configuration
glovebox config edit --reset
```

## Installation Issues

### Python Version Problems

**Symptoms:**
- `glovebox: command not found`
- ImportError or syntax errors
- Package installation failures

**Solutions:**

```bash
# Check Python version (must be 3.11+)
python --version
python3 --version

# Install with correct Python version
python3.11 -m pip install glovebox

# Check installation location
python -m site --user-base
# Add /bin to PATH if needed

# Fix PATH issues
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Package Installation Issues

**Symptoms:**
- pip install failures
- Missing dependencies
- Version conflicts

**Solutions:**

```bash
# Update pip
python -m pip install --upgrade pip

# Install with verbose output
pip install glovebox --verbose

# Use virtual environment
python -m venv glovebox-env
source glovebox-env/bin/activate
pip install glovebox

# Install from source (development)
git clone https://github.com/your-org/glovebox.git
cd glovebox
pip install -e .
```

### Permission Issues

**Symptoms:**
- Permission denied errors
- Cannot write to directories
- USB access denied

**Solutions:**

```bash
# Fix USB permissions (Linux)
sudo usermod -aG dialout $USER
sudo udevadm control --reload-rules
# Log out and back in

# Fix Docker permissions (Linux)
sudo usermod -aG docker $USER
# Log out and back in

# Fix configuration directory permissions
chmod 755 ~/.config/glovebox/
chmod 644 ~/.config/glovebox/config.yaml
```

## Docker Issues

### Docker Not Running

**Symptoms:**
- `Cannot connect to Docker daemon`
- `docker: command not found`
- Build failures with Docker errors

**Solutions:**

```bash
# Check Docker status
docker --version
docker info

# Start Docker (Linux)
sudo systemctl start docker
sudo systemctl enable docker

# Start Docker (macOS)
open -a Docker

# Start Docker (Windows)
# Start Docker Desktop from Start menu

# Test Docker connectivity
docker run hello-world
```

### Docker Permission Issues

**Symptoms:**
- `permission denied while trying to connect to Docker daemon`
- Docker commands require sudo

**Solutions:**

```bash
# Add user to docker group (Linux)
sudo usermod -aG docker $USER

# Apply group changes
newgrp docker
# Or log out and back in

# Test without sudo
docker run hello-world

# Alternative: use sudo for Glovebox
sudo glovebox firmware compile layout.json output/ --profile glove80/v25.05
```

### Docker Image Issues

**Symptoms:**
- Image pull failures
- Outdated images
- Build environment issues

**Solutions:**

```bash
# Update Docker images
docker pull zmkfirmware/zmk-build-arm:3.5
docker pull zmkfirmware/zmk-build-arm:3.2

# Check available images
docker images | grep zmk

# Clean old images
docker image prune -a

# Force image update in build
glovebox firmware compile layout.json output/ \
  --profile glove80/v25.05 \
  --update-docker
```

### Docker Resource Issues

**Symptoms:**
- Out of memory errors
- Disk space errors
- Build timeouts

**Solutions:**

```bash
# Check Docker resource usage
docker system df

# Clean Docker resources
docker system prune -a

# Increase Docker memory (Docker Desktop)
# Settings → Resources → Memory → 4GB+

# Free disk space
docker volume prune
docker container prune
docker image prune -a

# Use clean builds
glovebox firmware compile layout.json output/ \
  --profile glove80/v25.05 \
  --clean
```

## USB and Device Issues

### Device Not Detected

**Symptoms:**
- `glovebox firmware devices` shows no devices
- Flash commands fail with device errors
- Keyboard not in bootloader mode

**Solutions:**

```bash
# Check device detection
glovebox firmware devices --verbose

# Put keyboard in bootloader mode
# Method varies by keyboard - usually reset button double-tap

# Check USB connections
lsusb  # Linux
system_profiler SPUSBDataType  # macOS

# Check udev rules (Linux)
ls -la /etc/udev/rules.d/*keyboard*
ls -la /etc/udev/rules.d/*bootloader*

# Add udev rules if missing
sudo tee /etc/udev/rules.d/50-keyboard-bootloaders.rules > /dev/null << 'EOF'
# RP2040 (Raspberry Pi Pico)
SUBSYSTEM=="usb", ATTRS{idVendor}=="2e8a", ATTRS{idProduct}=="0003", MODE="0666", GROUP="dialout"
# STM32 DFU
SUBSYSTEM=="usb", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="df11", MODE="0666", GROUP="dialout"
EOF

sudo udevadm control --reload-rules
sudo udevadm trigger
```

### Flash Permission Issues

**Symptoms:**
- Permission denied during flash
- Cannot access /dev/ttyACM* devices
- Flash commands hang

**Solutions:**

```bash
# Check device permissions
ls -la /dev/ttyACM*
ls -la /dev/ttyUSB*

# Add user to dialout group
sudo usermod -aG dialout $USER
# Log out and back in

# Check group membership
groups | grep dialout

# Test device access
echo "test" > /dev/ttyACM0  # Should not give permission error
```

### Device Connection Issues

**Symptoms:**
- Device connects then disconnects
- Inconsistent device detection
- Flash failures mid-process

**Solutions:**

```bash
# Use different USB cable
# Try different USB port
# Avoid USB hubs when possible

# Wait for device stabilization
glovebox firmware flash firmware.uf2 --profile glove80 --wait

# Increase flash timeout
glovebox firmware flash firmware.uf2 \
  --profile glove80 \
  --timeout 60

# Manual device specification
glovebox firmware flash firmware.uf2 --device /dev/ttyACM0
```

## Configuration Issues

### Invalid Profile Errors

**Symptoms:**
- `Profile not found` errors
- `Invalid profile format` errors
- Build failures with profile issues

**Solutions:**

```bash
# List available profiles
glovebox profile list

# Check profile format
glovebox profile show glove80/v25.05

# Fix profile configuration
glovebox config edit --set profile=glove80/v25.05

# Reset to default profile
glovebox config edit --set profile=glove80/v25.05

# Add custom profile paths
glovebox config edit --add profiles_paths=/path/to/custom/profiles
```

### Cache Issues

**Symptoms:**
- Slow builds despite cache
- Cache errors or corruption
- Disk space issues

**Solutions:**

```bash
# Check cache status
glovebox cache show --verbose

# Clear problematic cache
glovebox cache clear

# Reset cache configuration
glovebox config edit --set cache_strategy=shared
glovebox config edit --set cache_path=~/.cache/glovebox

# Disable cache temporarily
glovebox firmware compile layout.json output/ \
  --profile glove80/v25.05 \
  --no-cache

# Clean old cache entries
glovebox cache clear --older-than 7d
```

### Configuration File Issues

**Symptoms:**
- Configuration not loading
- YAML syntax errors
- Settings not persisting

**Solutions:**

```bash
# Check configuration file location
ls -la ~/.config/glovebox/config.yaml

# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('~/.config/glovebox/config.yaml'))"

# Backup and reset configuration
cp ~/.config/glovebox/config.yaml ~/.config/glovebox/config.yaml.bak
rm ~/.config/glovebox/config.yaml
glovebox config show  # Recreates with defaults

# Edit configuration manually
vim ~/.config/glovebox/config.yaml

# Validate after changes
glovebox config show --validate
```

## Layout and Compilation Issues

### Layout Validation Failures

**Symptoms:**
- Layout validation errors
- JSON syntax errors
- Missing required fields

**Solutions:**

```bash
# Validate layout with verbose output
glovebox layout validate layout.json --verbose

# Check JSON syntax
python -m json.tool layout.json

# Fix common JSON issues
# - Missing commas
# - Trailing commas
# - Unescaped quotes
# - Invalid Unicode characters

# Use layout editor for complex fixes
glovebox layout edit layout.json --interactive

# Start with working example
curl -O https://example.com/working_layout.json
glovebox layout validate working_layout.json
```

### Compilation Errors

**Symptoms:**
- ZMK compilation failures
- Missing includes or behaviors
- Syntax errors in generated files

**Solutions:**

```bash
# Compile with verbose output
glovebox layout compile layout.json output/ \
  --profile glove80/v25.05 \
  --verbose

# Check generated files
glovebox layout compile layout.json output/ \
  --profile glove80/v25.05
cat output/layout.keymap

# Validate behavior usage
glovebox layout validate layout.json \
  --profile glove80/v25.05 \
  --check-behaviors

# Use simpler layout for testing
glovebox layout compile minimal_layout.json output/ \
  --profile glove80/v25.05
```

### Profile Compatibility Issues

**Symptoms:**
- Layout works with one profile but not another
- Missing keyboard-specific features
- Incorrect key assignments

**Solutions:**

```bash
# Check profile details
glovebox profile show glove80/v25.05
glovebox profile show corne/main

# Test layout with multiple profiles
glovebox layout validate layout.json --profile glove80/v25.05
glovebox layout validate layout.json --profile corne/main

# Use profile-specific layouts
# Some features are keyboard-specific

# Check behavior compatibility
glovebox layout show layout.json --profile glove80/v25.05 --verbose
```

## Build Failures

### ZMK Build Errors

**Symptoms:**
- West build failures
- Compilation errors in ZMK
- Missing dependencies

**Solutions:**

```bash
# Build with verbose output
glovebox firmware compile layout.json output/ \
  --profile glove80/v25.05 \
  --verbose

# Try clean build
glovebox firmware compile layout.json output/ \
  --profile glove80/v25.05 \
  --clean

# Check workspace
glovebox cache workspace show

# Reset workspace
glovebox cache workspace delete zmk
glovebox cache workspace create zmk --profile glove80/v25.05

# Use different strategy
glovebox firmware compile layout.json output/ \
  --profile glove80/v25.05 \
  --strategy moergo-nix
```

### Network and Download Issues

**Symptoms:**
- Workspace creation failures
- Git clone errors
- Download timeouts

**Solutions:**

```bash
# Check network connectivity
ping github.com
curl -I https://github.com/zmkfirmware/zmk

# Check proxy settings
echo $HTTP_PROXY
echo $HTTPS_PROXY

# Configure Git for proxy
git config --global http.proxy $HTTP_PROXY

# Use alternative repositories
glovebox firmware compile layout.json output/ \
  --profile glove80/v25.05 \
  --zmk-repository https://github.com/alternative/zmk.git

# Increase timeouts
glovebox firmware compile layout.json output/ \
  --profile glove80/v25.05 \
  --timeout 900
```

### Memory and Resource Issues

**Symptoms:**
- Out of memory errors
- Build timeouts
- System slowdown during builds

**Solutions:**

```bash
# Check available resources
free -h  # Linux
vm_stat  # macOS

# Close unnecessary applications
# Increase swap space if needed

# Use single-threaded builds
glovebox firmware compile layout.json output/ \
  --profile glove80/v25.05 \
  --jobs 1

# Build smaller layouts
# Split complex layouts into parts

# Monitor resource usage
top  # Linux/macOS
htop  # Enhanced version
```

## Library and MoErgo Issues

### MoErgo Connection Issues

**Symptoms:**
- Cannot login to MoErgo
- Library fetch failures
- Authentication errors

**Solutions:**

```bash
# Check MoErgo status
glovebox moergo status

# Login to MoErgo
glovebox moergo login

# Check credentials
glovebox moergo keystore-info

# Clear and re-login
glovebox moergo logout
glovebox moergo login

# Test library access
glovebox library search test
```

### Library Fetch Issues

**Symptoms:**
- Cannot download layouts
- Invalid UUIDs
- Network timeouts

**Solutions:**

```bash
# Verify UUID format
# Should be: 12345678-1234-1234-1234-123456789abc

# Test library search
glovebox library search "test layout"

# Use alternative download method
curl -o layout.json "https://moergo.com/api/layouts/UUID"

# Check library configuration
glovebox config show | grep library
```

## Performance Issues

### Slow Build Times

**Symptoms:**
- Very long compilation times
- Builds take much longer than expected
- System becomes unresponsive during builds

**Solutions:**

```bash
# Enable aggressive caching
glovebox config edit --set cache_strategy=shared

# Pre-warm cache
glovebox cache workspace create zmk --profile glove80/v25.05

# Use parallel builds (if resources allow)
glovebox firmware compile layout.json output/ \
  --profile glove80/v25.05 \
  --jobs 4

# Monitor build progress
glovebox firmware compile layout.json output/ \
  --profile glove80/v25.05 \
  --verbose \
  --progress
```

### Cache Performance Issues

**Symptoms:**
- Cache misses on repeated builds
- Cache corruption
- Disk space issues

**Solutions:**

```bash
# Check cache efficiency
glovebox cache show --stats

# Optimize cache settings
glovebox config edit --set cache_ttls.compilation=7200

# Clean cache periodically
glovebox cache clear --older-than 7d

# Reset cache if corrupted
glovebox cache clear
glovebox cache workspace cleanup
```

## Environment-Specific Issues

### Linux-Specific Issues

**Common Problems:**
- Permission issues with USB devices
- Docker group membership
- udev rules for keyboards

**Solutions:**

```bash
# Fix USB permissions
sudo usermod -aG dialout $USER

# Fix Docker permissions
sudo usermod -aG docker $USER

# Install udev rules
sudo tee /etc/udev/rules.d/50-keyboard-bootloaders.rules > /dev/null << 'EOF'
# RP2040, STM32, Atmel, Pro Micro bootloaders
SUBSYSTEM=="usb", ATTRS{idVendor}=="2e8a", ATTRS{idProduct}=="0003", MODE="0666", GROUP="dialout"
SUBSYSTEM=="usb", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="df11", MODE="0666", GROUP="dialout"
SUBSYSTEM=="usb", ATTRS{idVendor}=="03eb", ATTRS{idProduct}=="2ff4", MODE="0666", GROUP="dialout"
SUBSYSTEM=="usb", ATTRS{idVendor}=="1b4f", ATTRS{idProduct}=="9203", MODE="0666", GROUP="dialout"
EOF

sudo udevadm control --reload-rules
sudo udevadm trigger
```

### macOS-Specific Issues

**Common Problems:**
- Homebrew conflicts
- Python version management
- Docker Desktop issues

**Solutions:**

```bash
# Use Python from Homebrew
brew install python@3.11
/opt/homebrew/bin/python3.11 -m pip install glovebox

# Fix PATH for Homebrew
echo 'export PATH="/opt/homebrew/bin:$PATH"' >> ~/.zshrc

# Docker Desktop issues
# Restart Docker Desktop
# Check Docker Desktop settings for resource limits
```

### Windows/WSL2-Specific Issues

**Common Problems:**
- WSL2 integration issues
- Docker Desktop configuration
- USB device passthrough

**Solutions:**

```bash
# Install in WSL2, not Windows directly
# Use Docker Desktop with WSL2 integration enabled

# WSL2 Docker integration
# Docker Desktop → Settings → Resources → WSL Integration

# USB device access (requires additional setup)
# May need usbipd for USB device forwarding
```

## Getting Help

### Debug Information Collection

When reporting issues, collect this information:

```bash
# System information
glovebox status --verbose

# Configuration dump
glovebox config show --format yaml

# Build logs
glovebox firmware compile layout.json output/ \
  --profile glove80/v25.05 \
  --verbose 2>&1 | tee debug.log

# Cache information
glovebox cache show --verbose

# Profile information
glovebox profile show glove80/v25.05 --verbose
```

### Log Files

Locate and examine log files:

```bash
# Default log locations
~/.config/glovebox/logs/     # Linux/macOS
%APPDATA%\glovebox\logs\     # Windows

# Enable debug logging
glovebox config edit --set log_level=DEBUG

# View recent logs
tail -f ~/.config/glovebox/logs/glovebox.log
```

### Community Resources

- **GitHub Issues**: Report bugs and feature requests
- **Documentation**: Check the complete documentation
- **Discord/Forums**: Community discussion and help
- **Examples**: Working layout examples and configurations

### Emergency Recovery

If Glovebox is completely broken:

```bash
# Reset everything to defaults
rm -rf ~/.config/glovebox/
rm -rf ~/.cache/glovebox/

# Clear Docker state
docker system prune -a

# Reinstall Glovebox
pip uninstall glovebox
pip install glovebox

# Verify installation
glovebox status
```

---

*Most issues can be resolved with the steps in this guide. Start with system diagnostics and work through the relevant sections for your specific problem.*