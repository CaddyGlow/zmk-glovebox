"""Tests for FileAdapter implementation."""

import json
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest
from pydantic import BaseModel, Field

from glovebox.adapters.file_adapter import (
    FileAdapter,
    create_file_adapter,
)
from glovebox.core.errors import FileSystemError, GloveboxError
from glovebox.protocols.file_adapter_protocol import FileAdapterProtocol


class TestFileAdapter:
    """Test FileAdapter class."""

    def test_file_adapter_initialization(self):
        """Test FileAdapter can be initialized."""
        adapter = FileAdapter()
        assert adapter is not None

    def test_read_json_with_aliases(self):
        """Test read_json preserves original field names for aliased Pydantic models."""
        adapter = FileAdapter()
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
        adapter = FileAdapter()
        test_content = "Hello, world!"

        with patch("pathlib.Path.open", mock_open(read_data=test_content)):
            result = adapter.read_text(Path("/test/file.txt"))

        assert result == test_content

    def test_read_text_with_encoding(self):
        """Test text file reading with specific encoding."""
        adapter = FileAdapter()
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
        adapter = FileAdapter()

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
        adapter = FileAdapter()

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
        adapter = FileAdapter()
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
        adapter = FileAdapter()
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
        adapter = FileAdapter()
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
        adapter = FileAdapter()

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
        adapter = FileAdapter()

        with patch("pathlib.Path.exists", return_value=True):
            result = adapter.check_exists(Path("/test/file.txt"))

        assert result is True

    def test_exists_file_not_exists(self):
        """Test exists returns False when file doesn't exist."""
        adapter = FileAdapter()

        with patch("pathlib.Path.exists", return_value=False):
            result = adapter.check_exists(Path("/nonexistent/file.txt"))

        assert result is False

    def test_is_file_true(self):
        """Test is_file returns True for files."""
        adapter = FileAdapter()

        with patch("pathlib.Path.is_file", return_value=True):
            result = adapter.is_file(Path("/test/file.txt"))

        assert result is True

    def test_is_file_false(self):
        """Test is_file returns False for directories."""
        adapter = FileAdapter()

        with patch("pathlib.Path.is_file", return_value=False):
            result = adapter.is_file(Path("/test/directory"))

        assert result is False

    def test_mkdir_success(self):
        """Test successful directory creation."""
        adapter = FileAdapter()
        test_path = Path("/test/new_directory")

        with patch("pathlib.Path.mkdir") as mock_mkdir:
            adapter.create_directory(test_path)

        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_mkdir_with_options(self):
        """Test directory creation with custom options."""
        adapter = FileAdapter()
        test_path = Path("/test/new_directory")

        with patch("pathlib.Path.mkdir") as mock_mkdir:
            adapter.create_directory(test_path, parents=False, exist_ok=False)

        mock_mkdir.assert_called_once_with(parents=False, exist_ok=False)

    def test_mkdir_permission_error(self):
        """Test mkdir raises PermissionError when access denied."""
        adapter = FileAdapter()

        with (
            patch(
                "pathlib.Path.mkdir", side_effect=PermissionError("Permission denied")
            ),
            pytest.raises(
                FileSystemError,
                match="File operation 'mkdir' failed on '/restricted/directory': Permission denied",
            ),
        ):
            adapter.create_directory(Path("/restricted/directory"))

    def test_copy_file_success(self):
        """Test successful file copying."""
        adapter = FileAdapter()
        src_path = Path("/test/source.txt")
        dst_path = Path("/test/destination.txt")

        with patch("shutil.copy2") as mock_copy, patch("pathlib.Path.mkdir"):
            adapter.copy_file(src_path, dst_path)

        mock_copy.assert_called_once_with(src_path, dst_path)

    def test_copy_file_creates_directory(self):
        """Test copy_file creates destination directory."""
        adapter = FileAdapter()
        src_path = Path("/test/source.txt")
        dst_path = Path("/new/directory/destination.txt")

        with patch("shutil.copy2"), patch("pathlib.Path.mkdir") as mock_mkdir:
            adapter.copy_file(src_path, dst_path)

        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_copy_file_source_not_found(self):
        """Test copy_file raises FileNotFoundError when source doesn't exist."""
        adapter = FileAdapter()

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
        adapter = FileAdapter()
        test_path = Path("/test/file.txt")

        with patch("pathlib.Path.unlink") as mock_unlink:
            adapter.remove_file(test_path)

        mock_unlink.assert_called_once_with(missing_ok=True)

    def test_remove_file_not_found(self):
        """Test remove_file handles FileNotFoundError gracefully by not raising an error."""
        adapter = FileAdapter()
        test_path = Path("/nonexistent/file.txt")

        # Patch unlink to simulate it being called (though it won't find the file)
        # The key is that adapter.remove_file should not raise an error.
        with patch("pathlib.Path.unlink") as mock_unlink:
            adapter.remove_file(test_path)
        # We expect unlink to be called with missing_ok=True
        mock_unlink.assert_called_once_with(missing_ok=True)

    def test_list_directory_success(self):
        """Test successful directory listing."""
        adapter = FileAdapter()
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
        adapter = FileAdapter()

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
        adapter = FileAdapter()

        with (
            patch("pathlib.Path.is_dir", return_value=False),
            pytest.raises(FileSystemError),
        ):
            adapter.list_directory(Path("/test/file.txt"))

    def test_read_binary_success(self):
        """Test successful binary file reading."""
        adapter = FileAdapter()
        test_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"

        with patch("pathlib.Path.open", mock_open(read_data=test_content)):
            result = adapter.read_binary(Path("/test/file.png"))

        assert result == test_content

    def test_read_binary_file_not_found(self):
        """Test read_binary raises GloveboxError when file doesn't exist."""
        adapter = FileAdapter()

        with (
            patch("pathlib.Path.open", side_effect=FileNotFoundError("File not found")),
            pytest.raises(
                FileSystemError,
                match="File operation 'read_binary' failed on '/nonexistent/file.bin': File not found",
            ),
        ):
            adapter.read_binary(Path("/nonexistent/file.bin"))

    def test_read_binary_permission_error(self):
        """Test read_binary raises GloveboxError when access denied."""
        adapter = FileAdapter()

        with (
            patch(
                "pathlib.Path.open", side_effect=PermissionError("Permission denied")
            ),
            pytest.raises(
                FileSystemError,
                match="File operation 'read_binary' failed on '/restricted/file.bin': Permission denied",
            ),
        ):
            adapter.read_binary(Path("/restricted/file.bin"))

    def test_write_binary_success(self):
        """Test successful binary file writing."""
        adapter = FileAdapter()
        test_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        test_path = Path("/test/file.png")

        with (
            patch("pathlib.Path.open", mock_open()) as mock_path_open,
            patch("pathlib.Path.mkdir") as mock_mkdir,
        ):
            adapter.write_binary(test_path, test_content)

        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_path_open.assert_called_once_with(mode="wb")
        mock_path_open().write.assert_called_once_with(test_content)

    def test_write_binary_creates_directory(self):
        """Test write_binary creates parent directories."""
        adapter = FileAdapter()
        test_path = Path("/new/directory/file.bin")

        with (
            patch("pathlib.Path.open", mock_open()) as mock_path_open,
            patch("pathlib.Path.mkdir") as mock_mkdir,
        ):
            adapter.write_binary(test_path, b"binary content")

        # Should create parent directory
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_write_binary_permission_error(self):
        """Test write_binary raises PermissionError when access denied."""
        adapter = FileAdapter()

        with (
            patch(
                "pathlib.Path.open", side_effect=PermissionError("Permission denied")
            ),
            patch("pathlib.Path.mkdir"),
            pytest.raises(
                FileSystemError,
                match="File operation 'write_binary' failed on '/restricted/file.bin': Permission denied",
            ),
        ):
            adapter.write_binary(Path("/restricted/file.bin"), b"content")

    def test_remove_dir_recursive_success(self):
        """Test successful recursive directory removal."""
        adapter = FileAdapter()
        test_path = Path("/test/directory")

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=True),
            patch("shutil.rmtree") as mock_rmtree,
        ):
            adapter.remove_dir(test_path, recursive=True)

        mock_rmtree.assert_called_once_with(test_path)

    def test_remove_dir_non_recursive_success(self):
        """Test successful non-recursive directory removal."""
        adapter = FileAdapter()
        test_path = Path("/test/directory")

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=True),
            patch("pathlib.Path.rmdir") as mock_rmdir,
        ):
            adapter.remove_dir(test_path, recursive=False)

        mock_rmdir.assert_called_once()

    def test_remove_dir_not_exists(self):
        """Test remove_dir handles non-existent directory gracefully."""
        adapter = FileAdapter()
        test_path = Path("/nonexistent/directory")

        with (
            patch("pathlib.Path.exists", return_value=False),
            patch("shutil.rmtree") as mock_rmtree,
        ):
            adapter.remove_dir(test_path)

        # Should not attempt to remove if directory doesn't exist
        mock_rmtree.assert_not_called()

    def test_remove_dir_not_directory(self):
        """Test remove_dir raises error when path is not a directory."""
        adapter = FileAdapter()
        test_path = Path("/test/file.txt")

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=False),
            pytest.raises(
                FileSystemError,
                match="File operation 'remove_dir' failed on '/test/file.txt': Not a directory",
            ),
        ):
            adapter.remove_dir(test_path)

    def test_remove_dir_permission_error(self):
        """Test remove_dir raises error when permission denied."""
        adapter = FileAdapter()
        test_path = Path("/restricted/directory")

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=True),
            patch("shutil.rmtree", side_effect=PermissionError("Permission denied")),
            pytest.raises(
                FileSystemError,
                match="File operation 'remove_dir' failed on '/restricted/directory': Permission denied",
            ),
        ):
            adapter.remove_dir(test_path)


