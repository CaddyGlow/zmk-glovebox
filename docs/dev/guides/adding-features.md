# Adding New Features to Glovebox

This guide provides step-by-step instructions for adding new features to Glovebox while maintaining the established architecture patterns, code conventions, and quality standards.

## Feature Development Process

### 1. Planning and Design

Before writing code, plan your feature thoroughly:

#### Analyze Requirements
- **📋 Define the problem** your feature solves
- **🎯 Identify target users** and use cases
- **📐 Determine scope** and acceptance criteria
- **🔍 Research existing solutions** in the codebase

#### Design the Feature
- **🏗️ Choose the appropriate domain** (layout, firmware, compilation, config)
- **📋 Define data models** and their relationships
- **🎯 Design service interfaces** and protocols
- **💻 Plan CLI commands** and user interactions
- **🧪 Consider testing strategy** and edge cases

#### Architecture Decisions
- **🔧 Will this extend existing services** or require new ones?
- **📊 What data models** need to be created or modified?
- **🎨 How will users interact** with this feature (CLI, API)?
- **💾 Does this require caching** or persistent storage?
- **🔌 What external dependencies** are needed?

### 2. Implementation Steps

Follow this systematic approach for implementation:

#### Step 1: Create Data Models

Start with domain models using Pydantic:

```python
# glovebox/layout/models/new_feature.py
from typing import Optional, List
from glovebox.models.base import GloveboxBaseModel

class NewFeatureData(GloveboxBaseModel):
    """Data model for the new feature."""
    
    name: str
    description: Optional[str] = None
    enabled: bool = True
    options: dict[str, Any] = {}
    
    def validate_options(self) -> bool:
        """Validate feature-specific options."""
        # Business logic validation
        return True
    
    def apply_defaults(self) -> "NewFeatureData":
        """Apply default values based on feature requirements."""
        # Business logic for defaults
        return self

class NewFeatureResult(GloveboxBaseModel):
    """Result model for feature operations."""
    
    success: bool
    data: Optional[NewFeatureData] = None
    message: str = ""
    errors: List[str] = []
```

#### Step 2: Define Service Protocol

Create protocol interface for type safety:

```python
# glovebox/protocols/new_feature_protocol.py
from typing import Protocol, runtime_checkable
from pathlib import Path

from glovebox.layout.models.new_feature import NewFeatureData, NewFeatureResult

@runtime_checkable
class NewFeatureServiceProtocol(Protocol):
    """Protocol for new feature service operations."""
    
    def process_feature(self, data: NewFeatureData) -> NewFeatureResult:
        """Process feature data and return result."""
        ...
    
    def validate_feature(self, data: NewFeatureData) -> bool:
        """Validate feature data."""
        ...
    
    def save_feature(self, data: NewFeatureData, output_path: Path) -> bool:
        """Save feature data to file."""
        ...
```

#### Step 3: Implement Domain Service

Create the service implementation:

```python
# glovebox/layout/new_feature_service.py
from pathlib import Path
from typing import Any

from glovebox.services import BaseService
from glovebox.protocols import FileAdapterProtocol
from glovebox.layout.models.new_feature import NewFeatureData, NewFeatureResult
from glovebox.core.errors import LayoutError

class NewFeatureService(BaseService):
    """Service for new feature operations."""
    
    def __init__(
        self,
        file_adapter: FileAdapterProtocol,
    ):
        super().__init__()
        self.file_adapter = file_adapter
    
    def process_feature(self, data: NewFeatureData) -> NewFeatureResult:
        """Process feature data and return result."""
        try:
            self._log_operation_start("feature_processing", feature=data.name)
            
            # Validate input data
            if not self.validate_feature(data):
                return NewFeatureResult(
                    success=False,
                    message="Feature validation failed",
                    errors=["Invalid feature data"]
                )
            
            # Apply business logic
            processed_data = self._apply_feature_logic(data)
            
            self._log_operation_success("feature_processing", feature=data.name)
            
            return NewFeatureResult(
                success=True,
                data=processed_data,
                message="Feature processed successfully"
            )
            
        except Exception as e:
            self._log_operation_failure("feature_processing", e, feature=data.name)
            raise LayoutError(f"Feature processing failed: {e}") from e
    
    def validate_feature(self, data: NewFeatureData) -> bool:
        """Validate feature data."""
        try:
            # Perform validation checks
            if not data.name:
                return False
            
            if not data.validate_options():
                return False
            
            return True
            
        except Exception as e:
            self.logger.warning("Feature validation error: %s", e)
            return False
    
    def save_feature(self, data: NewFeatureData, output_path: Path) -> bool:
        """Save feature data to file."""
        try:
            self._log_operation_start("feature_saving", path=str(output_path))
            
            # Serialize data using proper Pydantic methods
            content = data.model_dump_json(indent=2, by_alias=True)
            
            # Use file adapter for actual file operations
            self.file_adapter.write_file(output_path, content)
            
            self._log_operation_success("feature_saving", path=str(output_path))
            return True
            
        except Exception as e:
            self._log_operation_failure("feature_saving", e, path=str(output_path))
            return False
    
    def _apply_feature_logic(self, data: NewFeatureData) -> NewFeatureData:
        """Apply feature-specific business logic."""
        # Implementation of feature logic
        processed_data = data.apply_defaults()
        
        # Additional processing as needed
        return processed_data
```

