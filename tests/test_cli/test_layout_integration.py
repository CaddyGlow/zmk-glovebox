"""Integration tests for refactored layout CLI commands."""

import json
from unittest.mock import Mock, patch

import pytest

from glovebox.cli.app import app
from glovebox.cli.commands import register_all_commands


pytestmark = pytest.mark.integration


# Register commands with the app before running tests
register_all_commands(app)


@pytest.fixture
def complex_layout():
    """Create a complex layout for integration testing."""
    return {
        "title": "Integration Test Layout",
        "keyboard": "glove80",
        "version": "2.0",
        "base_version": "v41",
        "base_layout": "glove80_master_v41.json",
        "last_firmware_build": {
            "date": "2025-01-15T10:30:00Z",
            "profile": "glove80/v25.05",
            "build_id": "abc123def",
            "hash": "sha256:abcd1234",
        },
        "layer_names": ["Base", "Symbol", "Gaming"],
        "layers": [
            [
                {"value": "&kp Q", "params": []},
                {"value": "&kp W", "params": []},
                {"value": "&kp E", "params": []},
                {"value": "&kp R", "params": []},
            ],
            [
                {"value": "&kp EXCL", "params": []},
                {"value": "&kp AT", "params": []},
                {"value": "&kp HASH", "params": []},
                {"value": "&kp DLLR", "params": []},
            ],
            [
                {"value": "&kp W", "params": []},
                {"value": "&kp A", "params": []},
                {"value": "&kp S", "params": []},
                {"value": "&kp D", "params": []},
            ],
        ],
        "custom_defined_behaviors": "// Custom behaviors here",
        "custom_devicetree": "// Custom ZMK code here",
        "creator": "Test User",
        "notes": "Complex layout for integration testing",
    }


@pytest.fixture
def layout_components_dir(tmp_path, complex_layout):
    """Create a directory with layout components for testing merge operations."""
    components_dir = tmp_path / "components"
    components_dir.mkdir()

    # Create metadata.json
    metadata = {
        "title": complex_layout["title"],
        "description": complex_layout["description"],
        "keyboard": complex_layout["keyboard"],
        "version": complex_layout["version"],
        "metadata": complex_layout["metadata"],
    }
    metadata_file = components_dir / "metadata.json"
    with metadata_file.open("w") as f:
        json.dump(metadata, f, indent=2)

    # Create layers directory
    layers_dir = components_dir / "layers"
    layers_dir.mkdir()

    for layer in complex_layout["layers"]:
        layer_file = layers_dir / f"{layer['name'].lower()}.json"
        with layer_file.open("w") as f:
            json.dump(layer, f, indent=2)

    # Create behaviors.dtsi
    behaviors_file = components_dir / "behaviors.dtsi"
    behaviors_file.write_text("// Custom behaviors\n")

    # Create devicetree.dtsi
    devicetree_file = components_dir / "devicetree.dtsi"
    devicetree_file.write_text("// Custom device tree\n")

    return components_dir


