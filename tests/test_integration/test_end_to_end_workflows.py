"""Comprehensive end-to-end integration tests for the complete glovebox pipeline.

Tests the full workflows from input to output using the new IOCommand patterns,
memory-first services, and unified error handling.
"""

import json
import logging
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.cli.core.command_base import IOCommand
from glovebox.firmware.models import BuildResult, FirmwareOutputFiles
from glovebox.layout.models import LayoutResult


pytestmark = pytest.mark.integration


@pytest.fixture
def sample_complete_layout():
    """Complete layout data for end-to-end testing."""
    return {
        "keyboard": "glove80",
        "title": "End-to-End Test Layout",
        "author": "Integration Test",
        "firmware_version": "3.0",
        "layout": "QWERTY",
        "layer_names": ["Base", "Lower", "Raise"],
        "layers": [
            # Base layer
            [
                "KC_Q",
                "KC_W",
                "KC_E",
                "KC_R",
                "KC_T",
                "KC_Y",
                "KC_U",
                "KC_I",
                "KC_O",
                "KC_P",
                "KC_A",
                "KC_S",
                "KC_D",
                "KC_F",
                "KC_G",
                "KC_H",
                "KC_J",
                "KC_K",
                "KC_L",
                "KC_SCLN",
                "KC_Z",
                "KC_X",
                "KC_C",
                "KC_V",
                "KC_B",
                "KC_N",
                "KC_M",
                "KC_COMM",
                "KC_DOT",
                "KC_SLSH",
                "&lt 1 SPACE",
                "&mo 2",
                "&kp LSHIFT",
            ],
            # Lower layer
            [
                "KC_1",
                "KC_2",
                "KC_3",
                "KC_4",
                "KC_5",
                "KC_6",
                "KC_7",
                "KC_8",
                "KC_9",
                "KC_0",
                "KC_EXLM",
                "KC_AT",
                "KC_HASH",
                "KC_DLR",
                "KC_PERC",
                "KC_CIRC",
                "KC_AMPR",
                "KC_ASTR",
                "KC_LPRN",
                "KC_RPRN",
                "_____",
                "_____",
                "_____",
                "_____",
                "_____",
                "_____",
                "_____",
                "_____",
                "_____",
                "_____",
                "_____",
                "_____",
                "_____",
            ],
            # Raise layer
            [
                "KC_F1",
                "KC_F2",
                "KC_F3",
                "KC_F4",
                "KC_F5",
                "KC_F6",
                "KC_F7",
                "KC_F8",
                "KC_F9",
                "KC_F10",
                "_____",
                "_____",
                "_____",
                "_____",
                "_____",
                "_____",
                "_____",
                "_____",
                "_____",
                "_____",
                "_____",
                "_____",
                "_____",
                "_____",
                "_____",
                "_____",
                "_____",
                "_____",
                "_____",
                "_____",
                "_____",
                "_____",
                "_____",
            ],
        ],
        "combos": [
            {
                "name": "copy",
                "keyPositions": [0, 1],
                "binding": "&kp LC(C)",
                "layers": ["Base"],
            },
            {
                "name": "paste",
                "keyPositions": [1, 2],
                "binding": "&kp LC(V)",
                "layers": ["Base"],
            },
        ],
        "macros": [
            {
                "name": "hello_macro",
                "bindings": [
                    {"behavior": "&kp", "param": "H"},
                    {"behavior": "&kp", "param": "E"},
                    {"behavior": "&kp", "param": "L"},
                    {"behavior": "&kp", "param": "L"},
                    {"behavior": "&kp", "param": "O"},
                ],
            }
        ],
        "custom_behaviors": [
            {
                "name": "td_esc_caps",
                "type": "tap-dance",
                "bindings": [
                    {"behavior": "&kp", "param": "ESC"},
                    {"behavior": "&kp", "param": "CAPS"},
                ],
                "tapping-term-ms": 200,
            }
        ],
    }


