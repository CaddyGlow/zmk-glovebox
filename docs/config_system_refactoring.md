# Keyboard Configuration System Refactoring

## Overview

This document outlines a plan to refactor the keyboard configuration system in Glovebox to:
1. Improve type safety using dataclasses
2. Encapsulate configuration logic in a dedicated KeyboardProfile class
3. Reduce complexity in KeymapService
4. Better align with design principles outlined in CLAUDE.md

## Current Issues

1. `KeymapService` exceeds 500 lines limit
2. Configuration logic is scattered and relies on raw dictionaries
3. Type safety is limited, reducing IDE completion capabilities
4. Testing is more complex due to untyped configuration data

## Solution

### 1. Create Typed Configuration Classes

Use Python's dataclasses to create strongly-typed representations of configuration data:

```python
@dataclass
class SystemBehavior:
    code: str
    name: str
    description: str
    expected_params: int
    origin: str
    params: List[Any]  # This could be further refined
    url: Optional[str] = None
    isMacroControlBehavior: bool = False
    includes: Optional[List[str]] = None
    commands: Optional[List[Dict[str, Any]]] = None

@dataclass
class Template:
    name: str
    content: str

@dataclass
class KConfigOption:
    kconfig_name: str
    type: str
    default: Any
    description: str

@dataclass
class KeymapSection:
    includes: List[str]
    system_behaviors: List[SystemBehavior]
    kconfig_options: Dict[str, KConfigOption]

@dataclass
class FlashConfig:
    method: str
    query: str
    usb_vid: str
    usb_pid: str

@dataclass
class BuildConfig:
    method: str
    docker_image: str
    repository: str
    branch: str

@dataclass
class FirmwareConfig:
    version: str
    description: str
    build_options: Dict[str, Any]
    kconfig: Optional[Dict[str, KConfigOption]] = None

@dataclass
class KeyboardConfig:
    keyboard: str
    description: str
    vendor: str
    key_count: int
    flash: FlashConfig
    build: BuildConfig
    visual_layout: Dict[str, Any]  # Could be further typed
    formatting: Dict[str, Any]
    firmwares: Dict[str, FirmwareConfig]
    keymap: KeymapSection
    templates: Dict[str, str]
```

### 2. Create KeyboardProfile Class

Create a class that merges and provides access to configuration data, following dependency injection principles:

```python
class KeyboardProfile:
    """Encapsulates all configuration for a keyboard with specific firmware."""

    def __init__(self, keyboard_config: KeyboardConfig, firmware_version: str):
        """Initialize with explicit configuration dependencies.

        Args:
            keyboard_config: Fully loaded keyboard configuration
            firmware_version: Version of firmware to use

        Raises:
            ConfigError: If the specified firmware version is not found
        """
        self.keyboard_config = keyboard_config
        self.keyboard_name = keyboard_config.keyboard
        self.firmware_version = firmware_version

        # Validate firmware version exists
        if firmware_version not in keyboard_config.firmwares:
            raise ConfigError(f"Firmware '{firmware_version}' not found in keyboard configuration")

        self.firmware_config = keyboard_config.firmwares[firmware_version]
```

### 3. Implement Core Profile Methods

Add methods to handle common configuration operations:

```python
class KeyboardProfile:
    # ... continued from above

    @property
    def system_behaviors(self) -> List[SystemBehavior]:
        """Get system behaviors for this profile."""
        return self.keyboard_config.keymap.system_behaviors

    @property
    def templates(self) -> Dict[str, str]:
        """Get templates for this profile."""
        return self.keyboard_config.templates

    @property
    def kconfig_options(self) -> Dict[str, KConfigOption]:
        """Get combined kconfig options from keyboard and firmware."""
        # Start with keyboard kconfig options
        combined = dict(self.keyboard_config.keymap.kconfig_options)

        # Add firmware kconfig options (overriding where they exist)
        if self.firmware_config.kconfig:
            for key, value in self.firmware_config.kconfig.items():
                combined[key] = value
                
        return combined
    
    def resolve_kconfig_with_user_options(self, user_options: Dict[str, Any]) -> Dict[str, str]:
        """Resolve kconfig settings with user-provided options."""
        options = self.kconfig_options
        resolved = {}
        
        # Apply defaults
        for key, config in options.items():
            resolved[config.kconfig_name] = str(config.default)
        
        # Apply user overrides
        for key, value in user_options.items():
            if key in options:
                resolved[options[key].kconfig_name] = str(value)
                
        return resolved
    
    def register_behaviors(self, behavior_registry: "BehaviorRegistryImpl") -> None:
        """Register all behaviors from this profile with a behavior registry.

        Args:
            behavior_registry: Registry to register behaviors with
        """
        for behavior in self.system_behaviors:
            behavior_registry.register_behavior(
                behavior.name,
                behavior.expected_params,
                behavior.origin
            )

    def resolve_includes(self, behaviors_used: List[str]) -> List[str]:
        """Resolve all necessary includes based on behaviors used.

        Args:
            behaviors_used: List of behavior codes used in keymap

        Returns:
            List of include statements
        """
        base_includes = set(self.keyboard_config.keymap.includes)

        # Add includes for each behavior
        for behavior in self.system_behaviors:
            if behavior.code in behaviors_used and behavior.includes:
                base_includes.update(behavior.includes)
                
        return sorted(list(base_includes))
```

