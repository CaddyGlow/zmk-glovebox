# CLAUDE.md

This file provides comprehensive guidance to Claude Code and other LLMs when working with code in this repository.

## CRITICAL: Tool Usage Precedence

**1. ALWAYS try Serena tools first when available:**
- Use `mcp__serena__*` tools for code analysis, search, editing, and project understanding
- Serena provides specialized code intelligence and symbol-aware operations

**2. If Serena tools fail or are unavailable, use standard tools:**
- Use `Read`, `Write`, `Edit`, `Glob`, `Grep` for file operations
- For extensive file changes, prefer `Read` + `Write` over multiple `Edit` calls

## Project Overview

**Glovebox** is a ZMK keyboard firmware management tool with a multi-stage pipeline:

```
Layout Editor → JSON File → ZMK Files → Firmware → Flash
  (Design)    →  (.json)  → (.keymap + .conf) → (.uf2) → (Keyboard)
```

**Architecture**: Domain-Driven Design with Service Layer, Adapter Pattern, Type-safe Configuration System, Cross-Platform USB abstraction.

## MANDATORY: Code Convention Enforcement

**MUST BE FOLLOWED WITHOUT EXCEPTION:**

1. **ALWAYS run linting before completion**:
   ```bash
   ruff check . --fix && ruff format . && mypy glovebox/
   ```

2. **Project Standards**:
   - Max 500 lines per file, 50 lines per method (ENFORCED)
   - Use pathlib for ALL file operations: `Path.open()` not `open()`
   - Modern typing: `dict` not `typing.Dict`
   - Lazy logging: `%` style, not f-strings

3. **MANDATORY Exception Logging**:
   ```python
   # ✅ REQUIRED - Debug-aware stack traces
   except Exception as e:
       exc_info = self.logger.isEnabledFor(logging.DEBUG)
       self.logger.error("Operation failed: %s", e, exc_info=exc_info)
   ```

4. **Pre-commit**: `pre-commit run --all-files && pytest`

## MANDATORY: Pydantic Model Rules

1. **ALL models inherit from GloveboxBaseModel**:
   ```python
   from glovebox.models.base import GloveboxBaseModel
   
   class MyModel(GloveboxBaseModel):
       field: str
   ```

2. **NEVER use bare .model_dump() - Use proper parameters**:
   ```python
   # ✅ CORRECT
   data = model.to_dict()  # Recommended
   data = model.model_dump(by_alias=True, exclude_unset=True, mode="json")
   
   # ❌ INCORRECT
   data = model.model_dump()  # Missing parameters
   ```

## MANDATORY: Test Isolation

1. **NEVER write to current directory in tests**:
   ```python
   # ✅ CORRECT - Use fixtures
   def test_operation(tmp_path):
       test_file = tmp_path / "test.json"
   
   # ❌ INCORRECT
   Path("test.json").write_text(data)  # NEVER
   ```

2. **Available Fixtures**: `isolated_config`, `isolated_cli_environment`, `temp_config_dir`

3. **Requirements**: 90% coverage, ALL public functions tested, comprehensive test coverage

## MANDATORY: UI Theming

1. **NO EMOJIS outside `glovebox/cli/helpers/theme.py`**:
   ```python
   # ✅ CORRECT
   from glovebox.cli.helpers.theme import Icons, get_themed_console
   console = get_themed_console(icon_mode="text")
   console.print_success("Operation completed")
   
   # ❌ INCORRECT
   print("✅ Success")
   ```

2. **NO HARDCODED COLORS outside theme.py**:
   ```python
   # ✅ CORRECT
   console.print_error("Error message")
   
   # ❌ INCORRECT
   console.print("Error", style="red")
   ```

## Naming Conventions (MANDATORY)

- **Adapters**: `*Adapter` (not `*Impl`)
- **Services**: `*Service` (inherit from BaseService)
- **Protocols**: `*Protocol`
- **Factory Functions**: `create_*` prefix
- **Booleans**: Question form (`is_enabled`, `has_firmware`)

## Domain Architecture

### Core Domains:
- **Layout** (`glovebox/layout/`): JSON→DTSI conversion, component operations, behavior models
- **Firmware** (`glovebox/firmware/`): Building, flashing, device detection, USB operations
- **Compilation** (`glovebox/compilation/`): Strategy-based compilation (ZMK West, MoErgo Nix)
- **Configuration** (`glovebox/config/`): Keyboard profiles, YAML includes, user settings
- **Adapters** (`glovebox/adapters/`): External interfaces (Docker, USB, File, Template)
- **Core** (`glovebox/core/`): Shared cache coordination, error handling, metrics

### Key Patterns:
1. **Factory Functions**: `create_*` for all service instantiation
2. **Shared Cache**: Domain isolation via tags, single instances
3. **Protocol-Based**: Type-safe abstractions with runtime checking
4. **Clean Boundaries**: No backward compatibility layers

### CLI Structure:
```
glovebox [command] [subcommand] [--profile KEYBOARD/FIRMWARE] [options]
```

Modular commands under `glovebox/cli/commands/` with consistent registration pattern.

## Essential Commands

```bash
# Quick operations
make test && make lint && make format
uv run pytest && uv run ruff check . --fix && uv run mypy glovebox/

# CLI usage
glovebox layout compile input.json output/ --profile glove80/v25.05
glovebox firmware flash firmware.uf2 --profile glove80/v25.05
```

## Key Import Patterns

```python
# Domain services (use factory functions)
from glovebox.layout import create_layout_service
from glovebox.firmware.flash import create_flash_service
from glovebox.compilation import create_compilation_service
from glovebox.config import create_keyboard_profile, create_user_config

# Core infrastructure
from glovebox.models.base import GloveboxBaseModel
from glovebox.core.cache import get_shared_cache_instance
from glovebox.cli.helpers.theme import get_themed_console, Icons
from glovebox.cli.decorators.error_handling import handle_errors
```

## Critical Anti-Patterns (NEVER DO)

1. **❌ Direct service instantiation**: Use factory functions
2. **❌ Global state/singletons**: Use shared cache coordination
3. **❌ Bare exceptions**: Always catch specific exceptions
4. **❌ Bypassing theme system**: Use theme helpers for all UI
5. **❌ Implementation suffixes**: Only use `*Impl` for actual implementations

## Technology Stack

**Core**: Python 3.11+, Pydantic 2.11+, Typer 0.16+, Rich 13.3+
**Key**: Docker (required), diskcache 5.6+, pytest 8.3+, ruff 0.11+, mypy 1.15+

## Git Workflow

- Main branch: `dev`
- Before commit: Lint, pre-commit, tests, mypy
- Small, focused changes preferred

## Final Reminders

- **Prioritize readability over cleverness**
- **Follow established patterns consistently**
- **Use factory functions for all services**
- **Maintain test isolation**
- **Leverage theme system for UI**
- **Keep domain boundaries clean**

When in doubt, follow existing patterns and prioritize simplicity.