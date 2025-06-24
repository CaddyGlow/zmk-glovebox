"""Integration tests for the migrated layout comparison service.

These tests verify that the comparison service migration from DeepDiff to the new
diffing library maintains compatibility with the CLI and produces expected outputs.
"""

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest

from glovebox.layout.comparison import create_layout_comparison_service
from glovebox.layout.models import LayoutBinding, LayoutData, LayoutParam


class TestComparisonServiceMigration:
    """Test suite for the migrated comparison service."""

    @pytest.fixture
    def test_layouts(self):
        """Create test layout data for comparison."""

        def create_test_layout(layer_names, layers_data, title="Test Layout"):
            layers = []
            for layer_data in layers_data:
                layer_bindings = []
                for binding_str in layer_data:
                    parts = binding_str.split()
                    if len(parts) >= 2:
                        binding = LayoutBinding(
                            value=parts[0],
                            params=[LayoutParam(value=parts[1])]
                            if len(parts) > 1
                            else [],
                        )
                    else:
                        binding = LayoutBinding(value=binding_str, params=[])
                    layer_bindings.append(binding)
                layers.append(layer_bindings)

            return LayoutData(
                keyboard="test_keyboard",
                title=title,
                layer_names=layer_names,
                layers=layers,
                version="1.0.0",
                uuid="test-uuid",
            )

        # Base layout
        base_layout = create_test_layout(
            ["base", "lower", "raise", "adjust"],
            [
                ["&kp Q", "&kp W", "&kp E", "&kp R", "&kp T"],
                ["&kp N1", "&kp N2", "&kp N3", "&kp N4", "&kp N5"],
                ["&kp F1", "&kp F2", "&kp F3", "&kp F4", "&kp F5"],
                [
                    "&kp C_PREV",
                    "&kp C_PLAY",
                    "&kp C_NEXT",
                    "&kp C_VOL_DN",
                    "&kp C_VOL_UP",
                ],
            ],
        )

        # Single key change: Q -> A
        single_change_layout = create_test_layout(
            ["base", "lower", "raise", "adjust"],
            [
                ["&kp A", "&kp W", "&kp E", "&kp R", "&kp T"],  # Q -> A
                ["&kp N1", "&kp N2", "&kp N3", "&kp N4", "&kp N5"],
                ["&kp F1", "&kp F2", "&kp F3", "&kp F4", "&kp F5"],
                [
                    "&kp C_PREV",
                    "&kp C_PLAY",
                    "&kp C_NEXT",
                    "&kp C_VOL_DN",
                    "&kp C_VOL_UP",
                ],
            ],
            title="Single Change Layout",
        )

        # Multiple changes: Q -> A, E -> D, N1 -> EXCL
        multiple_changes_layout = create_test_layout(
            ["base", "lower", "raise", "adjust"],
            [
                ["&kp A", "&kp W", "&kp D", "&kp R", "&kp T"],  # Q -> A, E -> D
                ["&kp EXCL", "&kp N2", "&kp N3", "&kp N4", "&kp N5"],  # N1 -> EXCL
                ["&kp F1", "&kp F2", "&kp F3", "&kp F4", "&kp F5"],
                [
                    "&kp C_PREV",
                    "&kp C_PLAY",
                    "&kp C_NEXT",
                    "&kp C_VOL_DN",
                    "&kp C_VOL_UP",
                ],
            ],
            title="Multiple Changes Layout",
        )

        # Layer reorder: swap lower and raise
        layer_reorder_layout = create_test_layout(
            ["base", "raise", "lower", "adjust"],  # swapped order
            [
                ["&kp Q", "&kp W", "&kp E", "&kp R", "&kp T"],
                ["&kp F1", "&kp F2", "&kp F3", "&kp F4", "&kp F5"],  # raise moved up
                ["&kp N1", "&kp N2", "&kp N3", "&kp N4", "&kp N5"],  # lower moved down
                [
                    "&kp C_PREV",
                    "&kp C_PLAY",
                    "&kp C_NEXT",
                    "&kp C_VOL_DN",
                    "&kp C_VOL_UP",
                ],
            ],
            title="Layer Reorder Layout",
        )

        return {
            "base": base_layout,
            "single_change": single_change_layout,
            "multiple_changes": multiple_changes_layout,
            "layer_reorder": layer_reorder_layout,
        }

    @pytest.fixture
    def temp_layout_files(self, test_layouts):
        """Create temporary layout files for CLI testing."""
        temp_dir = Path(tempfile.mkdtemp())

        layout_files = {}
        for name, layout in test_layouts.items():
            file_path = temp_dir / f"{name}.json"
            file_path.write_text(layout.model_dump_json(by_alias=True, indent=2))
            layout_files[name] = file_path

        yield layout_files

        # Cleanup - remove all files in temp directory first
        import shutil

        if temp_dir.exists():
            shutil.rmtree(temp_dir)

    def test_service_compare_layouts_summary_format(
        self, temp_layout_files, isolated_config
    ):
        """Test comparison service with summary format."""
        service = create_layout_comparison_service(isolated_config)
        result = service.compare_layouts(
            temp_layout_files["base"],
            temp_layout_files["single_change"],
            output_format="summary",
        )

        # Check basic structure
        assert result["success"] is True
        assert result["deepdiff_summary"]["has_changes"] is True
        assert result["deepdiff_summary"]["total_changes"] > 0

        # Check layer changes
        layers = result["layers"]
        assert layers["count_changed"] is True
        assert len(layers["behavior_changes"]) == 1

        # Check the specific change
        change = layers["behavior_changes"][0]
        assert change["layer"] == 0
        assert change["position"] == 0
        assert change["from"]["params"][0]["value"] == "Q"
        assert change["to"]["params"][0]["value"] == "A"

        # Check the "changed" structure for CLI compatibility
        assert "changed" in layers
        assert "layer_0" in layers["changed"]
        assert layers["changed"]["layer_0"]["total_key_differences"] == 1

    def test_service_compare_layouts_json_format(
        self, temp_layout_files, isolated_config
    ):
        """Test comparison service with JSON format."""
        service = create_layout_comparison_service(isolated_config)
        result = service.compare_layouts(
            temp_layout_files["base"],
            temp_layout_files["multiple_changes"],
            output_format="json",
        )

        # Check JSON patch is included
        assert "json_patch" in result
        assert "full_diff" in result

        # Check JSON patch operations
        json_patch = result["json_patch"]
        assert len(json_patch) > 0

        # Should have replacement operations for the key changes
        replacement_ops = [op for op in json_patch if op["op"] == "replace"]
        assert len(replacement_ops) >= 3  # At least Q->A, E->D, N1->EXCL

    def test_service_apply_patch_round_trip(self, temp_layout_files, isolated_config):
        """Test that applying a patch recreates the target layout."""
        service = create_layout_comparison_service(isolated_config)

        # Create diff
        diff_result = service.compare_layouts(
            temp_layout_files["base"],
            temp_layout_files["single_change"],
            output_format="json",
        )

        # Save patch to temporary file
        temp_dir = temp_layout_files["base"].parent
        patch_file = temp_dir / "test_patch.json"
        patch_file.write_text(json.dumps(diff_result, indent=2, default=str))

        # Apply patch
        output_file = temp_dir / "patched_output.json"
        patch_result = service.apply_patch(
            temp_layout_files["base"], patch_file, output=output_file
        )

        # Check patch was applied successfully
        assert patch_result["source"] == temp_layout_files["base"]
        assert patch_result["patch"] == patch_file
        assert patch_result["output"] == output_file
        assert patch_result["total_changes"] > 0

        # Verify the patched file exists and has correct content
        assert output_file.exists()
        patched_data = json.loads(output_file.read_text())

        # Check the key change was applied
        first_binding = patched_data["layers"][0][0]
        assert first_binding["value"] == "&kp"
        assert first_binding["params"][0]["value"] == "A"

    def test_cli_diff_summary_format(self, temp_layout_files):
        """Test CLI diff command with summary format."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "glovebox.cli",
                "layout",
                "diff",
                str(temp_layout_files["base"]),
                str(temp_layout_files["single_change"]),
                "--format",
                "summary",
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )

        assert result.returncode == 0
        output = result.stdout

        # Check for expected summary output
        assert "✅ Found" in output
        assert "difference(s):" in output
        assert "Layers: 1 changed" in output
        assert "layer_0: 1 changes" in output

    def test_cli_diff_detailed_format(self, temp_layout_files):
        """Test CLI diff command with detailed format."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "glovebox.cli",
                "layout",
                "diff",
                str(temp_layout_files["base"]),
                str(temp_layout_files["single_change"]),
                "--format",
                "detailed",
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )

        assert result.returncode == 0
        output = result.stdout

        # Check for expected detailed output
        assert "✅ Found" in output
        assert "difference(s):" in output
        assert "Layer 'layer_0': 1 key differences" in output
        assert "Key  0: '&kp Q' → '&kp A'" in output

    def test_cli_diff_pretty_format(self, temp_layout_files):
        """Test CLI diff command with pretty format."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "glovebox.cli",
                "layout",
                "diff",
                str(temp_layout_files["base"]),
                str(temp_layout_files["multiple_changes"]),
                "--format",
                "pretty",
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )

        assert result.returncode == 0
        output = result.stdout

        # Check for expected pretty output
        assert "Total operations:" in output
        assert "Replacements:" in output
        assert "Layer Changes:" in output
        assert "Key Binding Changes:" in output
        assert "Layer 0[0]: &kp Q → &kp A" in output

    def test_cli_diff_json_format(self, temp_layout_files):
        """Test CLI diff command with JSON format."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "glovebox.cli",
                "layout",
                "diff",
                str(temp_layout_files["base"]),
                str(temp_layout_files["single_change"]),
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )

        assert result.returncode == 0

        # Parse JSON output
        json_output = json.loads(result.stdout)

        # Check JSON structure
        assert json_output["success"] is True
        assert "deepdiff_summary" in json_output
        assert "layers" in json_output
        assert "json_patch" in json_output
        assert "full_diff" in json_output

        # Check the specific change is captured
        behavior_changes = json_output["layers"]["behavior_changes"]
        assert len(behavior_changes) == 1
        assert behavior_changes[0]["from"]["params"][0]["value"] == "Q"
        assert behavior_changes[0]["to"]["params"][0]["value"] == "A"

    def test_cli_patch_application(self, temp_layout_files):
        """Test CLI patch command."""
        temp_dir = temp_layout_files["base"].parent

        # First, generate a patch file using diff command
        patch_file = temp_dir / "test.patch.json"
        diff_result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "glovebox.cli",
                "layout",
                "diff",
                str(temp_layout_files["base"]),
                str(temp_layout_files["single_change"]),
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )

        assert diff_result.returncode == 0
        patch_file.write_text(diff_result.stdout)

        # Apply the patch
        output_file = temp_dir / "patched_layout.json"
        patch_result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "glovebox.cli",
                "layout",
                "patch",
                str(temp_layout_files["base"]),
                str(patch_file),
                "--output",
                str(output_file),
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )

        assert patch_result.returncode == 0
        output = patch_result.stdout

        # Check for success message
        assert "✅ Applied patch successfully" in output
        assert "Source:" in output
        assert "Patch:" in output
        assert "Output:" in output
        assert "Applied Changes:" in output

        # Verify the output file was created and has correct content
        assert output_file.exists()
        patched_data = json.loads(output_file.read_text())

        # Check the key change was applied
        first_binding = patched_data["layers"][0][0]
        assert first_binding["value"] == "&kp"
        assert first_binding["params"][0]["value"] == "A"

    def test_cli_no_differences(self, temp_layout_files):
        """Test CLI diff command when layouts are identical."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "glovebox.cli",
                "layout",
                "diff",
                str(temp_layout_files["base"]),
                str(temp_layout_files["base"]),  # Compare with itself
                "--format",
                "summary",
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )

        assert result.returncode == 0
        output = result.stdout

        # Should report no differences
        assert "✅ No significant differences found" in output

    def test_multiple_output_formats_consistency(self, temp_layout_files):
        """Test that all output formats detect the same changes."""
        formats = ["summary", "detailed", "pretty", "json"]
        results = {}

        for fmt in formats:
            if fmt == "json":
                # JSON format returns raw JSON
                result = subprocess.run(
                    [
                        "uv",
                        "run",
                        "python",
                        "-m",
                        "glovebox.cli",
                        "layout",
                        "diff",
                        str(temp_layout_files["base"]),
                        str(temp_layout_files["single_change"]),
                        "--format",
                        fmt,
                    ],
                    capture_output=True,
                    text=True,
                    cwd=Path.cwd(),
                )

                assert result.returncode == 0
                json_data = json.loads(result.stdout)
                results[fmt] = json_data["deepdiff_summary"]["total_changes"]
            else:
                # Text formats return formatted output
                result = subprocess.run(
                    [
                        "uv",
                        "run",
                        "python",
                        "-m",
                        "glovebox.cli",
                        "layout",
                        "diff",
                        str(temp_layout_files["base"]),
                        str(temp_layout_files["single_change"]),
                        "--format",
                        fmt,
                    ],
                    capture_output=True,
                    text=True,
                    cwd=Path.cwd(),
                )

                assert result.returncode == 0
                output = result.stdout

                # All should indicate changes were found
                assert ("✅ Found" in output and "difference(s):" in output) or (
                    "Total operations:" in output
                ), f"Format {fmt} should show changes"

        # JSON format should report consistent change count
        assert results["json"] > 0, "Should detect changes in JSON format"

    def test_layer_reordering_detection(self, temp_layout_files, isolated_config):
        """Test detection of layer reordering changes."""
        service = create_layout_comparison_service(isolated_config)
        result = service.compare_layouts(
            temp_layout_files["base"],
            temp_layout_files["layer_reorder"],
            output_format="json",
        )

        # Check that reordering is detected
        layers = result["layers"]
        assert layers["layer_names_changed"] is True or layers["reordering"] is True

        # Should have changes in the layer structure
        assert result["deepdiff_summary"]["has_changes"] is True
        assert result["deepdiff_summary"]["total_changes"] > 0

    def test_service_api_compatibility(self, temp_layout_files, isolated_config):
        """Test that the service maintains API compatibility with the old interface."""
        service = create_layout_comparison_service(isolated_config)

        # Test all the main methods exist and work
        result = service.compare_layouts(
            temp_layout_files["base"], temp_layout_files["single_change"]
        )
        assert "success" in result
        assert "layers" in result
        assert "behaviors" in result
        assert "metadata" in result
        assert "custom_dtsi" in result

        # Test patch application
        diff_result = service.compare_layouts(
            temp_layout_files["base"],
            temp_layout_files["single_change"],
            output_format="json",
        )

        temp_dir = temp_layout_files["base"].parent
        patch_file = temp_dir / "api_test_patch.json"
        patch_file.write_text(json.dumps(diff_result, indent=2, default=str))

        patch_result = service.apply_patch(temp_layout_files["base"], patch_file)
        assert "source" in patch_result
        assert "patch" in patch_result
        assert "output" in patch_result
        assert "total_changes" in patch_result
