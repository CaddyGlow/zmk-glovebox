# Testing Requirements and Standards

This document outlines the mandatory testing requirements for the Glovebox project. **ALL CODE MUST HAVE COMPREHENSIVE TEST COVERAGE - NO EXCEPTIONS.**

## Mandatory Testing Requirements

### 1. Coverage Requirements

**EVERY public function, method, class, and module MUST have corresponding tests:**

- **Public Functions**: Every function exposed in a module's public interface
- **Public Methods**: Every method in public classes, including constructors
- **Public Classes**: All public classes with comprehensive method coverage
- **Module Interfaces**: All exported functionality from each module
- **Minimum 90% code coverage** for all new code
- **Integration tests** for all CLI commands and workflows
- Should pass: `mypy`

### 2. Test Structure Standards

#### Class Testing Pattern
```python
class TestLayoutService:
    """Test class naming: Test + ClassUnderTest"""
    
    def test_compile_layout_success(self):
        """Test successful operation"""
        pass
    
    def test_compile_layout_invalid_input(self):
        """Test error handling"""
        pass
    
    def test_compile_layout_missing_file(self):
        """Test edge cases"""
        pass
    
    def test_validate_layout_data(self):
        """Test each public method"""
        pass
```

#### Function Testing Pattern
```python
def test_parse_binding_with_valid_input():
    """Test normal operation"""
    pass

def test_parse_binding_with_empty_string():
    """Test edge case - empty input"""
    pass

def test_parse_binding_with_invalid_format():
    """Test error handling"""
    pass

def test_parse_binding_with_special_characters():
    """Test boundary conditions"""
    pass
```

### 3. Required Test Categories

#### Unit Tests
- **Purpose**: Test individual functions/methods in isolation
- **Location**: `tests/test_[domain]/test_[module].py`
- **Requirements**: Mock all external dependencies
- **Coverage**: Every public function and method

#### Integration Tests
- **Purpose**: Test component interactions and workflows
- **Location**: `tests/test_integration/`
- **Requirements**: Test real component interactions
- **Coverage**: All major workflows and use cases

#### CLI Tests
- **Purpose**: Test all command-line interfaces
- **Location**: `tests/test_cli/`
- **Requirements**: Test all commands, options, and error scenarios
- **Coverage**: Every CLI command and flag combination

#### Error Handling Tests
- **Purpose**: Test all error conditions and edge cases
- **Requirements**: Test exception types, error messages, and recovery
- **Coverage**: All error paths and exception scenarios

#### Regression Tests
- **Purpose**: Prevent previously fixed bugs from returning
- **Requirements**: Test case for every bug fix
- **Coverage**: All historical bug scenarios

#### Metrics and Decorator Tests
- **Purpose**: Test automatic metrics collection and decorator functionality
- **Location**: `tests/test_metrics/`
- **Requirements**: Test decorator behavior, context extraction, and dependency injection
- **Coverage**: All decorator patterns, context extractors, and metrics collection scenarios

### 4. Testing Technology Stack

#### Core Testing Framework
```python
import pytest
import pytest_asyncio
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import shutil
```

#### Fixtures and Test Data
```python
@pytest.fixture
def sample_layout_data():
    """Reusable test data fixture"""
    return {
        "keyboard": "glove80",
        "layers": [{"name": "default", "bindings": []}]
    }

@pytest.fixture
def temp_directory():
    """Temporary directory for file operations"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)
```

#### Mocking External Dependencies
```python
@patch('glovebox.adapters.docker.DockerAdapter')
def test_compilation_with_docker(mock_docker):
    """Mock external systems"""
    mock_docker.build.return_value = BuildResult(success=True)
    # Test implementation
```

### 5. Parametrized Testing

Use parametrized tests for multiple input variations:

```python
@pytest.mark.parametrize("input_data,expected", [
    ({"valid": "data"}, True),
    ({"invalid": None}, False),
    ({}, False),
])
def test_validate_input(input_data, expected):
    result = validate_input(input_data)
    assert result == expected
```

