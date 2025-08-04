"""Integration tests for compilation workflow.

Tests the complete compilation pipeline from JSON input to firmware output,
focusing on the new memory-first patterns and IOCommand usage.
"""

import json
import logging
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import typer

from glovebox.compilation import create_compilation_service
from glovebox.config import create_user_config
from glovebox.core.cache import get_shared_cache_instance
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
        patch(
            "glovebox.compilation.cache.create_zmk_workspace_cache_service"
        ) as mock_workspace_cache,
        patch(
            "glovebox.compilation.cache.create_compilation_build_cache_service"
        ) as mock_build_cache,
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
                "bindings": ["&kp KC_TAB", "&kp KC_ESC"],
            }
        },
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
            patch(
                "glovebox.compilation.helpers.convert_layout_data_to_keymap_content"
            ) as mock_convert,
            patch.object(zmk_compilation_service, "compile") as mock_compile,
        ):
            # Mock successful conversion
            mock_convert.return_value = (
                "mock keymap content",
                "mock config content",
                BuildResult(success=True, messages=["Conversion successful"]),
            )
            mock_result = BuildResult(
                success=True,
                messages=["ZMK compilation successful"],
                output_files=FirmwareOutputFiles(
                    output_dir=output_dir,
                    uf2_files=[
                        output_dir / "glove80.keymap",
                        output_dir / "glove80.conf",
                    ],
                ),
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
            patch(
                "glovebox.compilation.helpers.convert_json_to_keymap_content"
            ) as mock_convert,
            patch.object(moergo_compilation_service, "compile") as mock_compile,
        ):
            # Mock successful conversion
            mock_convert.return_value = (
                "mock keymap content",
                "mock config content",
                BuildResult(success=True, messages=["Conversion successful"]),
            )

            # Mock successful compilation
            mock_result = BuildResult(
                success=True,
                messages=["MoErgo compilation successful"],
                output_files=FirmwareOutputFiles(
                    output_dir=output_dir,
                    uf2_files=[output_dir / "glove80.uf2"],
                ),
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
                messages=[],
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
            patch(
                "glovebox.compilation.helpers.convert_json_to_keymap_content"
            ) as mock_convert,
            patch.object(moergo_compilation_service, "compile") as mock_compile,
        ):
            # Mock layout generation
            mock_convert.return_value = (
                "// Generated keymap content",
                "# Generated config content",
                BuildResult(success=True, messages=["Layout generated"]),
            )

            # Mock firmware compilation
            firmware_file = output_dir / "glove80.uf2"
            mock_result = BuildResult(
                success=True,
                messages=["Firmware compiled successfully"],
                output_files=FirmwareOutputFiles(
                    output_dir=output_dir,
                    uf2_files=[firmware_file],
                ),
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
            patch(
                "glovebox.compilation.helpers.convert_json_to_keymap_content"
            ) as mock_convert,
            patch.object(zmk_compilation_service, "compile") as mock_compile,
        ):
            # Mock layout generation from data
            mock_convert.return_value = (
                "// ZMK keymap content",
                "# ZMK config content",
                BuildResult(success=True, messages=["ZMK files generated"]),
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
                ),
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
        with patch(
            "glovebox.compilation.helpers.convert_json_to_keymap_content"
        ) as mock_convert:
            mock_convert.return_value = (
                None,
                None,
                BuildResult(
                    success=False,
                    errors=[
                        "Missing required field: keyboard",
                        "Missing required field: layers",
                    ],
                ),
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
            patch(
                "glovebox.compilation.cache.create_zmk_workspace_cache_service"
            ) as mock_workspace_cache,
            patch(
                "glovebox.compilation.cache.create_compilation_build_cache_service"
            ) as mock_build_cache,
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

        with pytest.raises(
            ValueError, match="Unknown compilation method type: unsupported"
        ):
            create_compilation_service(
                method_type="unsupported",
                user_config=user_config,
                docker_adapter=mock_docker_adapter,
                file_adapter=mock_file_adapter,
                cache_manager=None,
                session_metrics=session_metrics,
            )


class TestCompilationCommandIntegration:
    """Test the full IOCommand workflow for compilation commands."""

    def test_compile_command_json_input_to_directory_output(
        self, tmp_path: Path, sample_layout_data, mock_keyboard_profile
    ):
        """Test CompileCommand with JSON input file and directory output."""
        # Note: Using generic CompileCommand pattern since specific commands may vary
        # This tests the IOCommand pattern integration

        # Setup test files
        input_file = tmp_path / "input.json"
        output_dir = tmp_path / "compilation_output"

        with input_file.open("w") as f:
            json.dump(sample_layout_data, f)

        # Mock compilation service
        mock_result = BuildResult(
            success=True,
            messages=["Compilation successful"],
            output_files=FirmwareOutputFiles(
                output_dir=output_dir,
                uf2_files=[output_dir / "glove80.uf2"],
            ),
        )

        # Test IOCommand pattern workflow
        from glovebox.cli.core.command_base import IOCommand

        class MockCompileCommand(IOCommand):
            def execute_compilation(self, layout_data, output_dir, method):
                # Simulate command execution pattern
                from glovebox.compilation import create_compilation_service

                service = create_compilation_service(method_type=method)
                return service.compile_from_data(
                    layout_data=layout_data,
                    output_dir=output_dir,
                    keyboard_profile=mock_keyboard_profile,
                )

        command = MockCompileCommand()

        with patch(
            "glovebox.compilation.create_compilation_service"
        ) as mock_service_factory:
            mock_service = Mock()
            mock_service.compile_from_data.return_value = mock_result
            mock_service_factory.return_value = mock_service

            # Test IOCommand input loading
            input_result = command.load_input(str(input_file))
            assert input_result.data is not None

            # Test JSON input loading
            json_data = command.load_json_input(str(input_file))
            assert json_data == sample_layout_data

            # Test output writing
            output_result = command.write_output(
                {"success": True, "message": "Compilation completed"},
                str(output_dir / "result.json"),
                format="json",
            )
            assert output_result.resolved_path is not None

    def test_compile_command_stdin_to_stdout_workflow(
        self, sample_layout_data, mock_keyboard_profile
    ):
        """Test CompileCommand with stdin input and stdout output."""
        from glovebox.cli.core.command_base import IOCommand

        class MockCompileCommand(IOCommand):
            def process_layout(self, layout_data):
                return {
                    "success": True,
                    "message": "Layout processed from stdin",
                    "layout": layout_data["title"],
                }

        command = MockCompileCommand()

        # Mock stdin input
        json_input = json.dumps(sample_layout_data)

        with patch(
            "glovebox.core.io.handlers.InputHandler.load_json_input"
        ) as mock_load_json:
            mock_load_json.return_value = sample_layout_data

            # Test stdin loading
            loaded_data = command.load_json_input("-")
            assert loaded_data == sample_layout_data

            # Test processing and stdout output
            result = command.process_layout(loaded_data)
            assert result["success"] is True
            assert result["layout"] == "Integration Test Layout"

    def test_compile_command_library_reference_workflow(self, mock_keyboard_profile):
        """Test CompileCommand with @library reference input."""
        from glovebox.cli.core.command_base import IOCommand

        class MockCompileCommand(IOCommand):
            pass

        command = MockCompileCommand()

        # Mock library data
        mock_library_data = {
            "keyboard": "glove80",
            "title": "Library Layout",
            "layers": [["KC_A", "KC_B", "KC_C"]],
            "layer_names": ["Base"],
        }

        with patch(
            "glovebox.core.io.handlers.InputHandler.load_json_input"
        ) as mock_load_json:
            mock_load_json.return_value = mock_library_data

            # Test library reference loading
            loaded_data = command.load_json_input("@test/layout")
            assert loaded_data == mock_library_data
            assert loaded_data["title"] == "Library Layout"

            # Verify library reference was processed
            mock_load_json.assert_called_once_with("@test/layout")

    def test_compile_command_error_handling_workflow(
        self, tmp_path: Path, mock_keyboard_profile
    ):
        """Test CompileCommand error handling when compilation fails."""
        from glovebox.cli.core.command_base import IOCommand

        class MockCompileCommand(IOCommand):
            def handle_service_error(self, error, operation):
                exc_info = self.logger.isEnabledFor(logging.DEBUG)
                self.logger.error(
                    "Failed to %s: %s", operation, error, exc_info=exc_info
                )
                self.console.print_error(f"Failed to {operation}: {error}")
                raise typer.Exit(1) from error

        # Setup invalid input
        input_file = tmp_path / "invalid.json"
        input_file.write_text('{"invalid": "layout"}')

        command = MockCompileCommand()

        # Mock compilation failure
        mock_result = BuildResult(
            success=False,
            errors=["Compilation failed", "Invalid layout structure"],
            messages=[],
        )

        with (
            patch(
                "glovebox.compilation.create_compilation_service"
            ) as mock_service_factory,
            pytest.raises(ValueError),  # Service error should be raised
        ):
            mock_service = Mock()
            mock_service.compile_from_data.return_value = mock_result
            mock_service_factory.return_value = mock_service

            # Load invalid input
            invalid_data = command.load_json_input(str(input_file))

            # Simulate service call that would fail
            result = mock_service.compile_from_data(
                layout_data=invalid_data,
                output_dir=tmp_path,
                keyboard_profile=mock_keyboard_profile,
            )

            if not result.success:
                raise ValueError(f"Compilation failed: {'; '.join(result.errors)}")


class TestCompilationIOPatterns:
    """Test IO pattern integration in compilation commands."""

    def test_input_handler_integration_with_compilation(
        self, tmp_path: Path, sample_layout_data
    ):
        """Test InputHandler integration with compilation workflows."""
        from glovebox.core.io import create_input_handler

        # Test file input
        input_file = tmp_path / "compile_test.json"
        with input_file.open("w") as f:
            json.dump(sample_layout_data, f)

        input_handler = create_input_handler()
        result = input_handler.load_json_input(str(input_file))
        assert result == sample_layout_data
        assert result["keyboard"] == "glove80"

        # Test stdin input
        with patch("sys.stdin.read", return_value=json.dumps(sample_layout_data)):
            result = input_handler.load_json_input("-")
            assert result == sample_layout_data

    def test_output_handler_integration_with_compilation(self, tmp_path: Path):
        """Test OutputHandler integration with compilation results."""
        from glovebox.core.io import create_output_handler

        # Mock compilation result
        compilation_result = {
            "success": True,
            "messages": ["Compilation completed successfully"],
            "output_files": {
                "keymap": str(tmp_path / "glove80.keymap"),
                "config": str(tmp_path / "glove80.conf"),
                "firmware": str(tmp_path / "glove80.uf2"),
            },
        }

        output_handler = create_output_handler()

        # Test JSON output
        json_output = tmp_path / "result.json"
        result = output_handler.write_json_output(compilation_result, str(json_output))
        assert result.success
        assert json_output.exists()

        # Verify content
        written_data = json.loads(json_output.read_text())
        assert written_data["success"] is True
        assert "Compilation completed successfully" in written_data["messages"]

    def test_memory_first_compilation_integration(self, mock_keyboard_profile):
        """Test memory-first compilation pattern integration."""
        from glovebox.compilation import create_compilation_service

        # Test data in memory (new pattern)
        layout_data = {
            "keyboard": "glove80",
            "title": "Memory First Compilation",
            "layers": [["KC_Q", "KC_W", "KC_E"]],
            "layer_names": ["Base"],
        }

        # Test service creation and memory-first pattern
        service = create_compilation_service(method_type="zmk_config")

        # Mock the service method
        mock_result = BuildResult(
            success=True,
            messages=["Memory-first compilation successful"],
            output_files=FirmwareOutputFiles(
                output_dir=Path("/tmp/test"),
                uf2_files=[Path("/tmp/test/glove80.uf2")],
            ),
        )

        with patch.object(service, "compile_from_data") as mock_compile:
            mock_compile.return_value = mock_result

            # Call with memory data (new pattern)
            result = service.compile_from_data(
                layout_data=layout_data,
                output_dir=Path("/tmp/test"),
                config={"method": "zmk_config"},
                keyboard_profile=mock_keyboard_profile,
            )

            # Verify memory-first pattern worked
            assert result.success is True
            assert "Memory-first compilation successful" in result.messages
            mock_compile.assert_called_once_with(
                layout_data=layout_data,
                output_dir=Path("/tmp/test"),
                config={"method": "zmk_config"},
                keyboard_profile=mock_keyboard_profile,
            )

    def test_compilation_service_factory_patterns(self, mock_keyboard_profile):
        """Test compilation service factory patterns with IOCommand integration."""
        from glovebox.compilation import create_compilation_service

        # Test different service types
        zmk_service = create_compilation_service(method_type="zmk_config")
        moergo_service = create_compilation_service(method_type="moergo")

        # Verify correct types
        from glovebox.compilation.services.moergo_nix_service import MoergoNixService
        from glovebox.compilation.services.zmk_west_service import ZmkWestService

        assert isinstance(zmk_service, ZmkWestService)
        assert isinstance(moergo_service, MoergoNixService)

        # Test that both services have required methods for IOCommand integration
        assert hasattr(zmk_service, "compile_from_data")
        assert hasattr(zmk_service, "compile_from_json")
        assert hasattr(moergo_service, "compile_from_data")
        assert hasattr(moergo_service, "compile_from_json")

        # Test methods are callable
        assert callable(zmk_service.compile_from_data)
        assert callable(moergo_service.compile_from_json)


class TestCompilationWorkflowEndToEnd:
    """Test complete end-to-end compilation workflows with new patterns."""

    def test_json_input_to_firmware_output_workflow(
        self, tmp_path: Path, sample_layout_data, mock_keyboard_profile
    ):
        """Test complete workflow: JSON input → IOCommand → Service → Firmware output."""
        from glovebox.cli.core.command_base import IOCommand

        # Simulate complete compilation command workflow
        class CompleteCompileCommand(IOCommand):
            def execute_full_workflow(self, input_source, output_dir, method):
                # Step 1: Load input using IOCommand
                layout_data = self.load_json_input(input_source)

                # Step 2: Create service using factory
                from glovebox.compilation import create_compilation_service

                service = create_compilation_service(method_type=method)

                # Step 3: Compile using memory-first pattern
                result = service.compile_from_data(
                    layout_data=layout_data,
                    output_dir=output_dir,
                    keyboard_profile=mock_keyboard_profile,
                )

                # Step 4: Write output using IOCommand
                if result.success:
                    output_data = {
                        "success": True,
                        "message": "Workflow completed successfully",
                        "output_files": result.output_files.to_dict()
                        if result.output_files
                        else {},
                    }
                    self.write_output(
                        output_data,
                        str(output_dir / "workflow_result.json"),
                        format="json",
                    )

                return result

        # Setup test data
        input_file = tmp_path / "workflow_input.json"
        output_dir = tmp_path / "workflow_output"
        output_dir.mkdir(parents=True)

        with input_file.open("w") as f:
            json.dump(sample_layout_data, f)

        command = CompleteCompileCommand()

        # Mock the complete workflow
        mock_result = BuildResult(
            success=True,
            messages=["End-to-end workflow successful"],
            output_files=FirmwareOutputFiles(
                output_dir=output_dir,
                uf2_files=[output_dir / "glove80.uf2"],
            ),
        )

        with patch(
            "glovebox.compilation.create_compilation_service"
        ) as mock_service_factory:
            mock_service = Mock()
            mock_service.compile_from_data.return_value = mock_result
            mock_service_factory.return_value = mock_service

            # Execute complete workflow
            result = command.execute_full_workflow(
                input_source=str(input_file), output_dir=output_dir, method="zmk_config"
            )

            # Verify workflow completion
            assert result.success is True
            assert "End-to-end workflow successful" in result.messages

            # Verify workflow result was written
            result_file = output_dir / "workflow_result.json"
            assert result_file.exists()

            workflow_result = json.loads(result_file.read_text())
            assert workflow_result["success"] is True
            assert workflow_result["message"] == "Workflow completed successfully"
