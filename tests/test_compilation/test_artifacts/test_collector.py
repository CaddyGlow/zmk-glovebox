"""Test Artifact Collector service."""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from glovebox.compilation.artifacts.collector import (
    ArtifactCollector,
    create_artifact_collector,
)
from glovebox.firmware.models import FirmwareOutputFiles


class TestArtifactCollector:
    """Test artifact collector functionality."""

    def setup_method(self):
        """Set up test instance."""
        self.mock_file_adapter = Mock()
        self.mock_firmware_scanner = Mock()

        self.collector = ArtifactCollector(
            file_adapter=self.mock_file_adapter,
            firmware_scanner=self.mock_firmware_scanner,
        )

    def test_initialization(self):
        """Test collector initialization."""
        assert self.collector.file_adapter is self.mock_file_adapter
        assert self.collector.firmware_scanner is self.mock_firmware_scanner

    def test_create_artifact_collector(self):
        """Test factory function creates collector."""
        collector = create_artifact_collector()
        assert isinstance(collector, ArtifactCollector)

    def test_collect_artifacts_nonexistent_directory(self):
        """Test collection from nonexistent directory."""
        output_dir = Path("/nonexistent/directory")
        self.mock_file_adapter.check_exists.return_value = False

        firmware_files, output_files = self.collector.collect_artifacts(output_dir)

        assert firmware_files == []
        assert output_files.output_dir == output_dir
        assert output_files.main_uf2 is None

    def test_collect_artifacts_with_firmware_scanner(self):
        """Test collection using firmware scanner."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            # Mock directory exists
            self.mock_file_adapter.check_exists.return_value = True

            # Mock firmware scanner returns files
            mock_files = [
                output_dir / "firmware1.uf2",
                output_dir / "firmware2.uf2",
            ]
            self.mock_firmware_scanner.scan_firmware_files.return_value = mock_files

            firmware_files, output_files = self.collector.collect_artifacts(output_dir)

            assert firmware_files == mock_files
            assert output_files.output_dir == output_dir
            assert output_files.main_uf2 == mock_files[0]

    def test_collect_artifacts_without_firmware_scanner(self):
        """Test collection without firmware scanner (direct scanning)."""
        collector = ArtifactCollector(
            file_adapter=self.mock_file_adapter,
            firmware_scanner=None,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            # Mock directory exists
            self.mock_file_adapter.check_exists.return_value = True

            # Mock base directory files
            base_files = [output_dir / "glove80.uf2"]
            self.mock_file_adapter.list_files.return_value = base_files

            # Mock no west build directory
            build_dir = output_dir / "build"
            self.mock_file_adapter.check_exists.side_effect = lambda p: p == output_dir

            # Mock no subdirectories
            self.mock_file_adapter.list_directory.return_value = []

            firmware_files, output_files = collector.collect_artifacts(output_dir)

            assert firmware_files == base_files
            assert output_files.main_uf2 == base_files[0]

    def test_scan_base_directory(self):
        """Test scanning base directory for firmware files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            # Mock firmware files in base directory
            firmware_files = [
                output_dir / "keyboard.uf2",
                output_dir / "glove80.uf2",
            ]
            self.mock_file_adapter.list_files.return_value = firmware_files

            result = self.collector._scan_base_directory(output_dir)

            assert result == firmware_files
            self.mock_file_adapter.list_files.assert_called_once_with(
                output_dir, "*.uf2"
            )

    def test_scan_base_directory_exception(self):
        """Test base directory scanning with exception."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            # Mock exception during file listing
            self.mock_file_adapter.list_files.side_effect = OSError("Permission denied")

            result = self.collector._scan_base_directory(output_dir)

            assert result == []

    def test_scan_west_build_directories(self):
        """Test scanning west build directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            build_dir = output_dir / "build"
            board_dir = build_dir / "glove80_lh"
            zephyr_dir = board_dir / "zephyr"
            zmk_file = zephyr_dir / "zmk.uf2"

            # Mock directory structure exists
            self.mock_file_adapter.check_exists.side_effect = lambda p: p in [
                build_dir,
                zephyr_dir,
                zmk_file,
            ]
            self.mock_file_adapter.is_dir.side_effect = lambda p: p in [
                build_dir,
                board_dir,
            ]

            # Mock board directories
            self.mock_file_adapter.list_directory.return_value = [board_dir]

            result = self.collector._scan_west_build_directories(output_dir)

            assert zmk_file in result

    def test_scan_west_build_directories_no_build(self):
        """Test west build scanning when build directory doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            build_dir = output_dir / "build"

            # Mock build directory doesn't exist
            self.mock_file_adapter.check_exists.return_value = False

            result = self.collector._scan_west_build_directories(output_dir)

            assert result == []

    def test_scan_zephyr_directory(self):
        """Test scanning zephyr directory within build subdirectory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            build_subdir = Path(temp_dir) / "glove80_lh"
            zephyr_dir = build_subdir / "zephyr"
            zmk_file = zephyr_dir / "zmk.uf2"

            # Mock zephyr directory and file exist
            self.mock_file_adapter.check_exists.side_effect = lambda p: p in [
                zephyr_dir,
                zmk_file,
            ]

            result = self.collector._scan_zephyr_directory(build_subdir)

            assert result == [zmk_file]

    def test_scan_zephyr_directory_no_zephyr(self):
        """Test zephyr directory scanning when zephyr dir doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            build_subdir = Path(temp_dir) / "glove80_lh"

            # Mock zephyr directory doesn't exist
            self.mock_file_adapter.check_exists.return_value = False

            result = self.collector._scan_zephyr_directory(build_subdir)

            assert result == []

    def test_scan_subdirectories(self):
        """Test scanning subdirectories for firmware files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            lf_dir = output_dir / "lf"
            rh_dir = output_dir / "rh"
            build_dir = output_dir / "build"

            # Mock subdirectories
            self.mock_file_adapter.list_directory.return_value = [
                lf_dir,
                rh_dir,
                build_dir,
            ]
            self.mock_file_adapter.is_dir.return_value = True

            # Mock firmware files in subdirectories
            lf_files = [lf_dir / "zmk.uf2"]
            rh_files = [rh_dir / "zmk.uf2"]

            def mock_list_files(directory, pattern):
                if directory == lf_dir:
                    return lf_files
                elif directory == rh_dir:
                    return rh_files
                return []

            self.mock_file_adapter.list_files.side_effect = mock_list_files

            result = self.collector._scan_subdirectories(output_dir)

            # Should find files in lf and rh, but skip build directory
            assert lf_files[0] in result
            assert rh_files[0] in result
            assert len(result) == 2

    def test_scan_subdirectories_exception(self):
        """Test subdirectory scanning with exception."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            # Mock exception during directory listing
            self.mock_file_adapter.list_directory.side_effect = OSError(
                "Permission denied"
            )

            result = self.collector._scan_subdirectories(output_dir)

            assert result == []

    def test_organize_output_files_no_files(self):
        """Test organizing output files with no firmware files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            firmware_files: list[Path] = []

            result = self.collector._organize_output_files(firmware_files, output_dir)

            assert result.output_dir == output_dir
            assert result.main_uf2 is None
            assert result.left_uf2 is None
            assert result.right_uf2 is None

    def test_organize_output_files_with_main(self):
        """Test organizing output files with main firmware."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            firmware_files = [output_dir / "glove80.uf2"]

            result = self.collector._organize_output_files(firmware_files, output_dir)

            assert result.main_uf2 == firmware_files[0]

    def test_organize_output_files_with_left_right(self):
        """Test organizing output files with left/right hand files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            lf_dir = output_dir / "lf"
            rh_dir = output_dir / "rh"

            firmware_files = [
                output_dir / "main.uf2",
                lf_dir / "zmk.uf2",
                rh_dir / "zmk.uf2",
            ]

            result = self.collector._organize_output_files(firmware_files, output_dir)

            assert result.main_uf2 == firmware_files[0]
            assert result.left_uf2 == firmware_files[1]
            assert result.right_uf2 == firmware_files[2]

    def test_organize_output_files_with_build_dir(self):
        """Test organizing output files with build artifacts directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            build_dir = output_dir / "build"
            firmware_files = [output_dir / "firmware.uf2"]

            # Mock build directory exists
            self.mock_file_adapter.check_exists.return_value = True

            result = self.collector._organize_output_files(firmware_files, output_dir)

            assert result.artifacts_dir == build_dir

    def test_collect_artifacts_integration(self):
        """Test complete artifact collection integration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            # Mock directory exists
            self.mock_file_adapter.check_exists.return_value = True

            # Mock base directory scan
            base_files = [output_dir / "glove80.uf2"]

            # Mock west build scan
            build_dir = output_dir / "build"
            board_dir = build_dir / "glove80_lh"
            zephyr_dir = board_dir / "zephyr"
            west_file = zephyr_dir / "zmk.uf2"

            # Mock subdirectory scan
            lf_dir = output_dir / "lf"
            lf_file = lf_dir / "zmk.uf2"

            # Set up mock responses for collector without firmware scanner
            collector = ArtifactCollector(
                file_adapter=self.mock_file_adapter,
                firmware_scanner=None,
            )

            def mock_check_exists(path):
                return path in [output_dir, build_dir, zephyr_dir, west_file, lf_file]

            def mock_is_dir(path):
                return path in [build_dir, board_dir, lf_dir]

            def mock_list_files(directory, pattern):
                if directory == output_dir:
                    return base_files
                elif directory == lf_dir:
                    return [lf_file]
                return []

            def mock_list_directory(directory):
                if directory == output_dir:
                    return [lf_dir]
                elif directory == build_dir:
                    return [board_dir]
                return []

            self.mock_file_adapter.check_exists.side_effect = mock_check_exists
            self.mock_file_adapter.is_dir.side_effect = mock_is_dir
            self.mock_file_adapter.list_files.side_effect = mock_list_files
            self.mock_file_adapter.list_directory.side_effect = mock_list_directory

            firmware_files, output_files = collector.collect_artifacts(output_dir)

            # Should collect files from base directory and subdirectories
            assert base_files[0] in firmware_files
            assert lf_file in firmware_files
            assert output_files.main_uf2 == base_files[0]
            assert output_files.left_uf2 == lf_file


class TestArtifactCollectorIntegration:
    """Test artifact collector integration scenarios."""

    def test_real_file_adapter_integration(self):
        """Test integration with real file adapter."""
        from glovebox.compilation.artifacts import create_artifact_collector

        collector = create_artifact_collector()
        assert collector is not None
        assert hasattr(collector, "file_adapter")
        assert hasattr(collector, "firmware_scanner")

    def test_collection_workflow(self):
        """Test complete collection workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            # Create real firmware files for testing
            firmware_file = output_dir / "test.uf2"
            firmware_file.write_bytes(b"test firmware content")

            lf_dir = output_dir / "lf"
            lf_dir.mkdir()
            lf_file = lf_dir / "zmk.uf2"
            lf_file.write_bytes(b"left hand firmware")

            collector = create_artifact_collector()
            firmware_files, output_files = collector.collect_artifacts(output_dir)

            # Should find the created files
            assert len(firmware_files) > 0
            assert any(f.name == "test.uf2" for f in firmware_files)
            assert output_files.output_dir == output_dir
            assert output_files.main_uf2 is not None