### 6. Async Testing

For async functions, use pytest-asyncio:

```python
@pytest.mark.asyncio
async def test_async_compilation():
    service = await create_compilation_service()
    result = await service.compile_async(layout_data)
    assert result.success
```

### 7. Testing Commands

#### Essential Test Commands
```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=glovebox --cov-report=term-missing

# Run specific test categories
pytest tests/test_integration/     # Integration tests
pytest tests/test_cli/            # CLI tests
pytest tests/test_unit/           # Unit tests

# Run tests with verbose output
pytest -v

# Run tests matching a pattern
pytest -k "test_layout"

# Run tests and stop on first failure
pytest -x
```

#### Coverage Analysis
```bash
# Generate HTML coverage report
pytest --cov=glovebox --cov-report=html

# Check coverage thresholds
pytest --cov=glovebox --cov-fail-under=90
```

### 8. Test Organization

#### Directory Structure
```
tests/
├── conftest.py                 # Shared fixtures with test isolation
├── test_unit/                  # Unit tests
│   ├── test_layout/
│   │   ├── test_services.py
│   │   ├── test_models.py
│   │   └── test_version_manager.py
│   ├── test_firmware/
│   ├── test_compilation/
│   └── test_config/
├── test_metrics/               # Metrics system tests
│   ├── test_models.py          # Metrics model validation
│   ├── test_service.py         # Service layer testing
│   ├── test_storage.py         # Storage adapter testing
│   ├── test_collector.py       # Context manager testing
│   ├── test_decorators.py      # Decorator functionality
│   ├── test_integration.py     # End-to-end metrics flow
│   ├── test_cli_commands.py    # Metrics CLI commands
│   └── test_dependency_injection.py  # DI pattern testing
├── test_integration/           # Integration tests
│   ├── test_layout_workflow.py
│   ├── test_compilation_workflow.py
│   └── test_firmware_workflow.py
├── test_cli/                   # CLI tests
│   ├── test_layout_commands.py
│   ├── test_firmware_commands.py
│   └── test_config_commands.py
└── fixtures/                   # Test data files
    ├── layouts/
    ├── keymaps/
    └── configs/
```

#### Test File Naming
- Unit tests: `test_[module_name].py`
- Integration tests: `test_[workflow_name].py`
- CLI tests: `test_[command_group]_commands.py`
- Metrics tests: `test_[component].py` (models, service, storage, etc.)
- Decorator tests: `test_decorators.py`

### 9. Quality Gates

#### Pre-Commit Requirements
All tests must pass before any code can be committed:

```bash
# Required commands that MUST pass
pytest                                    # All tests pass
pytest --cov=glovebox --cov-fail-under=90  # Coverage threshold
ruff check .                             # Linting passes
mypy glovebox/                           # Type checking passes
```

#### Pull Request Requirements
- All tests pass in CI/CD
- Code coverage maintained or improved
- New functionality includes comprehensive tests
- Bug fixes include regression tests

### 10. Testing Best Practices

#### Test Isolation
- Each test should be independent
- Use fixtures for common setup
- Clean up resources after tests
- Avoid shared mutable state

#### Test Clarity
- Use descriptive test names
- Include docstrings for complex tests
- Arrange-Act-Assert pattern
- Clear failure messages

#### Error Testing
```python
def test_invalid_input_raises_validation_error():
    with pytest.raises(ValidationError, match="Invalid keyboard type"):
        validate_keyboard_config({"invalid": "config"})
```

#### Mock Strategy
- Mock external dependencies (Docker, USB, network)
- Don't mock the code under test
- Use realistic mock return values
- Verify mock calls when relevant

### 11. Continuous Integration

#### GitHub Actions Integration
Tests run automatically on:
- Every pull request
- Every push to main/dev branches
- Nightly builds for regression testing

#### Test Matrix
- Multiple Python versions (3.11, 3.12)
- Multiple operating systems (Linux, macOS, Windows)
- Different dependency versions

