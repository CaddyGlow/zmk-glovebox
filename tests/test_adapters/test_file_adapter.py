"""Tests for FileAdapter implementation."""

import json
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest
from pydantic import BaseModel, Field

from glovebox.adapters.file_adapter import (
    FileSystemAdapter,
    create_file_adapter,
)
from glovebox.core.errors import FileSystemError, GloveboxError
from glovebox.protocols.file_adapter_protocol import FileAdapterProtocol


class TestFileSystemAdapter:
    """Test FileSystemAdapter class."""

    def test_file_adapter_initialization(self):
        """Test FileAdapter can be initialized."""
        adapter = FileSystemAdapter()
        assert adapter is not None

    def test_read_json_with_aliases(self):
        """Test read_json preserves original field names for aliased Pydantic models."""
        adapter = FileSystemAdapter()
        mock_json_content = (
            '{"camelCase": "test", "withNumber1": 42, "normal_field": "value"}'
        )

        with patch("pathlib.Path.open", mock_open(read_data=mock_json_content)):
            result = adapter.read_json(Path("/test/aliased.json"))

        # Verify original field names are preserved
        assert "camelCase" in result
        assert "withNumber1" in result
        assert result["camelCase"] == "test"
        assert result["withNumber1"] == 42

    def test_read_text_success(self):
        """Test successful text file reading."""
        adapter = FileSystemAdapter()
        test_content = "Hello, world!"

        with patch("pathlib.Path.open", mock_open(read_data=test_content)):
            result = adapter.read_text(Path("/test/file.txt"))

        assert result == test_content

    def test_read_text_with_encoding(self):
        """Test text file reading with specific encoding."""
        adapter = FileSystemAdapter()
        test_content = "Hello, world!"

        with patch(
            "pathlib.Path.open", mock_open(read_data=test_content)
        ) as mock_path_open:
            result = adapter.read_text(Path("/test/file.txt"), encoding="utf-16")

        assert result == test_content
        # Path.open is called with mode="r" by default if only encoding is specified.
        mock_path_open.assert_called_once_with(mode="r", encoding="utf-16")

    def test_read_text_file_not_found(self):
        """Test read_text raises GloveboxError when file doesn't exist."""
        adapter = FileSystemAdapter()

        with (
            patch("pathlib.Path.open", side_effect=FileNotFoundError("File not found")),
            pytest.raises(
                FileSystemError,
                match="File operation 'read_text' failed on '/nonexistent/file.txt': File not found",
            ),
        ):
            adapter.read_text(Path("/nonexistent/file.txt"))

    def test_read_text_permission_error(self):
        """Test read_text raises GloveboxError when access denied."""
        adapter = FileSystemAdapter()

        with (
            patch(
                "pathlib.Path.open", side_effect=PermissionError("Permission denied")
            ),
            pytest.raises(
                FileSystemError,
                match="File operation 'read_text' failed on '/restricted/file.txt': Permission denied",
            ),
        ):
            adapter.read_text(Path("/restricted/file.txt"))

    def test_write_text_success(self):
        """Test successful text file writing."""
        adapter = FileSystemAdapter()
        test_content = "Hello, world!"
        test_path = Path("/test/file.txt")

        with (
            patch("pathlib.Path.open", mock_open()) as mock_path_open,
            patch("pathlib.Path.mkdir") as mock_mkdir,
        ):
            adapter.write_text(test_path, test_content)

        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_path_open.assert_called_once_with(mode="w", encoding="utf-8")
        mock_path_open().write.assert_called_once_with(test_content)

    def test_write_text_with_encoding(self):
        """Test text file writing with specific encoding."""
        adapter = FileSystemAdapter()
        test_content = "Hello, world!"
        test_path = Path("/test/file.txt")

        with (
            patch("pathlib.Path.open", mock_open()) as mock_path_open,
            patch("pathlib.Path.mkdir"),
        ):
            adapter.write_text(test_path, test_content, encoding="utf-16")

        mock_path_open.assert_called_once_with(mode="w", encoding="utf-16")

    def test_write_text_creates_directory(self):
        """Test write_text creates parent directories."""
        adapter = FileSystemAdapter()
        test_path = Path("/new/directory/file.txt")

        with (
            patch("pathlib.Path.open", mock_open()) as mock_path_open,
            patch("pathlib.Path.mkdir") as mock_mkdir,
        ):
            adapter.write_text(test_path, "content")

        # Should create parent directory
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_write_text_permission_error(self):
        """Test write_text raises PermissionError when access denied."""
        adapter = FileSystemAdapter()

        with (
            patch(
                "pathlib.Path.open", side_effect=PermissionError("Permission denied")
            ),
            patch("pathlib.Path.mkdir"),
            pytest.raises(
                FileSystemError,
                match="File operation 'write_text' failed on '/restricted/file.txt': Permission denied",
            ),
        ):
            adapter.write_text(Path("/restricted/file.txt"), "content")

    def test_exists_file_exists(self):
        """Test exists returns True when file exists."""
        adapter = FileSystemAdapter()

        with patch("pathlib.Path.exists", return_value=True):
            result = adapter.exists(Path("/test/file.txt"))

        assert result is True

    def test_exists_file_not_exists(self):
        """Test exists returns False when file doesn't exist."""
        adapter = FileSystemAdapter()

        with patch("pathlib.Path.exists", return_value=False):
            result = adapter.exists(Path("/nonexistent/file.txt"))

        assert result is False

    def test_is_file_true(self):
        """Test is_file returns True for files."""
        adapter = FileSystemAdapter()

        with patch("pathlib.Path.is_file", return_value=True):
            result = adapter.is_file(Path("/test/file.txt"))

        assert result is True

    def test_is_file_false(self):
        """Test is_file returns False for directories."""
        adapter = FileSystemAdapter()

        with patch("pathlib.Path.is_file", return_value=False):
            result = adapter.is_file(Path("/test/directory"))

        assert result is False

    def test_mkdir_success(self):
        """Test successful directory creation."""
        adapter = FileSystemAdapter()
        test_path = Path("/test/new_directory")

        with patch("pathlib.Path.mkdir") as mock_mkdir:
            adapter.mkdir(test_path)

        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_mkdir_with_options(self):
        """Test directory creation with custom options."""
        adapter = FileSystemAdapter()
        test_path = Path("/test/new_directory")

        with patch("pathlib.Path.mkdir") as mock_mkdir:
            adapter.mkdir(test_path, parents=False, exist_ok=False)

        mock_mkdir.assert_called_once_with(parents=False, exist_ok=False)

    def test_mkdir_permission_error(self):
        """Test mkdir raises PermissionError when access denied."""
        adapter = FileSystemAdapter()

        with (
            patch(
                "pathlib.Path.mkdir", side_effect=PermissionError("Permission denied")
            ),
            pytest.raises(
                FileSystemError,
                match="File operation 'mkdir' failed on '/restricted/directory': Permission denied",
            ),
        ):
            adapter.mkdir(Path("/restricted/directory"))

    def test_copy_file_success(self):
        """Test successful file copying."""
        adapter = FileSystemAdapter()
        src_path = Path("/test/source.txt")
        dst_path = Path("/test/destination.txt")

        with patch("shutil.copy2") as mock_copy, patch("pathlib.Path.mkdir"):
            adapter.copy_file(src_path, dst_path)

        mock_copy.assert_called_once_with(src_path, dst_path)

    def test_copy_file_creates_directory(self):
        """Test copy_file creates destination directory."""
        adapter = FileSystemAdapter()
        src_path = Path("/test/source.txt")
        dst_path = Path("/new/directory/destination.txt")

        with patch("shutil.copy2"), patch("pathlib.Path.mkdir") as mock_mkdir:
            adapter.copy_file(src_path, dst_path)

        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_copy_file_source_not_found(self):
        """Test copy_file raises FileNotFoundError when source doesn't exist."""
        adapter = FileSystemAdapter()

        with (
            patch("shutil.copy2", side_effect=FileNotFoundError("Source not found")),
            patch("pathlib.Path.mkdir"),
            pytest.raises(
                FileSystemError,
                match="File operation 'copy_file' failed on '/nonexistent/source.txt': Source not found",
            ),
        ):
            adapter.copy_file(Path("/nonexistent/source.txt"), Path("/test/dest.txt"))

    def test_remove_file_success(self):
        """Test successful file removal."""
        adapter = FileSystemAdapter()
        test_path = Path("/test/file.txt")

        with patch("pathlib.Path.unlink") as mock_unlink:
            adapter.remove_file(test_path)

        mock_unlink.assert_called_once_with(missing_ok=True)

    def test_remove_file_not_found(self):
        """Test remove_file handles FileNotFoundError gracefully by not raising an error."""
        adapter = FileSystemAdapter()
        test_path = Path("/nonexistent/file.txt")

        # Patch unlink to simulate it being called (though it won't find the file)
        # The key is that adapter.remove_file should not raise an error.
        with patch("pathlib.Path.unlink") as mock_unlink:
            adapter.remove_file(test_path)
        # We expect unlink to be called with missing_ok=True
        mock_unlink.assert_called_once_with(missing_ok=True)

    def test_list_directory_success(self):
        """Test successful directory listing."""
        adapter = FileSystemAdapter()
        test_path = Path("/test/directory")
        mock_files = [
            Path("/test/directory/file1.txt"),
            Path("/test/directory/file2.txt"),
        ]

        with (
            patch("pathlib.Path.iterdir", return_value=mock_files),
            patch("pathlib.Path.is_dir", return_value=True),
        ):
            result = adapter.list_directory(test_path)

        assert result == mock_files

    def test_list_directory_not_found(self):
        """Test list_directory raises GloveboxError when directory doesn't exist."""
        adapter = FileSystemAdapter()

        with (
            patch("pathlib.Path.is_dir", return_value=True),
            patch(
                "pathlib.Path.iterdir",
                side_effect=FileNotFoundError("Directory not found"),
            ),
            pytest.raises(FileSystemError),
        ):
            adapter.list_directory(Path("/nonexistent/directory"))

    def test_list_directory_not_directory(self):
        """Test list_directory raises GloveboxError when path is not a directory."""
        adapter = FileSystemAdapter()

        with (
            patch("pathlib.Path.is_dir", return_value=False),
            pytest.raises(FileSystemError),
        ):
            adapter.list_directory(Path("/test/file.txt"))


