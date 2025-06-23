# File Operations Module

A high-performance, protocol-based file copy system with multithreading support and comprehensive benchmarking capabilities.

## Overview

This module provides optimized file copying strategies designed for heavy file operations during ZMK workspace compilation. It implements a protocol-based architecture with automatic strategy selection, multithreading support, and comprehensive performance benchmarking.

## Key Features

- 🚀 **Multithreaded Copy Operations**: Parallel file copying with configurable worker threads
- 📊 **Performance Benchmarking**: Compare rglob vs psutil directory traversal methods
- 🎯 **Automatic Strategy Selection**: Intelligent selection based on file size and system capabilities
- 🔧 **Pluggable Architecture**: Protocol-based design following CLAUDE.md conventions
- ⚡ **System Optimization**: Uses sendfile, buffered I/O, and parallel processing
- 🧪 **Comprehensive Testing**: Full test coverage with isolation fixtures

## Architecture

### Core Components

```
glovebox/core/file_operations/
├── __init__.py          # Module exports and factory functions
├── protocols.py         # CopyStrategyProtocol interface
├── models.py           # CopyResult and data models
├── strategies.py       # Copy strategy implementations
├── service.py          # FileCopyService main interface
├── benchmarks.py       # Performance benchmarking suite
└── README.md           # This file
```

### Copy Strategies

1. **Baseline Strategy**: Standard `shutil.copytree` for baseline performance
2. **Buffered Strategy**: Custom buffered I/O with configurable buffer sizes
3. **Sendfile Strategy**: Linux/Unix `sendfile()` system call optimization
4. **Parallel Strategy**: Multithreaded copying with ThreadPoolExecutor

### Strategy Selection Logic

The system automatically selects optimal strategies based on:
- Directory size and file count
- System capabilities (sendfile availability)
- User configuration preferences
- Performance heuristics

## Quick Start

### Basic Usage

```python
from glovebox.core.file_operations import create_copy_service

# Create copy service with default settings
copy_service = create_copy_service()

# Copy directory with auto strategy selection
result = copy_service.copy_directory(
    src=Path("/source/directory"),
    dst=Path("/destination/directory"),
    exclude_git=True
)

print(f"Copied {result.bytes_copied} bytes in {result.elapsed_time:.2f}s")
print(f"Strategy used: {result.strategy_used}")
print(f"Speed: {result.speed_mbps:.1f} MB/s")
```

### Force Specific Strategy

```python
# Use parallel strategy with 8 workers
copy_service = create_copy_service()

result = copy_service.copy_directory(
    src=Path("/source"),
    dst=Path("/destination"),
    strategy="parallel",  # Force parallel strategy
    exclude_git=True
)
```

### Configuration from User Config

```python
from glovebox.config import create_user_config
from glovebox.core.file_operations import create_copy_service

# Load user configuration
user_config = create_user_config()

# Create service with user preferences
copy_service = create_copy_service(user_config)
```

## Benchmarking

### Pipeline Copy Benchmark (Two-Phase Parallel)

This matches the user's `option2_pipeline_copy` pattern:

```python
from glovebox.core.file_operations import create_benchmark_runner

benchmark = create_benchmark_runner()

# Run pipeline copy benchmark
result = benchmark.pipeline_copy_benchmark(
    workspace_path=Path("/path/to/zmk/workspace"),
    cache_dir=Path("/cache/directory"),
    components=["zmk", "zephyr", "modules", ".west"]
)

print(f"Pipeline copy: {result.duration:.2f}s, {result.speed_summary}")
```

### Directory Traversal Comparison (rglob vs psutil)

```python
# Compare rglob vs os.walk performance
traversal_results = benchmark.benchmark_directory_traversal(
    Path("/large/directory"),
    iterations=3
)

for result in traversal_results:
    print(f"{result.method}: {result.duration:.3f}s, {result.file_count} files")
```

### Copy Strategy Comparison

```python
# Benchmark all available copy strategies
copy_results = benchmark.benchmark_copy_strategies(
    src_dir=Path("/source"),
    dst_base=Path("/tmp/benchmark"),
    strategies=["baseline", "buffered", "parallel", "sendfile"]
)

for result in copy_results:
    status = "SUCCESS" if not result.errors else "FAILED"
    print(f"{result.method}: {result.duration:.2f}s, {result.speed_summary}, {status}")
```

### Parallel Worker Scaling

```python
# Test different worker thread counts
worker_results = benchmark.benchmark_parallel_workers(
    src_dir=Path("/source"),
    dst_base=Path("/tmp/workers"),
    worker_counts=[1, 2, 4, 8, 16]
)

for result in worker_results:
    workers = result.method.split("_")[1]
    print(f"{workers} workers: {result.duration:.2f}s, {result.speed_summary}")
```

### Comprehensive Benchmark Suite

```python
# Run all benchmarks with detailed output
results = benchmark.run_comprehensive_benchmark(
    workspace_path=Path("/zmk/workspace"),
    output_dir=Path("/tmp/benchmark"),
    verbose=True  # Shows progress and formatted tables
)

# Results dictionary contains:
# - results["traversal"] - Directory traversal methods
# - results["copy_strategies"] - All copy strategies  
# - results["parallel_workers"] - Worker thread scaling
# - results["pipeline"] - Two-phase pipeline approach
```

