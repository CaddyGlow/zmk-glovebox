# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Essential Commands

### Command Execution

If the virtual environment is not activated, prefix any Python command with `uv run` to ensure it runs with the correct dependencies:

```bash
# Run commands with uv
uv run pytest
uv run ruff check .
uv run mypy glovebox/
```

### Installation

```bash
# Regular installation
pip install -e .

# Development installation with development dependencies
pip install -e ".[dev]"
pre-commit install
```

### Build and Run

```bash
# Run glovebox CLI directly
python -m glovebox.cli [command]
# or with uv:
uv run python -m glovebox.cli [command]

# Build a keymap
glovebox keymap compile my_layout.json output/my_keymap --profile glove80/v25.05
# or with uv:
uv run glovebox keymap compile my_layout.json output/my_keymap --profile glove80/v25.05

# Build firmware
glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05

# Flash firmware
glovebox firmware flash firmware.uf2 --profile glove80/v25.05
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=glovebox

# Run a specific test file
pytest tests/test_services/test_keymap_service_config.py

# Run a specific test function
pytest tests/test_services/test_keymap_service_config.py::test_function_name

# Run CLI tests
pytest tests/test_cli/test_command_execution.py
```

Note: The CLI tests have been simplified to focus on basic functionality and command structure verification.

### Linting and Formatting

```bash
# Run ruff linter
ruff check .

# Run ruff formatter
ruff format .

# Run type checking
mypy glovebox/

# Run all pre-commit hooks
pre-commit run --all-files
```

### Debug Logging

```bash
# Enable debug output
glovebox --debug [command]

# Log to file
glovebox --log-file debug.log [command]
```

### LSP Tools

When using Claude Code, these Language Server Protocol tools are available to enhance code navigation and editing:

```
# Find symbol definition
mcp__language-server__definition

# Get diagnostics for a file
mcp__language-server__diagnostics

# Apply multiple edits to a file
mcp__language-server__edit_file

# Get type information and documentation for a symbol
mcp__language-server__hover

# Find all references to a symbol in the codebase
mcp__language-server__references

# Rename a symbol throughout the codebase
mcp__language-server__rename_symbol
```

## Project Architecture

Glovebox is a comprehensive tool for ZMK keyboard firmware management with a clean, modular architecture:

### Core Structure

- **Service Layer**: Business logic with single responsibility classes
  - `KeymapService`: Handles keymap operations
  - `BuildService`: Manages firmware building
  - `FlashService`: Controls device detection and firmware flashing
  - `DisplayService`: Renders keyboard layouts in the terminal

- **Adapter Pattern**: External system interfaces
  - `DockerAdapter`: Docker interaction for builds
  - `FileAdapter`: File system operations
  - `USBAdapter`: USB device detection and mounting
  - `TemplateAdapter`: Template rendering

- **Configuration System**: Type-safe configuration with KeyboardProfile pattern
  - Typed dataclasses for all configuration components
  - KeyboardProfile combines keyboard and firmware configurations
  - YAML-based configuration files with schema validation
  - Helper functions for profile creation and management

- **Build Chains**: Pluggable build system for different toolchains all based on ZMK

### Key Design Patterns

1. **Simplicity First**: Functions over classes when state isn't needed
2. **Minimal Dependencies**: Carefully selected external libraries
3. **Clear Error Handling**: Specific exceptions with context
4. **Service Oriented**: Business logic organized by feature areas
5. **File Organization**: Logical size limits and function grouping
6. **Dependency Injection**: Services accept dependencies rather than creating them
7. **Factory Functions**: Simplify creation of properly configured services

### KeyboardProfile Pattern

The KeyboardProfile pattern is a central concept in the architecture:

1. **Creation**: 
   ```python
   from glovebox.config.keyboard_config import create_keyboard_profile
   
   profile = create_keyboard_profile("glove80", "v25.05")
   ```

2. **CLI Integration**:
   ```bash
   # Using profile parameter
   glovebox keymap compile input.json output/ --profile glove80/v25.05
   ```

3. **Service Usage**:
   ```python
   # Service methods accept profile
   result = keymap_service.compile(profile, json_data, target_prefix)
   ```

4. **Configuration Access**:
   ```python
   # Access nested configuration
   profile.keyboard_config.description
   profile.firmware_config.version
   ```

### CLI Structure

All CLI commands follow a consistent pattern with profile-based parameter:

```
glovebox [command] [subcommand] [--profile KEYBOARD/FIRMWARE] [options]
```

For example:
- `glovebox keymap compile my_layout.json output/my_keymap --profile glove80/v25.05`
- `glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05`
- `glovebox firmware flash firmware.uf2 --profile glove80/v25.05`
- `glovebox keymap show my_layout.json --profile glove80/v25.05`

