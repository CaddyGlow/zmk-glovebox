# Glovebox Textual TUI

A modern Terminal User Interface (TUI) application built with [Textual](https://textual.textualize.io/) that demonstrates advanced TUI concepts including real-time updates, tabbed interfaces, and background services.

## Features

### 🚀 Core Functionality
- **Tabbed Interface**: Clean navigation between Logs, System, and Settings
- **Real-time Log Viewer**: Live log streaming with scrolling and auto-scroll
- **System Monitoring**: Live CPU, memory, and system metrics
- **Interactive Settings**: Configurable application settings with live updates
- **Keyboard Navigation**: Full keyboard control with vim-like bindings

### 🎨 Modern UI/UX
- **Responsive Layout**: Adapts to terminal size changes
- **Rich Text Support**: Colored, styled text throughout the interface
- **Progress Indicators**: Real-time progress bars for system metrics
- **Smooth Scrolling**: Efficient scrolling in log viewer
- **CSS Styling**: Customizable appearance with Textual CSS

### ⚡ Background Services
- **Log Service**: Generates realistic log messages for demonstration
- **System Service**: Monitors system resources with configurable intervals
- **Async Architecture**: Non-blocking background operations

## Quick Start

### Basic Usage
```bash
# Run the application
python -m glovebox_tui.main

# Or use the demo script
python demo_tui.py

# Test components
python test_tui.py
```

### Keyboard Controls

#### Global Navigation
- `q` - Quit application
- `1` - Switch to Logs tab
- `2` - Switch to System tab  
- `3` - Switch to Settings tab

#### Logs Tab
- `j` / `↓` - Scroll down
- `k` / `↑` - Scroll up
- `g` - Go to top
- `G` - Go to bottom
- `Space` - Page down
- `a` - Toggle auto-scroll

#### Settings Tab
- `a` - Toggle auto-scroll setting
- `l` - Cycle log level
- `r` - Adjust refresh rate

## Architecture

### Component Structure
```
glovebox_tui/
├── app.py              # Main Textual application
├── screens/
│   └── main_screen.py  # Primary application screen
├── widgets/
│   ├── log_viewer.py   # Real-time log display
│   ├── system_info.py  # System metrics panel
│   └── settings_panel.py # Interactive settings
├── services/
│   ├── log_service.py     # Background log generation
│   └── system_service.py  # System monitoring
└── styles/
    └── main.tcss       # Textual CSS styling
```

### Key Design Patterns

#### Reactive Programming
- Uses Textual's reactive attributes for real-time updates
- Automatic UI updates when data changes
- Clean separation between data and presentation

#### Event-Driven Architecture
- Proper message passing between components
- Keyboard events handled at appropriate widget levels
- Background services communicate via callbacks

#### Service Architecture
- Dedicated services for different concerns
- Async/await for non-blocking operations
- Clean shutdown and resource management

## Advanced Features

### Real-time Log Streaming
```python
# Service generates logs asynchronously
await log_service.start()

# Widget receives logs via callback
log_service.set_log_callback(log_viewer.add_log)
```

### System Monitoring
```python
# Background system metrics collection
metrics = await system_service.get_current_metrics()

# Reactive UI updates
system_widget.cpu_percent = metrics["cpu"]["percent"]
```

### Interactive Settings
```python
# Settings changes trigger immediate updates
def on_switch_changed(self, event):
    self.auto_scroll_enabled = event.value
    self.notify_setting_changed("auto_scroll", event.value)
```

## Customization

### CSS Styling
Edit `styles/main.tcss` to customize appearance:
```css
/* Custom color scheme */
ProgressBar {
    color: $success;
}

/* Layout adjustments */
#log-display {
    border: solid $primary;
    height: 1fr;
}
```

### Adding New Tabs
1. Create widget in `widgets/`
2. Add to `main_screen.py`
3. Update keyboard bindings in `app.py`

### Background Services
```python
class CustomService:
    async def start(self):
        # Your background logic here
        pass
```

## Comparison with Rich-based TUI

### Advantages over Rich Live
- **Better Event Handling**: Native keyboard/mouse event system
- **Widget Lifecycle**: Proper mounting/unmounting of components
- **Reactive Updates**: Automatic UI updates with reactive attributes
- **CSS Styling**: Cleaner styling with CSS-like syntax
- **Built-in Widgets**: Rich set of pre-built UI components
- **Better Performance**: Optimized rendering and update cycles

### Migration Benefits
- **Maintainable Code**: Clear widget boundaries and responsibilities
- **Extensible Architecture**: Easy to add new features and components
- **Better Testing**: Widget-based architecture is easier to test
- **Rich Ecosystem**: Access to Textual's growing widget library

## Requirements

- Python 3.11+
- Textual 3.5.0+
- psutil (for system monitoring)
- Rich (included with Textual)

## Development

### Testing
```bash
# Run component tests
python test_tui.py

# Check imports and basic functionality
python -c "from glovebox_tui.app import GloveboxTUIApp; print('OK')"
```

### Debugging
- Use Textual's built-in debugging features
- Log service can be used for debugging output
- CSS can be hot-reloaded during development

## Troubleshooting

### Common Issues
1. **Terminal Size Errors**: Ensure terminal is large enough (80x24 minimum)
2. **CSS Parsing Errors**: Check CSS syntax in `main.tcss`
3. **Import Errors**: Verify Textual is installed correctly

### Performance Tips
- Adjust system monitoring interval in settings
- Disable auto-scroll for better performance with many logs
- Use appropriate terminal size for optimal rendering

This TUI demonstrates modern terminal application development with Textual, showcasing real-time updates, interactive controls, and clean architecture patterns.