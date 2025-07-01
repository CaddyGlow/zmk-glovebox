# Testing Strategy and Guidelines

This document outlines the comprehensive testing strategy for Glovebox, covering testing approaches, patterns, and requirements that ensure code quality and reliability.

## Testing Philosophy

Glovebox follows a **test-driven quality approach** with these core principles:

- **🚫 NO CODE can be merged without tests** - This is NON-NEGOTIABLE
- **📊 Minimum 90% code coverage** for all new code
- **🔄 Test isolation** - Tests must not pollute the file system or global state
- **⚡ Fast feedback** - Tests should run quickly for rapid development cycles
- **🎯 Domain-focused testing** - Tests organized by domain boundaries

## Testing Levels

### 1. Unit Tests (Primary)

Test individual components in isolation with mocked dependencies.

**Scope**: Single functions, methods, or classes
**Speed**: Very fast (milliseconds)
**Coverage**: 90%+ of business logic

```python
# Example: Testing a domain service
class TestLayoutService:
    def test_generate_layout_success(self):
        # Arrange
        mock_file_adapter = Mock(spec=FileAdapterProtocol)
        mock_template_adapter = Mock(spec=TemplateAdapterProtocol)
        
        service = LayoutService(
            file_adapter=mock_file_adapter,
            template_adapter=mock_template_adapter
        )
        
        layout_data = create_test_layout_data()
        profile = create_test_keyboard_profile()
        
        # Act
        result = service.generate(profile, layout_data)
        
        # Assert
        assert isinstance(result, LayoutResult)
        assert result.success is True
        mock_template_adapter.render.assert_called_once()
```

### 2. Integration Tests

Test component interactions and domain boundaries.

**Scope**: Multiple components working together
**Speed**: Fast (seconds)
**Coverage**: Critical integration points

```python
# Example: Testing domain interaction
class TestLayoutCompilationIntegration:
    def test_layout_to_compilation_flow(self, tmp_path):
        # Arrange
        layout_service = create_layout_service()
        compilation_service = create_compilation_service("zmk_config")
        
        # Act - Generate layout files
        layout_result = layout_service.generate(profile, layout_data, tmp_path)
        
        # Act - Compile generated files
        build_result = compilation_service.compile(
            keymap_file=layout_result.keymap_path,
            config_file=layout_result.config_path,
            options=CompilationOptions()
        )
        
        # Assert
        assert layout_result.success is True
        assert build_result.success is True
        assert build_result.firmware_path.exists()
```

### 3. CLI Tests

Test command-line interface functionality with isolated environments.

**Scope**: CLI commands and user workflows
**Speed**: Medium (seconds)
**Coverage**: All CLI commands and edge cases

```python
# Example: Testing CLI commands
class TestLayoutCLI:
    def test_compile_command_success(self, isolated_cli_environment, cli_runner):
        # Arrange
        layout_file = isolated_cli_environment.create_layout_file()
        output_dir = isolated_cli_environment.temp_dir / "output"
        
        # Act
        result = cli_runner.invoke(app, [
            "layout", "compile", 
            str(layout_file), 
            str(output_dir),
            "--profile", "glove80/v25.05"
        ])
        
        # Assert
        assert result.exit_code == 0
        assert "Successfully compiled layout" in result.output
        assert (output_dir / "keymap.keymap").exists()
```

### 4. End-to-End Tests (Limited)

Test complete user workflows with real external dependencies.

**Scope**: Full application workflows
**Speed**: Slow (minutes)
**Coverage**: Critical user paths only

```python
# Example: E2E test with Docker compilation
@pytest.mark.e2e
@pytest.mark.slow
class TestE2EWorkflow:
    def test_complete_layout_to_firmware_workflow(self, tmp_path):
        # This test requires Docker and takes longer
        # Only used for critical workflows
        pass
```

## Test Organization

### Directory Structure

