# Service Layer Improvements

This document outlines improvements to strengthen the service layer architecture and enforce cleaner separation of concerns.

## Moving Logic from CLI Commands to Services

### Current Issues

1. **Input Validation in CLI**: Currently, CLI commands perform validation that should be in the service layer:
   - File existence checks (`json_file_path.exists()`)
   - Keymap data validation (`KeymapData.model_validate()`)
   - Path validation before service calls

2. **Data Conversion in CLI**: CLI commands perform data conversion before passing to services:
   - JSON parsing (`json.loads(json_file_path.read_text())`)
   - Model conversion (`KeymapData.model_validate(json_data)`)

3. **Complex Conditional Logic**: CLI commands contain conditional logic that belongs in services:
   - Profile handling with fallbacks
   - Error handling with different response codes

### Recommended Changes

#### 1. Create Service Methods for CLI-Specific Operations

```python
# KeymapService should have these methods:
def compile_from_file(self, profile: KeyboardProfile, json_file_path: Path, target_prefix: str) -> KeymapResult:
    """Compile keymap from a JSON file path rather than pre-parsed data."""
    # Handle file existence check
    # Handle JSON parsing
    # Handle model validation
    # Call self.compile() with parsed data
    
def validate_file(self, profile: KeyboardProfile, json_file_path: Path) -> ValidationResult:
    """Validate a keymap file including file existence and JSON parsing."""
    # Handle file existence check
    # Handle JSON parsing
    # Handle model validation
    # Return detailed validation result
```

#### 2. Simplify CLI Command Implementation

```python
@keymap_app.command(name="compile")
@handle_errors
def keymap_compile(
    target_prefix: Annotated[str, typer.Argument(help="Target directory and base filename")],
    json_file: Annotated[str, typer.Argument(help="Path to keymap JSON file")],
    profile: Annotated[str, typer.Option(help="Profile to use")] = "glove80/default",
    force: Annotated[bool, typer.Option("--force", help="Overwrite existing files")] = False,
) -> None:
    """Compile a keymap JSON file into ZMK keymap and config files."""
    # Create profile from profile option
    keyboard_profile = create_profile_from_option(profile)
    
    # Compile keymap using the file-based service method
    keymap_service = create_keymap_service()
    result = keymap_service.compile_from_file(keyboard_profile, Path(json_file), target_prefix)
    
    # Handle result display
    if result.success:
        print_success_message("Keymap compiled successfully")
        output_files = result.get_output_files()
        for file_type, file_path in output_files.items():
            print_list_item(f"{file_type}: {file_path}")
    else:
        print_error_message("Keymap compilation failed")
        for error in result.errors:
            print_list_item(error)
        raise typer.Exit(1)
```

## Enforcing Strict Dependency Injection

### Current Issues

1. **Inconsistent Patterns**: Some services create their dependencies internally, others accept them via constructor.

2. **Hidden Dependencies**: Some dependencies are created through factory functions inside methods.

3. **Type Casting**: Explicit type casting is used to adapt protocols, indicating potential design issues.

### Recommended Changes

#### 1. Make All Dependencies Explicit in Constructor

```python
class KeymapService(BaseServiceImpl):
    """Service for all keymap operations."""

    def __init__(
        self,
        file_adapter: FileAdapter,
        template_adapter: TemplateAdapter,
        behavior_registry: BehaviorRegistry,
        behavior_formatter: BehaviorFormatter,
        dtsi_generator: DTSIGenerator,
        component_service: KeymapComponentService,
        layout_service: LayoutDisplayService,
        context_builder: TemplateContextBuilder,
    ):
        """Initialize with all dependencies explicitly provided."""
        super().__init__(service_name="KeymapService", service_version="1.0.0")
        self._file_adapter = file_adapter
        self._template_adapter = template_adapter
        self._behavior_registry = behavior_registry
        self._behavior_formatter = behavior_formatter
        self._dtsi_generator = dtsi_generator
        self._component_service = component_service
        self._layout_service = layout_service
        self._context_builder = context_builder
```

#### 2. Enhance Factory Functions to Handle All Dependencies

```python
def create_keymap_service(
    file_adapter: FileAdapter | None = None,
    template_adapter: TemplateAdapter | None = None,
    behavior_registry: BehaviorRegistry | None = None,
    # ... other dependencies
) -> KeymapService:
    """Create KeymapService with all dependencies properly wired up."""
    # Create default dependencies if not provided
    if file_adapter is None:
        file_adapter = create_file_adapter()
    if template_adapter is None:
        template_adapter = create_template_adapter()
    if behavior_registry is None:
        behavior_registry = create_behavior_registry()
        
    # Create dependent services
    behavior_formatter = BehaviorFormatterImpl(behavior_registry)
    dtsi_generator = DTSIGenerator(behavior_formatter)
    component_service = create_keymap_component_service(file_adapter)
    layout_service = create_layout_display_service()
    context_builder = create_template_context_builder(dtsi_generator)
    
    # Create and return the service with all dependencies
    return KeymapService(
        file_adapter,
        template_adapter,
        behavior_registry,
        behavior_formatter,
        dtsi_generator,
        component_service,
        layout_service,
        context_builder,
    )
```

#### 3. Remove Type Casting by Proper Interface Design

Replace:
```python
self._behavior_formatter = BehaviorFormatterImpl(
    cast(FormatterBehaviorRegistry, self._behavior_registry)
)
```

