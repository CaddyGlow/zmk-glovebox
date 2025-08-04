# CLI Core Infrastructure

This module provides base classes for implementing Glovebox CLI commands with consistent patterns for error handling, I/O operations, and service management.

## Base Classes

### BaseCommand

Abstract base class for all CLI commands. Provides:
- Consistent logging setup
- Error handling patterns
- Themed console output
- Success/failure reporting

```python
from glovebox.cli.core import BaseCommand

class MyCommand(BaseCommand):
    def execute(self, name: str) -> None:
        self.print_operation_info(f"Processing {name}...")
        try:
            # Do work
            result = process_something(name)
            self.print_operation_success("Completed successfully", {"result": result})
        except Exception as e:
            self.handle_service_error(e, "process item")
```

### IOCommand

Base class for commands with input/output operations. Provides:
- Simplified parameter handling for files and stdin/stdout
- Automatic input resolution
- Output formatting (JSON, YAML, table, text)

```python
from glovebox.cli.core import IOCommand

class ConvertCommand(IOCommand):
    def execute(self, input_file: str, output_file: str) -> None:
        # Load JSON input
        data = self.load_json_input(input_file)
        
        # Process data
        processed = transform_data(data)
        
        # Write output in requested format
        self.write_output(processed, output_file, format="yaml")
```

### ServiceCommand

Base class for commands using domain services. Provides:
- Service initialization with factory pattern
- Caching of service instances
- Progress tracking helpers

```python
from glovebox.cli.core import ServiceCommand
from glovebox.layout import create_layout_service

class CompileCommand(ServiceCommand):
    def execute(self, input_file: str) -> None:
        # Get or create service instance
        layout_service = self.get_service(
            "layout", 
            create_layout_service,
            keyboard_profile=profile
        )
        
        # Use progress tracking
        with self.with_progress("Compiling layout") as progress:
            result = layout_service.compile(input_file)
            progress.update("Compilation complete")
```

## Usage in Typer Commands

These base classes work seamlessly with Typer:

```python
import typer
from glovebox.cli.core import IOCommand

app = typer.Typer()

class ShowCommand(IOCommand):
    def execute(self, file: Path, format: str = "json") -> None:
        data = self.load_json_input(file)
        self.format_and_print(data, format)

# Create command instance
show_cmd = ShowCommand()

@app.command()
def show(
    file: Path = typer.Argument(..., help="Layout file to display"),
    format: str = typer.Option("json", help="Output format"),
) -> None:
    """Display layout file contents."""
    show_cmd(file, format)  # Uses __call__ with error handling
```