"""Core test fixtures for the glovebox project."""

import json
import os
import tempfile
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest
import yaml
from typer.testing import CliRunner

from glovebox.config.models import (
    BuildOptions,
    FirmwareConfig,
    FormattingConfig,
    KConfigOption,
    KeyboardConfig,
    KeymapSection,
)
from glovebox.config.profile import KeyboardProfile
from glovebox.config.user_config import UserConfig
from glovebox.firmware.flash.models import FlashResult
from glovebox.firmware.models import BuildResult, FirmwareOutputFiles
from glovebox.layout.models import LayoutResult, SystemBehavior
from glovebox.protocols import FileAdapterProtocol, TemplateAdapterProtocol


# ---- Base Fixtures ----


@pytest.fixture
def cli_runner() -> CliRunner:
    """Return a Typer CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_file_adapter() -> Mock:
    """Create a mock file adapter for testing."""
    adapter = Mock(spec=FileAdapterProtocol)
    return adapter


@pytest.fixture
def mock_template_adapter() -> Mock:
    """Create a mock template adapter for testing."""
    adapter = Mock(spec=TemplateAdapterProtocol)
    return adapter


# ---- Test Isolation Fixtures ----


@pytest.fixture
def isolated_config(tmp_path: Path) -> Generator[UserConfig, None, None]:
    """Create an isolated UserConfig instance with temporary directories.

    This fixture provides complete configuration isolation by:
    - Using a temporary config directory instead of ~/.glovebox/
    - Mocking environment variables to prevent external influence
    - Creating a clean UserConfig instance for each test

    Usage:
        def test_config_operation(isolated_config):
            config = isolated_config
            config.set("profile", "test_keyboard/v1.0")
            # All operations are isolated to temp directory
    """
    # Create isolated config directory structure
    config_dir = tmp_path / ".glovebox"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "glovebox.yaml"

    # Create minimal valid config
    initial_config = {
        "profile": "test_keyboard/v1.0",
        "log_level": "INFO",
        "keyboard_paths": [],
    }

    with config_file.open("w") as f:
        yaml.dump(initial_config, f)

    # Mock environment to prevent external config influence
    original_env = dict(os.environ)

    # Clear any existing GLOVEBOX_ env vars
    for key in list(os.environ.keys()):
        if key.startswith("GLOVEBOX_"):
            del os.environ[key]

    # Set isolated environment
    os.environ["GLOVEBOX_CONFIG_DIR"] = str(config_dir)

    try:
        # Create isolated UserConfig instance
        user_config = UserConfig(cli_config_path=config_file)
        yield user_config
    finally:
        # Restore original environment
        os.environ.clear()
        os.environ.update(original_env)


@pytest.fixture
def isolated_cache_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[dict[str, Any], None, None]:
    """Create isolated cache environment for tests.

    This fixture provides cache isolation by:
    - Setting XDG_CACHE_HOME to a temporary directory
    - Creating cache directory structure
    - Providing cache-related paths in context

    Usage:
        def test_cache_operation(isolated_cache_environment):
            # Cache operations isolated to temp directory
            cache = create_default_cache(tag="test")
            cache.set("key", "value")

        # Can be combined with other fixtures:
        def test_combined(isolated_cache_environment, isolated_config):
            # Both cache and config isolated
    """
    # Create cache directory structure
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    # Mock XDG_CACHE_HOME to use temporary directory
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache_dir))

    # Create environment context
    cache_context = {
        "cache_dir": cache_dir,
        "cache_root": cache_dir / "glovebox",
        "temp_dir": tmp_path,
    }

    try:
        yield cache_context
    finally:
        # Reset shared cache instances for test isolation
        from glovebox.core.cache_v2 import reset_shared_cache_instances

        reset_shared_cache_instances()


@pytest.fixture
def isolated_cli_environment(
    isolated_config: UserConfig,
    isolated_cache_environment: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[dict[str, Any], None, None]:
    """Create isolated environment for CLI command tests.

    This fixture provides complete CLI isolation by:
    - Using isolated_config for configuration management
    - Using isolated_cache_environment for cache isolation
    - Setting current directory to a temporary path
    - Mocking environment variables
    - Providing a clean environment context

    Usage:
        def test_cli_command(isolated_cli_environment, cli_runner):
            result = cli_runner.invoke(app, ["config", "list"])
            # All file operations isolated to temp directory
    """
    # Change to temporary directory for the test
    original_cwd = Path.cwd()
    os.chdir(tmp_path)

    # Create working directories
    work_dir = tmp_path / "work"
    output_dir = tmp_path / "output"
    work_dir.mkdir()
    output_dir.mkdir()

    # Mock common environment variables
    config_dir = (
        str(isolated_config.config_file_path.parent)
        if isolated_config.config_file_path is not None
        else str(tmp_path / ".glovebox")
    )
    monkeypatch.setenv("GLOVEBOX_CONFIG_DIR", config_dir)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("TMPDIR", str(tmp_path / "tmp"))
    # XDG_CACHE_HOME is already set by isolated_cache_environment

    # Create environment context combining both cache and CLI contexts
    env_context = {
        "config": isolated_config,
        "work_dir": work_dir,
        "output_dir": output_dir,
        "temp_dir": tmp_path,
        "config_file": isolated_config.config_file_path,
        # Include cache context
        "cache_dir": isolated_cache_environment["cache_dir"],
        "cache_root": isolated_cache_environment["cache_root"],
    }

    try:
        yield env_context
    finally:
        # Restore original working directory
        os.chdir(original_cwd)


@pytest.fixture(autouse=True)
def reset_shared_cache() -> Generator[None, None, None]:
    """Reset shared cache instances before each test for isolation.

    This fixture ensures test isolation by resetting all shared cache instances
    following CLAUDE.md requirements for test pollution prevention.

    The fixture is autouse=True to automatically reset cache between tests.
    """
    from glovebox.core.cache_v2 import reset_shared_cache_instances

    # Reset cache before test
    reset_shared_cache_instances()

    yield

    # Reset cache after test for extra safety
    reset_shared_cache_instances()


@pytest.fixture
def shared_cache_stats() -> Generator[Callable[[], dict[str, Any]], None, None]:
    """Provide access to shared cache statistics for testing.

    Returns:
        Callable that returns cache instance count and keys for debugging
    """
    from glovebox.core.cache_v2 import (
        get_cache_instance_count,
        get_cache_instance_keys,
    )

    def get_stats() -> dict[str, Any]:
        return {
            "instance_count": get_cache_instance_count(),
            "instance_keys": get_cache_instance_keys(),
        }

    yield get_stats


# ---- Test Data Directories ----


@pytest.fixture
def test_data_dir():
    """Return the path to the test data directory."""
    return Path(__file__).parent / "test_config" / "test_data"


@pytest.fixture
def keyboard_search_path(test_data_dir):
    """Return the keyboard search path for testing."""
    return str(test_data_dir / "keyboards")


# ---- Configuration Fixtures ----


@pytest.fixture
def mock_keyboard_config_dict() -> dict[str, Any]:
    """Create a mock keyboard configuration dictionary for testing."""
    return {
        "keyboard": "test_keyboard",
        "description": "Mock keyboard for testing",
        "vendor": "Test Vendor",
        "key_count": 80,
        "compile_methods": [
            {
                "type": "moergo",
                "image": "test-zmk-build",
                "repository": "test/zmk",
                "branch": "main",
            }
        ],
        "flash_methods": [
            {
                "device_query": "vendor=Test and removable=true",
                "mount_timeout": 30,
                "copy_timeout": 60,
                "sync_after_copy": True,
            },
        ],
        "firmwares": {
            "default": {
                "description": "Default test firmware",
                "version": "v1.0.0",
                "build_options": {"repository": "test/zmk", "branch": "main"},
            },
            "bluetooth": {
                "description": "Bluetooth-focused test firmware",
                "version": "v2.0.0",
                "build_options": {"repository": "test/zmk", "branch": "bluetooth"},
            },
            "v25.05": {
                "description": "Bluetooth-focused test firmware",
                "version": "v25.05",
                "build_options": {"repository": "test/zmk", "branch": "v25.05"},
                "kconfig": {
                    "CONFIG_ZMK_BLE": {
                        "name": "CONFIG_ZMK_BLE",
                        "type": "bool",
                        "default": True,
                        "description": "Enable BLE",
                    },
                    "CONFIG_ZMK_USB": {
                        "name": "CONFIG_ZMK_USB",
                        "type": "bool",
                        "default": False,
                        "description": "Disable USB",
                    },
                },
            },
        },
        "keymap": {
            "includes": ["<dt-bindings/zmk/keys.h>"],
            "system_behaviors": [],
            "kconfig_options": {},
            "keymap_dtsi": "#include <behaviors.dtsi>",
            "system_behaviors_dts": "test behaviors",
            "key_position_header": "test header",
            "formatting": {"key_gap": "  ", "base_indent": ""},
        },
    }


@pytest.fixture
def mock_firmware_config_dict() -> dict[str, Any]:
    """Create a mock firmware configuration dictionary for testing."""
    return {
        "description": "Default test firmware",
        "version": "v1.0.0",
        "build_options": {"repository": "test/zmk", "branch": "main"},
    }


@pytest.fixture
def keyboard_config_dir(tmp_path):
    """Create a temporary directory with test keyboard configurations."""
    # Create keyboards directory
    keyboards_dir = tmp_path / "keyboards"
    keyboards_dir.mkdir()

    # Create test keyboard configuration
    test_keyboard_config = {
        "keyboard": "test_keyboard",
        "description": "Test keyboard for integration testing",
        "vendor": "Test Vendor",
        "key_count": 80,
        "compile_methods": [
            {
                "type": "moergo",
                "image": "test-zmk-build",
                "repository": "test/zmk",
                "branch": "main",
            }
        ],
        "flash_methods": [
            {
                "device_query": "vendor=Test and removable=true",
                "mount_timeout": 30,
                "copy_timeout": 60,
                "sync_after_copy": True,
            },
        ],
        "firmwares": {
            "default": {
                "version": "v1.0.0",
                "description": "Default test firmware",
                "build_options": {
                    "repository": "test/zmk",
                    "branch": "main",
                },
            },
            "bluetooth": {
                "version": "bluetooth",
                "description": "Bluetooth-focused test firmware",
                "build_options": {
                    "repository": "test/zmk",
                    "branch": "bluetooth",
                },
                "kconfig": {
                    "CONFIG_ZMK_BLE": {
                        "name": "CONFIG_ZMK_BLE",
                        "type": "bool",
                        "default": "y",
                        "description": "Enable BLE support",
                    },
                    "CONFIG_ZMK_USB": {
                        "name": "CONFIG_ZMK_USB",
                        "type": "bool",
                        "default": "n",
                        "description": "Enable USB support",
                    },
                },
            },
        },
        "keymap": {
            "includes": ["#include <dt-bindings/zmk/keys.h>"],
            "system_behaviors": [
                {
                    "code": "&kp",
                    "name": "&kp",
                    "description": "Key press behavior",
                    "expected_params": 1,
                    "origin": "zmk",
                    "params": [],
                }
            ],
            "kconfig_options": {
                "CONFIG_ZMK_KEYBOARD_NAME": {
                    "name": "CONFIG_ZMK_KEYBOARD_NAME",
                    "type": "string",
                    "default": "Test Keyboard",
                    "description": "Keyboard name",
                }
            },
            "keymap_dtsi": """
            #include <behaviors.dtsi>
            #include <dt-bindings/zmk/keys.h>
            {{ resolved_includes }}

            / {
                keymap {
                    compatible = "zmk,keymap";
                    {{ keymap_node }}
                };
            };
            """,
            "key_position_header": """
            // Key positions
            #define KEY_0 0
            #define KEY_1 1
            // ... more keys
            """,
        },
        "formatting": {"key_gap": "  ", "base_indent": "    "},
    }

    # Create glove80 configuration
    glove80_config = {
        "keyboard": "glove80",
        "description": "MoErgo Glove80 split ergonomic keyboard",
        "vendor": "MoErgo",
        "key_count": 80,
        "compile_methods": [
            {
                "type": "moergo",
                "image": "moergo-zmk-build",
                "repository": "moergo-sc/zmk",
                "branch": "v25.05",
                "jobs": 8,
                "fallback_methods": ["local"],
            }
        ],
        "flash_methods": [
            {
                "method_type": "usb",
                "device_query": "vendor=Adafruit and serial~=GLV80-.* and removable=true",
                "mount_timeout": 30,
                "copy_timeout": 60,
                "sync_after_copy": True,
                "fallback_methods": ["dfu"],
            },
            {
                "method_type": "dfu",
                "device_query": "DFU",
                "vid": "0x1209",
                "pid": "0x0080",
                "interface": 0,
                "alt_setting": 0,
                "timeout": 30,
                "fallback_methods": [],
            },
        ],
        "firmwares": {
            "v25.05": {
                "version": "v25.05",
                "description": "Stable MoErgo firmware v25.05",
                "build_options": {
                    "repository": "moergo-sc/zmk",
                    "branch": "v25.05",
                },
            },
            "v25.04-beta.1": {
                "version": "v25.04-beta.1",
                "description": "Beta MoErgo firmware v25.04-beta.1",
                "build_options": {
                    "repository": "moergo-sc/zmk",
                    "branch": "v25.04-beta.1",
                },
            },
        },
        "keymap": {
            "includes": ["#include <dt-bindings/zmk/keys.h>"],
            "system_behaviors": [
                {
                    "code": "&kp",
                    "name": "&kp",
                    "description": "Key press behavior",
                    "expected_params": 1,
                    "origin": "zmk",
                    "params": [],
                }
            ],
            "kconfig_options": {
                "CONFIG_ZMK_KEYBOARD_NAME": {
                    "name": "CONFIG_ZMK_KEYBOARD_NAME",
                    "type": "string",
                    "default": "Glove80",
                    "description": "Keyboard name",
                }
            },
            "keymap_dtsi": "// Glove80 keymap template",
        },
        "formatting": {"key_gap": "  ", "base_indent": "    "},
    }

    # Write config files
    (keyboards_dir / "test_keyboard.yaml").write_text(yaml.dump(test_keyboard_config))
    (keyboards_dir / "glove80.yaml").write_text(yaml.dump(glove80_config))

    # Return the parent directory
    return tmp_path


@pytest.fixture
def typed_config_file(tmp_path, mock_keyboard_config_dict):
    """Create a temporary YAML file with the mock config."""
    config_file = tmp_path / "test_keyboard.yaml"
    config_file.write_text(yaml.dump(mock_keyboard_config_dict))
    return config_file


# ---- Typed Object Fixtures ----


@pytest.fixture
def mock_keyboard_config() -> Mock:
    """Create a mocked KeyboardConfig instance to avoid initialization issues."""
    mock_config = Mock(spec=KeyboardConfig)

    # Set attributes that tests will access
    mock_config.keyboard = "test_keyboard"
    mock_config.description = "Mock keyboard for testing"
    mock_config.vendor = "Test Vendor"
    mock_config.key_count = 80

    # Create mock flash methods
    mock_flash_method = Mock()
    mock_flash_method.method_type = "usb"
    mock_flash_method.device_query = "vendor=Test and removable=true"
    mock_flash_method.vid = "0x1234"
    mock_flash_method.pid = "0x5678"
    mock_config.flash_methods = [mock_flash_method]

    # Create mock compile methods
    mock_compile_method = Mock()
    mock_compile_method.method_type = "docker"
    mock_compile_method.image = "test-zmk-build"
    mock_compile_method.repository = "test/zmk"
    mock_compile_method.branch = "main"
    mock_config.compile_methods = [mock_compile_method]

    # Create mock firmwares
    mock_config.firmwares = {
        "default": Mock(spec=FirmwareConfig),
        "bluetooth": Mock(spec=FirmwareConfig),
        "v25.05": Mock(spec=FirmwareConfig),
    }

    # Set up firmware attributes
    for name, firmware in mock_config.firmwares.items():
        firmware.version = (
            "v1.0.0"
            if name == "default"
            else ("v2.0.0" if name == "bluetooth" else "v25.05")
        )
        firmware.description = f"{name.capitalize()} test firmware"

        # Create mock build options
        firmware.build_options = Mock(spec=BuildOptions)
        firmware.build_options.repository = "test/zmk"
        firmware.build_options.branch = name if name != "default" else "main"

    # Create mock keymap config
    mock_config.keymap = Mock(spec=KeymapSection)
    mock_config.keymap.includes = ["<dt-bindings/zmk/keys.h>"]
    mock_config.keymap.system_behaviors = []
    mock_config.keymap.kconfig_options = {}
    mock_config.keymap.keymap_dtsi = "#include <behaviors.dtsi>"
    mock_config.keymap.system_behaviors_dts = "test behaviors"
    mock_config.keymap.key_position_header = "test header"

    # Create mock formatting
    mock_config.keymap.formatting = Mock(spec=FormattingConfig)
    mock_config.keymap.formatting.key_gap = "  "
    mock_config.keymap.formatting.base_indent = ""

    return mock_config


@pytest.fixture
def mock_firmware_config() -> Mock:
    """Create a mocked FirmwareConfig instance."""
    mock_config = Mock(spec=FirmwareConfig)
    mock_config.version = "v1.0.0"
    mock_config.description = "Default test firmware"

    # Create mock build options
    mock_config.build_options = Mock(spec=BuildOptions)
    mock_config.build_options.repository = "test/zmk"
    mock_config.build_options.branch = "main"

    # Kconfig is None by default
    mock_config.kconfig = None

    return mock_config


@pytest.fixture
def create_keyboard_profile_fixture():
    """Factory fixture to create mock KeyboardProfile with customizable properties."""

    def _create_profile(
        keyboard_name="test_keyboard",
        firmware_version="default",
        system_behaviors=None,
        kconfig_options=None,
    ):
        mock_profile = Mock(spec=KeyboardProfile)
        mock_profile.keyboard_name = keyboard_name
        mock_profile.firmware_version = firmware_version

        # Set up properties that use the above mocks
        mock_profile.keyboard_config = Mock(spec=KeyboardConfig)
        mock_profile.firmware_config = Mock(spec=FirmwareConfig)

        # Set up the system behaviors
        if system_behaviors is None:
            # Default system behaviors
            behavior1 = SystemBehavior(
                code="&kp",
                name="&kp",
                description=None,
                expected_params=1,
                origin="zmk",
                params=[],
                includes=None,
            )

            behavior2 = SystemBehavior(
                code="&bt",
                name="&bt",
                description=None,
                expected_params=1,
                origin="zmk",
                params=[],
                includes=["#include <dt-bindings/zmk/bt.h>"],
            )

            mock_profile.system_behaviors = [behavior1, behavior2]
        else:
            mock_profile.system_behaviors = system_behaviors

        # Set up the keyboard_config mock with keymap
        mock_profile.keyboard_config.keymap = Mock(spec=KeymapSection)
        mock_profile.keyboard_config.keymap.keymap_dtsi = (
            "#include <behaviors.dtsi>\n{{ keymap_node }}"
        )
        mock_profile.keyboard_config.keymap.key_position_header = "// Key positions"
        mock_profile.keyboard_config.keymap.system_behaviors_dts = "// System behaviors"

        # Set up the get_template method
        mock_profile.get_template = lambda name, default=None: {
            "keymap_dtsi": mock_profile.keyboard_config.keymap.keymap_dtsi,
            "key_position_header": mock_profile.keyboard_config.keymap.key_position_header,
            "system_behaviors_dts": mock_profile.keyboard_config.keymap.system_behaviors_dts,
        }.get(name, default)

        # Set up kconfig options
        if kconfig_options is None:
            # Default kconfig option
            kconfig_option = Mock(spec=KConfigOption)
            kconfig_option.name = "CONFIG_ZMK_KEYBOARD_NAME"
            kconfig_option.default = "Test Keyboard"
            kconfig_option.type = "string"
            kconfig_option.description = "Keyboard name"

            mock_profile.kconfig_options = {"CONFIG_ZMK_KEYBOARD_NAME": kconfig_option}
        else:
            mock_profile.kconfig_options = kconfig_options

        # Set up resolve_includes method
        mock_profile.resolve_includes = lambda behaviors_used: [
            "#include <dt-bindings/zmk/keys.h>",
            "#include <dt-bindings/zmk/bt.h>",
        ]

        # Set up extract_behavior_codes method
        mock_profile.extract_behavior_codes = lambda keymap_data: ["&kp", "&bt", "&lt"]

        # Set up resolve_kconfig_with_user_options method
        mock_profile.resolve_kconfig_with_user_options = lambda user_options: {
            "CONFIG_ZMK_KEYBOARD_NAME": "Test Keyboard"
        }

        # Set up generate_kconfig_content method
        mock_profile.generate_kconfig_content = lambda kconfig_settings: (
            '# Generated ZMK configuration\n\nCONFIG_ZMK_KEYBOARD_NAME="Test Keyboard"\n'
        )

        return mock_profile

    return _create_profile


@pytest.fixture
def mock_keyboard_profile(create_keyboard_profile_fixture):
    """Create a standard mocked KeyboardProfile."""
    return create_keyboard_profile_fixture()


@pytest.fixture
def mock_load_keyboard_config(mock_keyboard_config) -> Generator[Mock, None, None]:
    """Mock the load_keyboard_config function."""
    with patch("glovebox.config.keyboard_profile.load_keyboard_config") as mock_load:
        mock_load.return_value = mock_keyboard_config
        yield mock_load


@pytest.fixture
def mock_get_available_keyboards() -> Generator[Mock, None, None]:
    """Mock the get_available_keyboards function."""
    with patch("glovebox.config.keyboard_profile.get_available_keyboards") as mock_get:
        mock_get.return_value = ["test_keyboard", "glove80", "corne"]
        yield mock_get


@pytest.fixture
def mock_get_firmware_config(mock_firmware_config) -> Generator[Mock, None, None]:
    """Mock the get_firmware_config function."""
    with patch("glovebox.config.keyboard_profile.get_firmware_config") as mock_get:
        mock_get.return_value = mock_firmware_config
        yield mock_get


@pytest.fixture
def mock_get_available_firmwares() -> Generator[Mock, None, None]:
    """Mock the get_available_firmwares function."""
    with patch("glovebox.config.keyboard_profile.get_available_firmwares") as mock_get:
        mock_get.return_value = ["default", "bluetooth", "v25.05"]
        yield mock_get


@pytest.fixture
def mock_create_keyboard_profile(mock_keyboard_profile) -> Generator[Mock, None, None]:
    """Mock the create_keyboard_profile function."""
    with patch(
        "glovebox.config.keyboard_profile.create_keyboard_profile"
    ) as mock_create:
        mock_create.return_value = mock_keyboard_profile
        yield mock_create


@pytest.fixture
def mock_layout_service() -> Mock:
    """Mock LayoutService with common behaviors."""
    mock = Mock()

    # Mock successful generate result
    result = LayoutResult(success=True)
    result.keymap_path = Path("/tmp/output/keymap.keymap")
    result.conf_path = Path("/tmp/output/keymap.conf")
    mock.generate.return_value = result
    mock.generate_from_file.return_value = result

    # Mock successful extract result
    extract_result = LayoutResult(success=True)
    mock.extract_components.return_value = extract_result
    mock.extract_components_from_file.return_value = extract_result

    # Mock successful merge result
    merge_result = LayoutResult(success=True)
    mock.combine_components.return_value = merge_result
    mock.combine_components_from_directory.return_value = merge_result

    # Mock show result
    mock.show.return_value = ["Layer 1", "Layer 2"]
    mock.show_from_file.return_value = ["Layer 1", "Layer 2"]

    # Mock validation result
    mock.validate.return_value = True
    mock.validate_file.return_value = True

    return mock


# Test factory functions for dependency injection
# These provide sensible defaults for testing while maintaining explicit dependencies in production


def create_layout_service_for_tests(
    file_adapter=None,
    template_adapter=None,
    behavior_registry=None,
    component_service=None,
    layout_service=None,
    behavior_formatter=None,
    dtsi_generator=None,
) -> "LayoutService":
    """Create a LayoutService with test-friendly defaults.

    This is a test-specific factory that provides sensible defaults for all dependencies.
    Production code should use create_layout_service() with explicit dependencies.
    """
    from glovebox.adapters import create_file_adapter, create_template_adapter
    from glovebox.layout import (
        create_behavior_registry,
        create_grid_layout_formatter,
        create_layout_component_service,
        create_layout_display_service,
        create_layout_service,
    )
    from glovebox.layout.behavior.formatter import BehaviorFormatterImpl
    from glovebox.layout.zmk_generator import ZmkFileContentGenerator

    # Create defaults if not provided
    if file_adapter is None:
        file_adapter = create_file_adapter()
    if template_adapter is None:
        template_adapter = create_template_adapter()
    if behavior_registry is None:
        behavior_registry = create_behavior_registry()
    if behavior_formatter is None:
        behavior_formatter = BehaviorFormatterImpl(behavior_registry)
    if dtsi_generator is None:
        dtsi_generator = ZmkFileContentGenerator(behavior_formatter)
    if layout_service is None:
        layout_generator = create_grid_layout_formatter()
        layout_service = create_layout_display_service(layout_generator)
    if component_service is None:
        component_service = create_layout_component_service(file_adapter)

    return create_layout_service(
        file_adapter=file_adapter,
        template_adapter=template_adapter,
        behavior_registry=behavior_registry,
        component_service=component_service,
        layout_service=layout_service,
        behavior_formatter=behavior_formatter,
        dtsi_generator=dtsi_generator,
    )


def create_layout_component_service_for_tests(
    file_adapter=None,
) -> "LayoutComponentService":
    """Create a LayoutComponentService with test-friendly defaults."""
    from glovebox.adapters import create_file_adapter
    from glovebox.layout import create_layout_component_service

    if file_adapter is None:
        file_adapter = create_file_adapter()

    return create_layout_component_service(file_adapter)


def create_layout_display_service_for_tests(
    layout_generator=None,
) -> "LayoutDisplayService":
    """Create a LayoutDisplayService with test-friendly defaults."""
    from glovebox.layout import (
        create_grid_layout_formatter,
        create_layout_display_service,
    )

    if layout_generator is None:
        layout_generator = create_grid_layout_formatter()

    return create_layout_display_service(layout_generator)


def create_usb_adapter_for_tests(
    flash_operations=None, detector=None
) -> "USBAdapterProtocol":
    """Create a USBAdapter with test-friendly defaults."""
    from glovebox.adapters.usb_adapter import create_usb_adapter
    from glovebox.firmware.flash.device_detector import create_device_detector
    from glovebox.firmware.flash.flash_operations import create_flash_operations
    from glovebox.firmware.flash.os_adapters import create_linux_flash_adapter
    from glovebox.firmware.flash.usb_monitor import MountPointCache, create_usb_monitor

    if flash_operations is None:
        os_adapter = create_linux_flash_adapter()
        flash_operations = create_flash_operations(os_adapter)

    if detector is None:
        mount_cache = MountPointCache()
        usb_monitor = create_usb_monitor()
        detector = create_device_detector(usb_monitor, mount_cache)

    return create_usb_adapter(flash_operations, detector)


def create_flash_service_for_tests(
    file_adapter=None, device_wait_service=None, loglevel="INFO"
) -> "FlashService":
    """Create a FlashService with test-friendly defaults."""
    from glovebox.adapters import create_file_adapter
    from glovebox.firmware.flash import create_device_wait_service, create_flash_service

    if file_adapter is None:
        file_adapter = create_file_adapter()

    if device_wait_service is None:
        device_wait_service = create_device_wait_service()

    return create_flash_service(file_adapter, device_wait_service, loglevel)


def create_usb_flasher_for_tests(usb_adapter=None, file_adapter=None) -> "USBFlasher":
    """Create a USBFlasher with test-friendly defaults."""
    from glovebox.adapters import create_file_adapter
    from glovebox.firmware.flash import create_usb_flasher

    if file_adapter is None:
        file_adapter = create_file_adapter()

    if usb_adapter is None:
        usb_adapter = create_usb_adapter_for_tests()

    return create_usb_flasher(usb_adapter, file_adapter)


def create_device_detector_for_tests(
    usb_monitor=None, mount_cache=None
) -> "DeviceDetector":
    """Create a DeviceDetector with test-friendly defaults."""
    from glovebox.firmware.flash.device_detector import create_device_detector
    from glovebox.firmware.flash.usb_monitor import MountPointCache, create_usb_monitor

    if usb_monitor is None:
        usb_monitor = create_usb_monitor()

    if mount_cache is None:
        mount_cache = MountPointCache()

    return create_device_detector(usb_monitor, mount_cache)


@pytest.fixture(scope="function")
def mock_flash_service() -> Mock:
    """Mock FlashService with common behaviors."""
    mock = Mock()

    # Mock successful flash result
    result = FlashResult(
        success=True,
        devices_flashed=2,
        devices_failed=0,
        device_details=[
            {"name": "Device 1", "status": "success"},
            {"name": "Device 2", "status": "success"},
        ],
    )
    mock.flash.return_value = result
    mock.flash_from_file.return_value = result

    return mock


# ---- Sample Data Fixtures ----


@pytest.fixture
def sample_keymap_json() -> dict[str, Any]:
    """Sample keymap JSON data for testing.

    This is the consolidated fixture used by all tests.
    """
    return {
        "keyboard": "test_keyboard",
        "firmware_api_version": "1",
        "locale": "en-US",
        "uuid": "test-uuid",
        "date": "2025-01-01T00:00:00",
        "creator": "test",
        "title": "Test Keymap",
        "notes": "Test keymap for unit tests",
        "tags": ["test", "unit"],
        "layers": [[{"value": "&kp", "params": [{"value": "Q"}]} for _ in range(80)]],
        "layer_names": ["DEFAULT"],
        "custom_defined_behaviors": "",
        "custom_devicetree": "",
        "config_parameters": [
            {
                "paramName": "CONFIG_ZMK_KEYBOARD_NAME",
                "value": "Test Keyboard",
                "description": "Keyboard name",
            }
        ],
        "macros": [],
        "combos": [],
        "hold_taps": [],
        "input_listeners": [],
    }


@pytest.fixture
def sample_keymap_json_file(tmp_path: Path) -> Path:
    """Create a sample keymap JSON file."""
    keymap_data = {
        "version": 1,
        "notes": "Test keymap",
        "keyboard": "glove80",
        "title": "Test Keymap",
        "layer_names": ["QWERTY"],
        "layers": [
            {
                "name": "QWERTY",
                "layout": [
                    {"key": "Q"},
                    {"key": "W"},
                    {"key": "E"},
                    {"key": "R"},
                    {"key": "T"},
                    {"key": "Y"},
                    {"key": "U"},
                    {"key": "I"},
                    {"key": "O"},
                    {"key": "P"},
                ],
            }
        ],
    }

    keymap_file = tmp_path / "test_keymap.json"
    keymap_file.write_text(json.dumps(keymap_data))

    return keymap_file


@pytest.fixture
def sample_keymap_dtsi(tmp_path: Path) -> Path:
    """Create a sample keymap dtsi file."""
    content = """
    / {
        keymap {
            compatible = "zmk,keymap";
            qwerty_layer {
                bindings = <
                    &kp Q &kp W &kp E &kp R &kp T
                    &kp Y &kp U &kp I &kp O &kp P
                >;
            };
        };
    };
    """

    keymap_file = tmp_path / "test_keymap.keymap"
    keymap_file.write_text(content)

    return keymap_file


@pytest.fixture
def sample_config_file(tmp_path: Path) -> Path:
    """Create a sample config file."""
    content = """
    CONFIG_ZMK_KEYBOARD_NAME="Test Keyboard"
    CONFIG_BT_CTLR_TX_PWR_PLUS_8=y
    """

    config_file = tmp_path / "test_config.conf"
    config_file.write_text(content)

    return config_file


@pytest.fixture
def sample_firmware_file(tmp_path: Path) -> Path:
    """Create a sample firmware file."""
    content = "FIRMWARE_BINARY_DATA"

    firmware_file = tmp_path / "test_firmware.uf2"
    firmware_file.write_text(content)

    return firmware_file
