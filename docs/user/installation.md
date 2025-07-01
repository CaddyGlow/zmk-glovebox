# Installation Guide

This guide will help you install and set up Glovebox on your system.

## System Requirements

### Operating System Support
- **Linux** (Ubuntu, Debian, Fedora, Arch, etc.)
- **macOS** (Intel and Apple Silicon)
- **Windows** (Windows 10/11 with WSL2 recommended)

### Dependencies
- **Python 3.11+** (required)
- **Docker** (required for firmware building)
- **USB access** (required for device flashing)
- **Git** (recommended for version management)

### Hardware Requirements
- At least 2GB free disk space (for Docker images and cache)
- USB port for keyboard flashing
- Internet connection for Docker images and library access

## Installation Methods

### Method 1: Using pip (Recommended)

```bash
# Install from PyPI
pip install glovebox

# Verify installation
glovebox --version
```

### Method 2: Using uv (Fast Package Manager)

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install glovebox
uv tool install glovebox

# Verify installation
glovebox --version
```

### Method 3: Development Installation

For development or the latest features:

```bash
# Clone the repository
git clone https://github.com/your-org/glovebox.git
cd glovebox

# Install in development mode
pip install -e .

# Or with uv
uv sync
uv run glovebox --version
```

## Docker Setup

Glovebox uses Docker for firmware compilation. Install Docker for your platform:

### Linux

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install docker.io docker-compose
sudo usermod -aG docker $USER

# Fedora
sudo dnf install docker docker-compose
sudo usermod -aG docker $USER

# Log out and back in for group changes to take effect
```

### macOS

1. Download and install [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop)
2. Start Docker Desktop from Applications
3. Verify: `docker --version`

### Windows (WSL2)

1. Install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop)
2. Enable WSL2 integration in Docker Desktop settings
3. Install Glovebox within WSL2 environment

## USB Permissions (Linux)

For device flashing on Linux, you may need to set up USB permissions:

```bash
# Add udev rules for common keyboard bootloaders
sudo tee /etc/udev/rules.d/50-keyboard-bootloaders.rules > /dev/null << 'EOF'
# RP2040 (Raspberry Pi Pico)
SUBSYSTEM=="usb", ATTRS{idVendor}=="2e8a", ATTRS{idProduct}=="0003", MODE="0666", GROUP="dialout"

# STM32 DFU
SUBSYSTEM=="usb", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="df11", MODE="0666", GROUP="dialout"

# Arduino/Atmel DFU
SUBSYSTEM=="usb", ATTRS{idVendor}=="03eb", ATTRS{idProduct}=="2ff4", MODE="0666", GROUP="dialout"

# Pro Micro/Elite-C
SUBSYSTEM=="usb", ATTRS{idVendor}=="1b4f", ATTRS{idProduct}=="9203", MODE="0666", GROUP="dialout"
SUBSYSTEM=="usb", ATTRS{idVendor}=="1b4f", ATTRS{idProduct}=="9205", MODE="0666", GROUP="dialout"
EOF

# Reload udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger

# Add yourself to dialout group
sudo usermod -aG dialout $USER
```

## Initial Setup

### 1. Run System Diagnostics

After installation, check that everything is working:

```bash
glovebox status
```

This will verify:
- Docker installation and connectivity
- USB device access
- Configuration file setup
- Available keyboard profiles

### 2. Create Configuration Directory

Glovebox will automatically create its configuration directory on first run:

- **Linux/macOS**: `~/.config/glovebox/`
- **Windows**: `%APPDATA%\glovebox\`

### 3. Set Default Profile

Configure your default keyboard and firmware:

```bash
# List available profiles
glovebox profile list

# Set default profile (example)
glovebox config edit --set profile=glove80/v25.05
```

### 4. Test Installation

Verify everything works with a simple command:

```bash
# Check available keyboards
glovebox profile list

# Show system status
glovebox status --verbose

# Test Docker connectivity
glovebox cache show
```

## Configuration

### Basic Configuration

Set up essential configuration options:

```bash
# Set default profile
glovebox config edit --set profile=glove80/v25.05

# Set cache directory (optional)
glovebox config edit --set cache_path=~/glovebox-cache

# Set icon mode (emoji, nerdfont, text)
glovebox config edit --set icon_mode=text

# Set default editor
glovebox config edit --set editor=vim
```

### Advanced Configuration

For advanced users, you can edit the configuration file directly:

```bash
# Open configuration in your editor
glovebox config edit

# Or edit specific sections
glovebox config edit --interactive
```

## Verification

### Test Layout Compilation

Try compiling an example layout:

```bash
# Download an example layout
curl -O https://raw.githubusercontent.com/your-org/glovebox/main/examples/layouts/glove80_basic.json

# Compile to keymap
glovebox layout compile glove80_basic.json output/ --profile glove80/v25.05

# Check output
ls output/
```

### Test Device Detection

Connect a keyboard in bootloader mode and test detection:

```bash
# List connected devices
glovebox firmware devices

# Check USB access
glovebox status --verbose
```

## Troubleshooting Installation

### Common Issues

#### Python Version
```bash
# Check Python version
python --version
# Should be 3.11 or higher

# If using multiple Python versions
python3.11 -m pip install glovebox
```

#### Docker Permissions
```bash
# Test Docker access
docker run hello-world

# If permission denied, add to docker group
sudo usermod -aG docker $USER
# Then log out and back in
```

#### USB Access Issues
```bash
# Check USB permissions
ls -l /dev/ttyACM*
ls -l /dev/ttyUSB*

# Add to dialout group if needed
sudo usermod -aG dialout $USER
```

#### Path Issues
```bash
# Check if glovebox is in PATH
which glovebox

# If not found, check pip install location
python -m site --user-base
# Add /bin to your PATH if needed
```

### Getting Help

If you encounter issues:

1. Run `glovebox status --verbose` to check system status
2. Check the [Troubleshooting Guide](troubleshooting.md)
3. Review the [FAQ](faq.md)
4. Check the project repository for known issues

## Next Steps

After successful installation:

1. **[Getting Started](getting-started.md)** - Your first layout compilation
2. **[Configuration](configuration.md)** - Customize Glovebox settings
3. **[Keyboard Profiles](profiles.md)** - Set up your keyboard profiles

---

*Congratulations! You now have Glovebox installed and ready to manage your keyboard firmware.*