class TestCompleteLayoutWorkflow:
    """Test the complete layout processing pipeline."""

    def test_json_to_layout_files_end_to_end(
        self, tmp_path: Path, sample_complete_layout
    ):
        """Test complete workflow: JSON input → Layout service → Keymap/Config files."""

        class LayoutWorkflowCommand(IOCommand):
            def execute_complete_layout_workflow(self, input_source, output_dir):
                # Step 1: Load JSON input
                layout_data = self.load_json_input(input_source)

                # Step 2: Create layout service
                from glovebox.layout import create_layout_service

                service = create_layout_service()

                # Step 3: Compile layout
                result = service.compile(layout_data)

                # Step 4: Write output files
                if result.success:
                    keymap_file = output_dir / "layout.keymap"
                    config_file = output_dir / "layout.conf"

                    self.write_output(result.keymap_content, str(keymap_file), "text")
                    self.write_output(result.config_content, str(config_file), "text")

                    # Write summary
                    summary = {
                        "success": True,
                        "message": "Layout workflow completed",
                        "files": {
                            "keymap": str(keymap_file),
                            "config": str(config_file),
                        },
                    }
                    self.write_output(summary, str(output_dir / "summary.json"), "json")

                return result

        # Setup test data
        input_file = tmp_path / "complete_layout.json"
        output_dir = tmp_path / "layout_output"
        output_dir.mkdir(parents=True)

        with input_file.open("w") as f:
            json.dump(sample_complete_layout, f)

        # Mock successful layout service
        mock_result = LayoutResult(
            success=True,
            keymap_content="// Generated keymap content for end-to-end test",
            config_content="# Generated config content for end-to-end test",
            errors=[],
        )

        command = LayoutWorkflowCommand()

        with patch("glovebox.layout.create_layout_service") as mock_service_factory:
            mock_service = Mock()
            mock_service.compile.return_value = mock_result
            mock_service_factory.return_value = mock_service

            # Execute complete workflow
            result = command.execute_complete_layout_workflow(
                input_source=str(input_file), output_dir=output_dir
            )

            # Verify workflow completion
            assert result.success is True

            # Verify output files were created
            assert (output_dir / "layout.keymap").exists()
            assert (output_dir / "layout.conf").exists()
            assert (output_dir / "summary.json").exists()

            # Verify file contents
            keymap_content = (output_dir / "layout.keymap").read_text()
            assert "Generated keymap content" in keymap_content

            config_content = (output_dir / "layout.conf").read_text()
            assert "Generated config content" in config_content

            summary = json.loads((output_dir / "summary.json").read_text())
            assert summary["success"] is True
            assert "Layout workflow completed" in summary["message"]

    def test_stdin_to_layout_stdout_workflow(self, sample_complete_layout):
        """Test workflow: stdin JSON → layout service → stdout result."""

        class StdinLayoutCommand(IOCommand):
            def process_stdin_layout(self):
                # Load from stdin
                layout_data = self.load_json_input("-")

                # Process with layout service
                from glovebox.layout import create_layout_service

                service = create_layout_service()
                result = service.compile(layout_data)

                # Format for stdout
                if result.success:
                    output = {
                        "success": True,
                        "title": layout_data.get("title", "Unknown"),
                        "layers": len(layout_data.get("layers", [])),
                        "combos": len(layout_data.get("combos", [])),
                        "macros": len(layout_data.get("macros", [])),
                    }
                else:
                    output = {"success": False, "errors": result.errors}

                self.format_and_print(output, "json")
                return output

        command = StdinLayoutCommand()

        # Mock successful layout service
        mock_result = LayoutResult(
            success=True,
            keymap_content="mock keymap",
            config_content="mock config",
            errors=[],
        )

        with (
            patch("glovebox.layout.create_layout_service") as mock_service_factory,
            patch(
                "glovebox.core.io.handlers.InputHandler.load_json_input"
            ) as mock_load_json,
            patch.object(command, "format_and_print") as mock_print,
        ):
            mock_service = Mock()
            mock_service.compile.return_value = mock_result
            mock_service_factory.return_value = mock_service
            mock_load_json.return_value = sample_complete_layout

            # Execute stdin workflow
            result = command.process_stdin_layout()

            # Verify workflow
            assert result["success"] is True
            assert result["title"] == "End-to-End Test Layout"
            assert result["layers"] == 3
            assert result["combos"] == 2
            assert result["macros"] == 1

            # Verify JSON output was printed
            mock_print.assert_called_once_with(result, "json")


