# Troubleshooting Guide

This guide helps developers diagnose and resolve common issues encountered while developing with Glovebox. It covers development environment problems, code quality issues, testing failures, and runtime errors.

## Quick Diagnosis

### 🔍 First Steps

When encountering any issue:

1. **🔬 Check the logs** with debug logging enabled
2. **⚡ Verify environment** setup and dependencies
3. **🧪 Run quality checks** to identify obvious problems
4. **📋 Check known issues** in this guide
5. **💬 Search GitHub Issues** for similar problems

### 🚨 Emergency Commands

```bash
# Reset development environment
make clean          # Clean all generated files
uv sync             # Reinstall dependencies
pre-commit install  # Reinstall hooks

# Quick quality check
make lint && make test

# Debug-enabled run
glovebox --debug [command]

# Check system diagnostics
glovebox status --verbose
```

## Development Environment Issues

### Python Environment Problems

#### Issue: Wrong Python Version
```bash
# Problem: Using Python < 3.11
python --version  # Python 3.9.0

# Solution: Install and use Python 3.11+
uv venv --python 3.11
source .venv/bin/activate
uv sync
```

#### Issue: Import Errors
```python
# Problem: Cannot import glovebox modules
ImportError: No module named 'glovebox'

# Solutions:
# 1. Install in editable mode
pip install -e .

# 2. Check Python path
python -c "import sys; print('\n'.join(sys.path))"

# 3. Verify installation
pip show glovebox
```

#### Issue: Virtual Environment Problems
```bash
# Problem: Commands not found or using wrong packages
which python  # Should point to .venv/bin/python

# Solution: Recreate virtual environment
rm -rf .venv
uv venv
source .venv/bin/activate
uv sync
```

### Docker Issues

#### Issue: Docker Daemon Not Running
```bash
# Problem: Docker commands fail
docker ps
# Cannot connect to the Docker daemon at unix:///var/run/docker.sock

# Solutions:
# Linux
sudo systemctl start docker
sudo systemctl enable docker

# macOS
open -a Docker

# Windows
# Start Docker Desktop
```

#### Issue: Docker Permission Errors
```bash
# Problem: Permission denied when running Docker
docker run hello-world
# permission denied while trying to connect to the Docker daemon socket

# Solution: Add user to docker group (Linux)
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker run hello-world
```

#### Issue: Docker Image Build Failures
```bash
# Problem: Compilation fails with Docker errors
docker build -t zmk-build .
# Step 5/10 : RUN apt-get update && apt-get install -y ...
# E: Unable to locate package

# Solutions:
# 1. Clear Docker cache
docker system prune -a

# 2. Update Docker images
docker pull zmkfirmware/zmk-build:3.2-branch

# 3. Check network connectivity
docker run --rm alpine ping -c 3 google.com
```

## Code Quality Issues

### Linting Problems

#### Issue: Ruff Linting Errors
```bash
# Problem: Code fails linting checks
uv run ruff check .
# glovebox/layout/service.py:45:1: E302 Expected 2 blank lines, found 1
# glovebox/layout/service.py:78:89: E501 Line too long (92 > 88 characters)

# Solutions:
# 1. Auto-fix issues
uv run ruff check . --fix

# 2. Format code
uv run ruff format .

# 3. Check specific files
uv run ruff check glovebox/layout/service.py --fix
```

#### Issue: MyPy Type Checking Errors
```bash
# Problem: Type checking fails
uv run mypy glovebox/
# glovebox/layout/service.py:45: error: Argument 1 to "create_layout" has incompatible type "str"; expected "Path"

# Solutions:
# 1. Add proper type annotations
def create_layout(path: Path) -> LayoutData:  # Not str

# 2. Use proper type conversions
path = Path(path_string)  # Convert str to Path

# 3. Add type: ignore for unavoidable issues
result = third_party_function()  # type: ignore[misc]
```

#### Issue: Import Organization Problems
```python
# Problem: Import order violations
import json
from pathlib import Path
import os  # Should be before pathlib

# Solution: Use ruff to fix imports
uv run ruff check . --select I --fix

# Correct order:
import json
import os
from pathlib import Path

from glovebox.models.base import GloveboxBaseModel
```

### File Size Violations

#### Issue: Files Exceed Size Limits
```bash
# Problem: File exceeds 500 lines
glovebox/layout/large_service.py:501: File exceeds 500 lines (ENFORCED)

# Solutions:
# 1. Split into multiple files
# Before: large_service.py (600 lines)
# After: 
#   - service.py (300 lines)
#   - validators.py (200 lines)
#   - formatters.py (150 lines)

# 2. Extract common functionality
# Move shared code to utils/ or helpers/

# 3. Split complex methods
def large_method(self):  # 80 lines
    # Split into smaller methods
    self._prepare_data()
    self._process_data()
    self._finalize_data()
```

