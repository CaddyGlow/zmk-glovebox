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
├── conftest.py                 # Shared fixtures
├── test_unit/                  # Unit tests
│   ├── test_layout/
│   │   ├── test_services.py
│   │   ├── test_models.py
│   │   └── test_version_manager.py
│   ├── test_firmware/
│   ├── test_compilation/
│   └── test_config/
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

### 12. Performance Testing

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
```

### 13. Documentation Testing

Test code examples in documentation:

```python
def test_readme_examples():
    """Ensure README examples work correctly"""
    # Test actual code from README
    pass
```

## Enforcement

**These testing requirements are MANDATORY and NON-NEGOTIABLE:**

1. **NO CODE** can be merged without comprehensive tests
2. **NO REFACTORING** without maintaining test coverage
3. **ALL BUG FIXES** must include regression tests
4. **ALL NEW FEATURES** must have complete test suites
5. **COVERAGE CANNOT DECREASE** from current levels

Testing is not optional - it is a fundamental requirement for code quality, maintainability, and reliability of the Glovebox project.