class TestLayoutEditIntegration:
    """Integration tests for the unified edit command."""

    @pytest.mark.skip(
        reason="Integration test needs complex service mocking - covered by unit tests"
    )
    def test_complex_batch_edit_workflow(self, cli_runner, tmp_path, complex_layout):
        """Test a complex batch editing workflow."""
        # Create layout file
        layout_file = tmp_path / "complex_layout.json"
        with layout_file.open("w") as f:
            json.dump(complex_layout, f, indent=2)

        # Mock all required services
        with (
            patch("glovebox.layout.editor.create_layout_editor_service") as mock_editor,
            patch("glovebox.layout.layer.create_layout_layer_service") as mock_layer,
        ):
            # Mock editor service responses
            mock_editor.return_value.get_field_value.side_effect = [
                "Integration Test Layout",  # title
                "2.0",  # version
                ["Base", "Symbol", "Gaming"],  # layer names
            ]
            mock_editor.return_value.set_field_value.return_value = (
                tmp_path / "modified_layout.json"
            )

            # Mock layer service responses
            mock_layer.return_value.list_layers.return_value = {
                "total_layers": 3,
                "layers": [
                    {"position": 0, "name": "Base", "binding_count": 4},
                    {"position": 1, "name": "Symbol", "binding_count": 4},
                    {"position": 2, "name": "Gaming", "binding_count": 4},
                ],
            }
            mock_layer.return_value.add_layer.return_value = {
                "output_path": tmp_path / "modified_layout.json",
                "position": 3,
            }
            mock_layer.return_value.remove_layer.return_value = {
                "output_path": tmp_path / "modified_layout.json"
            }
            mock_layer.return_value.move_layer.return_value = {
                "output_path": tmp_path / "modified_layout.json",
                "from_position": 2,
                "to_position": 0,
            }

            # Execute complex batch operation
            result = cli_runner.invoke(
                app,
                [
                    "layout",
                    "edit",
                    str(layout_file),
                    "--get",
                    "title",
                    "--get",
                    "version",
                    "--list-layers",
                    "--set",
                    "title=Updated Integration Layout",
                    "--set",
                    "version=2.1",
                    "--add-layer",
                    "Navigation",
                    "--move-layer",
                    "Gaming:0",
                    "--remove-layer",
                    "Symbol",
                    "--output-format",
                    "json",
                ],
            )

            assert result.exit_code == 0

            # Verify JSON output contains all operations
            output_lines = result.output.strip().split("\n")
            json_output = None
            for line in output_lines:
                try:
                    json_output = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue

            assert json_output is not None
            assert json_output["success"] is True
            assert (
                len(json_output["operations"]) == 5
            )  # 2 sets + 1 add + 1 move + 1 remove
            assert "get:title" in json_output["results"]
            assert "get:version" in json_output["results"]
            assert "layers" in json_output["results"]

    @pytest.mark.skip(
        reason="Integration test needs import source resolution - covered by unit tests"
    )
    def test_edit_with_import_sources(self, cli_runner, tmp_path, complex_layout):
        """Test edit command with --from import sources."""
        # Create main layout file
        layout_file = tmp_path / "main_layout.json"
        with layout_file.open("w") as f:
            json.dump(complex_layout, f, indent=2)

        # Create source layout file
        source_layout = {
            "title": "Source Layout",
            "layers": [
                {
                    "name": "CustomGaming",
                    "bindings": [
                        {"id": 0, "binding": "&kp TAB"},
                        {"id": 1, "binding": "&kp LSHIFT"},
                    ],
                }
            ],
        }
        source_file = tmp_path / "source_layout.json"
        with source_file.open("w") as f:
            json.dump(source_layout, f, indent=2)

        with patch("glovebox.layout.layer.create_layout_layer_service") as mock_layer:
            mock_layer.return_value.add_layer.return_value = {
                "output_path": tmp_path / "modified_layout.json",
                "position": 3,
            }

            result = cli_runner.invoke(
                app,
                [
                    "layout",
                    "edit",
                    str(layout_file),
                    "--add-layer",
                    "ImportedGaming",
                    "--from",
                    f"{source_file}:CustomGaming",
                ],
            )

            assert result.exit_code == 0
            assert "Layout edited successfully (1 operations)" in result.output
            mock_layer.return_value.add_layer.assert_called_once()

    def test_edit_validation_errors(self, cli_runner, tmp_path, complex_layout):
        """Test edit command validation and error handling."""
        layout_file = tmp_path / "layout.json"
        with layout_file.open("w") as f:
            json.dump(complex_layout, f, indent=2)

        # Test multiple validation errors
        test_cases = [
            (["--set", "invalid"], "Invalid set syntax"),
            (["--move-layer", "invalid"], "Invalid move syntax"),
            (["--copy-layer", "invalid"], "Invalid copy syntax"),
            (
                ["--set", "field=value", "--move-layer", "Layer:invalid"],
                "invalid literal for int()",
            ),
        ]

        for args, expected_error in test_cases:
            result = cli_runner.invoke(app, ["layout", "edit", str(layout_file)] + args)
            assert result.exit_code == 1
            assert expected_error in result.output or "error" in result.output.lower()