### 4. Enhance Existing keyboard_config.py Module

Instead of creating a new service, we'll enhance the existing `keyboard_config.py` module to support typed configurations:

```python
# In glovebox/config/keyboard_config.py

# Existing functions for backward compatibility
def load_keyboard_config(keyboard_name: str) -> Dict[str, Any]:
    """Load a keyboard configuration by name (raw dictionary version)."""
    # Existing implementation remains unchanged
    pass

def get_firmware_config(keyboard_name: str, firmware_name: str) -> Dict[str, Any]:
    """Get a firmware configuration for a keyboard (raw dictionary version)."""
    # Existing implementation remains unchanged
    pass

# New typed functions

def load_keyboard_config_typed(keyboard_name: str) -> KeyboardConfig:
    """Load a keyboard configuration as a typed object.

    Args:
        keyboard_name: Name of the keyboard to load

    Returns:
        Typed KeyboardConfig object

    Raises:
        ConfigError: If the keyboard configuration cannot be found or loaded
    """
    raw_config = load_keyboard_config(keyboard_name)
    return KeyboardConfig(**raw_config)

def get_firmware_config_typed(keyboard_name: str, firmware_name: str) -> FirmwareConfig:
    """Get a firmware configuration as a typed object.

    Args:
        keyboard_name: Name of the keyboard
        firmware_name: Name of the firmware

    Returns:
        Typed FirmwareConfig object

    Raises:
        ConfigError: If the keyboard or firmware configuration cannot be found
    """
    raw_config = get_firmware_config(keyboard_name, firmware_name)
    return FirmwareConfig(**raw_config)

def create_keyboard_profile(keyboard_name: str, firmware_version: str) -> KeyboardProfile:
    """Create a KeyboardProfile for the given keyboard and firmware.

    Args:
        keyboard_name: Name of the keyboard
        firmware_version: Version of firmware to use

    Returns:
        KeyboardProfile configured for the keyboard and firmware

    Raises:
        ConfigError: If the keyboard or firmware configuration cannot be found
    """
    keyboard_config = load_keyboard_config_typed(keyboard_name)
    return KeyboardProfile(keyboard_config, firmware_version)
```

This approach:
1. Maintains backward compatibility with existing code
2. Adds new typed functions for the enhanced functionality
3. Reuses the existing file loading logic
4. Provides a clean factory function for creating keyboard profiles

### Factory Method in KeyboardProfile

We'll also add a factory method to KeyboardProfile for convenience:

```python
class KeyboardProfile:
    @classmethod
    def from_names(cls, keyboard_name: str, firmware_version: str) -> "KeyboardProfile":
        """Create a profile from keyboard name and firmware version.

        Args:
            keyboard_name: Name of the keyboard
            firmware_version: Version of firmware to use

        Returns:
            Configured KeyboardProfile instance

        Raises:
            ConfigError: If configuration cannot be found
        """
        from glovebox.config.keyboard_config import load_keyboard_config_typed
        keyboard_config = load_keyboard_config_typed(keyboard_name)
        return cls(keyboard_config, firmware_version)
```

### 5. Refactor KeymapService

Update KeymapService to use the new KeyboardProfile:

```python
class KeymapService(BaseServiceImpl):
    def __init__(
        self,
        file_adapter: FileAdapter,
        template_adapter: TemplateAdapter,
    ):
        """Initialize keymap service with adapter dependencies.

        Args:
            file_adapter: Adapter for file system operations
            template_adapter: Adapter for template rendering
        """
        super().__init__(service_name="KeymapService", service_version="1.0.0")
        self._file_adapter = file_adapter
        self._template_adapter = template_adapter

        # Initialize internal components
        self._behavior_registry = create_behavior_registry()
        self._behavior_formatter = BehaviorFormatterImpl(self._behavior_registry)
        self._dtsi_generator = DTSIGenerator(self._behavior_formatter)
        self._config_generator = create_config_generator()

    def compile(
        self,
        json_data: dict[str, Any] | KeymapData,
        source_json_path: Optional[Path],
        target_prefix: str,
        keyboard_name: str,
        firmware_version: str,
    ) -> KeymapResult:
        """Compile ZMK keymap files from JSON data.

        Args:
            json_data: Raw keymap JSON data or validated KeymapData
            source_json_path: Optional path to source JSON file
            target_prefix: Base path and name for output files
            keyboard_name: Name of the keyboard to build for
            firmware_version: Version of firmware to use

        Returns:
            KeymapResult with paths to generated files and build metadata
        """
        # Create profile using factory method
        profile = KeyboardProfile.from_names(keyboard_name, firmware_version)
        profile_name = f"{keyboard_name}/{firmware_version}"

        logger.info(f"Starting keymap build using profile: {profile_name}")

        result = KeymapResult(success=False)
        result.profile_name = profile_name

        try:
            # Validate and prepare input data
            validated_data = self._validate_data(json_data)
            result.layer_count = len(validated_data.get("layers", []))

            # Prepare output paths
            output_paths = self._prepare_output_paths(target_prefix)

            # Create output directory
            self._file_adapter.mkdir(output_paths["keymap"].parent)

            # Register system behaviors using profile
            profile.register_behaviors(self._behavior_registry)

            # Generate configuration file
            kconfig_settings = self._generate_config_file(
                validated_data, profile.kconfig_options, output_paths["conf"]
            )

            # Resolve includes based on behaviors used in the keymap
            behaviors_used = self._extract_behaviors_used(validated_data)
            resolved_includes = profile.resolve_includes(behaviors_used)

            # Generate keymap file
            self._generate_keymap_file(
                validated_data,
                profile,
                resolved_includes,
                output_paths["keymap"],
            )

            # Save JSON file
            self._save_json_file(validated_data, source_json_path, output_paths["json"])

            # Set result paths
            result.keymap_path = output_paths["keymap"]
            result.conf_path = output_paths["conf"]
            result.json_path = output_paths["json"]
            result.success = True

            result.add_message(f"Keymap built successfully for {profile_name}")
            logger.info(f"Keymap build completed successfully")

            return result

        except Exception as e:
            result.add_error(f"Keymap build failed: {e}")
            logger.error(f"Keymap build failed: {e}")
            raise KeymapError(f"Keymap build failed: {e}") from e
```

Note how this implementation:
1. Simplifies the constructor by removing the KeyboardConfigService dependency
2. Uses the KeyboardProfile.from_names() factory method
3. Maintains the same core functionality
4. Reduces complexity by removing conversion logic

## Implementation Plan

### Phase 1: Data Classes and Schema Validation

1. Create dataclasses in a new module `glovebox/config/models.py` that exactly match the structure in `keyboards/glove80.yaml`
2. Create a YAML schema for configuration validation in `glovebox/config/schema.py`
3. Add validation and serialization methods with schema validation
4. Add unit tests for dataclass conversion and schema validation

### Phase 2: Complete Replacement of keyboard_config.py Module

1. Refactor keyboard_config.py to use the new dataclasses without backward compatibility
2. Replace the existing KeyboardConfigService with simpler loading functions
3. Use schema validation when loading YAML files
4. Add unit tests for the new loading functions

### Phase 3: KeyboardProfile Implementation

1. Create KeyboardProfile class in `glovebox/config/profile.py`
2. Implement core methods for configuration access and resolution
3. Add static factory method for convenient creation
4. Add unit tests for profile functionality

### Phase 4: KeymapService Refactoring

1. Update KeymapService to use KeyboardProfile
2. Remove duplicated configuration handling code
3. Update tests to use the new interfaces

### Phase 5: CLI Integration

1. Update CLI commands to use the KeyboardProfile factory methods
2. Remove any backward compatibility code in CLI
3. Add comprehensive integration tests

## Implementation Tracking

| Task | Status | Notes |
|------|--------|-------|
| Create dataclasses for keyboard configuration | Completed | Created all necessary classes in models.py |
| Create YAML schema for validation | Completed | Created schema.py with JSON schema validation |
| Create KeyboardProfile class | Completed | Created profile.py with full implementation |
| Refactor keyboard_config.py | Completed | Updated to use typed dataclasses with schema validation |
| Update DisplayService | Completed | Added KeyboardProfile support to DisplayService |
| Update BuildService | Completed | Modified to use KeyboardProfile with backward compatibility |
| Update KeymapService | Completed | Fully migrated to use KeyboardProfile |
| Update FlashService | Completed | Added KeyboardProfile support with backward compatibility |
| Add tests | Completed | Added comprehensive tests for all services and KeyboardProfile |
| CLI Integration | Completed | Updated all CLI commands to use KeyboardProfile with --profile parameter |
| Documentation | Completed | Updated typed_configuration.md with usage examples and migration guidance |

## Expected Benefits

1. **Improved Type Safety**: Better IDE completion and static analysis
2. **Reduced Complexity**: KeymapService focused on core responsibilities
3. **Better Testability**: Typed interfaces are easier to mock and test
4. **Increased Maintainability**: Cleaner separation of concerns
5. **Clearer Documentation**: Types document expected data structure
6. **File Size Compliance**: Keep files under 500 lines as specified in CLAUDE.md

## Conclusion

This refactoring aligns with the project architecture principles in CLAUDE.md by emphasizing:
- Service-oriented design with clear responsibilities
- Simplicity first approach with minimal dependencies
- Clear error handling with specific exceptions
- Maintainable code with logical file organization

The improvements will make the codebase more robust, easier to understand, and simpler to extend in the future.