## Testing Issues

### Test Execution Problems

#### Issue: Tests Fail to Run
```bash
# Problem: pytest cannot find tests
pytest
# No tests ran in 0.01s

# Solutions:
# 1. Check test discovery
pytest --collect-only

# 2. Run from correct directory
cd /path/to/glovebox
pytest

# 3. Specify test paths
pytest tests/test_layout/
```

#### Issue: Import Errors in Tests
```python
# Problem: Cannot import modules in tests
ModuleNotFoundError: No module named 'glovebox'

# Solutions:
# 1. Install in editable mode
pip install -e .

# 2. Add PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# 3. Check test imports
# Use absolute imports in tests
from glovebox.layout.models import LayoutData
```

#### Issue: Test Isolation Failures
```bash
# Problem: Tests pollute file system
tests/test_layout/test_service.py::test_create_files FAILED
# FileExistsError: [Errno 17] File exists: 'test_output.json'

# Solutions:
# 1. Use tmp_path fixture
def test_create_files(tmp_path):
    output_file = tmp_path / "test_output.json"

# 2. Use isolated fixtures
def test_config_operations(isolated_config):
    config = UserConfig(cli_config_path=isolated_config.config_file)

# 3. Clean up in tests
def test_operation():
    try:
        # Test operations
        pass
    finally:
        # Cleanup
        if test_file.exists():
            test_file.unlink()
```

### Coverage Issues

#### Issue: Low Test Coverage
```bash
# Problem: Coverage below 90%
pytest --cov=glovebox --cov-fail-under=90
# FAIL Required test coverage of 90% not reached. Total coverage: 85.67%

# Solutions:
# 1. Identify missing coverage
pytest --cov=glovebox --cov-report=html
open htmlcov/index.html

# 2. Add tests for uncovered code
# Focus on business logic and error paths

# 3. Add integration tests for complex workflows
```

### Mock Issues

#### Issue: Mock Configuration Problems
```python
# Problem: Mocks not working as expected
@patch('glovebox.adapters.FileAdapter')
def test_service(mock_file_adapter):
    service = create_layout_service()  # Still uses real FileAdapter

# Solution: Mock the factory function
@patch('glovebox.adapters.create_file_adapter')
def test_service(mock_create_file_adapter):
    mock_file_adapter = Mock(spec=FileAdapterProtocol)
    mock_create_file_adapter.return_value = mock_file_adapter
    
    service = create_layout_service()  # Now uses mock
```

## Runtime Issues

### Service Creation Problems

#### Issue: Circular Import Errors
```python
# Problem: Circular imports when creating services
ImportError: cannot import name 'create_layout_service' from partially initialized module

# Solutions:
# 1. Use runtime imports in factory functions
def create_layout_service():
    from glovebox.layout.service import LayoutService  # Import here
    return LayoutService()

# 2. Restructure imports
# Move factory functions to separate modules

# 3. Use TYPE_CHECKING for type hints
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from glovebox.layout.service import LayoutService

def create_service() -> "LayoutService":  # String annotation
    from glovebox.layout.service import LayoutService
    return LayoutService()
```

#### Issue: Dependency Resolution Failures
```python
# Problem: Service creation fails due to missing dependencies
TypeError: LayoutService.__init__() missing 1 required positional argument: 'file_adapter'

# Solutions:
# 1. Check factory function implementation
def create_layout_service(
    file_adapter: FileAdapterProtocol | None = None,
):
    if file_adapter is None:
        file_adapter = create_file_adapter()  # Ensure this is called
    
    return LayoutService(file_adapter=file_adapter)

# 2. Verify protocol implementations
assert isinstance(file_adapter, FileAdapterProtocol)
```

### Configuration Issues

#### Issue: Profile Not Found Errors
```bash
# Problem: Cannot load keyboard profile
glovebox layout compile input.json output/ --profile invalid/keyboard
# ProfileNotFoundError: Profile 'invalid/keyboard' not found

# Solutions:
# 1. List available profiles
glovebox profile list

# 2. Check profile configuration files
ls keyboards/
cat keyboards/glove80.yaml

# 3. Verify profile format
# Correct: glove80/v25.05
# Incorrect: glove80-v25.05
```

#### Issue: Configuration File Errors
```bash
# Problem: Invalid YAML configuration
yaml.parser.ParserError: while parsing a block mapping

# Solutions:
# 1. Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('keyboards/glove80.yaml'))"

# 2. Check indentation (use spaces, not tabs)
# 3. Quote special characters
description: "Glove80: A split ergonomic keyboard"  # Quote colons
```

### Cache Issues