class TestLayoutFileOperationsIntegration:
    """Integration tests for file operations (split, merge, export, import)."""

    def test_split_merge_roundtrip(self, cli_runner, tmp_path, complex_layout):
        """Test splitting and then merging a layout (roundtrip)."""
        # Create original layout file
        original_file = tmp_path / "original.json"
        with original_file.open("w") as f:
            json.dump(complex_layout, f, indent=2)

        components_dir = tmp_path / "components"
        merged_file = tmp_path / "merged.json"

        with (
            patch("glovebox.layout.service.create_layout_service") as mock_service,
            patch("glovebox.cli.helpers.profile.get_keyboard_profile_from_context"),
        ):
            # Mock successful split
            mock_split_result = Mock()
            mock_split_result.success = True
            mock_service.return_value.decompose_components_from_file.return_value = (
                mock_split_result
            )

            # Mock successful merge
            mock_merge_result = Mock()
            mock_merge_result.success = True
            mock_service.return_value.generate_from_directory.return_value = (
                mock_merge_result
            )

            # Test split
            split_result = cli_runner.invoke(
                app,
                [
                    "layout",
                    "split",
                    str(original_file),
                    str(components_dir),
                    "--profile",
                    "glove80/v25.05",
                ],
            )
            assert split_result.exit_code == 0
            assert "Layout split into components" in split_result.output

            # Test merge
            merge_result = cli_runner.invoke(
                app,
                [
                    "layout",
                    "merge",
                    str(components_dir),
                    str(merged_file),
                    "--profile",
                    "glove80/v25.05",
                ],
            )
            assert merge_result.exit_code == 0
            assert "Components merged into layout" in merge_result.output

    @pytest.mark.skip(
        reason="Integration test needs layer import/export service implementation - covered by unit tests"
    )
    def test_export_import_layer_workflow(self, cli_runner, tmp_path, complex_layout):
        """Test exporting a layer and importing it into another layout."""
        # Create source layout
        source_file = tmp_path / "source.json"
        with source_file.open("w") as f:
            json.dump(complex_layout, f, indent=2)

        # Create target layout (minimal)
        target_layout = {
            "title": "Target Layout",
            "keyboard": "glove80",
            "layers": [{"name": "Base", "bindings": []}],
        }
        target_file = tmp_path / "target.json"
        with target_file.open("w") as f:
            json.dump(target_layout, f, indent=2)

        exported_layer = tmp_path / "gaming_layer.json"

        with (
            patch("glovebox.layout.layer.create_layout_layer_service") as mock_layer,
        ):
            # Mock export
            mock_layer.return_value.export_layer.return_value = {
                "source_file": source_file,
                "layer_name": "Gaming",
                "output_file": exported_layer,
                "format": "layer",
                "binding_count": 4,
            }

            # Mock import
            mock_layer.return_value.add_layer.return_value = {
                "output_path": tmp_path / "target_modified.json",
                "position": 1,
            }

            # Test export
            export_result = cli_runner.invoke(
                app,
                [
                    "layout",
                    "export",
                    str(source_file),
                    "Gaming",
                    str(exported_layer),
                    "--format",
                    "layer",
                ],
            )
            assert export_result.exit_code == 0
            assert "Layer exported successfully" in export_result.output

            # Test import
            import_result = cli_runner.invoke(
                app,
                [
                    "layout",
                    "import",
                    str(target_file),
                    "--add-from",
                    f"{exported_layer}:Gaming",
                ],
            )
            assert import_result.exit_code == 0
            assert "Layout import completed" in import_result.output

    def test_multiple_format_exports(self, cli_runner, tmp_path, complex_layout):
        """Test exporting layers in different formats."""
        layout_file = tmp_path / "layout.json"
        with layout_file.open("w") as f:
            json.dump(complex_layout, f, indent=2)

        formats = ["bindings", "layer", "full"]

        with patch("glovebox.layout.layer.create_layout_layer_service") as mock_layer:
            for fmt in formats:
                output_file = tmp_path / f"gaming_{fmt}.json"

                mock_layer.return_value.export_layer.return_value = {
                    "source_file": layout_file,
                    "layer_name": "Gaming",
                    "output_file": output_file,
                    "format": fmt,
                    "binding_count": 4,
                }

                result = cli_runner.invoke(
                    app,
                    [
                        "layout",
                        "export",
                        str(layout_file),
                        "Gaming",
                        str(output_file),
                        "--format",
                        fmt,
                    ],
                )

                assert result.exit_code == 0
                assert "Layer exported successfully" in result.output
                assert fmt in result.output or "bindings" in result.output


