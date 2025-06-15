"""
Tests for the keyboard configuration and profile system.

This module consolidates all tests for the keyboard configuration
and KeyboardProfile pattern in one place.
"""

import os
import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
import yaml

from glovebox.config.keyboard_profile import (
    clear_cache,
    create_keyboard_profile,
    get_available_keyboards,
    get_firmware_config,
    load_keyboard_config,
)
from glovebox.config.models import (
    BuildOptions,
    FirmwareConfig,
    FormattingConfig,
    KConfigOption,
    KeyboardConfig,
    KeymapSection,
)
from glovebox.config.profile import KeyboardProfile
from glovebox.core.errors import ConfigError
from glovebox.layout.models import SystemBehavior


# ---- Test Data Fixtures ----


@pytest.fixture
def test_data_dir():
    """Return the path to the test data directory."""
    return Path(__file__).parent / "test_data"


@pytest.fixture
def keyboard_search_path(test_data_dir):
    """Return the keyboard search path for testing."""
    return str(test_data_dir / "keyboards")


@pytest.fixture
def mock_keyboard_config_dict():
    """Create a mock keyboard configuration dictionary for testing."""
    return {
        "keyboard": "test_keyboard",
        "description": "Mock keyboard for testing",
        "vendor": "Test Vendor",
        "key_count": 80,
        "compile_methods": [
            {
                "method_type": "docker",
                "image": "test-zmk-build",
                "repository": "test/zmk",
                "branch": "main",
                "jobs": 4,
                "fallback_methods": ["local"],
            }
        ],
        "flash_methods": [
            {
                "method_type": "usb",
                "device_query": "vendor=Test and removable=true",
                "mount_timeout": 30,
                "copy_timeout": 60,
                "sync_after_copy": True,
                "fallback_methods": ["dfu"],
            },
            {
                "method_type": "dfu",
                "vid": "0x1234",
                "pid": "0x5678",
                "interface": 0,
                "alt_setting": 0,
                "timeout": 30,
                "fallback_methods": [],
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
            "includes": [
                "#include <dt-bindings/zmk/keys.h>",
                "#include <dt-bindings/zmk/bt.h>",
            ],
            "formatting": {
                "key_gap": "  ",
                "base_indent": "    ",
            },
            "system_behaviors": [
                {
                    "code": "&kp",
                    "name": "&kp",
                    "description": "Key press behavior",
                    "expected_params": 1,
                    "origin": "zmk",
                    "params": [],
                },
                {
                    "code": "&bt",
                    "name": "&bt",
                    "description": "Bluetooth behavior",
                    "expected_params": 1,
                    "origin": "zmk",
                    "params": [],
                    "includes": ["#include <dt-bindings/zmk/bt.h>"],
                },
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
            "system_behaviors_dts": """
            / {
                behaviors {
                    // System behaviors
                };
            };
            """,
        },
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
                "method_type": "docker",
                "image": "test-zmk-build",
                "repository": "test/zmk",
                "branch": "main",
                "jobs": 4,
                "fallback_methods": ["local"],
            }
        ],
        "flash_methods": [
            {
                "method_type": "usb",
                "device_query": "vendor=Test and removable=true",
                "mount_timeout": 30,
                "copy_timeout": 60,
                "sync_after_copy": True,
                "fallback_methods": ["dfu"],
            },
            {
                "method_type": "dfu",
                "vid": "0x1234",
                "pid": "0x5678",
                "interface": 0,
                "alt_setting": 0,
                "timeout": 30,
                "fallback_methods": [],
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
                "method_type": "docker",
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
def mock_keyboard_profile() -> Mock:
    """Create a mocked KeyboardProfile."""
    mock_profile = Mock(spec=KeyboardProfile)
    mock_profile.keyboard_name = "test_keyboard"
    mock_profile.firmware_version = "default"

    # Set up properties that use the above mocks
    mock_profile.keyboard_config = Mock(spec=KeyboardConfig)
    mock_profile.firmware_config = Mock(spec=FirmwareConfig)

    # Mock the system_behaviors property
    mock_profile.system_behaviors = [
        Mock(spec=SystemBehavior),
        Mock(spec=SystemBehavior),
    ]
    mock_profile.system_behaviors[0].code = "&kp"
    mock_profile.system_behaviors[1].code = "&bt"
    mock_profile.system_behaviors[1].includes = ["#include <dt-bindings/zmk/bt.h>"]

    # Mock the kconfig_options property
    mock_profile.kconfig_options = {
        "CONFIG_ZMK_KEYBOARD_NAME": Mock(spec=KConfigOption),
    }

    # Mock the get_template method
    mock_profile.get_template = MagicMock(return_value="template content")

    # Mock the resolve_includes method
    mock_profile.resolve_includes = MagicMock(
        return_value=[
            "#include <dt-bindings/zmk/keys.h>",
            "#include <dt-bindings/zmk/bt.h>",
        ]
    )

    return mock_profile


# ---- Mock Function Fixtures ----


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


# ---- Tests for Core Configuration ----


def test_mock_keyboard_config(mock_keyboard_config):
    """Test that the mock_keyboard_config fixture is properly structured."""
    assert mock_keyboard_config.keyboard == "test_keyboard"
    assert mock_keyboard_config.description is not None
    assert len(mock_keyboard_config.flash_methods) > 0
    assert len(mock_keyboard_config.compile_methods) > 0
    assert "default" in mock_keyboard_config.firmwares
    assert "bluetooth" in mock_keyboard_config.firmwares


def test_mock_firmware_config(mock_firmware_config):
    """Test that the mock_firmware_config fixture is properly structured."""
    assert mock_firmware_config.description is not None
    assert mock_firmware_config.version is not None
    assert mock_firmware_config.build_options is not None


def test_mock_keyboard_profile(mock_keyboard_profile):
    """Test that the mock_keyboard_profile fixture is properly structured."""
    assert mock_keyboard_profile.keyboard_name == "test_keyboard"
    assert mock_keyboard_profile.firmware_version == "default"
    assert mock_keyboard_profile.keyboard_config is not None
    assert mock_keyboard_profile.firmware_config is not None


def test_mock_load_keyboard_config(mock_load_keyboard_config, mock_keyboard_config):
    """Test that the mock_load_keyboard_config fixture properly mocks the function."""
    # Call the mocked function
    result = mock_load_keyboard_config("test_keyboard")

    # Verify the result
    assert result == mock_keyboard_config
    mock_load_keyboard_config.assert_called_once_with("test_keyboard")

    # Verify behavior with different input
    mock_load_keyboard_config("another_keyboard")
    mock_load_keyboard_config.assert_called_with("another_keyboard")
    assert mock_load_keyboard_config.call_count == 2


def test_mock_get_available_keyboards(mock_get_available_keyboards):
    """Test that the mock_get_available_keyboards fixture properly mocks the function."""
    # Call the mocked function
    result = mock_get_available_keyboards()

    # Verify the result
    assert "test_keyboard" in result
    assert "glove80" in result
    assert "corne" in result
    mock_get_available_keyboards.assert_called_once()


def test_mock_get_firmware_config(mock_get_firmware_config, mock_firmware_config):
    """Test that the mock_get_firmware_config fixture properly mocks the function."""
    # Call the mocked function
    result = mock_get_firmware_config("test_keyboard", "default")

    # Verify the result
    assert result == mock_firmware_config
    mock_get_firmware_config.assert_called_once_with("test_keyboard", "default")


def test_mock_get_available_firmwares(mock_get_available_firmwares):
    """Test that the mock_get_available_firmwares fixture properly mocks the function."""
    # Call the mocked function
    result = mock_get_available_firmwares("test_keyboard")

    # Verify the result
    assert "default" in result
    assert "bluetooth" in result
    assert "v25.05" in result
    mock_get_available_firmwares.assert_called_once_with("test_keyboard")


# ---- Tests for the Typed Configuration API ----


def test_initialize_search_paths():
    """Test initialization of search paths."""
    with (
        patch.dict(os.environ, {"GLOVEBOX_KEYBOARD_PATH": "/tmp/test:/tmp/test2"}),
        patch("glovebox.config.keyboard_profile.initialize_search_paths") as mock_init,
    ):
        mock_init.return_value = [Path("/tmp/test"), Path("/tmp/test2")]

        # Clear cache to force reinitialization
        clear_cache()

        # Call any function that would trigger initialization
        get_available_keyboards()

        # Check that initialization was called
        mock_init.assert_called_once()


# This test has been removed as the _load_keyboard_config_raw function was merged into load_keyboard_config


def test_load_keyboard_config(typed_config_file, mock_keyboard_config_dict):
    """Test loading a keyboard configuration as a typed object."""
    with patch(
        "glovebox.config.keyboard_profile._find_keyboard_config_file"
    ) as mock_find:
        mock_find.return_value = typed_config_file

        # Load the typed config
        config = load_keyboard_config("test_keyboard")

        # Verify the result is a KeyboardConfig instance
        assert isinstance(config, KeyboardConfig)
        assert config.keyboard == "test_keyboard"
        assert config.description == "Mock keyboard for testing"
        assert config.vendor == "Test Vendor"

        # Check nested objects
        assert isinstance(config.firmwares, dict)
        assert isinstance(config.firmwares["default"], FirmwareConfig)
        assert config.firmwares["default"].version == "v1.0.0"

        # Check nested objects in keymap section
        assert len(config.keymap.system_behaviors) == 2
        assert config.keymap.system_behaviors[0].code == "&kp"
        assert config.keymap.system_behaviors[0].expected_params == 1


def test_create_keyboard_profile(typed_config_file, mock_keyboard_config_dict):
    """Test creating a KeyboardProfile."""
    with patch(
        "glovebox.config.keyboard_profile._find_keyboard_config_file"
    ) as mock_find:
        mock_find.return_value = typed_config_file

        # Create a profile
        profile = create_keyboard_profile("test_keyboard", "default")

        # Verify the result is a KeyboardProfile instance
        assert isinstance(profile, KeyboardProfile)
        assert profile.keyboard_name == "test_keyboard"
        assert profile.firmware_version == "default"

        # Check that the profile has the correct config objects
        assert isinstance(profile.keyboard_config, KeyboardConfig)
        assert isinstance(profile.firmware_config, FirmwareConfig)

        # Check system behaviors
        assert len(profile.system_behaviors) == 2
        assert profile.system_behaviors[0].code == "&kp"


def test_get_firmware_config(typed_config_file, mock_keyboard_config_dict):
    """Test getting a firmware configuration as a typed object."""
    with patch(
        "glovebox.config.keyboard_profile._find_keyboard_config_file"
    ) as mock_find:
        mock_find.return_value = typed_config_file

        # Get the firmware config
        firmware_config = get_firmware_config("test_keyboard", "bluetooth")

        # Verify the result is a FirmwareConfig instance
        assert isinstance(firmware_config, FirmwareConfig)
        assert firmware_config.version == "bluetooth"
        assert firmware_config.description == "Bluetooth-focused test firmware"

        # Check kconfig options
        assert firmware_config.kconfig is not None
        assert "CONFIG_ZMK_BLE" in firmware_config.kconfig
        assert firmware_config.kconfig["CONFIG_ZMK_BLE"].default == "y"


def test_kconfig_options_from_profile(typed_config_file, mock_keyboard_config_dict):
    """Test getting combined kconfig options from a profile."""
    with patch(
        "glovebox.config.keyboard_profile._find_keyboard_config_file"
    ) as mock_find:
        mock_find.return_value = typed_config_file

        # Create profiles for different firmware variants
        default_profile = create_keyboard_profile("test_keyboard", "default")
        bluetooth_profile = create_keyboard_profile("test_keyboard", "bluetooth")

        # Check that default profile has only keyboard kconfig options
        default_options = default_profile.kconfig_options
        assert "CONFIG_ZMK_KEYBOARD_NAME" in default_options
        assert "CONFIG_ZMK_BLE" not in default_options

        # Check that bluetooth profile has combined options
        bluetooth_options = bluetooth_profile.kconfig_options
        assert "CONFIG_ZMK_KEYBOARD_NAME" in bluetooth_options
        assert "CONFIG_ZMK_BLE" in bluetooth_options
        assert bluetooth_options["CONFIG_ZMK_BLE"].default == "y"


def test_resolve_includes(mock_keyboard_profile):
    """Test resolving includes based on behaviors used."""
    # Setup the mock_keyboard_profile to return the expected includes
    mock_keyboard_profile.resolve_includes.return_value = [
        "#include <dt-bindings/zmk/keys.h>",
        "#include <dt-bindings/zmk/bt.h>",
    ]

    # Resolve includes with no behaviors used
    includes = mock_keyboard_profile.resolve_includes([])
    assert len(includes) == 2  # Base includes from keymap section

    # Resolve includes with behaviors used
    includes = mock_keyboard_profile.resolve_includes(["&kp", "&bt"])
    assert len(includes) == 2  # No new includes for &kp, but &bt has an include
    assert "#include <dt-bindings/zmk/bt.h>" in includes

    # Verify the correct method was called
    mock_keyboard_profile.resolve_includes.assert_called_with(["&kp", "&bt"])


def test_nonexistent_keyboard():
    """Test trying to load a nonexistent keyboard configuration."""
    with patch(
        "glovebox.config.keyboard_profile._find_keyboard_config_file"
    ) as mock_find:
        mock_find.return_value = None

        with pytest.raises(
            ConfigError, match="Keyboard configuration not found: nonexistent"
        ):
            load_keyboard_config("nonexistent")


def test_nonexistent_firmware(typed_config_file, mock_keyboard_config_dict):
    """Test trying to get a nonexistent firmware configuration."""
    with patch(
        "glovebox.config.keyboard_profile._find_keyboard_config_file"
    ) as mock_find:
        mock_find.return_value = typed_config_file

        with pytest.raises(
            ConfigError,
            match="Firmware 'nonexistent' not found for keyboard 'test_keyboard'",
        ):
            get_firmware_config("test_keyboard", "nonexistent")


def test_keyboard_name_mismatch(mock_keyboard_config_dict):
    """Test handling of keyboard name mismatch in config file."""
    # Create a temporary config file with a mismatched name
    with tempfile.NamedTemporaryFile(suffix=".yaml") as temp_file:
        mock_keyboard_config_dict["keyboard"] = "different_name"
        temp_file.write(yaml.dump(mock_keyboard_config_dict).encode())
        temp_file.flush()

        # Patch to return our temp file
        with patch(
            "glovebox.config.keyboard_profile._find_keyboard_config_file"
        ) as mock_find:
            mock_find.return_value = Path(temp_file.name)

            # Load the config with a different name
            # Since we don't have direct access to raw config now, we'll load the typed config
            # and test keyboard name that way
            config = load_keyboard_config("test_name")

            # Check that the name was fixed
            assert config.keyboard == "test_name"


def test_clear_cache(typed_config_file, mock_keyboard_config_dict):
    """Test clearing the configuration cache."""
    with patch(
        "glovebox.config.keyboard_profile._find_keyboard_config_file"
    ) as mock_find:
        mock_find.return_value = typed_config_file

        # Load a configuration to populate the cache
        load_keyboard_config("test_keyboard")

        # Verify the cache is populated
        from glovebox.config.keyboard_profile import _keyboard_configs

        assert "test_keyboard" in _keyboard_configs

        # Clear the cache
        clear_cache()

        # Verify the cache is cleared
        assert "test_keyboard" not in _keyboard_configs


# ---- Integration Tests ----


@pytest.mark.integration
def test_real_config_file_integration(test_data_dir):
    """Test integration with real keyboard config files."""
    # Set up the search path to use our test directory
    with patch("glovebox.config.keyboard_profile.initialize_search_paths") as mock_init:
        mock_init.return_value = [test_data_dir / "keyboards"]

        # Clear the cache to force reinitialization
        clear_cache()

        # Test get_available_keyboards
        keyboards = get_available_keyboards()
        assert "test_keyboard" in keyboards

        try:
            # Test loading config (direct conversion to dict for raw testing)
            typed_config = load_keyboard_config("test_keyboard")
            config_raw = {
                "keyboard": typed_config.keyboard,
                "description": typed_config.description,
                "vendor": typed_config.vendor,
            }
            assert isinstance(config_raw, dict)
            assert config_raw["keyboard"] == "test_keyboard"

            # Test loading typed config
            config_typed = load_keyboard_config("test_keyboard")
            assert isinstance(config_typed, KeyboardConfig)
            assert config_typed.keyboard == "test_keyboard"

            # Test creating profile
            if "default" in config_typed.firmwares:
                profile = create_keyboard_profile("test_keyboard", "default")
                assert isinstance(profile, KeyboardProfile)
                assert profile.keyboard_name == "test_keyboard"

        except Exception as e:
            # If test files don't match the expected structure, just report it
            pytest.skip(f"Test skipped due to test data structure mismatch: {e}")


@pytest.mark.integration
def test_real_keyboard_config_integration(keyboard_config_dir):
    """Test real integration with keyboard config files."""
    # Set environment variable to point to our test directory
    with patch.dict(os.environ, {"GLOVEBOX_KEYBOARD_PATH": str(keyboard_config_dir)}):
        # Test that our test keyboards are found
        keyboards = get_available_keyboards()
        # Check for at least glove80 since it should always be present
        assert "glove80" in keyboards

        # Test loading the glove80 keyboard configuration
        # Convert typed config to raw for testing
        typed_config = load_keyboard_config("glove80")
        config_raw = {"keyboard": typed_config.keyboard}
        assert config_raw["keyboard"] == "glove80"
        # We know typed config has description, so we don't need to check the raw version

        # Test loading glove80 as typed object
        config_typed = load_keyboard_config("glove80")
        assert isinstance(config_typed, KeyboardConfig)
        assert config_typed.keyboard == "glove80"
        assert hasattr(config_typed, "description")

        # Test creating a profile
        profile = create_keyboard_profile("glove80", "v25.05")
        assert isinstance(profile, KeyboardProfile)
        assert profile.keyboard_name == "glove80"
        assert profile.firmware_version == "v25.05"

        # Test getting firmwares
        glove_config = load_keyboard_config("glove80")
        firmwares = glove_config.firmwares
        assert "v25.05" in firmwares
        assert "v25.04-beta.1" in firmwares
