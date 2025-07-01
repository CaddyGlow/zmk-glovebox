# Factory Functions Pattern

This document explains the factory function pattern used throughout Glovebox for consistent object creation, dependency injection, and configuration management.

## Factory Function Philosophy

Glovebox uses factory functions instead of singletons or global state to achieve:

- **🏗️ Consistent Creation**: All services and adapters use the same creation pattern
- **🔧 Dependency Injection**: Clean, testable dependency management
- **🎯 No Global State**: Every function call creates new instances
- **⚡ Easy Testing**: Simple mocking and isolation in tests
- **📋 Clear Interfaces**: Explicit dependencies and configuration

## Basic Factory Function Pattern

Every service, adapter, and major component has a corresponding factory function:

```python
# Basic factory function structure
def create_service_name(
    dependency1: Protocol | None = None,
    dependency2: Protocol | None = None,
    config: Config | None = None,
) -> ServiceProtocol:
    """Create service with specified or default dependencies.
    
    Args:
        dependency1: First dependency. If None, creates default.
        dependency2: Second dependency. If None, creates default.
        config: Configuration object. If None, uses default config.
    
    Returns:
        Configured service instance ready for use.
    """
    # Resolve dependencies
    if dependency1 is None:
        dependency1 = create_dependency1()
    
    if dependency2 is None:
        dependency2 = create_dependency2()
    
    if config is None:
        config = create_default_config()
    
    # Create and return service instance
    return ServiceImplementation(
        dependency1=dependency1,
        dependency2=dependency2,
        config=config,
    )
```

## Domain Service Factories

### Layout Domain Factory Functions

```python
# glovebox/layout/__init__.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from glovebox.protocols import FileAdapterProtocol, TemplateAdapterProtocol
    from glovebox.layout.behavior import BehaviorRegistryProtocol

def create_layout_service(
    file_adapter: "FileAdapterProtocol | None" = None,
    template_adapter: "TemplateAdapterProtocol | None" = None,
    behavior_registry: "BehaviorRegistryProtocol | None" = None,
) -> "LayoutService":
    """Create layout service with specified or default dependencies."""
    
    # Import at runtime to avoid circular imports
    from glovebox.layout.service import LayoutService
    
    # Resolve dependencies using their factory functions
    if file_adapter is None:
        from glovebox.adapters import create_file_adapter
        file_adapter = create_file_adapter()
    
    if template_adapter is None:
        from glovebox.adapters import create_template_adapter
        template_adapter = create_template_adapter()
    
    if behavior_registry is None:
        from glovebox.layout.behavior import create_behavior_registry
        behavior_registry = create_behavior_registry()
    
    return LayoutService(
        file_adapter=file_adapter,
        template_adapter=template_adapter,
        behavior_registry=behavior_registry,
    )

def create_layout_component_service(
    file_adapter: "FileAdapterProtocol | None" = None,
    layout_service: "LayoutService | None" = None,
) -> "LayoutComponentService":
    """Create layout component service for decompose/compose operations."""
    
    from glovebox.layout.component_service import LayoutComponentService
    
    if file_adapter is None:
        from glovebox.adapters import create_file_adapter
        file_adapter = create_file_adapter()
    
    if layout_service is None:
        layout_service = create_layout_service(file_adapter=file_adapter)
    
    return LayoutComponentService(
        file_adapter=file_adapter,
        layout_service=layout_service,
    )

def create_layout_display_service(
    formatter: "GridLayoutFormatter | None" = None,
) -> "LayoutDisplayService":
    """Create layout display service for terminal visualization."""
    
    from glovebox.layout.display_service import LayoutDisplayService
    
    if formatter is None:
        formatter = create_grid_layout_formatter()
    
    return LayoutDisplayService(formatter=formatter)
```

### Compilation Domain Factory Functions