```
tests/
├── conftest.py                    # Global test fixtures
├── test_unit/                     # Unit tests (majority)
│   ├── test_layout/              # Layout domain tests
│   │   ├── conftest.py           # Domain-specific fixtures
│   │   ├── test_service.py       # Service tests
│   │   ├── test_models.py        # Model tests
│   │   └── test_utils.py         # Utility tests
│   ├── test_firmware/            # Firmware domain tests
│   ├── test_compilation/         # Compilation domain tests
│   └── test_config/              # Configuration tests
├── test_integration/             # Integration tests
│   ├── test_domain_interactions.py
│   └── test_service_integration.py
├── test_cli/                     # CLI tests
│   ├── conftest.py               # CLI-specific fixtures
│   ├── test_layout_commands.py
│   ├── test_firmware_commands.py
│   └── test_config_commands.py
├── test_e2e/                     # End-to-end tests
│   └── test_workflows.py
└── fixtures/                     # Test data
    ├── layouts/
    ├── keymaps/
    └── configs/
```

### File Size Limits

**ENFORCED**: Maximum 500 lines per test file

When test files exceed this limit:
1. Split by functional area (e.g., `test_service_generation.py`, `test_service_validation.py`)
2. Create subdirectories for complex domains
3. Use shared fixtures in `conftest.py` files

## Test Isolation Requirements

### CRITICAL: Anti-Pollution Rules

Tests MUST be isolated to prevent interference:

#### ❌ FORBIDDEN Practices

```python
# ❌ NEVER write to current working directory
def test_bad_file_creation():
    Path("test.json").write_text('{"test": "data"}')  # POLLUTES PROJECT

# ❌ NEVER use real user configuration
def test_bad_config():
    config = UserConfig()  # Uses real ~/.glovebox/ directory

# ❌ NEVER modify global state without restoration
def test_bad_global_state():
    os.environ["GLOBAL_VAR"] = "test_value"  # No cleanup
```

#### ✅ REQUIRED Practices

```python
# ✅ Always use tmp_path for file operations
def test_file_creation(tmp_path):
    test_file = tmp_path / "test.json"
    test_file.write_text('{"test": "data"}')

# ✅ Use isolated_config for configuration tests
def test_config_operation(isolated_config):
    config = UserConfig(cli_config_path=isolated_config.config_file)

# ✅ Use environment restoration
def test_environment_change():
    with patch.dict(os.environ, {"TEST_VAR": "test_value"}):
        # Test code here
        pass
    # Environment automatically restored
```

### Isolation Fixtures

Critical fixtures that ensure test isolation:

```python
# conftest.py - Global fixtures

@pytest.fixture
def isolated_config(tmp_path):
    """Provide completely isolated configuration environment."""
    config_dir = tmp_path / ".glovebox"
    config_dir.mkdir(parents=True)
    
    config_file = config_dir / "config.yaml"
    config_file.write_text("""
cache_strategy: "disabled"
log_level: "WARNING"
""")
    
    yield ConfigContext(
        config_dir=config_dir,
        config_file=config_file,
        temp_dir=tmp_path
    )

@pytest.fixture
def isolated_cli_environment(isolated_config):
    """Provide isolated environment for CLI command testing."""
    return CLIEnvironment(
        config=isolated_config,
        temp_dir=isolated_config.temp_dir,
        output_capture=True
    )

@pytest.fixture(autouse=True)
def reset_shared_cache():
    """Reset shared cache instances between tests (autouse=True)."""
    from glovebox.core.cache import reset_shared_cache_instances
    reset_shared_cache_instances()
    yield
    reset_shared_cache_instances()
```

## Testing Patterns by Component Type

### Domain Service Testing

```python
class TestLayoutService:
    """Test pattern for domain services."""
    
    @pytest.fixture
    def mock_dependencies(self):
        """Create mocked dependencies for the service."""
        return {
            'file_adapter': Mock(spec=FileAdapterProtocol),
            'template_adapter': Mock(spec=TemplateAdapterProtocol),
            'behavior_registry': Mock(spec=BehaviorRegistryProtocol),
        }
    
    @pytest.fixture
    def service(self, mock_dependencies):
        """Create service instance with mocked dependencies."""
        return LayoutService(**mock_dependencies)
    
    def test_successful_operation(self, service, mock_dependencies):
        """Test successful operation with proper mocking."""
        # Arrange
        mock_dependencies['file_adapter'].read_file.return_value = "content"
        mock_dependencies['template_adapter'].render.return_value = "rendered"
        
        # Act
        result = service.generate(create_test_profile(), create_test_layout())
        
        # Assert
        assert result.success is True
        assert mock_dependencies['template_adapter'].render.called
    
    def test_error_handling(self, service, mock_dependencies):
        """Test error handling and logging."""
        # Arrange
        mock_dependencies['file_adapter'].read_file.side_effect = FileNotFoundError()
        
        # Act & Assert
        with pytest.raises(LayoutError, match="File not found"):
            service.generate(create_test_profile(), create_test_layout())
```