class TestCompleteFirmwareWorkflow:
    """Test the complete firmware compilation and flashing pipeline."""

    def test_json_to_firmware_to_flash_end_to_end(
        self, tmp_path: Path, sample_complete_layout
    ):
        """Test complete workflow: JSON → Compilation → Firmware → Flash."""

        class FirmwareWorkflowCommand(IOCommand):
            def execute_complete_firmware_workflow(
                self, input_source, output_dir, device_path=None
            ):
                # Step 1: Load JSON input
                layout_data = self.load_json_input(input_source)

                # Step 2: Compile to firmware
                from glovebox.compilation import create_compilation_service

                compilation_service = create_compilation_service(
                    method_type="zmk_config"
                )

                compile_result = compilation_service.compile_from_data(
                    layout_data=layout_data,
                    output_dir=output_dir,
                    keyboard_profile=None,  # Would be resolved in real usage
                )

                if not compile_result.success:
                    return {
                        "success": False,
                        "stage": "compilation",
                        "errors": compile_result.errors,
                    }

                # Step 3: Flash firmware to device
                from glovebox.firmware.flash import create_flash_service

                flash_service = create_flash_service()

                # Get first firmware file
                firmware_file = compile_result.output_files.uf2_files[0]

                flash_result = flash_service.flash(
                    firmware_file=firmware_file,
                    device_path=device_path,
                    profile=None,  # Would be resolved in real usage
                )

                # Step 4: Create workflow summary
                workflow_result = {
                    "success": flash_result.success,
                    "stages": {
                        "compilation": {
                            "success": compile_result.success,
                            "output_files": len(compile_result.output_files.uf2_files),
                            "messages": compile_result.messages,
                        },
                        "flash": {
                            "success": flash_result.success,
                            "devices_flashed": flash_result.devices_flashed,
                            "messages": flash_result.messages,
                        },
                    },
                }

                # Write workflow summary
                self.write_output(
                    workflow_result, str(output_dir / "workflow.json"), "json"
                )

                return workflow_result

        # Setup test data
        input_file = tmp_path / "firmware_layout.json"
        output_dir = tmp_path / "firmware_output"
        output_dir.mkdir(parents=True)

        with input_file.open("w") as f:
            json.dump(sample_complete_layout, f)

        # Mock successful compilation
        firmware_file = output_dir / "glove80.uf2"
        firmware_file.write_bytes(b"mock firmware content")

        mock_compile_result = BuildResult(
            success=True,
            messages=["Compilation successful"],
            output_files=FirmwareOutputFiles(
                output_dir=output_dir, uf2_files=[firmware_file]
            ),
        )

        # Mock successful flash
        from glovebox.firmware.flash.models import FlashResult

        mock_flash_result = FlashResult(success=True, devices_flashed=1)
        mock_flash_result.add_message("Firmware flashed successfully")

        command = FirmwareWorkflowCommand()

        with (
            patch(
                "glovebox.compilation.create_compilation_service"
            ) as mock_compile_factory,
            patch("glovebox.firmware.flash.create_flash_service") as mock_flash_factory,
        ):
            # Mock compilation service
            mock_compile_service = Mock()
            mock_compile_service.compile_from_data.return_value = mock_compile_result
            mock_compile_factory.return_value = mock_compile_service

            # Mock flash service
            mock_flash_service = Mock()
            mock_flash_service.flash.return_value = mock_flash_result
            mock_flash_factory.return_value = mock_flash_service

            # Execute complete workflow
            result = command.execute_complete_firmware_workflow(
                input_source=str(input_file),
                output_dir=output_dir,
                device_path="/dev/test_device",
            )

            # Verify complete workflow
            assert result["success"] is True
            assert result["stages"]["compilation"]["success"] is True
            assert result["stages"]["flash"]["success"] is True
            assert result["stages"]["flash"]["devices_flashed"] == 1

            # Verify workflow summary was written
            workflow_file = output_dir / "workflow.json"
            assert workflow_file.exists()

            workflow_data = json.loads(workflow_file.read_text())
            assert workflow_data["success"] is True

    def test_compilation_failure_stops_flash_workflow(
        self, tmp_path: Path, sample_complete_layout
    ):
        """Test that compilation failure prevents flash step."""

        class FailureWorkflowCommand(IOCommand):
            def execute_workflow_with_failure_handling(self, input_source, output_dir):
                try:
                    # Step 1: Load JSON
                    layout_data = self.load_json_input(input_source)

                    # Step 2: Attempt compilation
                    from glovebox.compilation import create_compilation_service

                    compilation_service = create_compilation_service(
                        method_type="zmk_config"
                    )

                    compile_result = compilation_service.compile_from_data(
                        layout_data=layout_data,
                        output_dir=output_dir,
                        keyboard_profile=None,
                    )

                    if not compile_result.success:
                        # Compilation failed - do not proceed to flash
                        error_summary = {
                            "success": False,
                            "stage_failed": "compilation",
                            "errors": compile_result.errors,
                            "flash_attempted": False,
                        }
                        self.write_output(
                            error_summary, str(output_dir / "error.json"), "json"
                        )
                        return error_summary

                    # Would proceed to flash here if compilation succeeded

                except Exception as e:
                    self.handle_service_error(e, "firmware workflow")

        # Setup test data
        input_file = tmp_path / "invalid_layout.json"
        output_dir = tmp_path / "error_output"
        output_dir.mkdir(parents=True)

        # Create invalid layout (missing required fields)
        invalid_layout = {"title": "Invalid Layout"}
        with input_file.open("w") as f:
            json.dump(invalid_layout, f)

        # Mock compilation failure
        mock_compile_result = BuildResult(
            success=False,
            errors=[
                "Missing required field: keyboard",
                "Missing required field: layers",
            ],
            messages=[],
        )

        command = FailureWorkflowCommand()

        with patch(
            "glovebox.compilation.create_compilation_service"
        ) as mock_compile_factory:
            mock_compile_service = Mock()
            mock_compile_service.compile_from_data.return_value = mock_compile_result
            mock_compile_factory.return_value = mock_compile_service

            # Execute workflow with failure
            result = command.execute_workflow_with_failure_handling(
                input_source=str(input_file), output_dir=output_dir
            )

            # Verify failure handling
            assert result["success"] is False
            assert result["stage_failed"] == "compilation"
            assert result["flash_attempted"] is False
            assert "Missing required field: keyboard" in result["errors"]

            # Verify error file was written
            error_file = output_dir / "error.json"
            assert error_file.exists()