With proper interface design:
```python
# Ensure BehaviorRegistry implements FormatterBehaviorRegistry
class BehaviorRegistry(FormatterBehaviorRegistry, Protocol):
    """Protocol defining the behavior registry interface."""
    # ...
```

## Making Behavior Registration Explicit

### Current Issues

1. **Implicit Registration**: Behaviors are registered implicitly through `profile.register_behaviors(registry)`.

2. **Side-Effects**: Services have side-effects when modifying a shared behavior registry.

3. **Unclear Responsibility**: It's not clear who is responsible for behavior registration.

### Recommended Changes

#### 1. Make Behavior Registration a Dedicated Service

```python
class BehaviorRegistrationService:
    """Service responsible for registering behaviors from various sources."""
    
    def __init__(self, behavior_registry: BehaviorRegistry):
        self._registry = behavior_registry
        
    def register_system_behaviors(self, profile: KeyboardProfile) -> None:
        """Register system behaviors from a keyboard profile."""
        for behavior in profile.system_behaviors:
            self._registry.register_behavior(behavior)
            
    def register_custom_behaviors(self, keymap_data: KeymapData) -> None:
        """Register custom behaviors defined in a keymap."""
        for behavior in keymap_data.get_custom_behaviors():
            self._registry.register_behavior(behavior)
```

#### 2. Make Behavior Registry Immutable After Setup

```python
class KeymapService(BaseServiceImpl):
    def compile(self, profile: KeyboardProfile, keymap_data: KeymapData, target_prefix: str) -> KeymapResult:
        """Compile ZMK keymap files from keymap data."""
        # Create a fresh registry for this compilation
        behavior_registry = create_behavior_registry()
        
        # Use the registration service to set up the registry
        registration_service = BehaviorRegistrationService(behavior_registry)
        registration_service.register_system_behaviors(profile)
        registration_service.register_custom_behaviors(keymap_data)
        
        # Use the prepared registry for formatting
        behavior_formatter = BehaviorFormatterImpl(behavior_registry)
        # ...
```

These changes will significantly improve the service layer design, making it more maintainable, testable, and easier to understand for new developers.

## Implementation Progress

### 1. File-Based Service Methods Implementation

The first phase of service layer improvements has been implemented for the `KeymapService`:

1. **New File-Based Methods Added**:
   - `compile_from_file()`: Compiles keymap from a JSON file path
   - `validate_file()`: Validates a keymap file
   - `show_from_file()`: Displays a keymap from a file
   - `split_keymap_from_file()`: Splits a keymap file into individual layers
   - `merge_layers_from_files()`: Merges layer files into a single keymap

2. **Helper Methods Added**:
   - `_load_json_file()`: Handles file loading and JSON parsing
   - `_validate_keymap_data()`: Validates JSON data as KeymapData

3. **CLI Command Updates**:
   - All CLI commands have been updated to use the file-based methods
   - Validation logic has been moved from CLI to service layer
   - Error handling is more consistent

4. **Factory Function Enhancement**:
   - Enhanced factory function signature to include all dependencies
   - Documented all dependencies with clear parameter descriptions

### 2. Strict Dependency Injection Implementation

The second phase of service layer improvements has been implemented for the `KeymapService`:

1. **Updated Constructor**:
   - Constructor now accepts all dependencies explicitly:
     ```python
     def __init__(
         self,
         file_adapter: FileAdapter,
         template_adapter: TemplateAdapter,
         behavior_registry: FormatterBehaviorRegistry,
         behavior_formatter: BehaviorFormatterImpl,
         dtsi_generator: DTSIGeneratorAdapter,
         component_service: KeymapComponentService,
         layout_service: LayoutDisplayService,
         context_builder: Any,
     ):
     ```
   - Added detailed documentation for all parameters
   - Removed internal dependency creation

2. **Enhanced Factory Function**:
   - Factory function now creates all required dependencies if not provided
   - All dependencies are properly typed
   - Dependencies are created in the correct order to handle dependencies between them
   - Named parameters are used for constructor call for clarity

### Next Steps

1. **Implement Behavior Registration Service**:
   - Create a dedicated service for behavior registration
   - Make behavior registry immutable after initial setup

2. **Extend to Other Services**:
   - Apply the same pattern to other services (BuildService, FlashService)
   - Ensure consistent patterns across all services

## Conclusion

The service layer improvements implemented so far have significantly enhanced the codebase:

1. **Cleaner Separation of Concerns**:
   - CLI layer is now focused on user interaction, parameter handling, and output formatting
   - Service layer handles all business logic, validation, and data processing
   - File operations are consistently managed in the service layer

2. **Improved Testability**:
   - Services can be tested with mock dependencies
   - CLI commands are simpler and easier to test
   - File operations can be mocked more effectively

3. **Better Maintainability**:
   - Dependencies are explicitly defined and documented
   - Consistent patterns make the code easier to understand
   - Factory functions provide a clean way to create properly configured services

4. **More Robust Error Handling**:
   - Validation happens at the appropriate layer
   - Error messages are more specific and helpful
   - Consistent error handling pattern across operations

These improvements align with the project's goals of maintaining a clean, understandable codebase that's easy for new developers to work with. The next steps will further enhance these benefits by addressing behavior registration and extending the patterns to other services.