# SessionMetrics - Prometheus-Compatible Local Metrics

A lightweight, prometheus_client-compatible metrics system for CLI applications that stores metrics locally in JSON format during CLI sessions.

## Overview

SessionMetrics provides the exact same API as prometheus_client but stores metrics locally in JSON files instead of exposing them via HTTP. This makes it perfect for CLI tools where you want prometheus-style instrumentation without running a metrics server.

## Key Features

- **🔄 Prometheus Compatible**: Identical API to prometheus_client - drop-in replacement
- **📁 Local Storage**: Metrics stored in human-readable JSON files
- **🎯 Session-Based**: Each CLI execution gets its own metrics file
- **⚡ Zero Dependencies**: No external metrics server required
- **🔀 Easy Migration**: Switch to real prometheus_client with zero code changes
- **📊 Complete Metrics**: Counter, Gauge, Histogram, Summary support
- **🏷️ Full Labels**: Complete label support with validation
- **⏱️ Context Managers**: Timing decorators and context managers

## Quick Start

### Basic Usage

```python
from glovebox.metrics import create_session_metrics

# Create metrics registry
metrics = create_session_metrics("my_session_metrics.json")

# Create metrics - exactly like prometheus_client
counter = metrics.Counter('operations_total', 'Total operations', ['type', 'status'])
histogram = metrics.Histogram('request_duration_seconds', 'Request duration')
gauge = metrics.Gauge('active_connections', 'Active connections')

# Use metrics - identical to prometheus_client
counter.labels('layout', 'success').inc()
counter.labels('firmware', 'error').inc(3)

with histogram.time():
    # Your code here
    do_some_work()

gauge.set(42)
gauge.inc(5)

# Save metrics to file
metrics.save()
```

### CLI Integration

SessionMetrics is automatically available in all CLI commands via the context:

```python
import typer
from typing import Annotated

@typer.command()
def my_command(
    ctx: typer.Context,
    layout_file: Annotated[str, typer.Argument()],
):
    """Example CLI command with metrics."""
    # Get metrics from CLI context
    metrics = ctx.obj.session_metrics
    
    # Create and use metrics
    operations = metrics.Counter('command_operations_total', 'Command operations', ['command'])
    duration = metrics.Histogram('command_duration_seconds', 'Command duration')
    
    operations.labels('my_command').inc()
    with duration.time():
        # Your command logic
        process_layout_file(layout_file)
    
    # Metrics are automatically saved when CLI exits
```

## Metric Types

### Counter

Counters go up and reset when the process restarts.

```python
# Create counter
requests_total = metrics.Counter('requests_total', 'Total requests', ['method', 'endpoint'])

# Increment
requests_total.labels('GET', '/api/users').inc()
requests_total.labels('POST', '/api/login').inc(5)

# Without labels
simple_counter = metrics.Counter('simple_counter', 'Simple counter')
simple_counter.inc()
```

### Gauge

Gauges can go up and down.

```python
# Create gauge
temperature = metrics.Gauge('temperature_celsius', 'Temperature', ['location'])

# Set value
temperature.labels('server_room').set(23.5)

# Increment/decrement
temperature.labels('server_room').inc(1.2)
temperature.labels('server_room').dec(0.5)

# Set to current timestamp
temperature.labels('server_room').set_to_current_time()
```

### Histogram

Histograms track the size and number of events in buckets.

```python
# Create histogram with default buckets
request_duration = metrics.Histogram('request_duration_seconds', 'Request duration')

# Create with custom buckets
response_size = metrics.Histogram(
    'response_size_bytes', 
    'Response size',
    buckets=[100, 1000, 10000, 100000, 1000000]
)

# Observe values
request_duration.observe(0.5)
request_duration.observe(1.2)

# Time code execution
with request_duration.time():
    # Your code here
    make_api_request()

# As decorator (when used with decorators module)
@request_duration.time()
def my_function():
    # Your code here
    pass
```

### Summary

Summaries track the size and number of events.

```python
# Create summary
response_size = metrics.Summary('response_size_bytes', 'Response size')

# Observe values
response_size.observe(1024)
response_size.observe(2048)

# Time code execution
with response_size.time():
    # Your code here
    process_response()
```

## Label Best Practices

### Label Naming
- Use snake_case: `http_method`, `error_type`
- Keep labels short but descriptive
- Avoid high-cardinality labels (e.g., user IDs, timestamps)

### Label Usage
```python
# Good: Low cardinality labels
requests = metrics.Counter('requests_total', 'Requests', ['method', 'status'])
requests.labels('GET', '200').inc()
requests.labels('POST', '404').inc()

# Bad: High cardinality labels
requests = metrics.Counter('bad_requests_total', 'Requests', ['user_id', 'timestamp'])
requests.labels('user_12345', '2023-12-01T10:30:00').inc()  # DON'T DO THIS
```

## JSON Output Format

SessionMetrics produces structured JSON output:

```json
{
  "session_info": {
    "session_id": "session_1703123456",
    "start_time": "2023-12-01T10:30:00.123456",
    "end_time": "2023-12-01T10:31:15.654321", 
    "duration_seconds": 75.53
  },
  "counters": {
    "operations_total": {
      "description": "Total operations",
      "labelnames": ["type", "status"],
      "values": {
        "('layout', 'success')": 5,
        "('firmware', 'error')": 2
      }
    }
  },
  "histograms": {
    "request_duration_seconds": {
      "description": "Request duration",
      "buckets": [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
      "bucket_counts": {
        "0.1": 3,
        "0.5": 7,
        "1.0": 10
      },
      "total_count": 10,
      "total_sum": 4.2
    }
  }
}
```