#### Step 4: Create Factory Function

Add factory function following the established pattern:

```python
# glovebox/layout/__init__.py (add to existing file)

def create_new_feature_service(
    file_adapter: FileAdapterProtocol | None = None,
) -> NewFeatureService:
    """Create new feature service with dependencies."""
    
    # Import at runtime to avoid circular imports
    from glovebox.layout.new_feature_service import NewFeatureService
    
    # Resolve dependencies
    if file_adapter is None:
        from glovebox.adapters import create_file_adapter
        file_adapter = create_file_adapter()
    
    return NewFeatureService(file_adapter=file_adapter)

# Add to __all__ list
__all__ = [
    # ... existing exports
    "create_new_feature_service",
]
```

#### Step 5: Add CLI Commands

Create CLI commands for the feature:

```python
# glovebox/cli/commands/layout/new_feature.py
import typer
from pathlib import Path
from typing import Optional

from glovebox.cli.decorators import with_profile, with_input_file, with_output_file
from glovebox.cli.helpers.parameters import OutputFormatOption, ForceOverwriteOption
from glovebox.cli.helpers.theme import get_themed_console, format_operation_status
from glovebox.cli.helpers.parameter_helpers import (
    get_input_data_from_context, get_output_path_from_context
)

def register_new_feature_commands(app: typer.Typer) -> None:
    """Register new feature commands."""
    app.command("process-feature")(process_feature_command)
    app.command("validate-feature")(validate_feature_command)

@with_profile()
@with_input_file()
@with_output_file()
def process_feature_command(
    ctx: typer.Context,
    force: ForceOverwriteOption = False,
    format: OutputFormatOption = "text",
) -> None:
    """Process feature data from input file.
    
    This command processes feature data according to the specified profile
    and generates output files with the processed results.
    
    Examples:
        glovebox layout process-feature input.json output.json --profile glove80/v25.05
        glovebox layout process-feature input.json output.json --force
    """
    console = get_themed_console()
    
    try:
        # Get processed parameters from context
        input_data = get_input_data_from_context(ctx)
        output_path = get_output_path_from_context(ctx)
        
        console.print(format_operation_status(
            "PROCESSING", f"Feature processing starting"
        ))
        
        # Create service
        from glovebox.layout import create_new_feature_service
        service = create_new_feature_service()
        
        # Process feature
        result = service.process_feature(input_data)
        
        if result.success:
            # Save result
            if service.save_feature(result.data, output_path):
                console.print_success(f"Feature processed and saved to {output_path}")
                
                if format == "json":
                    output_data = {
                        "success": True,
                        "output_path": str(output_path),
                        "message": result.message
                    }
                    console.print_json(output_data)
            else:
                console.print_error("Failed to save processed feature")
                raise typer.Exit(1)
        else:
            console.print_error(f"Feature processing failed: {result.message}")
            if result.errors:
                for error in result.errors:
                    console.print_error(f"  - {error}")
            raise typer.Exit(1)
        
    except Exception as e:
        console.print_error(f"Feature processing error: {e}")
        if ctx.obj and ctx.obj.get("debug"):
            console.print_exception()
        raise typer.Exit(1)

@with_input_file()
def validate_feature_command(
    ctx: typer.Context,
    format: OutputFormatOption = "text",
) -> None:
    """Validate feature data from input file.
    
    This command validates feature data structure and content without
    performing any processing operations.
    
    Examples:
        glovebox layout validate-feature input.json
        glovebox layout validate-feature input.json --format json
    """
    console = get_themed_console()
    
    try:
        # Get input data
        input_data = get_input_data_from_context(ctx)
        
        console.print(format_operation_status(
            "VALIDATING", f"Feature validation starting"
        ))
        
        # Create service
        from glovebox.layout import create_new_feature_service
        service = create_new_feature_service()
        
        # Validate feature
        is_valid = service.validate_feature(input_data)
        
        if is_valid:
            console.print_success("Feature validation passed")
            
            if format == "json":
                console.print_json({"valid": True, "message": "Validation passed"})
        else:
            console.print_error("Feature validation failed")
            
            if format == "json":
                console.print_json({"valid": False, "message": "Validation failed"})
            
            raise typer.Exit(1)
        
    except Exception as e:
        console.print_error(f"Feature validation error: {e}")
        if ctx.obj and ctx.obj.get("debug"):
            console.print_exception()
        raise typer.Exit(1)
```