class TestLibraryIntegrationWorkflow:
    """Test library reference integration in workflows."""

    def test_library_reference_to_output_workflow(self, tmp_path: Path):
        """Test workflow: @library reference → service → output."""

        class LibraryWorkflowCommand(IOCommand):
            def process_library_layout(self, library_ref, output_dir):
                # Load from library reference
                layout_data = self.load_json_input(library_ref)

                # Process with layout service
                from glovebox.layout import create_layout_service

                service = create_layout_service()
                result = service.compile(layout_data)

                if result.success:
                    # Write processed library layout
                    output_data = {
                        "source": "library",
                        "reference": library_ref,
                        "title": layout_data.get("title", "Unknown"),
                        "processed": True,
                        "keymap_lines": len(result.keymap_content.split("\n"))
                        if result.keymap_content
                        else 0,
                        "config_lines": len(result.config_content.split("\n"))
                        if result.config_content
                        else 0,
                    }
                else:
                    output_data = {
                        "source": "library",
                        "reference": library_ref,
                        "processed": False,
                        "errors": result.errors,
                    }

                self.write_output(
                    output_data, str(output_dir / "library_result.json"), "json"
                )
                return output_data

        output_dir = tmp_path / "library_output"
        output_dir.mkdir(parents=True)

        # Mock library data
        mock_library_layout = {
            "keyboard": "glove80",
            "title": "Library Test Layout",
            "layers": [["KC_A", "KC_B", "KC_C"]],
            "layer_names": ["Base"],
        }

        # Mock successful layout processing
        mock_result = LayoutResult(
            success=True,
            keymap_content="// Library keymap\nline 1\nline 2\nline 3",
            config_content="# Library config\nconfig line 1\nconfig line 2",
            errors=[],
        )

        command = LibraryWorkflowCommand()

        with (
            patch(
                "glovebox.core.io.handlers.InputHandler.load_json_input"
            ) as mock_load_json,
            patch("glovebox.layout.create_layout_service") as mock_service_factory,
        ):
            mock_load_json.return_value = mock_library_layout

            mock_service = Mock()
            mock_service.compile.return_value = mock_result
            mock_service_factory.return_value = mock_service

            # Execute library workflow
            result = command.process_library_layout(
                library_ref="@test/library_layout", output_dir=output_dir
            )

            # Verify library processing
            assert result["source"] == "library"
            assert result["reference"] == "@test/library_layout"
            assert result["processed"] is True
            assert result["title"] == "Library Test Layout"
            assert result["keymap_lines"] == 4  # 4 lines in mock keymap
            assert result["config_lines"] == 3  # 3 lines in mock config

            # Verify result file was written
            result_file = output_dir / "library_result.json"
            assert result_file.exists()

            # Verify library reference was loaded
            mock_load_json.assert_called_once_with("@test/library_layout")