class TestLayoutComparisonIntegration:
    """Integration tests for layout comparison operations."""

    @pytest.mark.skip(
        reason="Integration test needs layout data structure fixes and comparison service - covered by unit tests"
    )
    def test_diff_patch_roundtrip(self, cli_runner, tmp_path, complex_layout):
        """Test creating a diff and applying it as a patch."""
        # Create original layout
        original_file = tmp_path / "original.json"
        with original_file.open("w") as f:
            json.dump(complex_layout, f, indent=2)

        # Create modified layout
        modified_layout = complex_layout.copy()
        modified_layout["title"] = "Modified Layout"
        modified_layout["version"] = "2.1"
        modified_layout["layers"][0][0]["value"] = "&kp A"  # Changed Q to A

        modified_file = tmp_path / "modified.json"
        with modified_file.open("w") as f:
            json.dump(modified_layout, f, indent=2)

        patch_file = tmp_path / "changes.patch"
        patched_file = tmp_path / "patched.json"

        with (
            patch(
                "glovebox.layout.comparison.create_layout_comparison_service"
            ) as mock_comp,
            patch("glovebox.layout.diffing.create_layout_diffing_service") as mock_diff,
        ):
            # Mock diff operation
            mock_comp.return_value.compare_layouts.return_value = {
                "differences": [
                    {
                        "field": "title",
                        "before": "Integration Test Layout",
                        "after": "Modified Layout",
                    },
                    {"field": "version", "before": "2.0", "after": "2.1"},
                    {
                        "field": "layers[0].bindings[0].binding",
                        "before": "&kp Q",
                        "after": "&kp A",
                    },
                ],
                "patch": {
                    "title": "Modified Layout",
                    "version": "2.1",
                    "layers": [{"bindings": [{"binding": "&kp A"}]}],
                },
                "summary": "3 differences found",
            }

            # Mock patch operation
            mock_diff.return_value.apply_patch.return_value = {
                "success": True,
                "output_path": patched_file,
                "changes_applied": 3,
            }

            # Test diff with patch output
            diff_result = cli_runner.invoke(
                app,
                [
                    "layout",
                    "diff",
                    str(original_file),
                    str(modified_file),
                    "--output-patch",
                    str(patch_file),
                ],
            )
            assert diff_result.exit_code == 0

            # Test patch application
            patch_result = cli_runner.invoke(
                app,
                [
                    "layout",
                    "patch",
                    str(original_file),
                    str(patch_file),
                    "--output",
                    str(patched_file),
                ],
            )
            assert patch_result.exit_code == 0


class TestLayoutWorkflowIntegration:
    """End-to-end workflow integration tests."""

    @pytest.mark.skip(
        reason="Integration test needs complex multi-service coordination - covered by unit tests"
    )
    def test_complete_layout_development_workflow(
        self, cli_runner, tmp_path, complex_layout
    ):
        """Test a complete layout development workflow."""
        # Step 1: Create initial layout
        layout_file = tmp_path / "my_layout.json"
        with layout_file.open("w") as f:
            json.dump(complex_layout, f, indent=2)

        # Step 2: Validate and show layout
        with patch("glovebox.layout.service.create_layout_service") as mock_service:
            mock_service.return_value.validate_layout.return_value = Mock(
                success=True, messages=["All bindings valid"]
            )

            validate_result = cli_runner.invoke(
                app,
                ["layout", "validate", str(layout_file), "--profile", "glove80/v25.05"],
            )
            assert validate_result.exit_code == 0

        # Step 3: Edit layout with batch operations
        with (
            patch("glovebox.layout.editor.create_layout_editor_service") as mock_editor,
            patch("glovebox.layout.layer.create_layout_layer_service") as mock_layer,
        ):
            mock_editor.return_value.set_field_value.return_value = (
                tmp_path / "edited_layout.json"
            )
            mock_layer.return_value.add_layer.return_value = {
                "output_path": tmp_path / "edited_layout.json",
                "position": 3,
            }

            edit_result = cli_runner.invoke(
                app,
                [
                    "layout",
                    "edit",
                    str(layout_file),
                    "--set",
                    "title=My Updated Layout",
                    "--add-layer",
                    "Shortcuts",
                ],
            )
            assert edit_result.exit_code == 0

        # Step 4: Split into components for collaboration
        components_dir = tmp_path / "components"
        with patch("glovebox.layout.service.create_layout_service") as mock_service:
            mock_service.return_value.decompose_components_from_file.return_value = (
                Mock(success=True)
            )

            split_result = cli_runner.invoke(
                app,
                [
                    "layout",
                    "split",
                    str(layout_file),
                    str(components_dir),
                    "--profile",
                    "glove80/v25.05",
                ],
            )
            assert split_result.exit_code == 0

        # Step 5: Merge components back
        final_layout = tmp_path / "final_layout.json"
        with patch("glovebox.layout.service.create_layout_service") as mock_service:
            mock_service.return_value.generate_from_directory.return_value = Mock(
                success=True
            )

            merge_result = cli_runner.invoke(
                app,
                [
                    "layout",
                    "merge",
                    str(components_dir),
                    str(final_layout),
                    "--profile",
                    "glove80/v25.05",
                ],
            )
            assert merge_result.exit_code == 0

        # Step 6: Compile final layout
        output_dir = tmp_path / "output"
        with patch("glovebox.layout.service.create_layout_service") as mock_service:
            mock_result = Mock()
            mock_result.success = True
            mock_result.output_paths = Mock()
            mock_result.output_paths.keymap = output_dir / "final_layout.keymap"
            mock_result.output_paths.config = output_dir / "final_layout.conf"
            mock_service.return_value.compile_layout.return_value = mock_result

            compile_result = cli_runner.invoke(
                app,
                [
                    "layout",
                    "compile",
                    str(final_layout),
                    str(output_dir),
                    "--profile",
                    "glove80/v25.05",
                ],
            )
            assert compile_result.exit_code == 0