#### Step 6: Register Commands

Add commands to the domain command registration:

```python
# glovebox/cli/commands/layout/__init__.py (modify existing file)

# Add import
from .new_feature import register_new_feature_commands

# Add to registration function
def register_commands(app: typer.Typer) -> None:
    """Register layout commands with the main app."""
    app.add_typer(layout_app, name="layout")

# Register with layout app
register_core_commands(layout_app)
register_comparison_commands(layout_app)
register_edit_commands(layout_app)
register_parsing_commands(layout_app)
register_file_commands(layout_app)
register_new_feature_commands(layout_app)  # Add this line
```

#### Step 7: Write Comprehensive Tests

Create thorough tests for all components:

```python
# tests/test_layout/test_new_feature_service.py
import pytest
from unittest.mock import Mock
from pathlib import Path

from glovebox.layout.new_feature_service import NewFeatureService
from glovebox.layout.models.new_feature import NewFeatureData, NewFeatureResult
from glovebox.protocols import FileAdapterProtocol
from glovebox.core.errors import LayoutError

class TestNewFeatureService:
    @pytest.fixture
    def mock_file_adapter(self):
        """Create mock file adapter."""
        return Mock(spec=FileAdapterProtocol)
    
    @pytest.fixture
    def service(self, mock_file_adapter):
        """Create service with mocked dependencies."""
        return NewFeatureService(file_adapter=mock_file_adapter)
    
    @pytest.fixture
    def sample_feature_data(self):
        """Create sample feature data for testing."""
        return NewFeatureData(
            name="test_feature",
            description="Test feature for unit testing",
            enabled=True,
            options={"param1": "value1", "param2": 42}
        )
    
    def test_process_feature_success(self, service, sample_feature_data):
        """Test successful feature processing."""
        # Act
        result = service.process_feature(sample_feature_data)
        
        # Assert
        assert isinstance(result, NewFeatureResult)
        assert result.success is True
        assert result.data is not None
        assert result.data.name == "test_feature"
        assert "successfully" in result.message.lower()
    
    def test_process_feature_invalid_data(self, service):
        """Test processing with invalid data."""
        # Arrange
        invalid_data = NewFeatureData(name="", enabled=True)
        
        # Act
        result = service.process_feature(invalid_data)
        
        # Assert
        assert result.success is False
        assert "validation failed" in result.message.lower()
        assert len(result.errors) > 0
    
    def test_validate_feature_valid_data(self, service, sample_feature_data):
        """Test validation with valid data."""
        # Act
        is_valid = service.validate_feature(sample_feature_data)
        
        # Assert
        assert is_valid is True
    
    def test_validate_feature_invalid_data(self, service):
        """Test validation with invalid data."""
        # Arrange
        invalid_data = NewFeatureData(name="", enabled=True)
        
        # Act
        is_valid = service.validate_feature(invalid_data)
        
        # Assert
        assert is_valid is False
    
    def test_save_feature_success(self, service, mock_file_adapter, sample_feature_data, tmp_path):
        """Test successful feature saving."""
        # Arrange
        output_path = tmp_path / "output.json"
        
        # Act
        success = service.save_feature(sample_feature_data, output_path)
        
        # Assert
        assert success is True
        mock_file_adapter.write_file.assert_called_once()
        
        # Verify content format
        call_args = mock_file_adapter.write_file.call_args
        assert call_args[0][0] == output_path
        assert '"name": "test_feature"' in call_args[0][1]
    
    def test_save_feature_file_error(self, service, mock_file_adapter, sample_feature_data, tmp_path):
        """Test feature saving with file error."""
        # Arrange
        output_path = tmp_path / "output.json"
        mock_file_adapter.write_file.side_effect = OSError("Permission denied")
        
        # Act
        success = service.save_feature(sample_feature_data, output_path)
        
        # Assert
        assert success is False
    
    def test_process_feature_exception_handling(self, service, mock_file_adapter):
        """Test exception handling in feature processing."""
        # Arrange
        invalid_data = Mock()
        invalid_data.name = "test"
        invalid_data.validate_options.side_effect = Exception("Validation error")
        
        # Act & Assert
        with pytest.raises(LayoutError, match="Feature processing failed"):
            service.process_feature(invalid_data)

# tests/test_layout/test_new_feature_models.py
class TestNewFeatureModels:
    def test_new_feature_data_creation(self):
        """Test creating NewFeatureData model."""
        # Act
        data = NewFeatureData(
            name="test_feature",
            description="Test description",
            enabled=True,
            options={"key": "value"}
        )
        
        # Assert
        assert data.name == "test_feature"
        assert data.description == "Test description"
        assert data.enabled is True
        assert data.options == {"key": "value"}
    
    def test_new_feature_data_defaults(self):
        """Test default values in NewFeatureData."""
        # Act
        data = NewFeatureData(name="test")
        
        # Assert
        assert data.name == "test"
        assert data.description is None
        assert data.enabled is True
        assert data.options == {}
    
    def test_new_feature_data_serialization(self):
        """Test Pydantic serialization."""
        # Arrange
        data = NewFeatureData(name="test", enabled=False)
        
        # Act
        serialized = data.model_dump(by_alias=True, exclude_unset=True, mode="json")
        
        # Assert
        assert "name" in serialized
        assert "enabled" in serialized
        assert serialized["name"] == "test"
        assert serialized["enabled"] is False
    
    def test_new_feature_result_creation(self):
        """Test creating NewFeatureResult model."""
        # Arrange
        feature_data = NewFeatureData(name="test")
        
        # Act
        result = NewFeatureResult(
            success=True,
            data=feature_data,
            message="Success",
            errors=[]
        )
        
        # Assert
        assert result.success is True
        assert result.data.name == "test"
        assert result.message == "Success"
        assert result.errors == []

# tests/test_cli/test_new_feature_commands.py
class TestNewFeatureCommands:
    def test_process_feature_command_success(self, isolated_cli_environment, cli_runner):
        """Test successful feature processing command."""
        # Arrange
        input_file = isolated_cli_environment.create_feature_file({
            "name": "test_feature",
            "enabled": True,
            "options": {}
        })
        output_file = isolated_cli_environment.temp_dir / "output.json"
        
        # Act
        result = cli_runner.invoke(app, [
            "layout", "process-feature",
            str(input_file),
            str(output_file),
            "--profile", "glove80/v25.05"
        ])
        
        # Assert
        assert result.exit_code == 0
        assert "successfully" in result.output.lower()
        assert output_file.exists()
    
    def test_validate_feature_command_success(self, isolated_cli_environment, cli_runner):
        """Test successful feature validation command."""
        # Arrange
        input_file = isolated_cli_environment.create_feature_file({
            "name": "test_feature",
            "enabled": True
        })
        
        # Act
        result = cli_runner.invoke(app, [
            "layout", "validate-feature",
            str(input_file)
        ])
        
        # Assert
        assert result.exit_code == 0
        assert "validation passed" in result.output.lower()
    
    def test_validate_feature_command_invalid_data(self, isolated_cli_environment, cli_runner):
        """Test feature validation with invalid data."""
        # Arrange
        input_file = isolated_cli_environment.create_feature_file({
            "name": "",  # Invalid: empty name
            "enabled": True
        })
        
        # Act
        result = cli_runner.invoke(app, [
            "layout", "validate-feature",
            str(input_file)
        ])
        
        # Assert
        assert result.exit_code != 0
        assert "validation failed" in result.output.lower()
```