## Migration to Prometheus

When you're ready to migrate to real prometheus_client, the changes are minimal:

### Before (SessionMetrics)
```python
from glovebox.metrics import create_session_metrics

metrics = create_session_metrics("metrics.json")
counter = metrics.Counter('ops_total', 'Operations')
counter.inc()
metrics.save()
```

### After (prometheus_client)
```python
from prometheus_client import Counter, start_http_server

# Remove session metrics creation
counter = Counter('ops_total', 'Operations')
counter.inc()

# Start HTTP server for Prometheus scraping
start_http_server(8000)
```

All your `.inc()`, `.observe()`, `.time()`, `.labels()` code stays exactly the same!

## CLI Context Integration

### Automatic Setup

SessionMetrics is automatically initialized in the CLI context:

```python
class AppContext:
    def __init__(self, ...):
        # SessionMetrics automatically created
        self.session_metrics = create_session_metrics(f"session_{self.session_id}_metrics.json")
```

### Auto-Save

Metrics are automatically saved when the CLI exits:

```python
# Metrics automatically saved via atexit handler
# No manual save() call needed in CLI commands
```

### Session Isolation

Each CLI execution gets its own metrics file:
- `session_1703123456_metrics.json`
- `session_1703123789_metrics.json`
- etc.

## Advanced Usage

### Custom Buckets

```python
# Create histogram with custom buckets for your use case
file_size_histogram = metrics.Histogram(
    'file_size_bytes',
    'File sizes',
    buckets=[1024, 10240, 102400, 1048576, 10485760]  # 1KB, 10KB, 100KB, 1MB, 10MB
)
```

### Multiple Metrics Files

```python
# Create separate metrics for different components
layout_metrics = create_session_metrics("layout_metrics.json")
firmware_metrics = create_session_metrics("firmware_metrics.json")

layout_counter = layout_metrics.Counter('layout_ops', 'Layout operations')
firmware_counter = firmware_metrics.Counter('firmware_ops', 'Firmware operations')
```

### Activity Logging

SessionMetrics includes activity logging for debugging:

```json
{
  "activity_log": [
    {
      "timestamp": 1703123456.789,
      "metric_name": "operations_total",
      "metric_type": "counter",
      "label_values": ["layout", "success"],
      "value": 1,
      "operation": "update"
    }
  ]
}
```

## Error Handling

SessionMetrics includes comprehensive error handling:

```python
# Label validation
counter = metrics.Counter('test', 'Test', ['method'])
counter.labels('GET', 'extra').inc()  # Raises ValueError

# Missing labels
counter.labels().inc()  # Raises ValueError  

# Mixed positional/keyword arguments
counter.labels('GET', endpoint='/api').inc()  # Raises ValueError
```

## Performance Considerations

### Memory Usage
- Observations are stored in memory during the session
- Histogram/Summary observations are truncated to last 50 entries
- Activity log is truncated to last 100 entries

### File I/O
- Metrics are only written to disk when `.save()` is called
- Auto-save occurs once at CLI exit
- JSON serialization is efficient for typical CLI session sizes

### Overhead
- Minimal overhead compared to prometheus_client
- No HTTP server or network calls
- Simple in-memory data structures

## Testing

SessionMetrics includes comprehensive test coverage:

```python
import pytest
from glovebox.metrics import create_session_metrics

def test_counter_basic():
    metrics = create_session_metrics()
    counter = metrics.Counter('test_counter', 'Test')
    counter.inc()
    assert counter._values[()] == 1

def test_histogram_timing():
    metrics = create_session_metrics()
    histogram = metrics.Histogram('test_duration', 'Test duration')
    
    with histogram.time():
        time.sleep(0.1)
    
    assert len(histogram._observations) == 1
    assert histogram._observations[0]['value'] >= 0.1
```

## Troubleshooting

### Common Issues

#### Metrics Not Saved
```python
# Make sure to call save() if not using CLI context
metrics = create_session_metrics("metrics.json")
# ... use metrics ...
metrics.save()  # Required for manual usage
```

#### Label Errors
```python
# Ensure all labels are provided
counter = metrics.Counter('test', 'Test', ['method', 'status'])
counter.labels('GET').inc()  # ERROR: Missing 'status' label
counter.labels('GET', '200').inc()  # OK
```

#### File Permissions
```python
# Ensure write permissions to output directory
metrics = create_session_metrics("/tmp/metrics.json")  # Use writable directory
```

### Debugging

Enable debug logging to see metrics operations:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# SessionMetrics will log metric creation and updates
metrics = create_session_metrics("debug_metrics.json")
```

## Contributing

When contributing to SessionMetrics:

1. **Follow prometheus_client API exactly** - any deviation breaks compatibility
2. **Add comprehensive tests** - all new functionality must be tested
3. **Update this README** - document new features and changes
4. **Run linting**: `ruff check . --fix && ruff format .`
5. **Verify compatibility**: Ensure prometheus_client migration still works

## Examples

See the test files for comprehensive usage examples:
- `tests/metrics/test_session_metrics.py` - Complete test suite
- Look for `TestPrometheusClientCompatibility` class for migration examples

## Related Documentation

- [Prometheus Client Python](https://prometheus.github.io/client_python/) - Original API reference
- [Prometheus Metric Types](https://prometheus.io/docs/concepts/metric_types/) - Metric type concepts
- [Glovebox Metrics System](../README.md) - Overall metrics architecture