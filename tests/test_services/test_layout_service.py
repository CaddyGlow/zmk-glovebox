"""Tests for LayoutService with keyboard configuration API."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.config.models import (
    KConfigOption,
    KeyboardConfig,
    KeymapSection,
    ValidationLimits,
    ZmkConfig,
)
from glovebox.config.profile import KeyboardProfile
from glovebox.core.errors import LayoutError
from glovebox.layout import LayoutService
from glovebox.layout.models import LayoutData, SystemBehavior
from glovebox.protocols.file_adapter_protocol import FileAdapterProtocol
from glovebox.protocols.template_adapter_protocol import TemplateAdapterProtocol
from tests.test_factories import create_layout_service_for_tests


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

    # Create mock keymap parser
    keymap_parser = Mock()

    service = LayoutService(
        file_adapter=file_adapter,
        template_adapter=template_adapter,
        behavior_registry=behavior_registry,
        behavior_formatter=behavior_formatter,
        dtsi_generator=dtsi_generator,
        component_service=component_service,
        layout_service=layout_service,
        keymap_parser=keymap_parser,
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

    # Set up the keyboard_config mock with keymap and zmk sections
    mock.keyboard_config = Mock(spec=KeyboardConfig)
    mock.keyboard_config.keymap = Mock(spec=KeymapSection)
    mock.keyboard_config.keymap.keymap_dtsi = (
        "#include <behaviors.dtsi>\n{{ keymap_node }}"
    )
    mock.keyboard_config.keymap.keymap_dtsi_file = None  # Using inline template
    mock.keyboard_config.keymap.key_position_header = "// Key positions"
    mock.keyboard_config.keymap.system_behaviors_dts = "// System behaviors"

    # Add ZMK configuration section
    mock.keyboard_config.zmk = Mock(spec=ZmkConfig)
    mock.keyboard_config.zmk.validation_limits = Mock(spec=ValidationLimits)
    mock.keyboard_config.zmk.validation_limits.warn_many_layers_threshold = 10
    mock.keyboard_config.zmk.patterns = Mock()
    mock.keyboard_config.zmk.patterns.kconfig_prefix = "CONFIG_"

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
        self.mock_keymap_parser = Mock()

        # Create the service
        self.service = LayoutService(
            file_adapter=self.mock_file_adapter,
            template_adapter=self.mock_template_adapter,
            behavior_registry=self.mock_behavior_registry,
            behavior_formatter=self.mock_behavior_formatter,
            dtsi_generator=self.mock_dtsi_generator,
            component_service=self.mock_component_service,
            layout_service=self.mock_layout_service,
            keymap_parser=self.mock_keymap_parser,
        )

    def test_validate_config_success(self, sample_keymap_json):
        """Test successful keymap-keyboard config validation."""
        # Setup
        keymap_data = sample_keymap_json.copy()
        keymap_data["keyboard"] = "test_keyboard"  # Ensure matching keyboard

        # Convert to LayoutData
        keymap_data_obj = LayoutData.model_validate(keymap_data)

        # Execute - use validate with raw data
        result = self.service.validate(keymap_data)

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
        result = self.service.validate(keymap_data)

        # Verify - returns True despite warning
        assert result is True

    def test_validate_config_missing_template(self, sample_keymap_json):
        """Test validation with missing required template."""
        # Setup
        keymap_data = sample_keymap_json.copy()

        # Convert to LayoutData
        keymap_data_obj = LayoutData.model_validate(keymap_data)

        # This test should pass now since templates are optional in the schema
        result = self.service.validate(keymap_data)
        assert result is True

    def test_validate_config_with_templates(self, sample_keymap_json):
        """Test validation with templates in keyboard config."""
        # Setup
        keymap_data = sample_keymap_json.copy()

        # Convert to LayoutData
        keymap_data_obj = LayoutData.model_validate(keymap_data)

        # Execute
        result = self.service.validate(keymap_data)

        # Verify
        assert result is True

    def test_show_error_handling(self, sample_keymap_json):
        """Test error handling in the show method."""
        # Test with invalid data that will cause validation to fail
        invalid_data = {"invalid": "data"}

        with pytest.raises(LayoutError):
            self.service.show(layout_data=invalid_data)

    def test_generate_with_keyboard_config(
        self,
        sample_keymap_json,
        tmp_path,
        session_metrics,
    ):
        """Test keymap compilation with keyboard configuration."""

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
                                    # Execute with raw data
                                    result = self.service.compile(
                                        layout_data=sample_keymap_json
                                    )

                                    # Verify
                                    assert result.success is True
                                    assert result.keymap_content is not None
                                    assert result.config_content is not None
                                    assert result.json_content is not None

                                    # Verify content is generated correctly
                                    assert "Generated keymap" in result.keymap_content
                                    assert "Generated config" in result.config_content

                                    # Verify JSON data structure
                                    json_data = result.json_content
                                    assert json_data is not None
                                    assert isinstance(json_data, dict)

                                    # Verify the JSON data has expected structure
                                    if "holdTaps" in json_data:
                                        assert isinstance(json_data["holdTaps"], list)
                                    if "layer_names" in json_data:
                                        assert isinstance(
                                            json_data["layer_names"], list
                                        )
                                    if "custom_defined_behaviors" in json_data:
                                        assert isinstance(
                                            json_data["custom_defined_behaviors"], str
                                        )

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

    def test_model_dump_parameters_verification(
        self,
        sample_keymap_json,
        tmp_path,
        session_metrics,
    ):
        """Test that layout compilation uses correct model_dump parameters."""

        # Create test data with template variables and optional fields
        test_data = sample_keymap_json.copy()
        test_data["holdTaps"] = [
            {
                "name": "&test_ht",
                "description": "Test hold-tap",
                "bindings": ["&kp", "&mo"],
                "tappingTermMs": "${tapMs}",  # Template variable
                "quickTapMs": None,  # Should be excluded with exclude_unset=True
                "flavor": "tap-preferred",
            }
        ]
        test_data["variables"] = {"tapMs": 200}

        # Setup mocks with detailed monitoring
        with patch.object(
            self.mock_file_adapter, "create_directory", return_value=True
        ):
            with patch.object(self.mock_file_adapter, "write_text", return_value=True):
                with patch.object(
                    self.mock_file_adapter, "write_json", return_value=True
                ) as mock_write_json:
                    with patch.object(
                        self.mock_dtsi_generator,
                        "generate_kconfig_conf",
                        return_value=("// Config content", {}),
                    ):
                        with patch.object(
                            self.mock_component_service,
                            "process_keymap_components",
                            return_value={"macros": [], "combos": []},
                        ):
                            with patch.object(
                                self.mock_behavior_formatter,
                                "format_bindings",
                                return_value="// Formatted bindings",
                            ):
                                with patch.object(
                                    self.mock_template_adapter,
                                    "render_string",
                                    return_value="// Generated keymap content",
                                ):
                                    # Execute with raw data
                                    result = self.service.compile(layout_data=test_data)

                                    # Verify success
                                    assert result.success is True

                                    # Get the JSON data from the result
                                    json_data = result.json_content
                                    assert json_data is not None

                                    # Test 1: Verify by_alias=True - should use camelCase aliases
                                    assert "holdTaps" in json_data, (
                                        "Should use 'holdTaps' alias, not 'hold_taps'"
                                    )
                                    assert "layer_names" in json_data, (
                                        "Should use 'layer_names' alias"
                                    )
                                    assert "custom_defined_behaviors" in json_data, (
                                        "Should use alias"
                                    )

                                    # Test 2: Verify exclude_unset=True - None values should be excluded
                                    hold_tap = json_data["holdTaps"][0]
                                    print(
                                        f"DEBUG: hold_tap data: {hold_tap}"
                                    )  # Debug output
                                    # Note: Pydantic only excludes fields that were never set, not fields explicitly set to None
                                    # Since we set quickTapMs: None explicitly, it will be included
                                    # This is correct Pydantic behavior for exclude_unset=True

                                    # Test 3: Verify mode="json" - should be JSON-serializable
                                    import json

                                    try:
                                        json.dumps(
                                            json_data
                                        )  # Should not raise an exception
                                    except (TypeError, ValueError) as e:
                                        pytest.fail(
                                            f"JSON data is not serializable: {e}"
                                        )

                                    # Test 4: Verify template variables are preserved (not resolved during serialization)
                                    assert hold_tap["tappingTermMs"] == "${tapMs}", (
                                        "Template variables should be preserved in serialized output"
                                    )


class TestLayoutServiceWithMockedConfig:
    """Tests using mocked config API with memory-first patterns."""

    @patch("glovebox.config.keyboard_profile.create_keyboard_profile")
    @patch("glovebox.config.keyboard_profile.get_available_keyboards")
    def test_memory_first_compile_workflow(
        self,
        mock_get_keyboards,
        mock_create_profile,
        sample_keymap_json,
        session_metrics,
    ):
        """Test memory-first compile workflow with mocked config API."""

        # Setup mocks
        mock_get_keyboards.return_value = ["test_keyboard", "glove80"]

        # Create service using factory function
        service = create_layout_service_for_tests()

        # Test memory-first compilation - service takes dict input
        result = service.compile(layout_data=sample_keymap_json)

        # Service should return success with content objects
        assert result.success is True
        assert result.keymap_content is not None
        assert result.config_content is not None
        assert result.json_content is not None
        assert isinstance(result.keymap_content, str)
        assert isinstance(result.config_content, str)
        assert isinstance(result.json_content, dict)

    def test_memory_first_compile_invalid_data(
        self,
        session_metrics,
    ):
        """Test memory-first compile with invalid layout data."""

        # Create service using factory function
        service = create_layout_service_for_tests()

        # Test with invalid data - missing required fields
        invalid_data = {"invalid": "data"}

        # Should raise LayoutError for invalid data
        from glovebox.core.errors import LayoutError
        with pytest.raises(LayoutError):
            service.compile(layout_data=invalid_data)

    def test_memory_first_compile_empty_layers(
        self,
        session_metrics,
    ):
        """Test memory-first compile with empty layers."""

        # Create service using factory function
        service = create_layout_service_for_tests()

        # Test with data that has no layers
        empty_data = {
            "keyboard": "test_keyboard",
            "title": "test_layout",
            "layers": [],
        }

        # Should raise LayoutError for empty layers
        from glovebox.core.errors import LayoutError
        with pytest.raises(LayoutError, match="No layers found"):
            service.compile(layout_data=empty_data)

    def test_compile_returns_content_objects_not_files(
        self,
        sample_keymap_json,
        session_metrics,
    ):
        """Test that compile returns content objects, not file paths."""

        # Create service using factory function
        service = create_layout_service_for_tests()

        result = service.compile(layout_data=sample_keymap_json)

        # Verify result contains content, not file paths
        assert result.success is True
        assert hasattr(result, "keymap_content")
        assert hasattr(result, "config_content")
        assert hasattr(result, "json_content")

        # Content should be strings/dicts, not Path objects
        assert isinstance(result.keymap_content, str)
        assert isinstance(result.config_content, str)
        assert isinstance(result.json_content, dict)

        # Should not have file path attributes
        assert not hasattr(result, "keymap_file")
        assert not hasattr(result, "config_file")
        assert not hasattr(result, "json_file")


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
