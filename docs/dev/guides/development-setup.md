# Development Environment Setup

This guide provides a comprehensive setup for developing Glovebox, covering all tools, dependencies, and workflows needed for effective contribution.

## Prerequisites

### Required Software

- **Python 3.11+** (required minimum version)
- **Docker** (for firmware compilation)
- **Git** (for version control)

### Recommended Tools

- **uv** (modern Python package manager - faster than pip)
- **VS Code** or **PyCharm** (IDE with Python support)
- **Terminal** with modern shell (zsh, fish, or bash)

## Installation Guide

### 1. Install Python 3.11+

#### On Ubuntu/Debian
```bash
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev
```

#### On macOS
```bash
# Using Homebrew
brew install python@3.11

# Or using pyenv
pyenv install 3.11.0
pyenv global 3.11.0
```

#### On Windows
Download Python 3.11+ from [python.org](https://python.org) or use Windows Subsystem for Linux (WSL).

### 2. Install Docker

#### On Ubuntu/Debian
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Verify installation
docker --version
```

#### On macOS
```bash
# Install Docker Desktop
brew install --cask docker

# Or download from docker.com
```

#### On Windows
Download Docker Desktop from [docker.com](https://docker.com) or use Docker in WSL.

### 3. Install uv (Recommended)

```bash
# Install uv (cross-platform)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or using pip
pip install uv

# Verify installation
uv --version
```

## Project Setup

### 1. Clone the Repository

```bash
# Clone the repository
git clone https://github.com/your-org/glovebox.git
cd glovebox

# Check your location
pwd  # Should show /path/to/glovebox
```

### 2. Set Up Python Environment

#### Using uv (Recommended)

```bash
# Install all dependencies including development tools
uv sync

# This creates a virtual environment and installs:
# - Main dependencies (pydantic, typer, rich, etc.)
# - Development dependencies (pytest, ruff, mypy, etc.)
# - Pre-commit hooks
# - Glovebox in editable mode

# Activate the environment
source .venv/bin/activate  # On Unix/macOS
# or
.venv\Scripts\activate     # On Windows
```

#### Using pip (Alternative)

```bash
# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate  # On Unix/macOS
# or
.venv\Scripts\activate     # On Windows

# Install in editable mode with development dependencies
pip install -e ".[dev]"
```

### 3. Install Pre-commit Hooks

```bash
# Install pre-commit hooks for code quality
pre-commit install

# Test the hooks
pre-commit run --all-files
```

### 4. Verify Installation

```bash
# Run tests to verify everything works
make test

# Or manually
uv run pytest

# Test CLI functionality
uv run python -m glovebox.cli --help
```

## Development Environment Configuration

### IDE Setup

#### VS Code Configuration

Create `.vscode/settings.json`:

```json
{
    "python.defaultInterpreterPath": "./.venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.ruffEnabled": true,
    "python.linting.mypyEnabled": true,
    "python.formatting.provider": "none",
    "[python]": {
        "editor.defaultFormatter": "charliermarsh.ruff",
        "editor.formatOnSave": true,
        "editor.codeActionsOnSave": {
            "source.fixAll.ruff": true,
            "source.organizeImports.ruff": true
        }
    },
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": ["tests/"],
    "files.exclude": {
        "**/__pycache__": true,
        "**/*.pyc": true,
        ".coverage": true,
        ".mypy_cache": true,
        ".pytest_cache": true,
        ".ruff_cache": true
    }
}
```

Install recommended VS Code extensions:
- Python
- Ruff
- Python Docstring Generator
- GitLens

#### PyCharm Configuration

1. **Open project** in PyCharm
2. **Configure interpreter**: Settings → Project → Python Interpreter → Add → Existing environment → `.venv/bin/python`
3. **Enable tools**:
   - Settings → Tools → External Tools → Add ruff, mypy
   - Settings → Code Style → Python → Set line length to 88
4. **Configure run configurations** for pytest and CLI commands

### Shell Configuration

Add helpful aliases to your shell configuration (`.bashrc`, `.zshrc`, etc.):

```bash
# Glovebox development aliases
alias gb="uv run python -m glovebox.cli"
alias gbt="uv run pytest"
alias gbl="uv run ruff check ."
alias gbf="uv run ruff format ."
alias gbm="uv run mypy glovebox/"
alias gbc="uv run pytest --cov=glovebox"

# Quick quality checks
alias gbqa="uv run ruff check . --fix && uv run ruff format . && uv run mypy glovebox/ && uv run pytest"
```

## Development Workflow

### Daily Development Commands

```bash
# Start development
cd glovebox
source .venv/bin/activate  # If not using uv run

# Pull latest changes
git pull origin dev

# Install/update dependencies
uv sync

# Make your changes...

# Quality checks (MANDATORY before commits)
make lint          # Run linting with ruff
make format        # Format code with ruff
make test          # Run all tests
make coverage      # Run tests with coverage

# Or individually
uv run ruff check . --fix    # Fix linting issues
uv run ruff format .         # Format code
uv run mypy glovebox/        # Type checking
uv run pytest               # Run tests
```

### Testing Your Changes

```bash
# Run specific test modules
uv run pytest tests/test_layout/
uv run pytest tests/test_firmware/
uv run pytest tests/test_compilation/

# Run with coverage
uv run pytest --cov=glovebox --cov-report=html

# Run integration tests
uv run pytest tests/test_integration/

# Test CLI commands
uv run python -m glovebox.cli layout compile --help
uv run python -m glovebox.cli firmware flash --help
```

### Code Quality Verification

```bash
# Full quality check (run before committing)
make lint && make test

# Individual checks
uv run ruff check .                    # Linting
uv run ruff format .                   # Formatting
uv run mypy glovebox/                  # Type checking
uv run pytest                         # Tests
uv run pytest --cov=glovebox          # Coverage
```

## Development Tools Deep Dive

### Ruff (Linting and Formatting)

Ruff is used for code linting and formatting:

```bash
# Check for issues
uv run ruff check .

# Fix issues automatically
uv run ruff check . --fix

# Format code
uv run ruff format .

# Check specific files
uv run ruff check glovebox/layout/service.py
```

Configuration in `pyproject.toml`:
```toml
[tool.ruff]
line-length = 88
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B"]
ignore = ["E501"]  # Line too long (handled by formatter)

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

### MyPy (Type Checking)

MyPy ensures type safety:

```bash
# Check all of glovebox
uv run mypy glovebox/

# Check specific modules
uv run mypy glovebox/layout/
uv run mypy glovebox/firmware/

# Generate coverage report
uv run mypy glovebox/ --html-report mypy-report/
```

Configuration in `pyproject.toml`:
```toml
[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true

[[tool.mypy.overrides]]
module = "glovebox.*"
strict = true
```

### Pytest (Testing)

Pytest for comprehensive testing:

```bash
# Run all tests
uv run pytest

# Run with output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_layout/test_service.py

# Run specific test function
uv run pytest tests/test_layout/test_service.py::test_generate_layout

# Run tests matching pattern
uv run pytest -k "test_layout"

# Run with coverage
uv run pytest --cov=glovebox --cov-report=html

# Run with profiling
uv run pytest --profile
```

Configuration in `pyproject.toml`:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "--strict-markers",
    "--disable-warnings",
    "--tb=short"
]
```

### Pre-commit Hooks

Pre-commit hooks ensure code quality:

```bash
# Install hooks
pre-commit install