### 3. Quality Assurance

Ensure your feature meets all quality standards:

#### Code Quality Checks

```bash
# MANDATORY before submitting
make lint          # Fix all linting issues
make format        # Format code properly
make test          # All tests must pass
make coverage      # Check coverage requirements

# Individual checks
uv run ruff check . --fix
uv run ruff format .
uv run mypy glovebox/
uv run pytest --cov=glovebox --cov-fail-under=90
```

#### Integration Testing

Test the feature in realistic scenarios:

```python
# tests/test_integration/test_new_feature_integration.py

class TestNewFeatureIntegration:
    def test_feature_end_to_end_workflow(self, tmp_path):
        """Test complete workflow from input to output."""
        # Arrange
        input_data = NewFeatureData(name="integration_test", enabled=True)
        input_file = tmp_path / "input.json"
        output_file = tmp_path / "output.json"
        
        # Save input data
        input_file.write_text(input_data.model_dump_json())
        
        # Act - Create services and process
        service = create_new_feature_service()
        
        # Load data
        loaded_data = NewFeatureData.model_validate_json(input_file.read_text())
        
        # Process data
        result = service.process_feature(loaded_data)
        
        # Save result
        success = service.save_feature(result.data, output_file)
        
        # Assert
        assert result.success is True
        assert success is True
        assert output_file.exists()
        
        # Verify output content
        output_data = NewFeatureData.model_validate_json(output_file.read_text())
        assert output_data.name == "integration_test"
    
    def test_feature_with_real_profile(self):
        """Test feature with real keyboard profile."""
        # Arrange
        profile = create_keyboard_profile("glove80", "v25.05")
        feature_data = NewFeatureData(name="profile_test", enabled=True)
        
        # Act
        service = create_new_feature_service()
        result = service.process_feature(feature_data)
        
        # Assert
        assert result.success is True
        # Add profile-specific assertions
```