### Maintainability Guidelines

This project is maintained by a small team (2-3 developers), so:

1. **Avoid Over-engineering**: Keep solutions as simple as possible
   - Prefer straightforward solutions over complex abstractions
   - Solve the problem at hand, not potential future problems
   - Only add complexity when there's a clear benefit

2. **Pragmatic Design**: Choose patterns that solve actual problems, not theoretical ones
   - Use design patterns when they simplify code, not for their own sake
   - Don't prematurely optimize or add flexibility that isn't needed yet
   - Prioritize maintainability over architectural purity

3. **Readability Over Cleverness**: Clear, explicit code is better than clever, complex code
   - Write code that's easy to read and understand at a glance
   - Avoid non-obvious language features unless truly necessary
   - Explicit is better than implicit (clear intent over concise code)

4. **Focused Changes**: Keep changes small and targeted rather than large refactors
   - Make incremental improvements that are easy to review
   - Test changes thoroughly before committing
   - Maintain backward compatibility whenever possible

5. **Comment Rationale**: Document WHY something is done a certain way, not just what it does
   - Explain complex logic or non-obvious design decisions
   - Include references to issues/tickets in comments for context
   - Document edge cases and limitations

6. **Optimize for Understanding**: Code should be easy for new developers to understand
   - Use descriptive variable names that explain purpose
   - Break complex logic into well-named helper functions
   - Follow consistent patterns across the codebase

7. **Use Standard Patterns**: Avoid exotic patterns that require specialized knowledge
   - Prefer common Python idioms that any Python developer would recognize
   - Document any necessary complex patterns clearly
   - Keep inheritance hierarchies shallow and understandable

### Logging Conventions

- Use appropriate logging levels:
  - `DEBUG`: Development/troubleshooting details
  - `INFO`: Important user-facing events
  - `WARNING`: Recoverable problems
  - `ERROR`: Failures that prevent operation completion
  - `CRITICAL`: System failures requiring immediate attention

- Always use lazy formatting (`%` style, not f-strings) in log calls:
  ```python
  logger.debug("Processing %d items: %s", len(items), items)
  ```

### Code Conventions

- Maximum 500 lines per file
- Maximum 50 lines per method
- Use comprehensive typing without complexity
- Document intent, not implementation
- Use pathlib for file operations
- Use modern typing when available
- Always lint/format before committing

### Common Linting Issues to Avoid

- **SIM117**: Use a single with statement with multiple contexts instead of nested with statements
- **UP035**: Use modern typing - `typing.Dict` is deprecated, use `dict` instead
- **PTH123**: Use `Path.open()` instead of built-in `open()`
- **B904**: Within except clauses, use `raise ... from err` to distinguish from errors in exception handling
- **N815**: Variable names in class scope should not be mixedCase
- **SIM102**: Use a single if statement instead of nested if statements
- **NB023**: Function definition should not bind loop variable

## Git Workflow

### Branch Strategy

- Main development branch is `dev`
- Feature branches should be created from `dev`
- Use meaningful branch names (e.g., `feature/new-keymap-format`, `fix/usb-detection-issue`)

### Commit Practices

- Commit regularly with small, focused changes
- Use descriptive commit messages following the conventional commits format:
  - `feat`: A new feature
  - `fix`: A bug fix
  - `refactor`: Code change that neither fixes a bug nor adds a feature
  - `docs`: Documentation only changes
  - `test`: Adding missing tests or correcting existing tests
  - `chore`: Changes to the build process or auxiliary tools
  - Example: `feat: add support for wireless keyboard detection`

### Before Working on Code

1. Always read and understand the model classes in `glovebox/models/` to understand the data structures
2. Check `glovebox/config/models.py` for configuration data structures
3. Read the `docs/keymap_file_format.md` document to understand the keymap file format

### Before Committing

1. Run the linter and fix any issues:
   ```bash
   ruff check .
   ruff format .
   ```

2. Run pre-commit hooks:
   ```bash
   pre-commit run --all-files
   ```

3. Run tests to ensure your changes don't break existing functionality:
   ```bash
   pytest
   ```

4. All new files must pass mypy type checking:
   ```bash
   mypy glovebox/
   ```

### Pull Request Process

1. Ensure all tests pass and code quality checks are successful
2. Request a review from at least one team member
3. After approval, squash commits for a clean history
4. Merge to `dev` branch:
   ```bash
   # Ensure you're on your feature branch
   git checkout feature/my-feature

   # Make sure your branch is up to date with dev
   git fetch
   git rebase origin/dev

   # Squash commits (interactive rebase)
   git rebase -i origin/dev

   # Push to remote (may need force push if you rebased)
   git push -f

   # Once PR is approved, merge to dev
   git checkout dev
   git merge feature/my-feature
   git push
   ```
