# Package Building and Distribution

This document describes how to build and distribute the Glovebox package to PyPI.

## Quick Start

```bash
# Build package
make build

# Check package metadata
make check-package

# Publish to TestPyPI (for testing)
make publish-test

# Publish to PyPI (production)
make publish
```

## Build Process

### Building Packages

The `make build` command creates both wheel and source distributions:

```bash
make build
```

This will:
1. Clean previous builds (`dist/`, `build/`, `*.egg-info/`)
2. Show current git version information
3. Build wheel (`.whl`) and source distribution (`.tar.gz`) files
4. Display built packages in `dist/` directory

### Package Checking

Before publishing, check the package metadata:

```bash
make check-package
```

This displays:
- Package files and sizes
- Version information
- PyPI readiness checklist

## Version Management

Glovebox uses **git-based versioning** with `hatch-vcs`:

- **Development versions**: `0.1.dev405+gedf98bf.d19800101`
- **Release versions**: Based on git tags (e.g., `v1.0.0` → `1.0.0`)

### Creating a Release

1. **Tag the release**:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. **Build from the tag**:
   ```bash
   git checkout v1.0.0
   make build
   ```

3. **Publish**:
   ```bash
   make publish
   ```

## Publishing

### TestPyPI (Recommended for Testing)

```bash
make publish-test
```

This publishes to https://test.pypi.org for testing without affecting the main PyPI repository.

**Testing the TestPyPI package**:
```bash
pip install --index-url https://test.pypi.org/simple/ glovebox
```

### Production PyPI

```bash
make publish
```

This will:
1. Show a warning about publishing to live PyPI
2. Prompt for confirmation
3. Publish to https://pypi.org

## Authentication

### PyPI Tokens

You need to configure PyPI authentication tokens:

1. **Create tokens**:
   - PyPI: https://pypi.org/manage/account/token/
   - TestPyPI: https://test.pypi.org/manage/account/token/

2. **Configure uv** (one-time setup):
   ```bash
   # For PyPI
   uv publish --username __token__ --password <your-pypi-token>
   
   # For TestPyPI  
   uv publish --index-url https://test.pypi.org/legacy/ --username __token__ --password <your-testpypi-token>
   ```

### Alternative: Environment Variables

```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=<your-token>
make publish
```

## Package Configuration

The package is configured in `pyproject.toml`:

```toml
[project]
name = "glovebox"
dynamic = ["version"]
description = "Comprehensive tool for ZMK keyboard firmware management"
requires-python = ">=3.11"

[project.scripts]
glovebox = "glovebox.cli:main"

[build-system]
requires = ["hatchling", "hatch-vcs"]
build-backend = "hatchling.build"

[tool.hatch.version]
source = "vcs"  # Git-based versioning

[tool.hatch.build.hooks.vcs]
version-file = "glovebox/_version.py"
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Build and Publish

on:
  push:
    tags:
      - 'v*'

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Install uv
      uses: astral-sh/setup-uv@v1
    - name: Build package
      run: make build
    - name: Publish to PyPI
      env:
        TWINE_PASSWORD: ${{ secrets.PYPI_TOKEN }}
      run: make publish
```

## Troubleshooting

### Common Issues

1. **Version conflicts**: Ensure the version hasn't been published before
2. **Authentication errors**: Check PyPI token configuration
3. **Missing files**: Verify `MANIFEST.in` or `pyproject.toml` includes all needed files
4. **Build errors**: Run `make lint` and `make test` before building

### Package Size

The built package includes:
- Source code
- Configuration files
- Documentation
- Dependencies metadata

Large packages (>50MB) may have upload issues. Consider excluding unnecessary files.

### Local Testing

Test the built package locally:

```bash
# Install from wheel
uv pip install dist/*.whl

# Test CLI
glovebox --version
glovebox --help
```

## Release Checklist

Before releasing:

- [ ] All tests pass (`make test`)
- [ ] Code is properly formatted (`make format`)
- [ ] Documentation is updated
- [ ] Version tag is created
- [ ] Package builds successfully (`make build`)
- [ ] Package metadata is correct (`make check-package`)
- [ ] Tested on TestPyPI (`make publish-test`)
- [ ] Ready for production release (`make publish`)

## See Also

- [Development Documentation](README.md)
- [Testing Guidelines](testing.md)
- [Code Conventions](conventions/code-style.md)