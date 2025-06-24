# Glovebox Documentation

This directory contains the Sphinx documentation for the Glovebox project.

## Building Documentation

### Quick Start

```bash
# Build documentation
make docs

# Build and open in browser
./scripts/view-docs.sh

# Build with live reload (development)
make docs-live

# Clean build artifacts
make docs-clean
```

### Manual Build

```bash
# Using the build script
./scripts/docs.sh

# Using Sphinx directly
uv run sphinx-build -b html docs docs/_build/html
```

## Documentation Structure

```
docs/
├── conf.py              # Sphinx configuration
├── index.rst            # Main documentation index
├── api/                 # Auto-generated API documentation
├── dev/                 # Developer documentation
├── user/                # User guides and tutorials
├── technical/           # Technical specifications
├── implementation/      # Implementation plans and completed features
├── _build/             # Generated documentation (gitignored)
├── _static/            # Static assets for documentation
└── _templates/         # Custom Sphinx templates
```

## Features

- **Auto-API Generation**: Comprehensive API documentation generated from docstrings
- **MyST Parser**: Support for Markdown files alongside reStructuredText
- **ReadTheDocs Theme**: Professional documentation theme
- **Live Reload**: Development server with automatic rebuilding
- **Cross-References**: Links between documentation sections and API
- **Search**: Full-text search functionality

## Configuration

The documentation is configured in `docs/conf.py` with:

- **Sphinx Extensions**: autodoc, autosummary, viewcode, napoleon, intersphinx, autoapi
- **Theme**: sphinx_rtd_theme with custom options
- **Auto-API**: Automatic API documentation from `glovebox/` package
- **MyST**: Markdown support with various extensions enabled

## Dependencies

Documentation dependencies are included in the `dev` dependency group in `pyproject.toml`:

- `sphinx>=8.2.3`
- `sphinx-autoapi>=3.6.0` 
- `sphinx-rtd-theme>=3.0.2`
- `sphinx-autobuild>=2024.10.3`
- `myst-parser>=4.0.1`
- `linkify-it-py>=2.0.0`

## Viewing Documentation

After building, the documentation is available at:
- `docs/_build/html/index.html`
- Use `./scripts/view-docs.sh` to build and open automatically

## Development Workflow

1. Edit documentation files (`.rst` or `.md`)
2. Run `make docs-live` for live reloading during development
3. Run `make docs` for final build before committing
4. The build process includes warnings but treats them as non-fatal

## Troubleshooting

### Common Issues

- **Missing dependencies**: Run `uv sync` to install documentation dependencies
- **Build warnings**: Most warnings about cross-references and docstring formatting are non-fatal
- **Live reload not working**: Check that port 8000 is available

### Build Artifacts

- Generated files are in `docs/_build/` (gitignored)
- AutoAPI files are in `docs/api/` (auto-generated, can be cleaned)
- Clean everything with `make docs-clean`