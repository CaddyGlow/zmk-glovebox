# Reusable Progress Display Component

The `ProgressDisplayManager` is a reusable TUI component that provides Rich-based terminal interfaces with full terminal size support and automatic resizing. This component was extracted from the firmware compilation progress display to enable reuse across different modules.

## Features

- **Full terminal utilization**: Automatically uses available terminal width and height
- **Terminal resize support**: Detects and adapts to terminal size changes in real-time
- **Log streaming**: Optional live log display with intelligent text wrapping
- **Type-safe**: Generic implementation with proper typing support
- **Thread-safe**: Async progress updates via queue system
- **Clean lifecycle**: Proper resource management with cleanup functions

## Basic Usage

### Simple Progress Display

```python
from glovebox.cli.components import ProgressDisplayManager

# Create manager for simple string progress
manager = ProgressDisplayManager[str](show_logs=False)

# Start the display
progress_callback = manager.start()

try:
    # Send progress updates
    progress_callback("Processing files...")
    progress_callback("Almost done...")
    progress_callback("Complete!")
finally:
    # Always clean up
    progress_callback.cleanup()
```

### Custom Progress Data

```python
from dataclasses import dataclass
from glovebox.cli.components import ProgressDisplayManager

@dataclass
class MyProgress:
    current: int
    total: int
    operation: str
    
    def get_status_text(self) -> str:
        return f"🔄 {self.operation} ({self.current}/{self.total})"
    
    def get_progress_info(self) -> tuple[int, int, str]:
        return (self.current, self.total, f"Step {self.current}")

# Create manager with custom type
manager = ProgressDisplayManager[MyProgress](show_logs=True)
progress_callback = manager.start()

# Send typed progress updates
progress_data = MyProgress(5, 10, "Processing")
progress_callback(progress_data)
```

### With Log Streaming

```python
class MyLogProvider:
    def __init__(self):
        self.captured_logs: list[tuple[str, str]] = []
    
    def add_log(self, level: str, message: str):
        self.captured_logs.append((level, message))

# Set up log provider
log_provider = MyLogProvider()
manager.set_log_provider(log_provider)

# Add logs during processing
log_provider.add_log("info", "Starting operation")
log_provider.add_log("warning", "Minor issue detected")
log_provider.add_log("error", "Operation failed")
```

## Specialized Components

### CompilationProgressDisplayManager

For compilation-specific progress, use the specialized manager:

```python
from glovebox.cli.components.progress_display import CompilationProgressDisplayManager
from glovebox.core.file_operations import CompilationProgress

manager = CompilationProgressDisplayManager(show_logs=True)
progress_callback = manager.start()

# Works with CompilationProgress objects
progress = CompilationProgress(
    repositories_downloaded=15,
    total_repositories=39,
    current_repository="zmkfirmware/zephyr",
    compilation_phase="west_update"
)
progress_callback(progress)
```

## Configuration Options

### Constructor Parameters

- `show_logs: bool = True` - Whether to display log panel alongside progress
- `refresh_rate: int = 8` - Screen refresh rate in FPS for smooth resizing
- `max_log_lines: int = 100` - Maximum log lines to keep in memory
- `console: Console | None = None` - Optional Rich console instance

### Methods

- `start() -> ProgressCallback[T]` - Start display and return callback function
- `stop() -> None` - Stop display and clean up resources
- `set_log_provider(provider: LogProviderProtocol) -> None` - Set log source

## Protocols

### ProgressDataProtocol

For custom progress data types, implement these methods:

```python
class MyProgressData:
    def get_status_text(self) -> str:
        """Return current status text for display."""
        pass
    
    def get_progress_info(self) -> tuple[int, int, str]:
        """Return (current, total, description) for progress bar."""
        pass
```

### LogProviderProtocol

For log streaming, implement:

```python
class MyLogProvider:
    captured_logs: list[tuple[str, str]]  # (level, message) pairs
```

## Terminal Resize Behavior

The component automatically handles terminal resizing:

- **Width changes**: Progress bars expand/contract, log text rewraps
- **Height changes**: Log panel adjusts to show more/fewer lines
- **Real-time adaptation**: Updates every 100ms or when progress changes
- **Minimum constraints**: Ensures readable display even in small terminals

## Thread Safety

- Progress updates are queued and processed asynchronously
- Multiple threads can safely call the progress callback
- Log provider access is thread-safe
- Clean shutdown with timeout prevents hanging

## Performance Considerations

- Higher refresh rates (8+ FPS) provide smoother resizing but use more CPU
- Log history is limited by `max_log_lines` to prevent memory growth
- Layout recreation only occurs when terminal size actually changes
- Efficient text wrapping with word boundary detection

## Error Handling

- Component gracefully handles terminal resize errors
- Progress display errors are caught and displayed to user
- Cleanup always executes even if errors occur during operation
- Timeout prevents hanging during shutdown

## Migration from Inline Implementation

If you have existing progress display code, migration is straightforward:

```python
# Before: Inline implementation
def my_old_progress_display():
    # 300+ lines of Rich display code
    pass

# After: Reusable component
manager = ProgressDisplayManager[MyDataType](show_logs=True)
progress_callback = manager.start()
# Use progress_callback instead of inline code
```

## Examples

See `examples/progress_display_usage.py` for complete working examples of:
- Custom progress data types
- Log provider integration
- Different configuration options
- Error handling patterns

## Integration with Existing Code

The component is designed to be backward compatible with existing firmware compilation code while enabling new use cases across the codebase.