## Configuration

The module respects user configuration settings:

```yaml
# In user config YAML
copy_strategy: "auto"          # auto, baseline, buffered, parallel, sendfile
copy_buffer_size_kb: 1024     # Buffer size for buffered/parallel strategies
copy_max_workers: 4           # Number of worker threads for parallel strategy
```

## Performance Characteristics

### Strategy Recommendations

- **Baseline**: Small directories (<10MB), simple operations
- **Buffered**: Medium directories (10-100MB), custom buffer optimization
- **Sendfile**: Large files (>100MB) on Linux/Unix systems
- **Parallel**: Large directories (>200MB) or many files (>20 files)

### Multithreading Benefits

The parallel strategy shows significant improvements for:
- Directories with many small files
- I/O bound operations
- Systems with multiple CPU cores
- Network storage or slow disks

### psutil vs rglob Performance

- **os.walk (psutil-style)**: Generally faster for large directories
- **rglob**: More Pythonic but can be slower on large directory trees
- **Automatic fallback**: Uses rglob if psutil is unavailable

## Integration Examples

### ZMK Workspace Caching

```python
from glovebox.core.file_operations import create_copy_service
from glovebox.config import create_user_config

def cache_zmk_workspace(workspace_path: Path, cache_path: Path):
    """Cache ZMK workspace with optimized copying."""
    user_config = create_user_config()
    copy_service = create_copy_service(user_config)
    
    result = copy_service.copy_directory(
        src=workspace_path,
        dst=cache_path,
        exclude_git=True,  # Skip .git directories
        strategy="auto"    # Auto-select optimal strategy
    )
    
    return result
```

### Build Pipeline Integration

```python
def copy_workspace_components(workspace_path: Path, cache_dir: Path):
    """Copy specific ZMK components with parallel optimization."""
    copy_service = create_copy_service()
    
    components = ["zmk", "zephyr", "modules", ".west"]
    results = []
    
    for component in components:
        src_path = workspace_path / component
        if src_path.exists():
            dst_path = cache_dir / component
            result = copy_service.copy_directory(
                src=src_path,
                dst=dst_path,
                strategy="parallel",  # Use parallel for component copying
                exclude_git=True
            )
            results.append(result)
    
    return results
```

## Testing

Run the demo script to see all features in action:

```bash
# Run comprehensive benchmark demo
python -m pytest tests/test_file_operations_demo.py::test_comprehensive_file_operations_benchmark -v -s

# Run just the pipeline copy example
python -m pytest tests/test_file_operations_demo.py::test_pipeline_copy_example -v -s

# Run demo directly
python tests/test_file_operations_demo.py
```

## Development Notes

### Following CLAUDE.md Conventions

- ✅ All code follows project linting and type checking requirements
- ✅ Factory functions used for service creation (no singletons)
- ✅ Protocol-based interfaces with runtime checking
- ✅ Comprehensive exception logging with debug-aware stack traces
- ✅ Maximum 500 lines per file enforced
- ✅ Full test coverage with isolation fixtures

### Error Handling

All strategies implement robust error handling:

```python
except Exception as e:
    exc_info = self.logger.isEnabledFor(logging.DEBUG)
    self.logger.error("Copy operation failed: %s", e, exc_info=exc_info)
    return CopyResult(
        success=False,
        error=str(e),
        elapsed_time=time.time() - start_time,
        strategy_used=self.name
    )
```

### Test Isolation

All tests use proper isolation to prevent filesystem pollution:

```python
def test_copy_operation(tmp_path):
    """All file operations use tmp_path for isolation."""
    copy_service = create_copy_service()
    result = copy_service.copy_directory(
        src=tmp_path / "source",
        dst=tmp_path / "destination"
    )
```

## Troubleshooting

### Common Issues

1. **Permission Errors**: Ensure read/write access to source and destination
2. **Sendfile Not Available**: Automatically falls back to buffered strategy
3. **Large Directory Performance**: Use parallel strategy for >200MB directories
4. **Memory Usage**: Adjust buffer size and worker count for large operations

### Debug Logging

Enable debug logging to see detailed strategy selection and performance metrics:

```python
import logging
logging.getLogger("glovebox.core.file_operations").setLevel(logging.DEBUG)
```

### Performance Monitoring

Use the benchmarking module to identify optimal settings for your use case:

```python
# Find optimal worker count for your system
benchmark = create_benchmark_runner()
results = benchmark.benchmark_parallel_workers(
    src_dir=your_typical_directory,
    dst_base=Path("/tmp/perf_test"),
    worker_counts=[1, 2, 4, 8, 12, 16]
)
```

## Future Enhancements

Potential improvements for future versions:
- Rsync-style incremental copying
- Progress callback support
- Compression during copy
- Network-aware optimizations
- GPU acceleration for very large operations

---

*This module is part of the Glovebox ZMK firmware management tool. For more information, see the main project documentation.*