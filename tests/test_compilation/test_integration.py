"""Integration tests for compilation workflow.

Tests the complete compilation pipeline from JSON input to firmware output,
focusing on the new memory-first patterns and IOCommand usage.
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.compilation import create_compilation_service
from glovebox.config import create_user_config
from glovebox.core.cache import get_shared_cache_instance
from glovebox.core.metrics import create_session_metrics
from glovebox.firmware.models import BuildResult, FirmwareOutputFiles


pytestmark = pytest.mark.integration


@pytest.fixture
def mock_docker_adapter():
    """Create a mock Docker adapter for testing."""
    from unittest.mock import Mock

    from glovebox.protocols import DockerAdapterProtocol

    adapter = Mock(spec=DockerAdapterProtocol)
    adapter.run_container.return_value = (0, [], [])  # success by default
    adapter.image_exists.return_value = True
    adapter.build_image.return_value = (0, [], [])
    return adapter


@pytest.fixture
def zmk_compilation_service(
    isolated_cli_environment,
    mock_docker_adapter,
    mock_file_adapter,
    session_metrics,
    isolated_cache_environment,
):
    """Create ZMK compilation service for testing."""
    user_config = create_user_config()
    cache_manager = get_shared_cache_instance(
        cache_root=isolated_cache_environment["cache_root"], tag="test_compilation"
    )

    # Mock cache services since we're testing integration, not cache functionality
    with (
        patch("glovebox.compilation.cache.create_zmk_workspace_cache_service") as mock_workspace_cache,
        patch("glovebox.compilation.cache.create_compilation_build_cache_service") as mock_build_cache,
    ):
        mock_workspace_cache.return_value = Mock()
        mock_build_cache.return_value = Mock()

        service = create_compilation_service(
            method_type="zmk_config",
            user_config=user_config,
            docker_adapter=mock_docker_adapter,
            file_adapter=mock_file_adapter,
            cache_manager=cache_manager,
            session_metrics=session_metrics,
            workspace_cache_service=mock_workspace_cache.return_value,
            build_cache_service=mock_build_cache.return_value,
        )
        return service


@pytest.fixture
def moergo_compilation_service(
    isolated_cli_environment,
    mock_docker_adapter,
    mock_file_adapter,
    session_metrics,
):
    """Create MoErgo compilation service for testing."""
    service = create_compilation_service(
        method_type="moergo",
        user_config=create_user_config(),
        docker_adapter=mock_docker_adapter,
        file_adapter=mock_file_adapter,
        cache_manager=None,
        session_metrics=session_metrics,
    )
    return service


@pytest.fixture
def sample_layout_data():
    """Sample layout data for testing."""
    return {
        "keyboard": "glove80",
        "title": "Integration Test Layout",
        "author": "Test User",
        "layers": [
            ["KC_Q", "KC_W", "KC_E", "KC_R", "KC_T"],
            ["KC_1", "KC_2", "KC_3", "KC_4", "KC_5"],
        ],
        "layer_names": ["Base", "Numbers"],
        "behaviors": {
            "test_tap_dance": {
                "type": "tap_dance",
                "tapping_term_ms": 200,
                "bindings": ["&kp KC_TAB", "&kp KC_ESC"]
            }
        }
    }


class TestCompilationServiceIntegration:
    """Test the full integration flow of compilation services."""

    def test_zmk_compile_from_data_success(
        self,
        zmk_compilation_service,
        sample_layout_data,
        mock_keyboard_profile,
        tmp_path,
    ):
        """Test successful ZMK compilation workflow from data."""
        output_dir = tmp_path / "zmk_output"
        output_dir.mkdir(parents=True)

        # Mock the helper function and underlying compile method to return success
        with (
            patch("glovebox.compilation.helpers.convert_layout_data_to_keymap_content") as mock_convert,
            patch.object(zmk_compilation_service, "compile") as mock_compile,
        ):
            # Mock successful conversion
            mock_convert.return_value = (
                "mock keymap content",
                "mock config content",
                BuildResult(success=True, messages=["Conversion successful"])
            )
            mock_result = BuildResult(
                success=True,
                messages=["ZMK compilation successful"],
                output_files=FirmwareOutputFiles(
                    output_dir=output_dir,
                    uf2_files=[output_dir / "glove80.keymap", output_dir / "glove80.conf"],
                )
            )
            mock_compile.return_value = mock_result

            # Test compile_from_data method (memory-first pattern)
            result = zmk_compilation_service.compile_from_data(
                layout_data=sample_layout_data,
                output_dir=output_dir,
                config={"git_clone_timeout": 300},
                keyboard_profile=mock_keyboard_profile,
            )

            assert result.success is True
            assert "ZMK compilation successful" in result.messages
            assert result.output_files is not None

    def test_moergo_compile_from_json_success(
        self,
        moergo_compilation_service,
        sample_layout_data,
        mock_keyboard_profile,
        tmp_path,
    ):
        """Test successful MoErgo compilation workflow from JSON file."""
        # Create test JSON file
        json_file = tmp_path / "test_layout.json"
        with json_file.open("w") as f:
            json.dump(sample_layout_data, f)

        output_dir = tmp_path / "moergo_output"
        output_dir.mkdir(parents=True)

        # Mock the conversion helper and compile method
        with (
            patch("glovebox.compilation.helpers.convert_json_to_keymap_content") as mock_convert,
            patch.object(moergo_compilation_service, "compile") as mock_compile,
        ):
            # Mock successful conversion
            mock_convert.return_value = (
                "mock keymap content",
                "mock config content",
                BuildResult(success=True, messages=["Conversion successful"])
            )

            # Mock successful compilation
            mock_result = BuildResult(
                success=True,
                messages=["MoErgo compilation successful"],
                output_files=FirmwareOutputFiles(
                    output_dir=output_dir,
                    uf2_files=[output_dir / "glove80.uf2"],
                )
            )
            mock_compile.return_value = mock_result

            # Test compile_from_json method
            result = moergo_compilation_service.compile_from_json(
                json_file=json_file,
                output_dir=output_dir,
                config={"image": "test-moergo-builder"},
                keyboard_profile=mock_keyboard_profile,
            )

            assert result.success is True
            assert len(result.messages) > 0

    def test_compilation_error_handling(
        self,
        zmk_compilation_service,
        sample_layout_data,
        mock_keyboard_profile,
        tmp_path,
    ):
        """Test compilation error handling."""
        output_dir = tmp_path / "error_output"
        output_dir.mkdir(parents=True)

        # Mock compilation failure
        with patch.object(zmk_compilation_service, "compile") as mock_compile:
            mock_result = BuildResult(
                success=False,
                errors=["Build failed", "Missing dependencies"],
                messages=[]
            )
            mock_compile.return_value = mock_result

            result = zmk_compilation_service.compile_from_data(
                layout_data=sample_layout_data,
                output_dir=output_dir,
                config={"git_clone_timeout": 300},
                keyboard_profile=mock_keyboard_profile,
            )

            assert result.success is False
            assert "Build failed" in result.errors
            assert "Missing dependencies" in result.errors


class TestCompilationWorkflowIntegration:
    """Test end-to-end compilation workflows with different input methods."""

    def test_file_input_to_firmware_output(
        self,
        moergo_compilation_service,
        sample_layout_data,
        mock_keyboard_profile,
        tmp_path,
    ):
        """Test complete workflow: JSON file → Compilation → Firmware output."""
        # Step 1: Create input JSON file
        input_file = tmp_path / "input_layout.json"
        with input_file.open("w") as f:
            json.dump(sample_layout_data, f)

        # Step 2: Set up output directory
        output_dir = tmp_path / "firmware_output"
        output_dir.mkdir(parents=True)

        # Step 3: Mock the complete compilation pipeline
        with (
            patch("glovebox.compilation.helpers.convert_json_to_keymap_content") as mock_convert,
            patch.object(moergo_compilation_service, "compile") as mock_compile,
        ):
            # Mock layout generation
            mock_convert.return_value = (
                "// Generated keymap content",
                "# Generated config content",
                BuildResult(success=True, messages=["Layout generated"])
            )

            # Mock firmware compilation
            firmware_file = output_dir / "glove80.uf2"
            mock_result = BuildResult(
                success=True,
                messages=["Firmware compiled successfully"],
                output_files=FirmwareOutputFiles(
                    output_dir=output_dir,
                    uf2_files=[firmware_file],
                )
            )
            mock_compile.return_value = mock_result

            # Step 4: Execute compilation
            result = moergo_compilation_service.compile_from_json(
                json_file=input_file,
                output_dir=output_dir,
                config={"image": "test-builder"},
                keyboard_profile=mock_keyboard_profile,
            )

            # Step 5: Verify workflow completion
            assert result.success is True
            assert "Firmware compiled successfully" in result.messages

            # Verify helper was called with correct file
            mock_convert.assert_called_once()

            # Verify compile was called
            mock_compile.assert_called_once()

    def test_data_input_to_zmk_output(
        self,
        zmk_compilation_service,
        sample_layout_data,
        mock_keyboard_profile,
        tmp_path,
    ):
        """Test workflow: Data → ZMK compilation → Keymap/Config output."""
        output_dir = tmp_path / "zmk_output"
        output_dir.mkdir(parents=True)

        # Mock the layout service and compilation pipeline
        with (
            patch("glovebox.compilation.helpers.convert_json_to_keymap_content") as mock_convert,
            patch.object(zmk_compilation_service, "compile") as mock_compile,
        ):
            # Mock layout generation from data
            mock_convert.return_value = (
                "// ZMK keymap content",
                "# ZMK config content",
                BuildResult(success=True, messages=["ZMK files generated"])
            )

            # Mock ZMK compilation
            keymap_file = output_dir / "glove80.keymap"
            config_file = output_dir / "glove80.conf"
            mock_result = BuildResult(
                success=True,
                messages=["ZMK compilation successful"],
                output_files=FirmwareOutputFiles(
                    output_dir=output_dir,
                    uf2_files=[keymap_file, config_file],
                )
            )
            mock_compile.return_value = mock_result

            # Execute compilation from data
            result = zmk_compilation_service.compile_from_data(
                layout_data=sample_layout_data,
                output_dir=output_dir,
                config={"git_clone_timeout": 300},
                keyboard_profile=mock_keyboard_profile,
            )

            # Verify workflow
            assert result.success is True
            assert "ZMK compilation successful" in result.messages
            assert result.output_files is not None
            assert keymap_file in result.output_files.uf2_files
            assert config_file in result.output_files.uf2_files

    def test_invalid_input_error_handling(
        self,
        zmk_compilation_service,
        mock_keyboard_profile,
        tmp_path,
    ):
        """Test error handling with invalid input data."""
        output_dir = tmp_path / "error_output"
        output_dir.mkdir(parents=True)

        # Invalid layout data (missing required fields)
        invalid_data = {
            "title": "Invalid Layout",
            # Missing keyboard, layers, layer_names
        }

        # Mock helper to return validation error
        with patch("glovebox.compilation.helpers.convert_json_to_keymap_content") as mock_convert:
            mock_convert.return_value = (
                None,
                None,
                BuildResult(
                    success=False,
                    errors=["Missing required field: keyboard", "Missing required field: layers"]
                )
            )

            result = zmk_compilation_service.compile_from_data(
                layout_data=invalid_data,
                output_dir=output_dir,
                keyboard_profile=mock_keyboard_profile,
            )

            assert result.success is False
            assert "Missing required field: keyboard" in result.errors
            assert "Missing required field: layers" in result.errors


class TestCompilationServiceFactoryIntegration:
    """Test factory function integration with different service types."""

    def test_create_zmk_service_with_dependencies(
        self,
        isolated_cli_environment,
        mock_docker_adapter,
        mock_file_adapter,
        session_metrics,
        isolated_cache_environment,
    ):
        """Test creating ZMK service with proper dependency injection."""
        user_config = create_user_config()
        cache_manager = get_shared_cache_instance(
            cache_root=isolated_cache_environment["cache_root"], tag="test_factory"
        )

        with (
            patch("glovebox.compilation.cache.create_zmk_workspace_cache_service") as mock_workspace_cache,
            patch("glovebox.compilation.cache.create_compilation_build_cache_service") as mock_build_cache,
        ):
            mock_workspace_cache.return_value = Mock()
            mock_build_cache.return_value = Mock()

            service = create_compilation_service(
                method_type="zmk_config",
                user_config=user_config,
                docker_adapter=mock_docker_adapter,
                file_adapter=mock_file_adapter,
                cache_manager=cache_manager,
                session_metrics=session_metrics,
                workspace_cache_service=mock_workspace_cache.return_value,
                build_cache_service=mock_build_cache.return_value,
            )

            # Verify service was created with correct type
            from glovebox.compilation.services.zmk_west_service import ZmkWestService
            assert isinstance(service, ZmkWestService)

    def test_create_moergo_service_with_dependencies(
        self,
        isolated_cli_environment,
        mock_docker_adapter,
        mock_file_adapter,
        session_metrics,
    ):
        """Test creating MoErgo service with proper dependency injection."""
        user_config = create_user_config()

        service = create_compilation_service(
            method_type="moergo",
            user_config=user_config,
            docker_adapter=mock_docker_adapter,
            file_adapter=mock_file_adapter,
            cache_manager=None,
            session_metrics=session_metrics,
        )

        # Verify service was created with correct type
        from glovebox.compilation.services.moergo_nix_service import MoergoNixService
        assert isinstance(service, MoergoNixService)

    def test_unsupported_method_type_error(
        self,
        isolated_cli_environment,
        mock_docker_adapter,
        mock_file_adapter,
        session_metrics,
    ):
        """Test error handling for unsupported compilation method types."""
        user_config = create_user_config()

        with pytest.raises(ValueError, match="Unknown compilation method type: unsupported"):
            create_compilation_service(
                method_type="unsupported",
                user_config=user_config,
                docker_adapter=mock_docker_adapter,
                file_adapter=mock_file_adapter,
                cache_manager=None,
                session_metrics=session_metrics,
            )