### Adapter Testing

```python
class TestFileAdapter:
    """Test pattern for adapter classes."""
    
    def test_read_file_success(self, tmp_path):
        """Test successful file reading."""
        # Arrange
        adapter = FileAdapter()
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        # Act
        content = adapter.read_file(test_file)
        
        # Assert
        assert content == "test content"
    
    def test_read_file_not_found(self):
        """Test error handling for missing files."""
        # Arrange
        adapter = FileAdapter()
        nonexistent_file = Path("/nonexistent/file.txt")
        
        # Act & Assert
        with pytest.raises(FileSystemError, match="File not found"):
            adapter.read_file(nonexistent_file)
    
    @patch('pathlib.Path.read_text')
    def test_read_file_permission_error(self, mock_read):
        """Test error handling for permission issues."""
        # Arrange
        adapter = FileAdapter()
        mock_read.side_effect = PermissionError("Access denied")
        
        # Act & Assert
        with pytest.raises(FileSystemError, match="Permission denied"):
            adapter.read_file(Path("test.txt"))
```

### Model Testing

```python
class TestLayoutData:
    """Test pattern for Pydantic models."""
    
    def test_model_validation_success(self):
        """Test successful model creation and validation."""
        # Arrange
        data = {
            "title": "Test Layout",
            "keyboard": "glove80",
            "layers": [{"name": "Base", "bindings": ["&kp A"] * 80}]
        }
        
        # Act
        layout = LayoutData.model_validate(data)
        
        # Assert
        assert layout.title == "Test Layout"
        assert layout.keyboard == "glove80"
        assert len(layout.layers) == 1
    
    def test_model_validation_error(self):
        """Test model validation with invalid data."""
        # Arrange
        invalid_data = {"title": "", "keyboard": ""}  # Missing required fields
        
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            LayoutData.model_validate(invalid_data)
        
        assert "layers" in str(exc_info.value)
    
    def test_model_serialization(self):
        """Test model serialization with proper parameters."""
        # Arrange
        layout = create_test_layout_data()
        
        # Act
        serialized = layout.model_dump(by_alias=True, exclude_unset=True, mode="json")
        
        # Assert
        assert isinstance(serialized, dict)
        assert "title" in serialized
        assert "keyboard" in serialized
    
    def test_business_logic_methods(self):
        """Test business logic methods on models."""
        # Arrange
        layout = create_test_layout_data()
        
        # Act
        base_layer = layout.get_layer_by_name("Base")
        has_required = layout.has_required_layers()
        
        # Assert
        assert base_layer is not None
        assert has_required is True
```

### CLI Command Testing

```python
class TestLayoutCommands:
    """Test pattern for CLI commands."""
    
    def test_compile_command_success(self, isolated_cli_environment, cli_runner):
        """Test successful layout compilation command."""
        # Arrange
        layout_file = isolated_cli_environment.create_test_layout()
        output_dir = isolated_cli_environment.temp_dir / "output"
        
        # Act
        result = cli_runner.invoke(app, [
            "layout", "compile",
            str(layout_file),
            str(output_dir),
            "--profile", "glove80/v25.05"
        ])
        
        # Assert
        assert result.exit_code == 0
        assert "Successfully compiled" in result.output
        assert (output_dir / "keymap.keymap").exists()
        assert (output_dir / "config.conf").exists()
    
    def test_compile_command_invalid_profile(self, isolated_cli_environment, cli_runner):
        """Test command with invalid profile."""
        # Arrange
        layout_file = isolated_cli_environment.create_test_layout()
        output_dir = isolated_cli_environment.temp_dir / "output"
        
        # Act
        result = cli_runner.invoke(app, [
            "layout", "compile",
            str(layout_file),
            str(output_dir),
            "--profile", "invalid/profile"
        ])
        
        # Assert
        assert result.exit_code != 0
        assert "Profile not found" in result.output
    
    def test_compile_command_missing_file(self, cli_runner):
        """Test command with missing input file."""
        # Act
        result = cli_runner.invoke(app, [
            "layout", "compile",
            "/nonexistent/file.json",
            "/tmp/output",
            "--profile", "glove80/v25.05"
        ])
        
        # Assert
        assert result.exit_code != 0
        assert "File not found" in result.output
```