```python
# glovebox/compilation/__init__.py

def create_compilation_service(strategy: str) -> "CompilationServiceProtocol":
    """Create compilation service with specified strategy.
    
    Args:
        strategy: Compilation strategy ('zmk_config', 'moergo', 'west', etc.)
    
    Returns:
        Compilation service implementing the specified strategy.
    
    Raises:
        ValueError: If strategy is not supported.
    """
    if strategy == "zmk_config":
        return create_zmk_west_service()
    elif strategy == "moergo":
        return create_moergo_nix_service()
    elif strategy == "west":
        return create_west_workspace_service()
    else:
        raise ValueError(f"Unsupported compilation strategy: {strategy}")

def create_zmk_west_service(
    docker_adapter: "DockerAdapterProtocol | None" = None,
    user_config: "UserConfig | None" = None,
    cache_manager: "CacheManager | None" = None,
    workspace_service: "ZmkWorkspaceCacheService | None" = None,
) -> "ZmkWestService":
    """Create ZMK west-based compilation service."""
    
    from glovebox.compilation.services.zmk_west_service import ZmkWestService
    
    # Resolve dependencies
    if docker_adapter is None:
        from glovebox.adapters import create_docker_adapter
        docker_adapter = create_docker_adapter()
    
    if user_config is None:
        from glovebox.config import create_user_config
        user_config = create_user_config()
    
    # Use shared cache coordination
    if cache_manager is None or workspace_service is None:
        from glovebox.compilation.cache import create_compilation_cache_service
        cache_manager, workspace_service = create_compilation_cache_service(user_config)
    
    return ZmkWestService(
        docker_adapter=docker_adapter,
        user_config=user_config,
        cache_manager=cache_manager,
        workspace_service=workspace_service,
    )

def create_moergo_nix_service(
    docker_adapter: "DockerAdapterProtocol | None" = None,
    user_config: "UserConfig | None" = None,
) -> "MoergoNixService":
    """Create MoErgo Nix-based compilation service."""
    
    from glovebox.compilation.services.moergo_nix_service import MoergoNixService
    
    if docker_adapter is None:
        from glovebox.adapters import create_docker_adapter
        docker_adapter = create_docker_adapter()
    
    if user_config is None:
        from glovebox.config import create_user_config
        user_config = create_user_config()
    
    return MoergoNixService(
        docker_adapter=docker_adapter,
        user_config=user_config,
    )
```

### Firmware Domain Factory Functions

```python
# glovebox/firmware/flash/__init__.py

def create_flash_service(
    device_detector: "DeviceDetectorProtocol | None" = None,
    usb_flasher: "USBFlasher | None" = None,
    flash_operations: "FlashOperations | None" = None,
) -> "FlashService":
    """Create flash service with specified or default dependencies."""
    
    from glovebox.firmware.flash.service import FlashService
    
    if device_detector is None:
        device_detector = create_device_detector()
    
    if usb_flasher is None:
        usb_flasher = create_usb_flasher()
    
    if flash_operations is None:
        flash_operations = create_flash_operations()
    
    return FlashService(
        device_detector=device_detector,
        usb_flasher=usb_flasher,
        flash_operations=flash_operations,
    )

def create_device_detector(
    usb_adapter: "USBAdapterProtocol | None" = None,
    flash_os_adapter: "FlashOSProtocol | None" = None,
) -> "DeviceDetector":
    """Create device detector with platform-specific adapters."""
    
    from glovebox.firmware.flash.device_detector import DeviceDetector
    
    if usb_adapter is None:
        from glovebox.adapters import create_usb_adapter
        usb_adapter = create_usb_adapter()
    
    if flash_os_adapter is None:
        from glovebox.firmware.flash.os_adapters import create_flash_os_adapter
        flash_os_adapter = create_flash_os_adapter()
    
    return DeviceDetector(
        usb_adapter=usb_adapter,
        flash_os_adapter=flash_os_adapter,
    )

def create_usb_flasher(
    flash_operations: "FlashOperations | None" = None,
) -> "USBFlasher":
    """Create USB flasher for low-level operations."""
    
    from glovebox.firmware.flash.flasher_methods import USBFlasher
    
    if flash_operations is None:
        flash_operations = create_flash_operations()
    
    return USBFlasher(flash_operations=flash_operations)
```

## Adapter Factory Functions

### Infrastructure Adapter Factories