class TestCreateFileAdapter:
    """Test create_file_adapter factory function."""

    def test_create_file_adapter(self):
        """Test factory function creates FileAdapter instance."""
        adapter = create_file_adapter()
        assert isinstance(adapter, FileSystemAdapter)
        assert isinstance(adapter, FileAdapterProtocol)


class TestFileAdapterIntegration:
    """Integration tests using real file operations."""

    def test_read_write_roundtrip(self, tmp_path):
        """Test reading and writing files with real file system."""
        adapter = FileSystemAdapter()
        test_file = tmp_path / "test.txt"
        test_content = "Hello, world!\nThis is a test file."

        # Write content
        adapter.write_text(test_file, test_content)

        # Verify file exists
        assert adapter.exists(test_file)
        assert adapter.is_file(test_file)

        # Read content back
        result = adapter.read_text(test_file)
        assert result == test_content

    def test_read_write_json_roundtrip(self, tmp_path):
        """Test reading and writing JSON files with real file system."""
        adapter = FileSystemAdapter()
        test_file = tmp_path / "test.json"
        test_data = {
            "name": "Test Name",
            "values": [1, 2, 3],
            "nested": {"key": "value"},
        }

        # Write JSON
        adapter.write_json(test_file, test_data)

        # Verify file exists
        assert adapter.exists(test_file)
        assert adapter.is_file(test_file)

        # Read JSON back
        result = adapter.read_json(test_file)
        assert result == test_data

    def test_read_json_with_pydantic_model_aliases(self, tmp_path):
        """Test reading JSON with aliased field names for Pydantic models."""

        # Define a Pydantic model with field aliases
        class TestModel(BaseModel):
            snake_case: str = Field(alias="camelCase")
            with_number_1: int = Field(alias="withNumber1")
            normal_field: str

        adapter = FileSystemAdapter()
        test_file = tmp_path / "test_aliased.json"

        # Create JSON with camelCase fields (as would be found in external JSON)
        json_data = {
            "camelCase": "test value",
            "withNumber1": 42,
            "normal_field": "normal value",
        }

        # Write the JSON with camelCase fields directly
        with test_file.open("w") as f:
            json.dump(json_data, f)

        # Read the JSON using the adapter
        result = adapter.read_json(test_file)

        # Verify the raw JSON maintains original field names
        assert "camelCase" in result
        assert "withNumber1" in result
        assert result["camelCase"] == "test value"
        assert result["withNumber1"] == 42

        # Create Pydantic model from the JSON data
        model = TestModel.model_validate(result)

        # Verify the Pydantic model correctly maps aliases to snake_case
        assert model.snake_case == "test value"
        assert model.with_number_1 == 42
        assert model.normal_field == "normal value"

    def test_directory_operations(self, tmp_path):
        """Test directory operations with real file system."""
        adapter = FileSystemAdapter()
        test_dir = tmp_path / "new_directory"

        # Create directory
        adapter.mkdir(test_dir)
        assert test_dir.exists()
        assert test_dir.is_dir()

        # List empty directory
        contents = adapter.list_directory(test_dir)
        assert contents == []

        # Create files in directory
        file1 = test_dir / "file1.txt"
        file2 = test_dir / "file2.txt"
        adapter.write_text(file1, "content1")
        adapter.write_text(file2, "content2")

        # List directory with files
        contents = adapter.list_directory(test_dir)
        assert len(contents) == 2
        assert file1 in contents
        assert file2 in contents

    def test_copy_and_remove_operations(self, tmp_path):
        """Test file copy and remove operations with real file system."""
        adapter = FileSystemAdapter()

        # Create source file
        source = tmp_path / "source.txt"
        content = "Test content for copying"
        adapter.write_text(source, content)

        # Copy file
        destination = tmp_path / "subdir" / "destination.txt"
        adapter.copy_file(source, destination)

        # Verify copy
        assert adapter.exists(destination)
        assert adapter.read_text(destination) == content

        # Remove original
        adapter.remove_file(source)
        assert not adapter.exists(source)

        # Destination should still exist
        assert adapter.exists(destination)


class TestFileAdapterProtocol:
    """Test FileAdapter protocol implementation."""

    def test_file_adapter_implements_protocol(self):
        """Test that FileSystemAdapter correctly implements FileAdapter protocol."""
        adapter = FileSystemAdapter()
        assert isinstance(adapter, FileAdapterProtocol), (
            "FileSystemAdapter must implement FileAdapterProtocol"
        )

    def test_runtime_protocol_check(self):
        """Test that FileSystemAdapter passes runtime protocol check."""
        adapter = FileSystemAdapter()
        assert isinstance(adapter, FileAdapterProtocol), (
            "FileSystemAdapter should be instance of FileAdapterProtocol"
        )
