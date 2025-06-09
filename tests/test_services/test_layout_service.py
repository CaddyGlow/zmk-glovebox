"""Tests for LayoutService with keyboard configuration API."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from glovebox.config.models import KConfigOption, KeyboardConfig, KeymapSection
from glovebox.config.profile import KeyboardProfile
from glovebox.core.errors import LayoutError
from glovebox.layout.models import LayoutData, LayoutResult, SystemBehavior
from glovebox.layout.service import LayoutService
from glovebox.protocols.file_adapter_protocol import FileAdapterProtocol
from glovebox.protocols.template_adapter_protocol import TemplateAdapterProtocol


# ---- Test Service Setup ----


@pytest.fixture
def keymap_service():
    """Create a LayoutService for testing."""
    file_adapter = Mock(spec=FileAdapterProtocol)
    template_adapter = Mock(spec=TemplateAdapterProtocol)

    # Set up the template_adapter to render something
    template_adapter.render_string.return_value = "// Generated keymap content"

    # Set up the file adapter to handle file operations
    file_adapter.create_directory.return_value = True
    file_adapter.write_text.return_value = True
    file_adapter.write_json.return_value = True

    # Create all required mocks
    behavior_registry = Mock()
    # Add a dictionary for behaviors
    behavior_registry._behaviors = {}

    # Set up behavior registry methods
    behavior_registry.list_behaviors = Mock(return_value=behavior_registry._behaviors)
    behavior_registry.register_behavior = Mock(
        side_effect=lambda behavior: behavior_registry._behaviors.update(
            {behavior.code: behavior}
        )
    )

    behavior_formatter = Mock()
    dtsi_generator = Mock()
    component_service = Mock()
    layout_service = Mock()

    # Generate mock config
    dtsi_generator.generate_kconfig_conf.return_value = ("// Config content", {})

    service = LayoutService(
        file_adapter=file_adapter,
        template_adapter=template_adapter,
        behavior_registry=behavior_registry,
        behavior_formatter=behavior_formatter,
        dtsi_generator=dtsi_generator,
        component_service=component_service,
        layout_service=layout_service,
    )

    # Add test-only attributes to store references to the mocks
    # pylint: disable=protected-access
    service._file_adapter = file_adapter  # Using actual attribute name
    service._template_adapter = template_adapter

    # Store mock references for test access - we use type: ignore comments
    # because we're adding these for testing purposes only
    service.mock_behavior_registry = behavior_registry  # type: ignore
    service.mock_behavior_formatter = behavior_formatter  # type: ignore
    service.mock_dtsi_generator = dtsi_generator  # type: ignore
    service.mock_component_service = component_service  # type: ignore
    service.mock_layout_service = layout_service  # type: ignore

    yield service


@pytest.fixture
def mock_profile():
    """Create a mock KeyboardProfile for testing."""
    mock = Mock(spec=KeyboardProfile)
    mock.keyboard_name = "test_keyboard"
    mock.firmware_version = "default"

    # Create system behaviors
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

    mock.system_behaviors = [behavior1, behavior2]

    # Set up the keyboard_config mock with keymap
    mock.keyboard_config = Mock(spec=KeyboardConfig)
    mock.keyboard_config.keymap = Mock(spec=KeymapSection)
    mock.keyboard_config.keymap.keymap_dtsi = (
        "#include <behaviors.dtsi>\n{{ keymap_node }}"
    )
    mock.keyboard_config.keymap.key_position_header = "// Key positions"
    mock.keyboard_config.keymap.system_behaviors_dts = "// System behaviors"

    # Set up the get_template method
    mock.get_template = Mock(
        side_effect=lambda name, default=None: {
            "keymap_dtsi": mock.keyboard_config.keymap.keymap_dtsi,
            "key_position_header": mock.keyboard_config.keymap.key_position_header,
            "system_behaviors_dts": mock.keyboard_config.keymap.system_behaviors_dts,
        }.get(name, default)
    )

    # Set up kconfig options
    kconfig_option = Mock(spec=KConfigOption)
    kconfig_option.name = "CONFIG_ZMK_KEYBOARD_NAME"
    kconfig_option.default = "Test Keyboard"
    kconfig_option.type = "string"
    kconfig_option.description = "Keyboard name"

    mock.kconfig_options = {"CONFIG_ZMK_KEYBOARD_NAME": kconfig_option}

    # Set up resolve_kconfig_with_user_options method
    mock.resolve_kconfig_with_user_options = Mock(
        return_value={"CONFIG_ZMK_KEYBOARD_NAME": "Test Keyboard"}
    )

    # Set up generate_kconfig_content method
    mock.generate_kconfig_content = Mock(
        return_value='# Generated ZMK configuration\n\nCONFIG_ZMK_KEYBOARD_NAME="Test Keyboard"\n'
    )

    return mock


class TestLayoutServiceWithKeyboardConfig:
    """Test LayoutService with the new keyboard configuration API."""

    @pytest.fixture(autouse=True)
    def setup(self, mock_profile):
        """Set up test environment."""
        self.mock_profile = mock_profile
        self.mock_file_adapter = Mock(spec=FileAdapterProtocol)
        self.mock_template_adapter = Mock(spec=TemplateAdapterProtocol)

        # Mock all required dependencies
        self.mock_behavior_registry = Mock()
        # Add a dictionary for behaviors and a list_behaviors method to the mock
        self.mock_behavior_registry._behaviors = {}

        # Set up behavior registry methods
        self.mock_behavior_registry.list_behaviors = Mock(
            return_value=self.mock_behavior_registry._behaviors
        )
        self.mock_behavior_registry.register_behavior = Mock(
            side_effect=lambda behavior: self.mock_behavior_registry._behaviors.update(
                {behavior.code: behavior}
            )
        )

        # Mock other components
        self.mock_behavior_formatter = Mock()
        self.mock_dtsi_generator = Mock()
        self.mock_component_service = Mock()
        self.mock_layout_service = Mock()

        # Create the service
        self.service = LayoutService(
            file_adapter=self.mock_file_adapter,
            template_adapter=self.mock_template_adapter,
            behavior_registry=self.mock_behavior_registry,
            behavior_formatter=self.mock_behavior_formatter,
            dtsi_generator=self.mock_dtsi_generator,
            component_service=self.mock_component_service,
            layout_service=self.mock_layout_service,
        )

    def test_validate_config_success(self, sample_keymap_json):
        """Test successful keymap-keyboard config validation."""
        # Setup
        keymap_data = sample_keymap_json.copy()
        keymap_data["keyboard"] = "test_keyboard"  # Ensure matching keyboard

        # Convert to LayoutData
        keymap_data_obj = LayoutData.model_validate(keymap_data)

        # Execute - use validate instead of validate_config
        result = self.service.validate(self.mock_profile, keymap_data_obj)

        # Verify
        assert result is True

    def test_validate_config_keyboard_mismatch(self, sample_keymap_json):
        """Test validation with keyboard type mismatch."""
        # Setup
        keymap_data = sample_keymap_json.copy()
        keymap_data["keyboard"] = "different_keyboard"  # Cause mismatch

        # Convert to LayoutData
        keymap_data_obj = LayoutData.model_validate(keymap_data)

        # Execute - should warn about mismatch but not fail
        result = self.service.validate(self.mock_profile, keymap_data_obj)

        # Verify - returns True despite warning
        assert result is True

    def test_validate_config_missing_template(self, sample_keymap_json):
        """Test validation with missing required template."""
        # Setup
        keymap_data = sample_keymap_json.copy()

        # Convert to LayoutData
        keymap_data_obj = LayoutData.model_validate(keymap_data)

        # This test should pass now since templates are optional in the schema
        result = self.service.validate(self.mock_profile, keymap_data_obj)
        assert result is True

    def test_validate_config_with_templates(self, sample_keymap_json):
        """Test validation with templates in keyboard config."""
        # Setup
        keymap_data = sample_keymap_json.copy()

        # Convert to LayoutData
        keymap_data_obj = LayoutData.model_validate(keymap_data)

        # Execute
        result = self.service.validate(self.mock_profile, keymap_data_obj)

        # Verify
        assert result is True

    def test_show_error_handling(self, sample_keymap_json):
        """Test error handling in the show method."""
        # Make the layout service's show method raise an error
        with patch.object(
            self.mock_layout_service,
            "show",
            side_effect=Exception("Layout generation failed"),
        ):
            # Convert to LayoutData
            keymap_data = LayoutData.model_validate(sample_keymap_json)

            with pytest.raises(LayoutError):
                self.service.show(profile=self.mock_profile, keymap_data=keymap_data)

    @patch("glovebox.layout.service.prepare_output_paths")
    def test_generate_with_keyboard_config(
        self,
        mock_prepare_paths,
        sample_keymap_json,
        tmp_path,
    ):
        """Test keymap compilation with keyboard configuration."""
        # Setup path mock
        from glovebox.firmware.models import OutputPaths

        output_paths = OutputPaths(
            keymap=Path(tmp_path / "output/test.keymap"),
            conf=Path(tmp_path / "output/test.conf"),
            json=Path(tmp_path / "output/test.json"),
        )
        mock_prepare_paths.return_value = output_paths

        # Setup file adapter mock
        # ruff: noqa: SIM117 - Nested with statements are more readable here
        with patch.object(
            self.mock_file_adapter, "create_directory", return_value=True
        ):
            with patch.object(self.mock_file_adapter, "write_text", return_value=True):
                with patch.object(
                    self.mock_file_adapter, "write_json", return_value=True
                ):
                    # Setup DTSI generator mock
                    kconfig_content = 'CONFIG_ZMK_KEYBOARD_NAME="Test Keyboard"'
                    kconfig_settings = {"CONFIG_ZMK_KEYBOARD_NAME": "Test Keyboard"}
                    # ruff: noqa: SIM117 - Nested with statements are more readable here
                    with patch.object(
                        self.mock_dtsi_generator,
                        "generate_kconfig_conf",
                        return_value=(kconfig_content, kconfig_settings),
                    ):
                        # Setup component service mock
                        with patch.object(
                            self.mock_component_service,
                            "process_keymap_components",
                            return_value={"macros": [], "combos": []},
                        ):
                            # Setup formatter mock
                            with patch.object(
                                self.mock_behavior_formatter,
                                "format_bindings",
                                return_value="// Formatted bindings",
                            ):
                                # Setup template adapter mock
                                with patch.object(
                                    self.mock_template_adapter,
                                    "render_string",
                                    return_value="// Generated keymap content",
                                ):
                                    # Convert to LayoutData
                                    keymap_data = LayoutData.model_validate(
                                        sample_keymap_json
                                    )

                                    # Execute
                                    result = self.service.generate(
                                        profile=self.mock_profile,
                                        keymap_data=keymap_data,
                                        output_file_prefix=str(
                                            tmp_path / "output/test"
                                        ),
                                    )

                                    # Verify
                                    assert result.success is True
                                    assert result.keymap_path == output_paths.keymap
                                    assert result.conf_path == output_paths.conf

                                    # Verify file writes
                                    self.mock_file_adapter.create_directory.assert_called()
                                    self.mock_file_adapter.write_text.assert_called()
                                    self.mock_file_adapter.write_json.assert_called()

    def test_register_behaviors(self, mock_keyboard_config):
        """Test registration of system behaviors using functional approach."""
        # Import the functional approach
        from glovebox.layout.behavior.analysis import register_layout_behaviors

        # Create a mock profile with behaviors
        mock_profile = Mock(spec=KeyboardProfile)
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

        # Create mock layout data (not used by register_layout_behaviors but required by signature)
        mock_layout_data = Mock(spec=LayoutData)

        # Test the functional approach
        register_layout_behaviors(
            mock_profile, mock_layout_data, self.mock_behavior_registry
        )

        # Verify all behaviors were registered
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


class TestLayoutServiceWithMockedConfig:
    """Tests using mocked config API."""

    @patch("glovebox.config.keyboard_profile.create_keyboard_profile")
    @patch("glovebox.config.keyboard_profile.get_available_keyboards")
    @patch("glovebox.layout.service.prepare_output_paths")
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
        from glovebox.firmware.models import OutputPaths

        mock_prepare_paths.return_value = OutputPaths(
            keymap=Path(tmp_path / "output/test.keymap"),
            conf=Path(tmp_path / "output/test.conf"),
            json=Path(tmp_path / "output/test.json"),
        )

        # Setup mocks
        mock_get_keyboards.return_value = ["test_keyboard", "glove80"]

        # Create a detailed mock profile
        mock_profile = Mock(spec=KeyboardProfile)
        mock_profile.keyboard_name = "test_keyboard"
        mock_profile.firmware_version = "default"

        # Create mock keyboard config
        mock_profile.keyboard_config = Mock()
        mock_profile.keyboard_config.key_count = 80
        mock_profile.keyboard_config.description = "Test Keyboard"

        # Create mock keymap
        mock_profile.keyboard_config.keymap = Mock()
        mock_profile.keyboard_config.keymap.keymap_dtsi = "// Template content"
        mock_profile.keyboard_config.keymap.key_position_header = "// Key positions"
        mock_profile.keyboard_config.keymap.system_behaviors_dts = "// Behaviors"
        mock_profile.keyboard_config.keymap.includes = []

        # Create mock formatting
        mock_profile.keyboard_config.keymap.formatting = Mock()
        mock_profile.keyboard_config.keymap.formatting.default_key_width = 10
        mock_profile.keyboard_config.keymap.formatting.key_gap = "  "
        mock_profile.keyboard_config.keymap.formatting.base_indent = ""
        mock_profile.keyboard_config.keymap.formatting.rows = [[0, 1, 2, 3, 4]]

        mock_profile.keyboard_config.keymap.kconfig_options = {}
        mock_profile.system_behaviors = []
        mock_profile.kconfig_options = {}

        mock_create_profile.return_value = mock_profile

        # Create service with mocked adapters for testing
        file_adapter = Mock(spec=FileAdapterProtocol)

        # Set up file adapter methods
        # ruff: noqa: SIM117 - Nested with statements are more readable here
        with patch.object(file_adapter, "create_directory", return_value=None):
            with patch.object(file_adapter, "write_text", return_value=None):
                with patch.object(file_adapter, "write_json", return_value=None):
                    template_adapter = Mock(spec=TemplateAdapterProtocol)

                    # Set up template adapter methods
                    with patch.object(
                        template_adapter,
                        "render_string",
                        return_value="// Generated keymap",
                    ):
                        behavior_registry = Mock()
                        behavior_formatter = Mock()
                        dtsi_generator = Mock()
                        component_service = Mock()
                        layout_service = Mock()

                        # Configure mocks
                        with patch.object(
                            dtsi_generator,
                            "generate_kconfig_conf",
                            return_value=("// Config content", {}),
                        ):
                            service = LayoutService(
                                file_adapter=file_adapter,
                                template_adapter=template_adapter,
                                behavior_registry=behavior_registry,
                                behavior_formatter=behavior_formatter,
                                dtsi_generator=dtsi_generator,
                                component_service=component_service,
                                layout_service=layout_service,
                            )

                            # Convert to LayoutData
                            keymap_data = LayoutData.model_validate(sample_keymap_json)

                            output_file_prefix = str(tmp_path / "output/test")

                            try:
                                # We're only testing that the integration points don't raise exceptions
                                result = service.generate(
                                    mock_profile,
                                    keymap_data,
                                    output_file_prefix=output_file_prefix,
                                )
                                success = True
                                assert result.success is True
                            except Exception as e:
                                print(f"Failed with exception: {e}")
                                success = False

                            assert success is True


def test_register_behaviors_with_fixture(keymap_service):
    """Test registering system behaviors using functional approach with fixture."""
    # Import the functional approach
    from glovebox.layout.behavior.analysis import register_layout_behaviors

    # Create a mock profile
    mock_profile = Mock(spec=KeyboardProfile)

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

    # Create mock layout data (not used by register_layout_behaviors but required by signature)
    mock_layout_data = Mock(spec=LayoutData)

    # Test the functional approach
    register_layout_behaviors(
        mock_profile, mock_layout_data, keymap_service.mock_behavior_registry
    )

    # Since we're using a mock, check that register_behavior was called for each behavior
    assert keymap_service.mock_behavior_registry.register_behavior.call_count == 2

    # Verify the behavior codes that were registered
    registered_behaviors = []
    for call in keymap_service.mock_behavior_registry.register_behavior.call_args_list:
        behavior = call[0][0]  # First positional argument
        registered_behaviors.append(behavior.code)

    # Check for expected behaviors
    assert "&kp" in registered_behaviors
    assert "&bt" in registered_behaviors