```python
# glovebox/adapters/__init__.py

def create_docker_adapter(
    user_context: "DockerUserContext | None" = None,
    middleware: "OutputMiddleware | None" = None,
) -> "DockerAdapterProtocol":
    """Create Docker adapter with specified configuration."""
    
    from glovebox.adapters.docker_adapter import DockerAdapter
    
    if user_context is None:
        from glovebox.models.docker import DockerUserContext
        user_context = DockerUserContext()
    
    if middleware is None:
        middleware = create_logger_middleware()
    
    return DockerAdapter(
        user_context=user_context,
        middleware=middleware,
    )

def create_file_adapter() -> "FileAdapterProtocol":
    """Create file adapter with default configuration."""
    
    from glovebox.adapters.file_adapter import FileAdapter
    return FileAdapter()

def create_template_adapter(
    template_paths: list[Path] | None = None,
) -> "TemplateAdapterProtocol":
    """Create template adapter with Jinja2 backend."""
    
    from glovebox.adapters.template_adapter import TemplateAdapter
    
    if template_paths is None:
        # Default template paths
        from glovebox.config import get_default_template_paths
        template_paths = get_default_template_paths()
    
    return TemplateAdapter(template_paths=template_paths)

def create_usb_adapter() -> "USBAdapterProtocol":
    """Create USB adapter with platform detection."""
    
    from glovebox.adapters.usb_adapter import USBAdapter
    return USBAdapter()
```

## Configuration Factory Functions

### Configuration System Factories

```python
# glovebox/config/__init__.py

def create_keyboard_profile(
    keyboard: str,
    firmware: str | None = None,
) -> "KeyboardProfile":
    """Create keyboard profile from configuration files.
    
    Args:
        keyboard: Keyboard identifier (e.g., 'glove80')
        firmware: Firmware version (e.g., 'v25.05'). If None, keyboard-only profile.
    
    Returns:
        KeyboardProfile with loaded configuration.
    
    Raises:
        ProfileNotFoundError: If keyboard or firmware not found.
    """
    from glovebox.config.keyboard_profile import load_keyboard_config, get_firmware_config
    from glovebox.config.profile import KeyboardProfile
    
    # Load keyboard configuration
    keyboard_config = load_keyboard_config(keyboard)
    
    # Load firmware configuration if specified
    firmware_config = None
    if firmware is not None:
        firmware_config = get_firmware_config(keyboard, firmware)
    
    return KeyboardProfile(
        name=f"{keyboard}/{firmware}" if firmware else keyboard,
        keyboard_config=keyboard_config,
        firmware_config=firmware_config,
    )

def create_user_config(
    cli_config_path: Path | None = None,
) -> "UserConfig":
    """Create user configuration with default or specified path."""
    
    from glovebox.config.user_config import UserConfig
    return UserConfig(cli_config_path=cli_config_path)
```

## Cache Factory Functions

### Shared Cache Coordination

```python
# glovebox/core/cache/__init__.py

def create_default_cache(
    tag: str | None = None,
    cache_root: Path | None = None,
    enabled: bool = True,
) -> "CacheManager":
    """Create cache manager with shared coordination.
    
    Args:
        tag: Cache namespace tag for domain isolation
        cache_root: Root directory for cache storage
        enabled: Whether caching is enabled
    
    Returns:
        CacheManager instance (shared if same tag used)
    """
    if cache_root is None:
        from glovebox.config import get_default_cache_root
        cache_root = get_default_cache_root()
    
    # Use shared coordination to avoid duplicate instances
    from glovebox.core.cache.cache_coordinator import get_shared_cache_instance
    return get_shared_cache_instance(
        cache_root=cache_root,
        tag=tag,
        enabled=enabled,
    )

def create_cache_from_user_config(
    user_config: "UserConfig",
    tag: str | None = None,
) -> "CacheManager":
    """Create cache manager from user configuration."""
    
    cache_root = user_config.cache_directory
    enabled = user_config.cache_enabled
    
    return create_default_cache(
        tag=tag,
        cache_root=cache_root,
        enabled=enabled,
    )
```

### Domain-Specific Cache Factories

```python
# glovebox/compilation/cache/__init__.py

def create_compilation_cache_service(
    user_config: "UserConfig | None" = None,
) -> tuple["CacheManager", "ZmkWorkspaceCacheService"]:
    """Create compilation cache services with shared coordination.
    
    Returns:
        Tuple of (cache_manager, workspace_service) for compilation operations.
    """
    from glovebox.compilation.cache.workspace_cache_service import ZmkWorkspaceCacheService
    
    if user_config is None:
        from glovebox.config import create_user_config
        user_config = create_user_config()
    
    # Use shared cache coordination with compilation tag
    from glovebox.core.cache import create_cache_from_user_config
    cache_manager = create_cache_from_user_config(user_config, tag="compilation")
    
    # Create workspace service
    workspace_service = ZmkWorkspaceCacheService(
        cache_manager=cache_manager,
        user_config=user_config,
    )
    
    return cache_manager, workspace_service
```