class TestCreateFileAdapter:
    """Test create_file_adapter factory function."""

    def test_create_file_adapter(self):
        """Test factory function creates FileAdapter instance."""
        adapter = create_file_adapter()
        assert isinstance(adapter, FileAdapter)
        assert isinstance(adapter, FileAdapterProtocol)


class TestFileAdapterIntegration:
    """Integration tests using real file operations."""

    def test_read_write_roundtrip(self, tmp_path):
        """Test reading and writing files with real file system."""
        adapter = FileAdapter()
        test_file = tmp_path / "test.txt"
        test_content = "Hello, world!\nThis is a test file."

        # Write content
        adapter.write_text(test_file, test_content)

        # Verify file exists
        assert adapter.check_exists(test_file)
        assert adapter.is_file(test_file)

        # Read content back
        result = adapter.read_text(test_file)
        assert result == test_content

    def test_read_write_json_roundtrip(self, tmp_path):
        """Test reading and writing JSON files with real file system."""
        adapter = FileAdapter()
        test_file = tmp_path / "test.json"
        test_data = {
            "name": "Test Name",
            "values": [1, 2, 3],
            "nested": {"key": "value"},
        }

        # Write JSON
        adapter.write_json(test_file, test_data)

        # Verify file exists
        assert adapter.check_exists(test_file)
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

        adapter = FileAdapter()
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
        adapter = FileAdapter()
        test_dir = tmp_path / "new_directory"

        # Create directory
        adapter.create_directory(test_dir)
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
        adapter = FileAdapter()

        # Create source file
        source = tmp_path / "source.txt"
        content = "Test content for copying"
        adapter.write_text(source, content)

        # Copy file
        destination = tmp_path / "subdir" / "destination.txt"
        adapter.copy_file(source, destination)

        # Verify copy
        assert adapter.check_exists(destination)
        assert adapter.read_text(destination) == content

        # Remove original
        adapter.remove_file(source)
        assert not adapter.check_exists(source)

        # Destination should still exist
        assert adapter.check_exists(destination)

    def test_binary_read_write_roundtrip(self, tmp_path):
        """Test reading and writing binary files with real file system."""
        adapter = FileAdapter()
        test_file = tmp_path / "test.bin"
        test_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x10"

        # Write binary content
        adapter.write_binary(test_file, test_content)

        # Verify file exists
        assert adapter.check_exists(test_file)
        assert adapter.is_file(test_file)

        # Read binary content back
        result = adapter.read_binary(test_file)
        assert result == test_content

    def test_remove_dir_operations(self, tmp_path):
        """Test directory removal operations with real file system."""
        adapter = FileAdapter()

        # Create test directory structure
        test_dir = tmp_path / "test_dir"
        sub_dir = test_dir / "sub_dir"
        adapter.create_directory(sub_dir)

        # Create files in directories
        file1 = test_dir / "file1.txt"
        file2 = sub_dir / "file2.txt"
        adapter.write_text(file1, "content1")
        adapter.write_text(file2, "content2")

        # Verify structure exists
        assert adapter.check_exists(test_dir)
        assert adapter.check_exists(sub_dir)
        assert adapter.check_exists(file1)
        assert adapter.check_exists(file2)

        # Remove directory recursively
        adapter.remove_dir(test_dir, recursive=True)

        # Verify directory and all contents are removed
        assert not adapter.check_exists(test_dir)
        assert not adapter.check_exists(sub_dir)
        assert not adapter.check_exists(file1)
        assert not adapter.check_exists(file2)

    def test_remove_dir_non_recursive_empty(self, tmp_path):
        """Test non-recursive directory removal on empty directory."""
        adapter = FileAdapter()

        # Create empty directory
        test_dir = tmp_path / "empty_dir"
        adapter.create_directory(test_dir)
        assert adapter.check_exists(test_dir)

        # Remove empty directory non-recursively
        adapter.remove_dir(test_dir, recursive=False)

        # Verify directory is removed
        assert not adapter.check_exists(test_dir)

    def test_remove_dir_non_recursive_with_contents_fails(self, tmp_path):
        """Test non-recursive directory removal fails when directory has contents."""
        adapter = FileAdapter()

        # Create directory with file
        test_dir = tmp_path / "non_empty_dir"
        test_file = test_dir / "file.txt"
        adapter.create_directory(test_dir)
        adapter.write_text(test_file, "content")

        # Attempt to remove non-recursively should fail
        with pytest.raises(FileSystemError):
            adapter.remove_dir(test_dir, recursive=False)

        # Directory should still exist
        assert adapter.check_exists(test_dir)
        assert adapter.check_exists(test_file)


class TestFileAdapterProtocol:
    """Test FileAdapter protocol implementation."""

    def test_file_adapter_implements_protocol(self):
        """Test that FileAdapter correctly implements FileAdapter protocol."""
        adapter = FileAdapter()
        assert isinstance(adapter, FileAdapterProtocol), (
            "FileAdapter must implement FileAdapterProtocol"
        )

    def test_runtime_protocol_check(self):
        """Test that FileAdapter passes runtime protocol check."""
        adapter = FileAdapter()
        assert isinstance(adapter, FileAdapterProtocol), (
            "FileAdapter should be instance of FileAdapterProtocol"
        )