#### Documentation

Document your feature thoroughly:

```python
# Add comprehensive docstrings
class NewFeatureService(BaseService):
    """Service for new feature operations.
    
    This service provides functionality for processing, validating, and saving
    feature data according to keyboard-specific requirements.
    
    Example:
        >>> service = create_new_feature_service()
        >>> data = NewFeatureData(name="my_feature", enabled=True)
        >>> result = service.process_feature(data)
        >>> assert result.success is True
    """
    
    def process_feature(self, data: NewFeatureData) -> NewFeatureResult:
        """Process feature data and return result.
        
        Args:
            data: Feature data to process
            
        Returns:
            NewFeatureResult with processing results
            
        Raises:
            LayoutError: If processing fails due to invalid data or system error
            
        Example:
            >>> data = NewFeatureData(name="test", enabled=True)
            >>> result = service.process_feature(data)
            >>> print(result.message)
        """
```

## Common Feature Patterns

### Adding a New Keyboard

When adding support for a new keyboard:

```yaml
# keyboards/new_keyboard.yaml
includes:
  - "new_keyboard/main.yaml"

# keyboards/new_keyboard/main.yaml
keyboard: "new_keyboard"
description: "New Keyboard Description"
includes:
  - "hardware.yaml"
  - "firmwares.yaml"
  - "strategies.yaml"
  - "kconfig.yaml"
  - "behaviors.yaml"

# keyboards/new_keyboard/hardware.yaml
hardware:
  matrix_rows: 6
  matrix_cols: 14
  key_count: 84
  split: true
  boards:
    - "nice_nano_v2"
    - "seeeduino_xiao_ble"

# keyboards/new_keyboard/firmwares.yaml
firmwares:
  v1.0:
    description: "Initial firmware release"
    compatibility: ">=1.0.0"
    kconfig_options:
      - "CONFIG_ZMK_KEYBOARD_NAME=\"new_keyboard\""
```

### Adding a New Compilation Strategy

When adding a new compilation strategy:

```python
# glovebox/compilation/services/new_strategy_service.py

class NewStrategyService(BaseService):
    """Service for new compilation strategy."""
    
    def __init__(
        self,
        docker_adapter: DockerAdapterProtocol,
        user_config: UserConfig,
    ):
        super().__init__()
        self.docker_adapter = docker_adapter
        self.user_config = user_config
    
    def compile(
        self,
        keymap_content: str,
        config_content: str,
        options: CompilationOptions,
    ) -> BuildResult:
        """Compile using new strategy."""
        # Implementation specific to new strategy
        pass

def create_new_strategy_service(
    docker_adapter: DockerAdapterProtocol | None = None,
    user_config: UserConfig | None = None,
) -> NewStrategyService:
    """Create new strategy compilation service."""
    # Standard factory function pattern
    pass

# Update glovebox/compilation/__init__.py
def create_compilation_service(strategy: str) -> CompilationServiceProtocol:
    """Create compilation service with specified strategy."""
    if strategy == "zmk_config":
        return create_zmk_west_service()
    elif strategy == "moergo":
        return create_moergo_nix_service()
    elif strategy == "new_strategy":  # Add this
        return create_new_strategy_service()
    else:
        raise ValueError(f"Unsupported compilation strategy: {strategy}")
```