## Advanced Factory Patterns

### Conditional Factory Functions

Factory functions that create different implementations based on conditions:

```python
def create_flash_os_adapter() -> "FlashOSProtocol":
    """Create platform-specific flash OS adapter."""
    
    import platform
    
    system = platform.system().lower()
    
    if system == "linux":
        from glovebox.firmware.flash.adapters.linux_adapter import LinuxFlashOS
        return LinuxFlashOS()
    elif system == "darwin":
        from glovebox.firmware.flash.adapters.macos_adapter import MacOSFlashOS
        return MacOSFlashOS()
    elif system == "windows":
        from glovebox.firmware.flash.adapters.windows_adapter import WindowsFlashOS
        return WindowsFlashOS()
    else:
        from glovebox.firmware.flash.adapters.stub_adapter import StubFlashOS
        return StubFlashOS()
```

### Factory Functions with Configuration

Factory functions that accept configuration objects:

```python
def create_compilation_service_from_config(
    config: "CompilationConfig",
    user_config: "UserConfig | None" = None,
) -> "CompilationServiceProtocol":
    """Create compilation service from configuration object."""
    
    # Resolve user config
    if user_config is None:
        from glovebox.config import create_user_config
        user_config = create_user_config()
    
    # Create service based on config type
    if isinstance(config, ZmkCompilationConfig):
        return create_zmk_west_service(user_config=user_config)
    elif isinstance(config, MoergoCompilationConfig):
        return create_moergo_nix_service(user_config=user_config)
    else:
        raise ValueError(f"Unsupported compilation config type: {type(config)}")
```

### Builder Pattern Integration

Combine factory functions with builder pattern for complex configuration:

```python
class LayoutServiceBuilder:
    """Builder for complex LayoutService configuration."""
    
    def __init__(self):
        self._file_adapter = None
        self._template_adapter = None
        self._behavior_registry = None
        self._cache_enabled = True
        self._template_paths = []
    
    def with_file_adapter(self, adapter: "FileAdapterProtocol") -> "LayoutServiceBuilder":
        """Set file adapter."""
        self._file_adapter = adapter
        return self
    
    def with_template_paths(self, paths: list[Path]) -> "LayoutServiceBuilder":
        """Add template search paths."""
        self._template_paths.extend(paths)
        return self
    
    def with_cache_disabled(self) -> "LayoutServiceBuilder":
        """Disable caching."""
        self._cache_enabled = False
        return self
    
    def build(self) -> "LayoutService":
        """Build configured LayoutService."""
        # Create template adapter with custom paths
        if self._template_adapter is None:
            self._template_adapter = create_template_adapter(
                template_paths=self._template_paths or None
            )
        
        return create_layout_service(
            file_adapter=self._file_adapter,
            template_adapter=self._template_adapter,
            behavior_registry=self._behavior_registry,
        )

# Factory function using builder
def create_layout_service_with_config(config: "LayoutServiceConfig") -> "LayoutService":
    """Create layout service from configuration object."""
    builder = LayoutServiceBuilder()
    
    if config.template_paths:
        builder.with_template_paths(config.template_paths)
    
    if not config.cache_enabled:
        builder.with_cache_disabled()
    
    return builder.build()
```

## Testing Factory Functions

### Mocking in Tests

Factory functions make testing easy with dependency injection:

```python
# tests/test_layout/test_service.py

class TestLayoutService:
    @pytest.fixture
    def mock_file_adapter(self):
        """Create mock file adapter for testing."""
        return Mock(spec=FileAdapterProtocol)
    
    @pytest.fixture
    def mock_template_adapter(self):
        """Create mock template adapter for testing."""
        return Mock(spec=TemplateAdapterProtocol)
    
    @pytest.fixture
    def service(self, mock_file_adapter, mock_template_adapter):
        """Create service with mocked dependencies."""
        return create_layout_service(
            file_adapter=mock_file_adapter,
            template_adapter=mock_template_adapter,
        )
    
    def test_generate_layout_success(self, service, mock_template_adapter):
        """Test successful layout generation."""
        # Arrange
        mock_template_adapter.render.return_value = "rendered content"
        layout_data = create_test_layout_data()
        profile = create_test_keyboard_profile()
        
        # Act
        result = service.generate(profile, layout_data, "/tmp/output")
        
        # Assert
        assert result.success is True
        mock_template_adapter.render.assert_called_once()
```