## Test Data Management

### Test Fixtures and Factories

Create reusable test data with factory functions:

```python
# tests/fixtures/factories.py

def create_test_layout_data(
    title: str = "Test Layout",
    keyboard: str = "glove80",
    layer_count: int = 4
) -> LayoutData:
    """Factory for creating test layout data."""
    layers = []
    for i in range(layer_count):
        layer = LayoutLayer(
            name=f"Layer{i}",
            bindings=["&kp A"] * 80  # Default bindings for Glove80
        )
        layers.append(layer)
    
    return LayoutData(
        title=title,
        keyboard=keyboard,
        layers=layers,
        config={},
        behaviors=[]
    )

def create_test_keyboard_profile(
    keyboard: str = "glove80",
    firmware: str = "v25.05"
) -> KeyboardProfile:
    """Factory for creating test keyboard profiles."""
    return KeyboardProfile(
        name=f"{keyboard}/{firmware}",
        keyboard_config=create_test_keyboard_config(keyboard),
        firmware_config=create_test_firmware_config(firmware)
    )
```

### Loading Test Data Files

```python
# tests/fixtures/loaders.py

def load_test_layout(name: str) -> LayoutData:
    """Load test layout from fixtures directory."""
    fixtures_dir = Path(__file__).parent / "data"
    layout_file = fixtures_dir / "layouts" / f"{name}.json"
    
    with layout_file.open() as f:
        data = json.load(f)
    
    return LayoutData.model_validate(data)

def load_test_keymap(name: str) -> str:
    """Load test keymap content from fixtures."""
    fixtures_dir = Path(__file__).parent / "data"
    keymap_file = fixtures_dir / "keymaps" / f"{name}.keymap"
    
    return keymap_file.read_text()
```

## Advanced Testing Techniques

### Parameterized Testing

Test multiple scenarios efficiently:

```python
@pytest.mark.parametrize("keyboard,expected_boards", [
    ("glove80", ["nice_nano_v2"]),
    ("crkbd", ["nice_nano_v2", "seeeduino_xiao_ble"]),
    ("lily58", ["nice_nano_v2"]),
])
def test_keyboard_board_detection(keyboard, expected_boards):
    """Test board detection for different keyboards."""
    profile = create_test_keyboard_profile(keyboard=keyboard)
    
    detected_boards = profile.get_supported_boards()
    
    assert detected_boards == expected_boards
```

### Property-Based Testing

Use hypothesis for property-based testing:

```python
from hypothesis import given, strategies as st

@given(
    title=st.text(min_size=1, max_size=100),
    layer_count=st.integers(min_value=1, max_value=10)
)
def test_layout_creation_properties(title, layer_count):
    """Property-based test for layout creation."""
    layout = create_test_layout_data(title=title, layer_count=layer_count)
    
    # Properties that should always hold
    assert layout.title == title
    assert len(layout.layers) == layer_count
    assert all(len(layer.bindings) == 80 for layer in layout.layers)
```

### Performance Testing

Test performance characteristics:

```python
import time
import pytest

def test_layout_generation_performance():
    """Test that layout generation completes within reasonable time."""
    # Arrange
    service = create_layout_service()
    layout = create_test_layout_data()
    profile = create_test_keyboard_profile()
    
    # Act
    start_time = time.time()
    result = service.generate(profile, layout)
    execution_time = time.time() - start_time
    
    # Assert
    assert result.success is True
    assert execution_time < 1.0  # Should complete within 1 second
```

## Continuous Integration Testing

### Test Execution Strategy

