"""Test Artifact Validator service."""

import tempfile
from pathlib import Path
from unittest.mock import Mock

from glovebox.compilation.artifacts.validator import (
    ArtifactValidator,
    create_artifact_validator,
)


class TestArtifactValidator:
    """Test artifact validator functionality."""

    def setup_method(self):
        """Set up test instance."""
        self.mock_file_adapter = Mock()
        self.validator = ArtifactValidator(file_adapter=self.mock_file_adapter)

    def test_initialization(self):
        """Test validator initialization."""
        assert self.validator.file_adapter is self.mock_file_adapter
        assert self.validator.MIN_UF2_SIZE == 512
        assert self.validator.UF2_MAGIC_START == 0x0A324655
        assert self.validator.UF2_MAGIC_END == 0x0AB16F30

    def test_create_artifact_validator(self):
        """Test factory function creates validator."""
        validator = create_artifact_validator()
        assert isinstance(validator, ArtifactValidator)

    def test_validate_artifacts_empty_list(self):
        """Test validation with empty artifact list."""
        result = self.validator.validate_artifacts([])
        assert result is False

    def test_validate_artifacts_all_valid(self):
        """Test validation with all valid artifacts."""
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact1 = Path(temp_dir) / "firmware1.uf2"
            artifact2 = Path(temp_dir) / "firmware2.uf2"
            artifacts = [artifact1, artifact2]

            # Mock all artifacts as valid
            self.mock_file_adapter.check_exists.return_value = True
            self.mock_file_adapter.is_file.return_value = True

            # Create real files with valid UF2 content
            artifact1.write_bytes(self._create_valid_uf2_content())
            artifact2.write_bytes(self._create_valid_uf2_content())

            result = self.validator.validate_artifacts(artifacts)

            assert result is True

    def test_validate_artifacts_some_invalid(self):
        """Test validation with some invalid artifacts."""
        with tempfile.TemporaryDirectory() as temp_dir:
            valid_artifact = Path(temp_dir) / "valid.uf2"
            invalid_artifact = Path(temp_dir) / "invalid.uf2"
            artifacts = [valid_artifact, invalid_artifact]

            # Mock first artifact as valid, second as invalid (doesn't exist)
            def mock_check_exists(path):
                return path == valid_artifact

            self.mock_file_adapter.check_exists.side_effect = mock_check_exists
            self.mock_file_adapter.is_file.return_value = True

            # Create only the valid file with valid UF2 content
            valid_artifact.write_bytes(self._create_valid_uf2_content())

            result = self.validator.validate_artifacts(artifacts)

            assert result is False

    def test_validate_single_artifact_valid(self):
        """Test validation of single valid artifact."""
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "firmware.uf2"

            # Mock artifact as existing and accessible
            self.mock_file_adapter.check_exists.return_value = True
            self.mock_file_adapter.is_file.return_value = True

            # Create real file with valid UF2 content
            uf2_content = self._create_valid_uf2_content()
            artifact.write_bytes(uf2_content)

            result = self.validator.validate_single_artifact(artifact)

            assert result is True

    def test_validate_single_artifact_exception(self):
        """Test validation with exception during processing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "firmware.uf2"

            # Mock exception during existence check
            self.mock_file_adapter.check_exists.side_effect = OSError(
                "Permission denied"
            )

            result = self.validator.validate_single_artifact(artifact)

            assert result is False

    def test_validate_existence_file_exists(self):
        """Test existence validation for existing file."""
        artifact = Path("/some/path/firmware.uf2")

        # Mock file exists and is a file
        self.mock_file_adapter.check_exists.return_value = True
        self.mock_file_adapter.is_file.return_value = True

        result = self.validator._validate_existence(artifact)

        assert result is True

    def test_validate_existence_file_not_exists(self):
        """Test existence validation for non-existing file."""
        artifact = Path("/nonexistent/firmware.uf2")

        # Mock file doesn't exist
        self.mock_file_adapter.check_exists.return_value = False

        result = self.validator._validate_existence(artifact)

        assert result is False

    def test_validate_existence_not_a_file(self):
        """Test existence validation for directory instead of file."""
        artifact = Path("/some/directory")

        # Mock exists but is not a file
        self.mock_file_adapter.check_exists.return_value = True
        self.mock_file_adapter.is_file.return_value = False

        result = self.validator._validate_existence(artifact)

        assert result is False

    def test_validate_accessibility_accessible(self):
        """Test accessibility validation for accessible file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "firmware.uf2"
            artifact.write_bytes(b"test content")

            result = self.validator._validate_accessibility(artifact)

            assert result is True

    def test_validate_accessibility_permission_denied(self):
        """Test accessibility validation with permission error."""
        artifact = Path("/root/firmware.uf2")  # Typically inaccessible

        result = self.validator._validate_accessibility(artifact)

        # Should handle permission error gracefully
        assert result is False

    def test_validate_size_valid_uf2(self):
        """Test size validation for valid UF2 file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "firmware.uf2"
            artifact.write_bytes(b"A" * 1024)  # Size > MIN_UF2_SIZE

            result = self.validator._validate_size(artifact)

            assert result is True

    def test_validate_size_empty_file(self):
        """Test size validation for empty file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "firmware.uf2"
            artifact.write_bytes(b"")  # Empty file

            result = self.validator._validate_size(artifact)

            assert result is False

    def test_validate_size_uf2_too_small(self):
        """Test size validation for UF2 file that's too small."""
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "firmware.uf2"
            artifact.write_bytes(b"small")  # Size < MIN_UF2_SIZE

            result = self.validator._validate_size(artifact)

            assert result is False

    def test_validate_size_non_uf2_valid(self):
        """Test size validation for non-UF2 file (should pass if not empty)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "firmware.hex"
            artifact.write_bytes(b"hex content")

            result = self.validator._validate_size(artifact)

            assert result is True

    def test_validate_size_exception(self):
        """Test size validation with exception."""
        artifact = Path("/nonexistent/firmware.uf2")

        result = self.validator._validate_size(artifact)

        assert result is False

    def test_validate_uf2_format_valid(self):
        """Test UF2 format validation for valid UF2 file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "firmware.uf2"

            # Create valid UF2 content with correct magic numbers
            uf2_content = self._create_valid_uf2_content()
            artifact.write_bytes(uf2_content)

            result = self.validator._validate_uf2_format(artifact)

            assert result is True

    def test_validate_uf2_format_invalid_start_magic(self):
        """Test UF2 format validation with invalid start magic."""
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "firmware.uf2"

            # Create UF2 content with invalid start magic
            uf2_content = self._create_invalid_uf2_content(corrupt_start=True)
            artifact.write_bytes(uf2_content)

            result = self.validator._validate_uf2_format(artifact)

            assert result is False

    def test_validate_uf2_format_invalid_end_magic(self):
        """Test UF2 format validation with invalid end magic."""
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "firmware.uf2"

            # Create UF2 content with invalid end magic
            uf2_content = self._create_invalid_uf2_content(corrupt_end=True)
            artifact.write_bytes(uf2_content)

            result = self.validator._validate_uf2_format(artifact)

            assert result is False

    def test_validate_uf2_format_too_short(self):
        """Test UF2 format validation for file that's too short."""
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "firmware.uf2"
            artifact.write_bytes(b"short")  # Less than 32 bytes

            result = self.validator._validate_uf2_format(artifact)

            assert result is False

    def test_validate_uf2_format_exception(self):
        """Test UF2 format validation with exception."""
        artifact = Path("/nonexistent/firmware.uf2")

        result = self.validator._validate_uf2_format(artifact)

        assert result is False

    def test_get_validation_report_comprehensive(self):
        """Test comprehensive validation report generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create mixed artifacts
            valid_uf2 = Path(temp_dir) / "valid.uf2"
            invalid_uf2 = Path(temp_dir) / "invalid.uf2"
            valid_hex = Path(temp_dir) / "valid.hex"

            # Create valid UF2 file
            uf2_content = self._create_valid_uf2_content()
            valid_uf2.write_bytes(uf2_content)

            # Create invalid UF2 file (too small)
            invalid_uf2.write_bytes(b"small")

            # Create valid hex file
            valid_hex.write_bytes(b"hex content")

            artifacts = [valid_uf2, invalid_uf2, valid_hex]

            report = self.validator.get_validation_report(artifacts)

            assert report["total_artifacts"] == 3
            assert report["valid_artifacts"] == 2
            assert report["invalid_artifacts"] == 1
            assert len(report["artifacts"]) == 3

            # Check summary
            assert report["summary"]["all_valid"] is False
            assert report["summary"]["validation_rate"] == 2 / 3
            assert report["summary"]["has_uf2_files"] is True

    def test_get_single_artifact_report_valid(self):
        """Test single artifact report for valid artifact."""
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "firmware.uf2"

            # Mock file operations
            self.mock_file_adapter.check_exists.return_value = True
            self.mock_file_adapter.is_file.return_value = True

            # Create valid UF2 file
            uf2_content = self._create_valid_uf2_content()
            artifact.write_bytes(uf2_content)

            report = self.validator._get_single_artifact_report(artifact)

            assert report["valid"] is True
            assert report["filename"] == "firmware.uf2"
            assert report["file_type"] == "uf2"
            assert all(report["checks"].values())
            assert len(report["errors"]) == 0

    def test_get_single_artifact_report_invalid(self):
        """Test single artifact report for invalid artifact."""
        artifact = Path("/nonexistent/firmware.uf2")

        # Mock file doesn't exist
        self.mock_file_adapter.check_exists.return_value = False

        report = self.validator._get_single_artifact_report(artifact)

        assert report["valid"] is False
        assert report["filename"] == "firmware.uf2"
        assert report["file_type"] == "uf2"
        assert not report["checks"]["exists"]
        assert "File does not exist" in report["errors"]

    def test_get_single_artifact_report_exception(self):
        """Test single artifact report with exception."""
        artifact = Path("/some/firmware.uf2")

        # Mock exception during existence check
        self.mock_file_adapter.check_exists.side_effect = OSError("Permission denied")

        report = self.validator._get_single_artifact_report(artifact)

        assert report["valid"] is False
        assert any("Validation exception" in error for error in report["errors"])

    def _create_valid_uf2_content(self) -> bytes:
        """Create valid UF2 file content with correct magic numbers."""
        content = bytearray(512)  # UF2 block size

        # Set start magic (bytes 0-3, little-endian)
        content[0:4] = self.validator.UF2_MAGIC_START.to_bytes(4, byteorder="little")

        # Set end magic (bytes 28-31, little-endian)
        content[28:32] = self.validator.UF2_MAGIC_END.to_bytes(4, byteorder="little")

        # Fill rest with dummy data
        for i in range(32, 512):
            content[i] = i % 256

        return bytes(content)

    def _create_invalid_uf2_content(
        self, corrupt_start=False, corrupt_end=False
    ) -> bytes:
        """Create invalid UF2 file content with corrupted magic numbers."""
        content = bytearray(512)

        # Set correct or corrupted start magic
        if corrupt_start:
            content[0:4] = (0xDEADBEEF).to_bytes(4, byteorder="little")
        else:
            content[0:4] = self.validator.UF2_MAGIC_START.to_bytes(
                4, byteorder="little"
            )

        # Set correct or corrupted end magic
        if corrupt_end:
            content[28:32] = (0xCAFEBABE).to_bytes(4, byteorder="little")
        else:
            content[28:32] = self.validator.UF2_MAGIC_END.to_bytes(
                4, byteorder="little"
            )

        # Fill rest with dummy data
        for i in range(32, 512):
            content[i] = i % 256

        return bytes(content)


class TestArtifactValidatorIntegration:
    """Test artifact validator integration scenarios."""

    def test_real_file_adapter_integration(self):
        """Test integration with real file adapter."""
        from glovebox.compilation.artifacts import create_artifact_validator

        validator = create_artifact_validator()
        assert validator is not None
        assert hasattr(validator, "file_adapter")

    def test_validation_workflow_with_real_files(self):
        """Test complete validation workflow with real files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)

            # Create real firmware files
            valid_uf2 = base_dir / "valid.uf2"
            invalid_uf2 = base_dir / "invalid.uf2"
            valid_hex = base_dir / "valid.hex"

            # Create valid UF2 content
            validator_instance = ArtifactValidator()
            uf2_content = bytearray(1024)
            uf2_content[0:4] = validator_instance.UF2_MAGIC_START.to_bytes(4, "little")
            uf2_content[28:32] = validator_instance.UF2_MAGIC_END.to_bytes(4, "little")
            valid_uf2.write_bytes(uf2_content)

            # Create invalid UF2 file (too small)
            invalid_uf2.write_bytes(b"small")

            # Create valid hex file
            valid_hex.write_bytes(b"hex firmware content")

            validator = create_artifact_validator()
            artifacts = [valid_uf2, invalid_uf2, valid_hex]

            # Test individual validation
            assert validator.validate_single_artifact(valid_uf2) is True
            assert validator.validate_single_artifact(invalid_uf2) is False
            assert validator.validate_single_artifact(valid_hex) is True

            # Test batch validation
            all_valid = validator.validate_artifacts(artifacts)
            assert all_valid is False  # Because invalid_uf2 fails

            # Test validation report
            report = validator.get_validation_report(artifacts)
            assert report["total_artifacts"] == 3
            assert report["valid_artifacts"] == 2
            assert report["invalid_artifacts"] == 1

    def test_uf2_format_validation_real_files(self):
        """Test UF2 format validation with real file operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)

            # Create UF2 file with correct magic numbers
            valid_uf2 = base_dir / "valid.uf2"
            validator_instance = ArtifactValidator()

            # Create proper UF2 block content
            uf2_block = bytearray(512)
            uf2_block[0:4] = validator_instance.UF2_MAGIC_START.to_bytes(4, "little")
            uf2_block[28:32] = validator_instance.UF2_MAGIC_END.to_bytes(4, "little")
            valid_uf2.write_bytes(uf2_block)

            validator = create_artifact_validator()

            # Should pass format validation
            assert validator._validate_uf2_format(valid_uf2) is True

            # Create UF2 with invalid magic
            invalid_uf2 = base_dir / "invalid.uf2"
            invalid_block = bytearray(512)
            invalid_block[0:4] = (0xDEADBEEF).to_bytes(4, "little")  # Wrong magic
            invalid_block[28:32] = validator_instance.UF2_MAGIC_END.to_bytes(
                4, "little"
            )
            invalid_uf2.write_bytes(invalid_block)

            # Should fail format validation
            assert validator._validate_uf2_format(invalid_uf2) is False