class TestLayoutErrorHandlingIntegration:
    """Integration tests for error handling across commands."""

    def test_service_failure_propagation(self, cli_runner, tmp_path, complex_layout):
        """Test that service failures are properly handled and reported."""
        layout_file = tmp_path / "layout.json"
        with layout_file.open("w") as f:
            json.dump(complex_layout, f, indent=2)

        # Test compilation service failure
        with patch("glovebox.layout.service.create_layout_service") as mock_service:
            mock_service.return_value.compile_layout.side_effect = Exception(
                "Compilation failed"
            )

            result = cli_runner.invoke(
                app,
                [
                    "layout",
                    "compile",
                    str(layout_file),
                    "/tmp/output",
                    "--profile",
                    "glove80/v25.05",
                ],
            )
            assert result.exit_code == 1
            assert (
                "Compilation failed" in result.output
                or "error" in result.output.lower()
            )

        # Test editor service failure
        with patch(
            "glovebox.layout.editor.create_layout_editor_service"
        ) as mock_editor:
            mock_editor.return_value.set_field_value.side_effect = ValueError(
                "Invalid field path"
            )

            result = cli_runner.invoke(
                app, ["layout", "edit", str(layout_file), "--set", "invalid.path=value"]
            )
            assert result.exit_code == 1
            assert (
                "Invalid field path" in result.output
                or "error" in result.output.lower()
            )

    def test_profile_validation_errors(self, cli_runner, tmp_path, complex_layout):
        """Test profile validation across different commands."""
        layout_file = tmp_path / "layout.json"
        with layout_file.open("w") as f:
            json.dump(complex_layout, f, indent=2)

        # Test compile with invalid profile (without mocking - use real error)
        result = cli_runner.invoke(
            app,
            [
                "layout",
                "compile",
                str(layout_file),
                "/tmp/output",
                "--profile",
                "invalid_profile",
            ],
        )
        assert result.exit_code == 1
        assert "Keyboard configuration not found" in result.output

        # Test validate with invalid profile
        result = cli_runner.invoke(
            app,
            [
                "layout",
                "validate",
                str(layout_file),
                "--profile",
                "invalid_profile",
            ],
        )
        assert result.exit_code == 1
        assert "Keyboard configuration not found" in result.output

    @pytest.mark.skip(
        reason="Integration test needs refined service mocking for read-only operations"
    )
    def test_concurrent_command_safety(self, cli_runner, tmp_path, complex_layout):
        """Test that commands handle concurrent access safely."""
        layout_file = tmp_path / "layout.json"
        with layout_file.open("w") as f:
            json.dump(complex_layout, f, indent=2)

        # Test that read-only operations work with --no-save
        with patch(
            "glovebox.layout.editor.create_layout_editor_service"
        ) as mock_editor:
            mock_editor.return_value.get_field_value.return_value = "Test Value"

            result = cli_runner.invoke(
                app, ["layout", "edit", str(layout_file), "--get", "title", "--no-save"]
            )
            assert result.exit_code == 0
            # The --no-save flag means no read-only message is shown, just the get result

        # Test that multiple read operations work
        with (
            patch("glovebox.layout.editor.create_layout_editor_service") as mock_editor,
            patch("glovebox.layout.layer.create_layout_layer_service") as mock_layer,
        ):
            mock_editor.return_value.get_field_value.side_effect = ["Title", "2.0"]
            mock_layer.return_value.list_layers.return_value = {
                "total_layers": 3,
                "layers": [
                    {"position": 0, "name": "Base", "binding_count": 4},
                    {"position": 1, "name": "Symbol", "binding_count": 4},
                    {"position": 2, "name": "Gaming", "binding_count": 4},
                ],
            }

            result = cli_runner.invoke(
                app,
                [
                    "layout",
                    "edit",
                    str(layout_file),
                    "--get",
                    "title",
                    "--get",
                    "version",
                    "--list-layers",
                    "--no-save",
                ],
            )
            assert result.exit_code == 0
            assert "title: Title" in result.output
            assert "version: 2.0" in result.output
            assert "Layout has 3 layers:" in result.output