### Adding CLI Command Groups

When adding a new command group:

```python
# glovebox/cli/commands/new_domain/__init__.py
import typer

new_domain_app = typer.Typer(
    name="new-domain",
    help="New domain management commands",
    no_args_is_help=True,
)

def register_commands(app: typer.Typer) -> None:
    """Register new domain commands."""
    app.add_typer(new_domain_app, name="new-domain")

# Register subcommands
from .core import register_core_commands
from .management import register_management_commands

register_core_commands(new_domain_app)
register_management_commands(new_domain_app)

# Update glovebox/cli/commands/__init__.py
def register_all_commands(app: typer.Typer) -> None:
    """Register all CLI commands with the main app."""
    register_layout_commands(app)
    register_firmware_commands(app)
    register_config_commands(app)
    register_new_domain_commands(app)  # Add this
    # ... other registrations
```

## Best Practices Checklist

### ✅ Architecture

- [ ] **Feature fits in appropriate domain** (layout, firmware, compilation, config)
- [ ] **Models inherit from GloveboxBaseModel** with proper validation
- [ ] **Service implements protocol interface** for type safety
- [ ] **Factory function follows create_* pattern** with optional dependencies
- [ ] **CLI commands use decorators** for parameter handling
- [ ] **Error handling follows domain patterns** with debug-aware logging

### ✅ Code Quality

- [ ] **All files under 500 lines** (split if needed)
- [ ] **All methods under 50 lines** (break down if needed)
- [ ] **Passes ruff linting** without warnings
- [ ] **Passes mypy type checking** without errors
- [ ] **Uses pathlib for file operations** (no os.path)
- [ ] **Comprehensive type annotations** on all functions
- [ ] **Proper docstrings** with examples

### ✅ Testing

- [ ] **Unit tests for all public methods** with mocked dependencies
- [ ] **Integration tests for workflows** with real components
- [ ] **CLI tests with isolated environment** preventing pollution
- [ ] **Test coverage above 90%** for new code
- [ ] **Error condition testing** with proper exception handling
- [ ] **Edge case coverage** for boundary conditions

### ✅ Documentation

- [ ] **Comprehensive docstrings** with parameters and examples
- [ ] **CLI help text** with usage examples
- [ ] **Update relevant guides** if architecture changes
- [ ] **Add to appropriate __all__ exports** for discoverability

### ✅ Integration

- [ ] **Factory function exported** from domain __init__.py
- [ ] **CLI commands registered** in command hierarchy
- [ ] **Models imported correctly** following domain boundaries
- [ ] **Error types follow hierarchy** with proper inheritance
- [ ] **Logging follows conventions** with lazy formatting

## Common Pitfalls to Avoid

### ❌ Architecture Violations

- **Don't cross domain boundaries** directly - use well-defined interfaces
- **Don't create singletons** - use factory functions for all services
- **Don't use global state** - pass dependencies explicitly
- **Don't bypass protocols** - always implement and use protocol interfaces

### ❌ Code Quality Issues

- **Don't use `os.path`** - always use `pathlib.Path`
- **Don't use `.dict()`** - use `.model_dump()` with proper parameters
- **Don't skip type annotations** - all parameters and returns must be typed
- **Don't use f-strings in logging** - use lazy `%` formatting

### ❌ Testing Problems

- **Don't write to current directory** - always use `tmp_path` or isolated fixtures
- **Don't skip error testing** - test both success and failure scenarios
- **Don't use real config paths** - use isolated configuration in tests
- **Don't create interdependent tests** - ensure each test is independent

### ❌ CLI Design Issues

- **Don't hardcode output formats** - use themed console and consistent formatting
- **Don't skip parameter validation** - validate all inputs with clear error messages
- **Don't ignore user experience** - provide helpful feedback and progress indicators
- **Don't forget autocompletion** - add smart autocompletion for parameters

## Getting Help

When you need assistance:

1. **📚 Review existing patterns** in similar domains for guidance
2. **🔍 Search codebase** for examples of similar features
3. **📖 Read domain documentation** for architectural guidance
4. **💬 Ask in GitHub Discussions** for design advice
5. **🐛 Check GitHub Issues** for related problems or solutions

---

**Next Steps**:
- Review [Service Layer Patterns](../patterns/service-layer.md) for service implementation details
- Check [Testing Strategy](testing-strategy.md) for comprehensive testing approaches
- Explore [Code Conventions](../patterns/code-conventions.md) for style guidelines