# Run all hooks
pre-commit run --all-files

# Update hook versions
pre-commit autoupdate

# Skip hooks (emergency only)
git commit --no-verify
```

Configuration in `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.0.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
```

## Troubleshooting

### Common Issues

#### Python Version Issues
```bash
# Check Python version
python --version
python3.11 --version

# If wrong version, create environment with specific Python
uv venv --python 3.11
```

#### Docker Issues
```bash
# Check Docker daemon
docker ps

# Restart Docker service (Linux)
sudo systemctl restart docker

# Test Docker permissions
docker run hello-world
```

#### Dependency Issues
```bash
# Clean and reinstall dependencies
rm -rf .venv
uv sync

# Or with pip
pip install -e ".[dev]" --force-reinstall
```

#### Permission Issues (Linux/macOS)
```bash
# Fix Docker permissions
sudo usermod -aG docker $USER
newgrp docker

# Fix file permissions
chmod +x scripts/*.sh
```

### Import Errors

If you encounter import errors:

```bash
# Ensure glovebox is installed in editable mode
pip show glovebox

# If not installed, reinstall
pip install -e .

# Check Python path
python -c "import sys; print('\n'.join(sys.path))"
```

### Test Failures

If tests fail:

```bash
# Run tests with more verbose output
uv run pytest -v --tb=long

# Run specific failing test
uv run pytest tests/test_layout/test_service.py::test_specific_function -v

# Check test isolation
uv run pytest --lf  # Run last failed tests
```

### Performance Issues

If commands are slow:

```bash
# Check disk space
df -h

# Clean cache directories
rm -rf .mypy_cache .pytest_cache .ruff_cache __pycache__

# Use faster test options
uv run pytest --tb=short -x  # Stop on first failure
```

## Advanced Development Setup

### Development Scripts

Create helpful development scripts in `scripts/`:

```bash
#!/bin/bash
# scripts/dev-setup.sh
set -e

echo "Setting up Glovebox development environment..."

# Install dependencies
uv sync

# Install pre-commit hooks
pre-commit install

# Run initial quality checks
make lint
make test

echo "Development environment ready!"
```

### Environment Variables

Set up environment variables for development:

```bash
# Add to your shell configuration
export GLOVEBOX_DEBUG=1
export GLOVEBOX_LOG_LEVEL=DEBUG
export GLOVEBOX_CACHE_DISABLED=1  # For testing
```

### Docker Development

For Docker-based development:

```dockerfile
# docker/dev.Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install -e ".[dev]"

CMD ["python", "-m", "glovebox.cli"]
```

```bash
# Build development image
docker build -f docker/dev.Dockerfile -t glovebox-dev .

# Run development container
docker run -it --rm -v $(pwd):/app glovebox-dev bash
```

### Remote Development

For remote development (VS Code):

```json
// .devcontainer/devcontainer.json
{
    "name": "Glovebox Development",
    "image": "python:3.11",
    "features": {
        "ghcr.io/devcontainers/features/docker-in-docker:2": {}
    },
    "postCreateCommand": "pip install -e '.[dev]' && pre-commit install",
    "customizations": {
        "vscode": {
            "extensions": [
                "ms-python.python",
                "charliermarsh.ruff"
            ]
        }
    }
}
```

## Next Steps

Once your development environment is set up:

1. **Read the [Architecture Overview](../architecture/overview.md)** to understand the codebase structure
2. **Explore [Domain Documentation](../domains/)** for specific areas you'll work on
3. **Review [Code Conventions](../patterns/code-conventions.md)** for coding standards
4. **Check [Testing Strategy](testing-strategy.md)** for testing approaches
5. **Try [Adding Features Guide](adding-features.md)** for your first contribution

## Getting Help

If you encounter issues during setup:

- **Check existing documentation** in this developer guide
- **Search GitHub Issues** for similar problems
- **Ask in GitHub Discussions** for setup help
- **Contact maintainers** for persistent issues

---

**Ready to start developing?** Your environment is now configured for effective Glovebox development!