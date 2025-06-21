# Testing Quick Reference Guide

## Metrics and Decorator Testing Patterns

### Basic Decorator Test Template

```python
class TestMyDecorator:
    """Test custom decorator functionality."""

    def test_basic_functionality(self):
        """Test basic decorator behavior."""
        mock_service = Mock(spec=MetricsServiceProtocol)

        @track_operation(OperationType.LAYOUT_COMPILATION, metrics_service=mock_service)
        def test_function(arg1: str) -> str:
            return f"result: {arg1}"

        result = test_function("test")
        assert result == "result: test"

    def test_with_context_extraction(self):
        """Test decorator with context extraction."""
        def custom_extractor(func, args, kwargs):
            return {"extracted": "context"}

        @track_operation(
            OperationType.LAYOUT_COMPILATION,
            extract_context=custom_extractor
        )
        def test_function():
            return "success"

        result = test_function()
        assert result == "success"

    def test_error_handling(self):
        """Test decorator behavior with exceptions."""
        @track_operation(OperationType.LAYOUT_COMPILATION)
        def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            failing_function()

    def test_dependency_injection(self):
        """Test decorator with injected dependencies."""
        mock_service = Mock(spec=MetricsServiceProtocol)

        tracker = create_operation_tracker(
            OperationType.LAYOUT_COMPILATION,
            metrics_service=mock_service
        )

        @tracker
        def test_function():
            return "injected"

        result = test_function()
        assert result == "injected"
```

### Context Extractor Test Template

```python
class TestContextExtractors:
    """Test context extraction functions."""

    def test_extract_basic_context(self):
        """Test basic context extraction."""
        def mock_function(arg1, arg2=None, **kwargs):
            pass

        args = ("value1",)
        kwargs = {"arg2": "value2", "extra": "context"}

        context = extract_service_context(mock_function, args, kwargs)

        # Verify expected context was extracted
        assert context["some_field"] == "expected_value"

    def test_extract_handles_exceptions(self):
        """Test that extractor handles invalid input gracefully."""
        def mock_function():
            pass

        context = extract_service_context(mock_function, (), {"invalid": object()})
        assert isinstance(context, dict)  # Should not crash
```

### Integration Test Template

```python
class TestMetricsIntegration:
    """Test metrics integration workflows."""

    def test_end_to_end_collection(self, isolated_config):
        """Test complete metrics collection workflow."""
        # Create isolated metrics service
        cache = create_default_cache(tag="test_metrics")
        storage = create_metrics_storage(cache=cache)
        service = create_metrics_service(storage=storage)

        # Perform operation with metrics
        with create_metrics_collector(
            OperationType.LAYOUT_COMPILATION, 
            metrics_service=service
        ) as metrics:
            metrics.set_context(profile_name="test/profile")
            metrics.record_timing("operation", 0.1)

        # Verify metrics were collected
        retrieved = service.get_operation_metrics(limit=1)
        assert len(retrieved) == 1
        assert retrieved[0].profile_name == "test/profile"
        assert retrieved[0].operation_time_seconds == 0.1
```

## Common Test Patterns

### CLI Command Testing with Decorators

```python
def test_cli_command_with_metrics(isolated_cli_environment, cli_runner):
    """Test CLI command that uses metrics decorator."""
    result = cli_runner.invoke(app, [
        "layout", "compile", 
        "test_layout.json", 
        "/tmp/output",
        "--profile", "glove80/v25.05"
    ])
    
    # Verify command executed
    assert result.exit_code == 0
    
    # Verify metrics were collected
    # (use metrics CLI to check)
```

### Service Method Testing with Decorators

```python
def test_service_method_with_metrics():
    """Test service method that uses metrics decorator."""
    mock_profile = Mock()
    mock_profile.keyboard_name = "test_keyboard"
    mock_profile.firmware_version = "v1.0"

    service = create_layout_service()
    
    # Method should work normally despite decorator
    result = service.some_decorated_method(
        profile=mock_profile,
        input_file=Path("/test/input.json")
    )
    
    assert result.success
```

### Performance Testing for Decorators

```python
def test_decorator_performance_overhead():
    """Test that decorators have minimal performance impact."""
    import time

    @track_operation(OperationType.LAYOUT_COMPILATION)
    def decorated_function():
        return "result"

    def undecorated_function():
        return "result"

    # Measure overhead
    iterations = 1000
    
    start = time.perf_counter()
    for _ in range(iterations):
        decorated_function()
    decorated_time = time.perf_counter() - start

    start = time.perf_counter()
    for _ in range(iterations):
        undecorated_function()
    undecorated_time = time.perf_counter() - start

    # Decorator should add < 2ms per call
    overhead = (decorated_time - undecorated_time) / iterations
    assert overhead < 0.002
```

## Test Isolation Fixtures

### Always Use These Fixtures

```python
def test_with_isolation(isolated_config):
    """Use isolated_config for configuration-related tests."""
    config = UserConfig(cli_config_path=isolated_config.config_file)
    # Safe to modify config - isolated to temp directory

def test_cli_with_isolation(isolated_cli_environment, cli_runner):
    """Use isolated_cli_environment for CLI tests."""
    result = cli_runner.invoke(app, ["config", "export"])
    # Safe - all file operations isolated

def test_with_temp_files(tmp_path):
    """Use tmp_path for file operations."""
    test_file = tmp_path / "test.json"
    test_file.write_text('{"test": "data"}')
    # Automatically cleaned up
```

### Shared Cache Reset

```python
@pytest.fixture(autouse=True)
def reset_shared_cache():
    """Reset shared cache instances between tests."""
    from glovebox.core.cache_v2 import reset_shared_cache_instances
    
    reset_shared_cache_instances()
    yield
    reset_shared_cache_instances()
```

## Essential Test Commands

```bash
# Run all metrics tests
pytest tests/test_metrics/ -v

# Run decorator tests only
pytest tests/test_metrics/test_decorators.py -v

# Run with coverage
pytest tests/test_metrics/ --cov=glovebox.metrics --cov-report=term-missing

# Run performance tests
pytest tests/test_metrics/ -k "performance" -v

# Check for test pollution
pytest tests/test_metrics/ --tb=short -x

# Type check tests
mypy tests/test_metrics/
```

## Key Testing Principles

1. **Test Isolation**: Every test should be independent
2. **Comprehensive Coverage**: Test success, failure, and edge cases
3. **Dependency Injection**: Use mocks and dependency injection for testing
4. **Performance Awareness**: Verify decorators don't impact performance
5. **Error Handling**: Test that errors are handled gracefully
6. **Documentation**: Test that examples in docs actually work

## Anti-Patterns to Avoid

❌ **Never do these in tests:**

```python
# Don't write to current directory
Path("test_file.json").write_text(data)

# Don't use real user config
config = UserConfig()  # Uses ~/.glovebox/

# Don't ignore isolation fixtures
def test_without_isolation(cli_runner):  # Missing isolated_cli_environment
    
# Don't test implementation details
assert len(mock_service.method_calls) == 3  # Too brittle

# Don't write tests over 500 lines
class HugeTestClass:  # Split into smaller classes
```

✅ **Always do these:**

```python
# Use isolation fixtures
def test_with_isolation(isolated_config, tmp_path):

# Test behavior, not implementation
assert result.success
assert result.message == "Expected output"

# Use dependency injection
@track_operation(OperationType.LAYOUT_COMPILATION, metrics_service=mock_service)

# Keep tests focused and small
class TestSpecificFeature:  # One feature per test class
```