### 12. Metrics and Decorator Testing Methodology

#### Comprehensive Metrics Testing Pattern

The metrics system requires thorough testing across multiple dimensions:

```python
class TestMetricsDecorators:
    """Test metrics decorators functionality."""

    def test_track_operation_basic_sync_function(self):
        """Test basic decorator on synchronous function."""
        mock_service = Mock(spec=MetricsServiceProtocol)

        @track_operation(OperationType.LAYOUT_COMPILATION, metrics_service=mock_service)
        def test_function(arg1: str, arg2: int = 42) -> str:
            return f"result: {arg1}-{arg2}"

        result = test_function("test", arg2=100)

        assert result == "result: test-100"
        # Verify decorator preserves function behavior

    def test_decorator_with_context_extraction(self):
        """Test decorator with context extraction."""
        mock_service = Mock(spec=MetricsServiceProtocol)

        def test_extractor(func, args, kwargs):
            return {"test_context": "extracted", "args_count": len(args)}

        @track_operation(
            OperationType.LAYOUT_COMPILATION,
            extract_context=test_extractor,
            metrics_service=mock_service,
        )
        def function_with_context(a, b, c=None):
            return f"{a}-{b}-{c}"

        result = function_with_context("x", "y", c="z")
        assert result == "x-y-z"

    def test_decorator_preserves_dependency_injection(self):
        """Test that decorator preserves dependency injection patterns."""
        mock_service = Mock(spec=MetricsServiceProtocol)

        # Create decorator with injected service
        tracker = create_operation_tracker(
            OperationType.LAYOUT_COMPILATION, metrics_service=mock_service
        )

        @tracker
        def service_method():
            return "injected"

        result = service_method()
        assert result == "injected"
```

#### Context Extractor Testing

```python
class TestContextExtractors:
    """Test context extraction functions."""

    def test_extract_cli_context_basic(self):
        """Test basic CLI context extraction."""
        def mock_cli_function(ctx, json_file, output_dir, profile=None, force=False):
            pass

        args = ()
        kwargs = {
            "ctx": Mock(spec=typer.Context),
            "json_file": "/path/to/layout.json",
            "output_dir": "/path/to/output",
            "profile": "glove80/v25.05",
            "force": True,
        }

        context = extract_cli_context(mock_cli_function, args, kwargs)

        assert context["profile_name"] == "glove80/v25.05"
        assert context["input_file"] == "/path/to/layout.json"
        assert context["output_directory"] == "/path/to/output"
        assert context["force"] is True

    def test_context_extractors_handle_exceptions(self):
        """Test that context extractors handle exceptions gracefully."""
        def mock_function():
            pass

        # Test with invalid arguments that would cause exceptions
        context = extract_cli_context(mock_function, (), {"invalid": object()})
        assert isinstance(context, dict)  # Should return empty dict, not crash
```

#### Dependency Injection Testing Pattern

```python
class TestMetricsDependencyInjection:
    """Test dependency injection functionality in metrics system."""

    def test_full_dependency_injection_chain(self):
        """Test injecting dependencies through the entire chain."""
        # Create mock cache
        mock_cache = Mock(spec=CacheManager)

        # Create storage with injected cache
        storage = create_metrics_storage(cache=mock_cache)

        # Create service with injected storage
        service = create_metrics_service(storage=storage)

        # Create collector with injected service
        collector = create_metrics_collector(
            operation_type=OperationType.FIRMWARE_COMPILATION,
            operation_id="test-operation",
            metrics_service=service,
        )

        # Verify the entire chain is connected
        assert collector.metrics_service is service
        assert service.storage is storage
        assert storage.cache is mock_cache
        assert collector.operation_id == "test-operation"

    def test_backward_compatibility(self):
        """Test that existing code without dependency injection still works."""
        # This simulates how existing code would call the factories
        service = create_metrics_service()
        storage = create_metrics_storage()
        collector = create_metrics_collector(OperationType.FIRMWARE_COMPILATION)

        # Verify everything is properly created
        assert service is not None
        assert storage is not None
        assert collector is not None
        assert service.storage is not None
        assert collector.metrics_service is not None
```