### Integration Testing

Test factory functions with real dependencies:

```python
class TestFactoryFunctions:
    def test_create_layout_service_default_dependencies(self):
        """Test factory function creates service with default dependencies."""
        # Act
        service = create_layout_service()
        
        # Assert
        assert isinstance(service, LayoutService)
        assert hasattr(service, 'file_adapter')
        assert hasattr(service, 'template_adapter')
        assert hasattr(service, 'behavior_registry')
    
    def test_create_layout_service_custom_dependencies(self):
        """Test factory function with custom dependencies."""
        # Arrange
        custom_file_adapter = create_file_adapter()
        custom_template_adapter = create_template_adapter()
        
        # Act
        service = create_layout_service(
            file_adapter=custom_file_adapter,
            template_adapter=custom_template_adapter,
        )
        
        # Assert
        assert service.file_adapter is custom_file_adapter
        assert service.template_adapter is custom_template_adapter
```

## Factory Function Guidelines

### Best Practices

1. **✅ Consistent Naming**: All factory functions use `create_*` prefix
2. **✅ Optional Dependencies**: All dependencies should be optional with defaults
3. **✅ Type Annotations**: Full type annotations including return types
4. **✅ Comprehensive Docstrings**: Document parameters, returns, and examples
5. **✅ Runtime Imports**: Import implementations at runtime to avoid circular imports
6. **✅ Protocol Dependencies**: Depend on protocols, not concrete classes

### Common Patterns

```python
# ✅ CORRECT - Standard factory function pattern
def create_service_name(
    dependency1: Protocol | None = None,
    dependency2: Protocol | None = None,
) -> ServiceProtocol:
    """Create service with dependencies."""
    
    # Runtime imports
    from .service_implementation import ServiceImplementation
    
    # Resolve dependencies
    if dependency1 is None:
        dependency1 = create_dependency1()
    
    if dependency2 is None:
        dependency2 = create_dependency2()
    
    # Create instance
    return ServiceImplementation(
        dependency1=dependency1,
        dependency2=dependency2,
    )

# ✅ CORRECT - Export in __init__.py
# domain/__init__.py
from .factories import create_service_name

__all__ = ["create_service_name"]
```

### Anti-Patterns to Avoid

```python
# ❌ WRONG - Singleton pattern
_service_instance = None

def get_service():  # Should be create_service
    global _service_instance
    if _service_instance is None:
        _service_instance = Service()
    return _service_instance

# ❌ WRONG - Required dependencies
def create_service(dependency: Protocol) -> Service:  # Should be optional
    return Service(dependency)

# ❌ WRONG - Global configuration
def create_service() -> Service:
    global_config = get_global_config()  # Avoid global state
    return Service(global_config)

# ❌ WRONG - Missing type annotations
def create_service(dependency=None):  # Missing types
    return Service(dependency)
```

## Factory Function Registry

For complex applications, maintain a registry of factory functions:

```python
from typing import Dict, Callable, TypeVar, Type

T = TypeVar('T')

class FactoryRegistry:
    """Registry for managing factory functions."""
    
    def __init__(self):
        self._factories: Dict[str, Callable] = {}
    
    def register(self, name: str, factory: Callable[..., T]) -> None:
        """Register a factory function."""
        self._factories[name] = factory
    
    def create(self, name: str, **kwargs) -> T:
        """Create instance using registered factory."""
        if name not in self._factories:
            raise ValueError(f"Factory '{name}' not registered")
        
        factory = self._factories[name]
        return factory(**kwargs)
    
    def list_factories(self) -> list[str]:
        """List registered factory names."""
        return list(self._factories.keys())

# Global registry instance
factory_registry = FactoryRegistry()

# Registration during module import
factory_registry.register("layout_service", create_layout_service)
factory_registry.register("flash_service", create_flash_service)
factory_registry.register("compilation_service", create_compilation_service)

# Usage
def create_service_by_name(service_name: str, **kwargs):
    """Create service by name using registry."""
    return factory_registry.create(service_name, **kwargs)
```

---

**Next Steps**:
- Review [Service Layer Patterns](service-layer.md) for service implementation details
- Explore [Protocol Design](protocol-design.md) for interface definition guidelines  
- Check [Dependency Injection](dependency-injection.md) for advanced dependency management