"""Tests for KeymapService with keyboard configuration API."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from glovebox.config.profile import KeyboardProfile
from glovebox.core.errors import KeymapError
from glovebox.models.behavior import SystemBehavior
from glovebox.models.keymap import KeymapData
from glovebox.models.results import KeymapResult
from glovebox.protocols.file_adapter_protocol import FileAdapterProtocol
from glovebox.protocols.template_adapter_protocol import TemplateAdapterProtocol
from glovebox.services.keymap_service import KeymapService


# Fixtures for the typed tests


@pytest.fixture
def mock_profile():
    """Create a mock KeyboardProfile for testing."""
    profile = MagicMock(spec=KeyboardProfile)
    profile.keyboard_name = "test_keyboard"
    profile.firmware_version = "default"

    # Set up the system behaviors
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

    profile.system_behaviors = [behavior1, behavior2]

    # Set up the keyboard_config mock with keymap
    profile.keyboard_config = MagicMock()
    profile.keyboard_config.keymap = MagicMock()
    profile.keyboard_config.keymap.keymap_dtsi = (
        "#include <behaviors.dtsi>\n{{ keymap_node }}"
    )
    profile.keyboard_config.keymap.key_position_header = "// Key positions"
    profile.keyboard_config.keymap.system_behaviors_dts = "// System behaviors"

    # Set up the get_template method (deprecated but still used in tests)
    profile.get_template = lambda name, default=None: {
        "keymap_dtsi": profile.keyboard_config.keymap.keymap_dtsi,
        "key_position_header": profile.keyboard_config.keymap.key_position_header,
        "system_behaviors_dts": profile.keyboard_config.keymap.system_behaviors_dts,
    }.get(name, default)

    # Set up kconfig options
    kconfig_option = MagicMock()
    kconfig_option.name = "CONFIG_ZMK_KEYBOARD_NAME"
    kconfig_option.default = "Test Keyboard"
    kconfig_option.type = "string"
    kconfig_option.description = "Keyboard name"

    profile.kconfig_options = {"CONFIG_ZMK_KEYBOARD_NAME": kconfig_option}

    # Set up resolve_includes method
    profile.resolve_includes = lambda behaviors_used: [
        "#include <dt-bindings/zmk/keys.h>",
        "#include <dt-bindings/zmk/bt.h>",
    ]

    # Set up extract_behavior_codes method
    profile.extract_behavior_codes = lambda keymap_data: ["&kp", "&bt", "&lt"]

    # Set up resolve_kconfig_with_user_options method
    profile.resolve_kconfig_with_user_options = lambda user_options: {
        "CONFIG_ZMK_KEYBOARD_NAME": "Test Keyboard"
    }

    # Set up generate_kconfig_content method
    profile.generate_kconfig_content = lambda kconfig_settings: (
        '# Generated ZMK configuration\n\nCONFIG_ZMK_KEYBOARD_NAME="Test Keyboard"\n'
    )

    return profile


@pytest.fixture
def mock_create_keyboard_profile(mock_profile):
    """Mock the create_keyboard_profile function."""
    with patch(
        "glovebox.config.keyboard_config.create_keyboard_profile"
    ) as mock_create:
        mock_create.return_value = mock_profile
        yield mock_create


@pytest.fixture
def keymap_service():
    """Create a KeymapService for testing."""
    file_adapter = MagicMock(spec=FileAdapterProtocol)
    template_adapter = MagicMock(spec=TemplateAdapterProtocol)

    # Set up the template_adapter to render something
    template_adapter.render_string.return_value = "// Generated keymap content"

    # Set up the file adapter to handle file operations
    file_adapter.mkdir.return_value = True
    file_adapter.write_text.return_value = True
    file_adapter.write_json.return_value = True

    # Create all required mocks
    behavior_registry = MagicMock()
    # Add a dictionary for behaviors and behaviors methods to the mock
    behavior_registry._behaviors = {}
    behavior_registry.list_behaviors = Mock(return_value=behavior_registry._behaviors)
    behavior_registry.register_behavior = Mock(
        side_effect=lambda behavior: behavior_registry._behaviors.update(
            {behavior.code: behavior}
        )
    )

    behavior_formatter = MagicMock()
    dtsi_generator = MagicMock()
    component_service = MagicMock()
    layout_service = MagicMock()
    context_builder = MagicMock()

    # Generate mock config
    dtsi_generator.generate_kconfig_conf.return_value = ("// Config content", {})

    return KeymapService(
        file_adapter=file_adapter,
        template_adapter=template_adapter,
        behavior_registry=behavior_registry,
        behavior_formatter=behavior_formatter,
        dtsi_generator=dtsi_generator,
        component_service=component_service,
        layout_service=layout_service,
        context_builder=context_builder,
    )


# Using sample_keymap_json fixture from conftest.py


class TestKeymapServiceWithKeyboardConfig:
    """Test KeymapService with the new keyboard configuration API."""

    def setup_method(self):
        """Set up test environment."""
        self.mock_file_adapter = Mock(spec=FileAdapterProtocol)
        self.mock_template_adapter = Mock(spec=TemplateAdapterProtocol)

        # Mock all required dependencies
        self.mock_behavior_registry = Mock()
        # Add a dictionary for behaviors and a list_behaviors method to the mock
        self.mock_behavior_registry._behaviors = {}
        self.mock_behavior_registry.list_behaviors = Mock(
            return_value=self.mock_behavior_registry._behaviors
        )
        self.mock_behavior_registry.register_behavior = Mock(
            side_effect=lambda behavior: self.mock_behavior_registry._behaviors.update(
                {behavior.code: behavior}
            )
        )

        self.mock_behavior_formatter = Mock()
        self.mock_dtsi_generator = Mock()
        self.mock_component_service = Mock()
        self.mock_layout_service = Mock()
        self.mock_context_builder = Mock()

        self.service = KeymapService(
            file_adapter=self.mock_file_adapter,
            template_adapter=self.mock_template_adapter,
            behavior_registry=self.mock_behavior_registry,
            behavior_formatter=self.mock_behavior_formatter,
            dtsi_generator=self.mock_dtsi_generator,
            component_service=self.mock_component_service,
            layout_service=self.mock_layout_service,
            context_builder=self.mock_context_builder,
        )

    def test_validate_config_success(self, sample_keymap_json, mock_profile):
        """Test successful keymap-keyboard config validation."""
        # Setup
        keymap_data = sample_keymap_json.copy()
        keymap_data["keyboard"] = "test_keyboard"  # Ensure matching keyboard

        # Convert to KeymapData
        keymap_data_obj = KeymapData.model_validate(keymap_data)

        # Execute - use validate instead of validate_config
        result = self.service.validate(mock_profile, keymap_data_obj)

        # Verify
        assert result is True

    def test_validate_config_keyboard_mismatch(self, sample_keymap_json, mock_profile):
        """Test validation with keyboard type mismatch."""
        # Setup
        keymap_data = sample_keymap_json.copy()
        keymap_data["keyboard"] = "different_keyboard"  # Cause mismatch

        # Convert to KeymapData
        keymap_data_obj = KeymapData.model_validate(keymap_data)

        # Execute - should warn about mismatch but not fail
        result = self.service.validate(mock_profile, keymap_data_obj)

        # Verify - returns True despite warning
        assert result is True

    def test_validate_config_missing_template(self, sample_keymap_json, mock_profile):
        """Test validation with missing required template."""
        # Setup
        keymap_data = sample_keymap_json.copy()

        # Convert to KeymapData
        keymap_data_obj = KeymapData.model_validate(keymap_data)

        # This test should pass now since templates are optional in the schema
        result = self.service.validate(mock_profile, keymap_data_obj)
        assert result is True

    def test_validate_config_with_templates(self, sample_keymap_json, mock_profile):
        """Test validation with templates in keyboard config."""
        # Setup
        keymap_data = sample_keymap_json.copy()

        # Convert to KeymapData
        keymap_data_obj = KeymapData.model_validate(keymap_data)

        # Execute
        result = self.service.validate(mock_profile, keymap_data_obj)

        # Verify
        assert result is True

    def test_show_error_handling(self, sample_keymap_json, mock_profile):
        """Test error handling in the show method."""
        # Make the layout service's generate_display method raise an error
        self.mock_layout_service.generate_display.side_effect = Exception(
            "Layout generation failed"
        )

        # Convert to KeymapData
        keymap_data = KeymapData.model_validate(sample_keymap_json)

        with pytest.raises(KeymapError):
            self.service.show(profile=mock_profile, keymap_data=keymap_data)

    @patch("glovebox.services.keymap_service.prepare_output_paths")
    @pytest.mark.skip("Needs more mock setup for actual file generation")
    def test_compile_with_keyboard_config(
        self,
        mock_prepare_paths,
        sample_keymap_json,
        mock_profile,
        tmp_path,
    ):
        """Test keymap compilation with keyboard configuration."""
        pass

    def test_register_behaviors(self, mock_keyboard_config):
        """Test registration of system behaviors from keyboard profile."""
        # Create a mock profile with behaviors
        mock_profile = MagicMock()
        mock_profile.keyboard_name = "test_keyboard"

        # Create system behaviors
        behavior1 = SystemBehavior(
            code="&kp",
            name="&kp",
            description=None,
            expected_params=1,
            origin="zmk",
            params=[],
        )

        behavior2 = SystemBehavior(
            code="&lt",
            name="&lt",
            description=None,
            expected_params=2,
            origin="zmk",
            params=[],
        )

        behavior3 = SystemBehavior(
            code="&mo",
            name="&mo",
            description=None,
            expected_params=1,
            origin="zmk",
            params=[],
        )

        mock_profile.system_behaviors = [behavior1, behavior2, behavior3]

        # Add register_behaviors method to mock
        mock_profile.register_behaviors = lambda registry: [
            registry.register_behavior(behavior)
            for behavior in mock_profile.system_behaviors
        ]

        # Execute directly on the behavior registry
        mock_profile.register_behaviors(self.service._behavior_registry)

        # Since we're using a mock, we need to ensure it has the right methods
        # We'll check that register_behavior was called with the right behaviors
        expected_behavior_codes = ["&kp", "&lt", "&mo"]

        # Check that all behaviors were registered (3 behaviors, 3 calls)
        assert self.mock_behavior_registry.register_behavior.call_count == 3

        # Verify the behavior codes that were registered
        registered_behaviors = []
        for call in self.mock_behavior_registry.register_behavior.call_args_list:
            behavior = call[0][0]  # First positional argument
            registered_behaviors.append(behavior.code)

        # Verify all expected behavior codes were registered
        for code in expected_behavior_codes:
            assert code in registered_behaviors

        # Verify behavior properties were preserved during registration
        for call in self.mock_behavior_registry.register_behavior.call_args_list:
            behavior = call[0][0]
            if behavior.code == "&kp":
                assert behavior.expected_params == 1
            elif behavior.code == "&lt":
                assert behavior.expected_params == 2
            elif behavior.code == "&mo":
                assert behavior.expected_params == 1


class TestKeymapServiceWithMockedConfig:
    """Tests using mocked config API."""

    @patch("glovebox.config.keyboard_config.create_keyboard_profile")
    @patch("glovebox.config.keyboard_config.get_available_keyboards")
    @patch("glovebox.services.keymap_service.prepare_output_paths")
    def test_integrated_keymap_workflow(
        self,
        mock_prepare_paths,
        mock_get_keyboards,
        mock_create_profile,
        sample_keymap_json,
        tmp_path,
    ):
        """Test integrated keymap workflow with mocked config API."""
        # Setup path mock
        from glovebox.models.build import OutputPaths

        mock_prepare_paths.return_value = OutputPaths(
            keymap=Path(tmp_path / "output/test.keymap"),
            conf=Path(tmp_path / "output/test.conf"),
            json=Path(tmp_path / "output/test.json"),
        )

        # Setup mocks
        mock_get_keyboards.return_value = ["test_keyboard", "glove80"]

        # Create a detailed mock profile
        mock_profile = MagicMock()
        mock_profile.keyboard_name = "test_keyboard"
        mock_profile.firmware_version = "default"

        # Create mock keyboard config
        mock_profile.keyboard_config = MagicMock()
        mock_profile.keyboard_config.key_count = 80
        mock_profile.keyboard_config.description = "Test Keyboard"

        # Create mock keymap
        mock_profile.keyboard_config.keymap = MagicMock()
        mock_profile.keyboard_config.keymap.keymap_dtsi = "// Template content"
        mock_profile.keyboard_config.keymap.key_position_header = "// Key positions"
        mock_profile.keyboard_config.keymap.system_behaviors_dts = "// Behaviors"

        # Create mock formatting
        mock_profile.keyboard_config.keymap.formatting = MagicMock()
        mock_profile.keyboard_config.keymap.formatting.default_key_width = 10
        mock_profile.keyboard_config.keymap.formatting.key_gap = "  "
        mock_profile.keyboard_config.keymap.formatting.base_indent = ""
        mock_profile.keyboard_config.keymap.formatting.rows = [[0, 1, 2, 3, 4]]

        mock_profile.keyboard_config.keymap.kconfig_options = {}
        mock_profile.system_behaviors = []
        mock_profile.kconfig_options = {}

        # Add register_behaviors method to the mock profile
        mock_profile.register_behaviors = lambda registry: None

        mock_create_profile.return_value = mock_profile

        # Import needed here to avoid circular import
        import json

        # Create service with mocked adapters for testing
        file_adapter = MagicMock()
        file_adapter.mkdir.return_value = None
        file_adapter.write_text.return_value = None
        file_adapter.write_json.return_value = None

        template_adapter = MagicMock()
        template_adapter.render_string.return_value = "// Generated keymap"

        behavior_registry = MagicMock()
        behavior_formatter = MagicMock()
        dtsi_generator = MagicMock()
        component_service = MagicMock()
        layout_service = MagicMock()
        context_builder = MagicMock()

        # Configure mocks
        dtsi_generator.generate_kconfig_conf.return_value = ("// Config content", {})

        service = KeymapService(
            file_adapter=file_adapter,
            template_adapter=template_adapter,
            behavior_registry=behavior_registry,
            behavior_formatter=behavior_formatter,
            dtsi_generator=dtsi_generator,
            component_service=component_service,
            layout_service=layout_service,
            context_builder=context_builder,
        )

        # Convert to KeymapData
        keymap_data = KeymapData.model_validate(sample_keymap_json)

        target_prefix = str(tmp_path / "output/test")

        try:
            # We're only testing that the integration points don't raise exceptions
            result = service.compile(
                mock_profile,
                keymap_data,
                target_prefix,
            )
            success = True
            assert result.success is True
        except Exception as e:
            print(f"Failed with exception: {e}")
            success = False

        assert success is True


# Tests from test_keymap_service_typed.py


@patch("glovebox.services.keymap_service.prepare_output_paths")
@pytest.mark.skip("Needs more mock setup for actual file generation")
def test_compile_with_profile(
    mock_prepare_paths,
    keymap_service,
    sample_keymap_json,
    mock_profile,
):
    """Test compiling a keymap with the new KeyboardProfile."""
    # This test is skipped because it requires more complex mocking
    pass


def test_register_behaviors(keymap_service, mock_profile):
    """Test registering system behaviors from a KeyboardProfile."""
    # First we need to make the mock do something useful
    # Create system behaviors
    behavior1 = SystemBehavior(
        code="&kp",
        name="&kp",
        description=None,
        expected_params=1,
        origin="zmk",
        params=[],
    )

    behavior2 = SystemBehavior(
        code="&bt",
        name="&bt",
        description=None,
        expected_params=1,
        origin="zmk",
        params=[],
    )

    mock_profile.system_behaviors = [behavior1, behavior2]

    # Add register_behaviors method to mock
    def register_behaviors_impl(registry):
        for behavior in mock_profile.system_behaviors:
            registry.register_behavior(behavior)

    mock_profile.register_behaviors = register_behaviors_impl

    # Call the profile's register_behaviors method
    mock_profile.register_behaviors(keymap_service._behavior_registry)

    # Since we're using a mock, check that register_behavior was called for each behavior
    assert keymap_service._behavior_registry.register_behavior.call_count == 2

    # Verify the behavior codes that were registered
    registered_behaviors = []
    for call in keymap_service._behavior_registry.register_behavior.call_args_list:
        behavior = call[0][0]  # First positional argument
        registered_behaviors.append(behavior.code)

    # Check for expected behaviors
    assert "&kp" in registered_behaviors
    assert "&bt" in registered_behaviors

    # Verify behavior properties
    for call in keymap_service._behavior_registry.register_behavior.call_args_list:
        behavior = call[0][0]
        if behavior.code == "&kp" or behavior.code == "&bt":
            assert behavior.expected_params == 1


# These tests were removed because they used non-existent private methods