#### Integration Testing for Metrics

```python
class TestMetricsSystemIntegration:
    """Test metrics system integration across components."""

    def test_end_to_end_metrics_collection(self, isolated_config):
        """Test complete metrics collection workflow."""
        # Create metrics service with isolated storage
        cache = create_default_cache(tag="test_metrics")
        storage = create_metrics_storage(cache=cache)
        service = create_metrics_service(storage=storage)

        # Collect metrics using context manager
        with create_metrics_collector(
            OperationType.LAYOUT_COMPILATION, metrics_service=service
        ) as metrics:
            metrics.set_context(
                profile_name="test/profile",
                input_file="/test/input.json"
            )
            # Simulate operation timing
            metrics.record_timing("parsing", 0.1)
            metrics.record_timing("validation", 0.05)

        # Verify metrics were stored
        retrieved_metrics = service.get_operation_metrics(limit=1)
        assert len(retrieved_metrics) == 1
        
        metric = retrieved_metrics[0]
        assert metric.operation_type == OperationType.LAYOUT_COMPILATION
        assert metric.status == OperationStatus.SUCCESS
        assert metric.profile_name == "test/profile"
        assert metric.parsing_time_seconds == 0.1
        assert metric.validation_time_seconds == 0.05
```

### 13. Performance Testing

For performance-critical components:

```python
import time
import pytest

def test_compilation_performance():
    start_time = time.time()
    result = compile_layout(large_layout_data)
    duration = time.time() - start_time
    
    assert result.success
    assert duration < 30.0  # Max 30 seconds

def test_metrics_decorator_overhead():
    """Test that metrics decorators have minimal performance impact."""
    import time
    
    @track_operation(OperationType.LAYOUT_COMPILATION)
    def decorated_function():
        return "result"
    
    def undecorated_function():
        return "result"
    
    # Measure decorator overhead
    start = time.perf_counter()
    for _ in range(1000):
        decorated_function()
    decorated_time = time.perf_counter() - start
    
    start = time.perf_counter()
    for _ in range(1000):
        undecorated_function()
    undecorated_time = time.perf_counter() - start
    
    # Decorator should add minimal overhead (< 2ms per call)
    overhead = (decorated_time - undecorated_time) / 1000
    assert overhead < 0.002  # Less than 2ms per call
```

### 14. Test Isolation and Anti-Pollution

#### Critical Test Isolation Requirements

**MANDATORY REQUIREMENTS - MUST BE FOLLOWED WITHOUT EXCEPTION:**

1. **NEVER write files to the current working directory in tests**:
   ```python
   # ✅ CORRECT - Always use tmp_path or isolated fixtures
   def test_file_creation(tmp_path):
       test_file = tmp_path / "test.json"
       test_file.write_text('{"test": "data"}')
   
   # ❌ INCORRECT - Never write to current directory
   def test_file_creation_bad():
       Path("test.json").write_text('{"test": "data"}')  # NEVER DO THIS
   ```

2. **ALWAYS use proper test isolation for configuration**:
   ```python
   # ✅ CORRECT - Use isolated_config fixture for any config-related tests
   def test_config_operation(isolated_config):
       config = UserConfig(cli_config_path=isolated_config.config_file)
       # Test operations are isolated to temp directory
   
   # ❌ INCORRECT - Never modify real user configuration
   def test_config_bad():
       config = UserConfig()  # Uses real ~/.glovebox/ directory
   ```

3. **MANDATORY use of isolation fixtures for CLI tests**:
   ```python
   # ✅ CORRECT - Use isolated_cli_environment for CLI command tests
   def test_cli_command(isolated_cli_environment, cli_runner):
       result = cli_runner.invoke(app, ["config", "list"])
       # All file operations isolated to temp directory
   
   # ❌ INCORRECT - CLI tests without isolation can pollute project
   def test_cli_bad(cli_runner):
       result = cli_runner.invoke(app, ["config", "export"])  # May write to current dir
   ```

