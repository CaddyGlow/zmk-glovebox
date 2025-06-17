# How to Use the Glovebox Nix Flake

This flake provides a complete development environment for the Glovebox Python project. Here's how you can use it:

## Basic Usage

### Enter Development Shell

To start a development environment with all dependencies:

```bash
nix develop
```

This provides:
- An editable installation of the Glovebox package
- All development dependencies
- The `uv` Python package manager
- Git

### Run the Application

To run the Glovebox application:

```bash
nix run
```

## Building and Testing

### Build the Package

```bash
nix build
```

This builds the package and places the result in `./result`

### Run Tests

```bash
nix flake check
```

This runs the test suite defined in the flake.

### Build a Wheel Distribution

```bash
nix build .#wheel
```

This creates a redistributable wheel package.

## Development Workflow

1. Enter the development shell with `nix develop`
2. Make changes to the code
3. Run the application with `python -m glovebox` or use the tools available in the shell
4. Run tests with `pytest`

The development shell uses an editable installation, so changes to your code will be immediately available without reinstalling.

## Working with the Virtual Environment

Access the Python virtual environment:

```bash
nix build .#venv
./result/bin/python
```

Or install it globally:

```bash
nix profile install .#venv
```

## Other Features

- Platform-specific packages are handled automatically
- Comprehensive test coverage and reporting is included
- Editable mode allows for hot module reloading during development

The flake is configured to use Python 3.12, but you can modify this in the flake if needed.