```yaml
# .github/workflows/test.yml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install dependencies
        run: |
          pip install uv
          uv sync
      
      - name: Run linting
        run: uv run ruff check .
      
      - name: Run type checking
        run: uv run mypy glovebox/
      
      - name: Run unit tests
        run: uv run pytest tests/test_unit/ -v
      
      - name: Run integration tests
        run: uv run pytest tests/test_integration/ -v
      
      - name: Run CLI tests
        run: uv run pytest tests/test_cli/ -v
      
      - name: Generate coverage report
        run: uv run pytest --cov=glovebox --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

### Test Categorization

Mark tests for different execution contexts:

```python
# Mark slow tests
@pytest.mark.slow
def test_full_compilation_workflow():
    """Test that requires Docker and takes longer."""
    pass

# Mark integration tests
@pytest.mark.integration
def test_service_integration():
    """Test multiple services working together."""
    pass

# Mark CLI tests
@pytest.mark.cli
def test_command_execution():
    """Test CLI command functionality."""
    pass
```

Run specific test categories:

```bash
# Run only fast unit tests
uv run pytest -m "not slow and not integration"

# Run integration tests
uv run pytest -m integration

# Skip slow tests in development
uv run pytest -m "not slow"
```

## Test Coverage Requirements

### Coverage Targets

- **Unit Tests**: 95%+ coverage of business logic
- **Integration Tests**: 100% coverage of critical paths
- **CLI Tests**: 100% coverage of user-facing commands
- **Overall**: 90%+ coverage of entire codebase

### Coverage Reporting

```bash
# Generate HTML coverage report
uv run pytest --cov=glovebox --cov-report=html

# Generate terminal coverage report
uv run pytest --cov=glovebox --cov-report=term-missing

# Fail if coverage below threshold
uv run pytest --cov=glovebox --cov-fail-under=90
```

### Coverage Configuration

```toml
# pyproject.toml
[tool.coverage.run]
source = ["glovebox"]
omit = [
    "*/tests/*",
    "*/conftest.py",
    "*/__init__.py",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
]
```

## Debugging Tests

### Debugging Failing Tests

```bash
# Run with verbose output and stop on first failure
uv run pytest -v -x --tb=long

# Run specific test with debugging
uv run pytest tests/test_layout/test_service.py::test_specific_function -v -s

# Run with pdb debugger
uv run pytest --pdb

# Run last failed tests only
uv run pytest --lf
```

### Debugging Test Isolation Issues

```python
# Add debug output to identify pollution sources
def test_debug_isolation(tmp_path):
    """Debug test isolation issues."""
    import os
    print(f"Current directory: {os.getcwd()}")
    print(f"Temp directory: {tmp_path}")
    print(f"Directory contents: {list(Path('.').iterdir())}")
    
    # Your test code here
```

### Test Logging

```python
# Enable logging in tests for debugging
import logging

def test_with_logging(caplog):
    """Test with captured logging output."""
    with caplog.at_level(logging.DEBUG):
        # Test code that produces log output
        service.perform_operation()
    
    # Assert log messages
    assert "Expected log message" in caplog.text
```

## Best Practices Summary

### ✅ DO

- **Write tests first** when adding new functionality
- **Use descriptive test names** that explain the scenario
- **Test error conditions** as thoroughly as success cases
- **Mock external dependencies** to ensure test isolation
- **Use appropriate test fixtures** for setup and teardown
- **Test business logic** in domain models
- **Verify both positive and negative cases**
- **Use `tmp_path` for all file operations**
- **Include integration tests** for critical workflows

### ❌ DON'T

- **Write tests that depend on external state**
- **Create files in the project directory during tests**
- **Use real network calls in unit tests**
- **Write tests longer than 50 lines** (split into multiple tests)
- **Skip testing error handling**
- **Use global variables or singletons**
- **Write flaky tests** that pass/fail inconsistently
- **Test implementation details** instead of behavior

---

**Next Steps**:
- Review [Code Conventions](../patterns/code-conventions.md) for coding standards
- Explore [Domain Testing Examples](../domains/) for domain-specific testing patterns
- Check [API Reference](../api/) for testing utilities and fixtures