4. **ENFORCE test file size limits**:
   - **Maximum 500 lines per test file** (ENFORCED)
   - Split large test files into domain-specific modules
   - Use shared fixtures in `conftest.py` files

#### Available Isolation Fixtures
- `isolated_config`: Complete configuration isolation with temp directories
- `isolated_cli_environment`: CLI command isolation with mocked environment
- `temp_config_dir`: Temporary configuration directory
- `mock_user_config`: Mocked user configuration that doesn't touch filesystem

#### Shared Cache Reset for Metrics Tests
```python
@pytest.fixture(autouse=True)
def reset_shared_cache() -> Generator[None, None, None]:
    """Reset shared cache instances between tests for isolation."""
    from glovebox.core.cache_v2 import reset_shared_cache_instances
    
    reset_shared_cache_instances()  # Before test
    yield
    reset_shared_cache_instances()  # After test
```

### 15. Documentation Testing

Test code examples in documentation:

```python
def test_readme_examples():
    """Ensure README examples work correctly"""
    # Test actual code from README
    pass

def test_decorator_documentation_examples():
    """Test that decorator examples in docs work correctly"""
    from glovebox.metrics.decorators import track_layout_operation
    from glovebox.metrics.context_extractors import extract_cli_context
    
    # Test examples from docs/dev/metrics_decorators.md
    @track_layout_operation(extract_context=extract_cli_context)
    def example_function(ctx, json_file, output_dir, profile=None):
        return "documented_example"
    
    # Verify example works
    result = example_function(None, "test.json", "/output", "test/profile")
    assert result == "documented_example"
```

## Enforcement

**These testing requirements are MANDATORY and NON-NEGOTIABLE:**

1. **NO CODE** can be merged without comprehensive tests
2. **NO REFACTORING** without maintaining test coverage
3. **ALL BUG FIXES** must include regression tests
4. **ALL NEW FEATURES** must have complete test suites
5. **COVERAGE CANNOT DECREASE** from current levels
6. **ALL DECORATORS** must have comprehensive test coverage including:
   - Basic functionality testing
   - Context extraction testing
   - Dependency injection testing
   - Error handling testing
   - Performance impact testing
7. **ALL METRICS FUNCTIONALITY** must be tested including:
   - Model validation and serialization
   - Service layer operations
   - Storage adapter functionality
   - Context manager behavior
   - CLI command integration
   - End-to-end integration workflows
8. **TEST ISOLATION** must be maintained:
   - No tests pollute the working directory
   - All configuration tests use isolation fixtures
   - Shared cache instances reset between tests
   - All tests clean up after themselves

### Metrics Testing Coverage Requirements

The metrics system has achieved **137 comprehensive tests** covering:

- **Decorator functionality**: Function wrapping, context extraction, dependency injection
- **Context extractors**: CLI, service, compilation, and flash context extraction
- **Model validation**: Pydantic model behavior, serialization, validation
- **Service operations**: CRUD operations, summary generation, filtering
- **Storage adapters**: Cache integration, persistence, retrieval
- **Integration workflows**: End-to-end metrics collection and reporting
- **CLI commands**: All metrics CLI functionality with output validation
- **Dependency injection**: Factory patterns, service composition, isolation
- **Performance testing**: Decorator overhead, large dataset handling

This comprehensive test suite serves as the **gold standard** for testing practices in the codebase.

### Testing Success Metrics

Current testing achievements:
- **137 tests** for metrics system alone
- **100% test pass rate** across all domains
- **Comprehensive decorator testing** with real-world CLI integration
- **Full dependency injection testing** with mocking and isolation
- **Performance validation** ensuring minimal overhead (<2ms per operation)
- **Documentation testing** ensuring code examples work correctly

Testing is not optional - it is a fundamental requirement for code quality, maintainability, and reliability of the Glovebox project. The metrics system implementation demonstrates the level of testing excellence expected for all code in this project.