class TestErrorHandlingWorkflows:
    """Test error handling in end-to-end workflows."""

    def test_invalid_input_error_propagation(self, tmp_path: Path):
        """Test error propagation through the complete workflow."""

        class ErrorHandlingCommand(IOCommand):
            def execute_with_error_handling(self, input_source):
                try:
                    # Attempt to load invalid JSON
                    layout_data = self.load_json_input(input_source)
                    return {"success": True, "data": layout_data}

                except ValueError as e:
                    # Handle JSON parsing errors
                    return {
                        "success": False,
                        "error_type": "json_parsing",
                        "error_message": str(e),
                    }
                except Exception as e:
                    # Handle other errors
                    return {
                        "success": False,
                        "error_type": "general",
                        "error_message": str(e),
                    }

        # Create invalid JSON file
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text('{"invalid": json syntax}')

        command = ErrorHandlingCommand()

        # Test invalid JSON error handling
        result = command.execute_with_error_handling(str(invalid_file))

        assert result["success"] is False
        assert result["error_type"] == "json_parsing"
        assert "Invalid JSON" in result["error_message"]

    def test_service_error_handling_workflow(self, tmp_path: Path):
        """Test service error handling in workflows."""

        class ServiceErrorCommand(IOCommand):
            def execute_with_service_error_handling(self, input_source):
                try:
                    layout_data = self.load_json_input(input_source)

                    # Create service that will fail
                    from glovebox.layout import create_layout_service

                    service = create_layout_service()
                    result = service.compile(layout_data)

                    if not result.success:
                        return {
                            "success": False,
                            "error_type": "service_failure",
                            "service_errors": result.errors,
                        }

                    return {"success": True, "result": "processed"}

                except Exception as e:
                    exc_info = self.logger.isEnabledFor(logging.DEBUG)
                    self.logger.error("Service error: %s", e, exc_info=exc_info)
                    return {
                        "success": False,
                        "error_type": "service_exception",
                        "error_message": str(e),
                    }

        # Create minimal but problematic layout
        problem_file = tmp_path / "problem.json"
        problem_layout = {
            "keyboard": "glove80",
            "title": "Problem Layout",
            "layers": [],  # Empty layers might cause issues
            "layer_names": [],
        }
        with problem_file.open("w") as f:
            json.dump(problem_layout, f)

        # Mock service failure
        mock_result = LayoutResult(
            success=False,
            keymap_content=None,
            config_content=None,
            errors=["Empty layers not allowed", "No valid key bindings found"],
        )

        command = ServiceErrorCommand()

        with patch("glovebox.layout.create_layout_service") as mock_service_factory:
            mock_service = Mock()
            mock_service.compile.return_value = mock_result
            mock_service_factory.return_value = mock_service

            # Execute with service failure
            result = command.execute_with_service_error_handling(str(problem_file))

            # Verify error handling
            assert result["success"] is False
            assert result["error_type"] == "service_failure"
            assert "Empty layers not allowed" in result["service_errors"]
            assert "No valid key bindings found" in result["service_errors"]