#### Issue: Cache Permission Errors
```bash
# Problem: Cannot write to cache directory
PermissionError: [Errno 13] Permission denied: '/home/user/.glovebox/cache'

# Solutions:
# 1. Fix directory permissions
chmod 755 ~/.glovebox/
chmod 755 ~/.glovebox/cache/

# 2. Use different cache directory
export GLOVEBOX_CACHE_DIR=/tmp/glovebox-cache

# 3. Disable caching temporarily
export GLOVEBOX_CACHE_DISABLED=1
```

#### Issue: Cache Corruption
```bash
# Problem: Cache operations fail
sqlite3.DatabaseError: database disk image is malformed

# Solutions:
# 1. Clear cache completely
rm -rf ~/.glovebox/cache/

# 2. Reset cache in code
from glovebox.core.cache import reset_shared_cache_instances
reset_shared_cache_instances()

# 3. Use memory cache temporarily
cache = create_default_cache(enabled=False)
```

## CLI Issues

### Command Execution Problems

#### Issue: Command Not Found
```bash
# Problem: glovebox command not available
glovebox --help
# command not found: glovebox

# Solutions:
# 1. Activate virtual environment
source .venv/bin/activate

# 2. Install in editable mode
pip install -e .

# 3. Use module execution
python -m glovebox.cli --help

# 4. Check PATH
echo $PATH
which glovebox
```

#### Issue: Parameter Validation Errors
```bash
# Problem: Invalid parameters passed to commands
glovebox layout compile
# Usage: glovebox layout compile [OPTIONS] INPUT OUTPUT

# Solutions:
# 1. Check command help
glovebox layout compile --help

# 2. Use correct parameter format
glovebox layout compile input.json output/ --profile glove80/v25.05

# 3. Check parameter types
# File paths should exist
# Profiles should be in keyboard/firmware format
```

### Output Formatting Issues

#### Issue: Broken Terminal Output
```bash
# Problem: Garbled output or encoding issues
glovebox layout show input.json
# ��[1m��[32m✓��[0m Layout displayed successfully

# Solutions:
# 1. Check terminal encoding
echo $LANG  # Should include UTF-8

# 2. Use text mode
glovebox layout show input.json --format text

# 3. Disable icons
export GLOVEBOX_ICON_MODE=text
```

## Debugging Techniques

### Enable Debug Logging

```bash
# Global debug mode
glovebox --debug layout compile input.json output/

# Specific log levels
glovebox --log-level DEBUG layout compile input.json output/

# Log to file
glovebox --debug --log-file debug.log layout compile input.json output/
```

### Python Debugging

```python
# Add debugging breakpoints
import pdb; pdb.set_trace()

# Or use ipdb for better interface
import ipdb; ipdb.set_trace()

# Rich debugging with variables
from rich import inspect
inspect(layout_data, methods=True)

# Debug exception handling
try:
    result = service.operation()
except Exception as e:
    import traceback
    traceback.print_exc()
    raise
```

### Performance Debugging

```python
# Profile code execution
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Your code here
result = service.expensive_operation()

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)  # Top 20 functions
```

### Memory Debugging

```python
# Monitor memory usage
import psutil
import os

process = psutil.Process(os.getpid())
print(f"Memory usage: {process.memory_info().rss / 1024 / 1024:.2f} MB")

# Use memory profiler for detailed analysis
from memory_profiler import profile

@profile
def memory_intensive_function():
    # Function implementation
    pass
```

## Getting Help

### 🔍 Self-Diagnosis

Before asking for help:

1. **📋 Check this troubleshooting guide** for your specific issue
2. **🔬 Enable debug logging** to understand what's happening
3. **⚡ Verify environment** meets all requirements
4. **🧪 Run diagnostics** with `glovebox status --verbose`
5. **📊 Check system resources** (disk space, memory, etc.)

### 🤝 Community Support

If you can't resolve the issue:

1. **🐛 Search GitHub Issues** for similar problems
2. **💬 Ask in GitHub Discussions** with detailed information
3. **📝 Create an Issue** with reproduction steps
4. **📚 Check documentation** for updated guidance

### 📋 Information to Provide

When asking for help, include:

```bash
# System information
glovebox status --verbose
python --version
docker --version
uv --version

# Error details
glovebox --debug [failing-command]

# Environment details
echo $PATH
echo $PYTHONPATH
pip list | grep glovebox
```

### 🚨 Creating Bug Reports

For bug reports, include:

1. **📄 Clear description** of the problem
2. **🔄 Steps to reproduce** the issue
3. **📱 Expected vs actual behavior**
4. **💻 Environment information** (OS, Python version, etc.)
5. **📋 Full error output** with stack traces
6. **📁 Sample files** if relevant (layouts, configs)

---

**Next Steps**:
- Review [Development Setup](guides/development-setup.md) for environment configuration
- Check [Testing Strategy](guides/testing-strategy.md) for test debugging approaches
- Explore [Architecture Overview](architecture/overview.md) for system understanding