"""Tests for layout layer service."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.layout.layer.service import (
    LayoutLayerService,
    create_layout_layer_service,
)
from glovebox.layout.models import LayoutBinding, LayoutData


@pytest.fixture
def sample_layout_data():
    """Create sample layout data for testing."""
    return LayoutData(
        keyboard="glove80",
        title="Test Layout",
        layer_names=["Base", "Lower", "Upper"],
        layers=[
            [
                LayoutBinding(value="&kp", params=[]),
                LayoutBinding(value="&none", params=[]),
            ],
            [
                LayoutBinding(value="&trans", params=[]),
                LayoutBinding(value="&mo", params=[]),
            ],
            [
                LayoutBinding(value="&tog", params=[]),
                LayoutBinding(value="&sl", params=[]),
            ],
        ],
    )


@pytest.fixture
def layer_service():
    """Create a layer service instance for testing."""
    return LayoutLayerService()


@pytest.fixture
def temp_layout_file(tmp_path, sample_layout_data):
    """Create a temporary layout file for testing."""
    layout_file = tmp_path / "test_layout.json"
    layout_file.write_text(sample_layout_data.model_dump_json())
    return layout_file


@pytest.fixture
def temp_import_file(tmp_path):
    """Create a temporary import file for testing."""
    import_file = tmp_path / "import_layer.json"
    import_data = [
        {"value": "&kp", "params": []},
        {"value": "&mt", "params": []},
    ]
    import_file.write_text(json.dumps(import_data))
    return import_file


class TestLayoutLayerServiceInit:
    """Test layer service initialization."""

    def test_layer_service_creation(self):
        """Test layer service can be created."""
        service = LayoutLayerService()
        assert isinstance(service, LayoutLayerService)

    def test_create_layout_layer_service(self):
        """Test factory function."""
        service = create_layout_layer_service()
        assert isinstance(service, LayoutLayerService)


class TestAddLayer:
    """Test add_layer method."""

    @patch("glovebox.layout.layer.service.load_layout_file")
    @patch("glovebox.layout.layer.service.save_layout_file")
    @patch("glovebox.layout.layer.service.validate_layer_name_unique")
    @patch("glovebox.layout.layer.service.validate_position_index")
    @patch("glovebox.layout.layer.service.validate_output_path")
    def test_add_layer_basic(
        self,
        mock_validate_output,
        mock_validate_position,
        mock_validate_unique,
        mock_save,
        mock_load,
        layer_service,
        sample_layout_data,
        temp_layout_file,
    ):
        """Test basic layer addition."""
        mock_load.return_value = sample_layout_data
        mock_validate_position.return_value = 3

        result = layer_service.add_layer(
            layout_file=temp_layout_file,
            layer_name="NewLayer",
            position=3,
        )

        assert result["layer_name"] == "NewLayer"
        assert result["position"] == 3
        assert result["total_layers"] == 4
        assert result["output_path"] == temp_layout_file
        assert result["copy_from"] is None
        assert result["import_from"] is None

        mock_validate_unique.assert_called_once_with(sample_layout_data, "NewLayer")
        mock_validate_position.assert_called_once_with(3, 3)
        mock_validate_output.assert_called_once_with(
            temp_layout_file, temp_layout_file, False
        )
        mock_save.assert_called_once()

    @patch("glovebox.layout.layer.service.load_layout_file")
    @patch("glovebox.layout.layer.service.save_layout_file")
    @patch("glovebox.layout.layer.service.validate_layer_name_unique")
    @patch("glovebox.layout.layer.service.validate_position_index")
    @patch("glovebox.layout.layer.service.validate_output_path")
    def test_add_layer_with_copy_from(
        self,
        mock_validate_output,
        mock_validate_position,
        mock_validate_unique,
        mock_save,
        mock_load,
        layer_service,
        sample_layout_data,
        temp_layout_file,
    ):
        """Test adding layer with copy_from parameter."""
        mock_load.return_value = sample_layout_data
        mock_validate_position.return_value = 1

        with patch.object(layer_service, "_copy_layer_bindings") as mock_copy:
            mock_copy.return_value = [LayoutBinding(value="&copied", params=[])]

            result = layer_service.add_layer(
                layout_file=temp_layout_file,
                layer_name="CopiedLayer",
                position=1,
                copy_from="Base",
            )

            assert result["layer_name"] == "CopiedLayer"
            assert result["copy_from"] == "Base"
            mock_copy.assert_called_once_with(sample_layout_data, "Base")

    @patch("glovebox.layout.layer.service.load_layout_file")
    @patch("glovebox.layout.layer.service.save_layout_file")
    @patch("glovebox.layout.layer.service.validate_layer_name_unique")
    @patch("glovebox.layout.layer.service.validate_position_index")
    @patch("glovebox.layout.layer.service.validate_output_path")
    def test_add_layer_with_import_from(
        self,
        mock_validate_output,
        mock_validate_position,
        mock_validate_unique,
        mock_save,
        mock_load,
        layer_service,
        sample_layout_data,
        temp_layout_file,
        temp_import_file,
    ):
        """Test adding layer with import_from parameter."""
        mock_load.return_value = sample_layout_data
        mock_validate_position.return_value = 2

        with patch.object(layer_service, "_import_layer_bindings") as mock_import:
            mock_import.return_value = [LayoutBinding(value="&imported", params=[])]

            result = layer_service.add_layer(
                layout_file=temp_layout_file,
                layer_name="ImportedLayer",
                position=2,
                import_from=temp_import_file,
                import_layer="TestLayer",
            )

            assert result["layer_name"] == "ImportedLayer"
            assert result["import_from"] == temp_import_file
            assert result["import_layer"] == "TestLayer"
            mock_import.assert_called_once_with(temp_import_file, "TestLayer")

    def test_add_layer_conflicting_options(
        self, layer_service, temp_layout_file, temp_import_file
    ):
        """Test adding layer with conflicting options raises error."""
        with pytest.raises(
            ValueError, match="Cannot use copy_from and import_from together"
        ):
            layer_service.add_layer(
                layout_file=temp_layout_file,
                layer_name="ConflictLayer",
                copy_from="Base",
                import_from=temp_import_file,
            )

    def test_add_layer_import_layer_without_import_from(
        self, layer_service, temp_layout_file
    ):
        """Test import_layer without import_from raises error."""
        with pytest.raises(ValueError, match="import_layer requires import_from"):
            layer_service.add_layer(
                layout_file=temp_layout_file,
                layer_name="ErrorLayer",
                import_layer="TestLayer",
            )

    @patch("glovebox.layout.layer.service.load_layout_file")
    @patch("glovebox.layout.layer.service.save_layout_file")
    @patch("glovebox.layout.layer.service.validate_layer_name_unique")
    @patch("glovebox.layout.layer.service.validate_position_index")
    @patch("glovebox.layout.layer.service.validate_output_path")
    def test_add_layer_default_bindings(
        self,
        mock_validate_output,
        mock_validate_position,
        mock_validate_unique,
        mock_save,
        mock_load,
        layer_service,
        sample_layout_data,
        temp_layout_file,
    ):
        """Test adding layer with default bindings."""
        mock_load.return_value = sample_layout_data
        mock_validate_position.return_value = 0

        result = layer_service.add_layer(
            layout_file=temp_layout_file,
            layer_name="DefaultLayer",
            position=0,
        )

        # Verify layer was added at position 0
        assert sample_layout_data.layer_names[0] == "DefaultLayer"
        # Check that default bindings were created (80 &none bindings)
        assert len(sample_layout_data.layers[0]) == 80
        assert all(binding.value == "&none" for binding in sample_layout_data.layers[0])

    @patch("glovebox.layout.layer.service.load_layout_file")
    @patch("glovebox.layout.layer.service.save_layout_file")
    @patch("glovebox.layout.layer.service.validate_layer_name_unique")
    @patch("glovebox.layout.layer.service.validate_position_index")
    @patch("glovebox.layout.layer.service.validate_output_path")
    def test_add_layer_with_output_path(
        self,
        mock_validate_output,
        mock_validate_position,
        mock_validate_unique,
        mock_save,
        mock_load,
        layer_service,
        sample_layout_data,
        temp_layout_file,
        tmp_path,
    ):
        """Test adding layer with custom output path."""
        mock_load.return_value = sample_layout_data
        mock_validate_position.return_value = 1

        output_path = tmp_path / "output_layout.json"
        result = layer_service.add_layer(
            layout_file=temp_layout_file,
            layer_name="OutputLayer",
            position=1,
            output=output_path,
            force=True,
        )

        assert result["output_path"] == output_path
        mock_validate_output.assert_called_once_with(
            output_path, temp_layout_file, True
        )


class TestRemoveLayer:
    """Test remove_layer method with enhanced capabilities."""

    @patch("glovebox.layout.layer.service.load_layout_file")
    @patch("glovebox.layout.layer.service.save_layout_file")
    @patch("glovebox.layout.layer.service.validate_output_path")
    def test_remove_layer_by_name(
        self,
        mock_validate_output,
        mock_save,
        mock_load,
        layer_service,
        sample_layout_data,
        temp_layout_file,
    ):
        """Test basic layer removal by name."""
        mock_load.return_value = sample_layout_data

        result = layer_service.remove_layer(
            layout_file=temp_layout_file,
            layer_identifier="Lower",
        )

        assert result["removed_count"] == 1
        assert len(result["removed_layers"]) == 1
        assert result["removed_layers"][0]["name"] == "Lower"
        assert result["removed_layers"][0]["position"] == 1
        assert result["remaining_layers"] == 2
        assert result["output_path"] == temp_layout_file

        mock_validate_output.assert_called_once_with(
            temp_layout_file, temp_layout_file, False
        )
        mock_save.assert_called_once()

    @patch("glovebox.layout.layer.service.load_layout_file")
    @patch("glovebox.layout.layer.service.save_layout_file")
    @patch("glovebox.layout.layer.service.validate_output_path")
    def test_remove_layer_by_index(
        self,
        mock_validate_output,
        mock_save,
        mock_load,
        layer_service,
        sample_layout_data,
        temp_layout_file,
    ):
        """Test layer removal by index."""
        mock_load.return_value = sample_layout_data

        result = layer_service.remove_layer(
            layout_file=temp_layout_file,
            layer_identifier="1",  # Remove "Lower" at index 1
        )

        assert result["removed_count"] == 1
        assert result["removed_layers"][0]["name"] == "Lower"
        assert result["removed_layers"][0]["position"] == 1
        assert result["remaining_layers"] == 2

    @patch("glovebox.layout.layer.service.load_layout_file")
    @patch("glovebox.layout.layer.service.save_layout_file")
    @patch("glovebox.layout.layer.service.validate_output_path")
    def test_remove_layer_by_wildcard_pattern(
        self,
        mock_validate_output,
        mock_save,
        mock_load,
        layer_service,
        temp_layout_file,
    ):
        """Test layer removal by wildcard pattern."""
        # Create layout with Mouse layers for pattern testing
        layout_data = LayoutData(
            keyboard="glove80",
            title="Test Layout",
            layer_names=["Base", "Mouse", "MouseSlow", "MouseFast", "Upper"],
            layers=[
                [LayoutBinding(value="&kp", params=[])],
                [LayoutBinding(value="&trans", params=[])],
                [LayoutBinding(value="&tog", params=[])],
                [LayoutBinding(value="&sl", params=[])],
                [LayoutBinding(value="&mt", params=[])],
            ],
        )
        mock_load.return_value = layout_data

        result = layer_service.remove_layer(
            layout_file=temp_layout_file,
            layer_identifier="Mouse*",
        )

        assert result["removed_count"] == 3
        removed_names = [layer["name"] for layer in result["removed_layers"]]
        assert "Mouse" in removed_names
        assert "MouseSlow" in removed_names
        assert "MouseFast" in removed_names
        assert result["remaining_layers"] == 2

    @patch("glovebox.layout.layer.service.load_layout_file")
    @patch("glovebox.layout.layer.service.save_layout_file")
    @patch("glovebox.layout.layer.service.validate_output_path")
    def test_remove_layer_by_regex_pattern(
        self,
        mock_validate_output,
        mock_save,
        mock_load,
        layer_service,
        temp_layout_file,
    ):
        """Test layer removal by regex pattern."""
        # Create layout with Index layers for regex testing
        layout_data = LayoutData(
            keyboard="glove80",
            title="Test Layout",
            layer_names=["Base", "LeftIndex", "RightIndex", "Upper"],
            layers=[
                [LayoutBinding(value="&kp", params=[])],
                [LayoutBinding(value="&trans", params=[])],
                [LayoutBinding(value="&tog", params=[])],
                [LayoutBinding(value="&sl", params=[])],
            ],
        )
        mock_load.return_value = layout_data

        result = layer_service.remove_layer(
            layout_file=temp_layout_file,
            layer_identifier=".*Index",  # Regex pattern
        )

        assert result["removed_count"] == 2
        removed_names = [layer["name"] for layer in result["removed_layers"]]
        assert "LeftIndex" in removed_names
        assert "RightIndex" in removed_names
        assert result["remaining_layers"] == 2

    def test_remove_layer_no_matches_with_warnings(
        self,
        layer_service,
        sample_layout_data,
        temp_layout_file,
    ):
        """Test removing layer with no matches returns warnings."""
        with patch("glovebox.layout.layer.service.load_layout_file") as mock_load:
            mock_load.return_value = sample_layout_data

            result = layer_service.remove_layer(
                layout_file=temp_layout_file,
                layer_identifier="NonExistent",
                warn_on_no_match=True,
            )
            
            assert result["removed_count"] == 0
            assert len(result["warnings"]) == 1
            assert "No layers found matching identifier 'NonExistent'" in result["warnings"][0]
            assert not result["had_matches"]

    def test_remove_layer_no_matches_without_warnings(
        self,
        layer_service,
        sample_layout_data,
        temp_layout_file,
    ):
        """Test removing layer with no matches and warnings disabled."""
        with patch("glovebox.layout.layer.service.load_layout_file") as mock_load:
            mock_load.return_value = sample_layout_data

            result = layer_service.remove_layer(
                layout_file=temp_layout_file,
                layer_identifier="NonExistent",
                warn_on_no_match=False,
            )
            
            assert result["removed_count"] == 0
            assert len(result["warnings"]) == 0
            assert not result["had_matches"]

    def test_remove_layer_invalid_index(
        self,
        layer_service,
        sample_layout_data,
        temp_layout_file,
    ):
        """Test removing layer with invalid index returns warnings."""
        with patch("glovebox.layout.layer.service.load_layout_file") as mock_load:
            mock_load.return_value = sample_layout_data

            result = layer_service.remove_layer(
                layout_file=temp_layout_file,
                layer_identifier="10",  # Beyond bounds
                warn_on_no_match=True,
            )
            
            assert result["removed_count"] == 0
            assert len(result["warnings"]) == 1
            assert "No layers found matching identifier '10'" in result["warnings"][0]
            assert not result["had_matches"]

    @patch("glovebox.layout.layer.service.load_layout_file")
    @patch("glovebox.layout.layer.service.save_layout_file")
    @patch("glovebox.layout.layer.service.validate_output_path")
    def test_remove_layer_bounds_check(
        self,
        mock_validate_output,
        mock_save,
        mock_load,
        layer_service,
        temp_layout_file,
    ):
        """Test removing layer with bounds check for layers list."""
        # Create layout data with more layer names than layers
        layout_data = LayoutData(
            keyboard="glove80",
            title="Test Layout",
            layer_names=["Base", "Lower", "Upper", "Extra"],
            layers=[
                [LayoutBinding(value="&kp", params=[])],
                [LayoutBinding(value="&trans", params=[])],
                [LayoutBinding(value="&tog", params=[])],
            ],
        )

        mock_load.return_value = layout_data

        result = layer_service.remove_layer(
            layout_file=temp_layout_file,
            layer_identifier="Extra",
        )

        # Should not attempt to pop from layers list since index >= len(layers)
        assert result["removed_layers"][0]["position"] == 3
        assert len(layout_data.layer_names) == 3  # One removed
        assert len(layout_data.layers) == 3  # Unchanged

    @patch("glovebox.layout.layer.service.load_layout_file")
    @patch("glovebox.layout.layer.service.save_layout_file")
    @patch("glovebox.layout.layer.service.validate_output_path")
    def test_remove_layer_with_output_path(
        self,
        mock_validate_output,
        mock_save,
        mock_load,
        layer_service,
        sample_layout_data,
        temp_layout_file,
        tmp_path,
    ):
        """Test removing layer with custom output path."""
        mock_load.return_value = sample_layout_data

        output_path = tmp_path / "removed_layout.json"
        result = layer_service.remove_layer(
            layout_file=temp_layout_file,
            layer_identifier="Base",
            output=output_path,
            force=True,
        )

        assert result["output_path"] == output_path
        mock_validate_output.assert_called_once_with(
            output_path, temp_layout_file, True
        )

    @patch("glovebox.layout.layer.service.load_layout_file")
    @patch("glovebox.layout.layer.service.save_layout_file")
    @patch("glovebox.layout.layer.service.validate_output_path")
    def test_remove_multiple_layers_index_order(
        self,
        mock_validate_output,
        mock_save,
        mock_load,
        layer_service,
        temp_layout_file,
    ):
        """Test that multiple layers are removed in correct order (high to low index)."""
        # Create layout with test layers
        layout_data = LayoutData(
            keyboard="glove80",
            title="Test Layout",
            layer_names=["Test1", "Test2", "Test3", "Test4"],
            layers=[
                [LayoutBinding(value="&kp", params=[])],
                [LayoutBinding(value="&trans", params=[])],
                [LayoutBinding(value="&tog", params=[])],
                [LayoutBinding(value="&sl", params=[])],
            ],
        )
        mock_load.return_value = layout_data

        result = layer_service.remove_layer(
            layout_file=temp_layout_file,
            layer_identifier="Test*",
        )

        assert result["removed_count"] == 4
        # Verify they were removed in descending order of original positions
        positions = [layer["position"] for layer in result["removed_layers"]]
        assert positions == [3, 2, 1, 0]  # High to low index order


class TestFindLayersToRemove:
    """Test _find_layers_to_remove helper method."""

    def test_find_layers_by_index(self, layer_service, sample_layout_data):
        """Test finding layers by valid index."""
        layers = layer_service._find_layers_to_remove(sample_layout_data, "1")

        assert len(layers) == 1
        assert layers[0]["name"] == "Lower"
        assert layers[0]["index"] == 1

    def test_find_layers_by_invalid_index(self, layer_service, sample_layout_data):
        """Test finding layers by invalid index returns empty list."""
        layers = layer_service._find_layers_to_remove(sample_layout_data, "10")
        assert layers == []

    def test_find_layers_by_negative_index(self, layer_service, sample_layout_data):
        """Test finding layers by negative index returns empty list."""
        layers = layer_service._find_layers_to_remove(sample_layout_data, "-1")
        assert layers == []

    def test_find_layers_by_exact_name(self, layer_service, sample_layout_data):
        """Test finding layers by exact name match."""
        layers = layer_service._find_layers_to_remove(sample_layout_data, "Upper")

        assert len(layers) == 1
        assert layers[0]["name"] == "Upper"
        assert layers[0]["index"] == 2

    def test_find_layers_by_wildcard_pattern(self, layer_service):
        """Test finding layers by wildcard pattern."""
        layout_data = LayoutData(
            keyboard="glove80",
            title="Test Layout",
            layer_names=["Base", "Mouse", "MouseSlow", "MouseFast", "Upper"],
            layers=[[], [], [], [], []],
        )

        layers = layer_service._find_layers_to_remove(layout_data, "Mouse*")

        assert len(layers) == 3
        names = [layer["name"] for layer in layers]
        assert "Mouse" in names
        assert "MouseSlow" in names
        assert "MouseFast" in names

    def test_find_layers_by_regex_pattern(self, layer_service):
        """Test finding layers by regex pattern."""
        layout_data = LayoutData(
            keyboard="glove80",
            title="Test Layout",
            layer_names=["Base", "LeftIndex", "RightIndex", "Upper"],
            layers=[[], [], [], []],
        )

        layers = layer_service._find_layers_to_remove(layout_data, ".*Index")

        assert len(layers) == 2
        names = [layer["name"] for layer in layers]
        assert "LeftIndex" in names
        assert "RightIndex" in names

    def test_find_layers_by_complex_regex(self, layer_service):
        """Test finding layers by complex regex pattern."""
        layout_data = LayoutData(
            keyboard="glove80",
            title="Test Layout",
            layer_names=["Base", "Layer1", "Layer2", "MyLayer", "Upper"],
            layers=[[], [], [], [], []],
        )

        layers = layer_service._find_layers_to_remove(layout_data, "Layer[0-9]+")

        assert len(layers) == 2
        names = [layer["name"] for layer in layers]
        assert "Layer1" in names
        assert "Layer2" in names
        assert "MyLayer" not in names

    def test_find_layers_invalid_regex(self, layer_service, sample_layout_data):
        """Test finding layers with invalid regex returns empty list."""
        layers = layer_service._find_layers_to_remove(sample_layout_data, "[invalid")
        assert layers == []

    def test_find_layers_no_matches(self, layer_service, sample_layout_data):
        """Test finding layers with no matches returns empty list."""
        layers = layer_service._find_layers_to_remove(sample_layout_data, "NonExistent")
        assert layers == []

    def test_find_layers_mixed_special_chars(self, layer_service):
        """Test wildcard conversion doesn't affect complex regex patterns."""
        layout_data = LayoutData(
            keyboard="glove80",
            title="Test Layout",
            layer_names=["Base", "Test[1]", "Test*Real", "Upper"],
            layers=[[], [], [], []],
        )

        # This contains both * and regex special chars, should not be converted
        layers = layer_service._find_layers_to_remove(layout_data, "Test\\*")

        assert len(layers) == 1
        assert layers[0]["name"] == "Test*Real"


class TestMoveLayer:
    """Test move_layer method."""

    @patch("glovebox.layout.layer.service.load_layout_file")
    @patch("glovebox.layout.layer.service.save_layout_file")
    @patch("glovebox.layout.layer.service.validate_layer_exists")
    @patch("glovebox.layout.layer.service.validate_output_path")
    def test_move_layer_basic(
        self,
        mock_validate_output,
        mock_validate_exists,
        mock_save,
        mock_load,
        layer_service,
        sample_layout_data,
        temp_layout_file,
    ):
        """Test basic layer movement."""
        mock_load.return_value = sample_layout_data
        mock_validate_exists.return_value = 0  # Move "Base" from position 0

        result = layer_service.move_layer(
            layout_file=temp_layout_file,
            layer_name="Base",
            new_position=2,
        )

        assert result["layer_name"] == "Base"
        assert result["from_position"] == 0
        assert result["to_position"] == 2
        assert result["moved"] is True
        assert result["output_path"] == temp_layout_file

        # Verify the layer was moved
        assert sample_layout_data.layer_names[2] == "Base"

    @patch("glovebox.layout.layer.service.load_layout_file")
    @patch("glovebox.layout.layer.service.save_layout_file")
    @patch("glovebox.layout.layer.service.validate_layer_exists")
    @patch("glovebox.layout.layer.service.validate_output_path")
    def test_move_layer_negative_position(
        self,
        mock_validate_output,
        mock_validate_exists,
        mock_save,
        mock_load,
        layer_service,
        sample_layout_data,
        temp_layout_file,
    ):
        """Test moving layer with negative position."""
        mock_load.return_value = sample_layout_data
        mock_validate_exists.return_value = 2  # Move "Upper" from position 2

        result = layer_service.move_layer(
            layout_file=temp_layout_file,
            layer_name="Upper",
            new_position=-1,  # Should become position 2 (last)
        )

        assert result["to_position"] == 2  # Should be normalized to last position

    @patch("glovebox.layout.layer.service.load_layout_file")
    @patch("glovebox.layout.layer.service.save_layout_file")
    @patch("glovebox.layout.layer.service.validate_layer_exists")
    @patch("glovebox.layout.layer.service.validate_output_path")
    def test_move_layer_beyond_bounds(
        self,
        mock_validate_output,
        mock_validate_exists,
        mock_save,
        mock_load,
        layer_service,
        sample_layout_data,
        temp_layout_file,
    ):
        """Test moving layer beyond layer count."""
        mock_load.return_value = sample_layout_data
        mock_validate_exists.return_value = 0  # Move "Base" from position 0

        result = layer_service.move_layer(
            layout_file=temp_layout_file,
            layer_name="Base",
            new_position=10,  # Beyond bounds
        )

        assert result["to_position"] == 2  # Should be clamped to last position

    def test_move_layer_no_change(
        self, layer_service, sample_layout_data, temp_layout_file
    ):
        """Test moving layer to same position."""
        with (
            patch("glovebox.layout.layer.service.load_layout_file") as mock_load,
            patch(
                "glovebox.layout.layer.service.validate_layer_exists"
            ) as mock_validate_exists,
        ):
            mock_load.return_value = sample_layout_data
            mock_validate_exists.return_value = 1  # Current position

            result = layer_service.move_layer(
                layout_file=temp_layout_file,
                layer_name="Lower",
                new_position=1,  # Same position
            )

            assert result["moved"] is False
            assert result["from_position"] == 1
            assert result["to_position"] == 1

    @patch("glovebox.layout.layer.service.load_layout_file")
    @patch("glovebox.layout.layer.service.save_layout_file")
    @patch("glovebox.layout.layer.service.validate_layer_exists")
    @patch("glovebox.layout.layer.service.validate_output_path")
    def test_move_layer_with_bindings(
        self,
        mock_validate_output,
        mock_validate_exists,
        mock_save,
        mock_load,
        layer_service,
        sample_layout_data,
        temp_layout_file,
    ):
        """Test moving layer that has bindings."""
        mock_load.return_value = sample_layout_data
        mock_validate_exists.return_value = 1  # Move "Lower" from position 1

        original_bindings = sample_layout_data.layers[1]

        result = layer_service.move_layer(
            layout_file=temp_layout_file,
            layer_name="Lower",
            new_position=0,
        )

        assert result["moved"] is True
        # Verify bindings moved with the layer
        assert sample_layout_data.layers[0] is original_bindings

    @patch("glovebox.layout.layer.service.load_layout_file")
    @patch("glovebox.layout.layer.service.save_layout_file")
    @patch("glovebox.layout.layer.service.validate_layer_exists")
    @patch("glovebox.layout.layer.service.validate_output_path")
    def test_move_layer_beyond_layers_list(
        self,
        mock_validate_output,
        mock_validate_exists,
        mock_save,
        mock_load,
        layer_service,
        temp_layout_file,
    ):
        """Test moving layer when current position is beyond layers list."""
        # Create layout data with more layer names than layers
        layout_data = LayoutData(
            keyboard="glove80",
            title="Test Layout",
            layer_names=["Base", "Lower", "Upper", "Extra"],
            layers=[
                [LayoutBinding(value="&kp", params=[])],
                [LayoutBinding(value="&trans", params=[])],
            ],
        )

        mock_load.return_value = layout_data
        mock_validate_exists.return_value = 3  # Position beyond layers list

        result = layer_service.move_layer(
            layout_file=temp_layout_file,
            layer_name="Extra",
            new_position=0,
        )

        assert result["moved"] is True
        # No bindings to move since current_idx >= len(layers), so layer_bindings was None
        # Since layer_bindings is None, nothing is inserted into layers list
        assert (
            len(layout_data.layers) == 2
        )  # Unchanged, no insertion since layer_bindings was None
        # But the layer name was moved successfully
        assert layout_data.layer_names[0] == "Extra"


class TestListLayers:
    """Test list_layers method."""

    @patch("glovebox.layout.layer.service.load_layout_file")
    def test_list_layers_basic(
        self,
        mock_load,
        layer_service,
        sample_layout_data,
        temp_layout_file,
    ):
        """Test basic layer listing."""
        mock_load.return_value = sample_layout_data

        result = layer_service.list_layers(temp_layout_file)

        assert result["total_layers"] == 3
        assert len(result["layers"]) == 3

        expected_layers = [
            {"position": 0, "name": "Base", "binding_count": 2},
            {"position": 1, "name": "Lower", "binding_count": 2},
            {"position": 2, "name": "Upper", "binding_count": 2},
        ]
        assert result["layers"] == expected_layers

    @patch("glovebox.layout.layer.service.load_layout_file")
    def test_list_layers_missing_bindings(
        self,
        mock_load,
        layer_service,
        temp_layout_file,
    ):
        """Test listing layers when some layers have no bindings."""
        layout_data = LayoutData(
            keyboard="glove80",
            title="Test Layout",
            layer_names=["Base", "Lower", "Extra"],
            layers=[
                [LayoutBinding(value="&kp", params=[])],
                [LayoutBinding(value="&trans", params=[])],
            ],
        )

        mock_load.return_value = layout_data

        result = layer_service.list_layers(temp_layout_file)

        assert result["total_layers"] == 3
        expected_layers = [
            {"position": 0, "name": "Base", "binding_count": 1},
            {"position": 1, "name": "Lower", "binding_count": 1},
            {"position": 2, "name": "Extra", "binding_count": 0},
        ]
        assert result["layers"] == expected_layers


class TestExportLayer:
    """Test export_layer method."""

    @patch("glovebox.layout.layer.service.load_layout_file")
    @patch("glovebox.layout.layer.service.save_json_data")
    @patch("glovebox.layout.layer.service.validate_layer_exists")
    @patch("glovebox.layout.layer.service.validate_layer_has_bindings")
    @patch("glovebox.layout.layer.service.validate_output_path")
    def test_export_layer_bindings_format(
        self,
        mock_validate_output,
        mock_validate_bindings,
        mock_validate_exists,
        mock_save,
        mock_load,
        layer_service,
        sample_layout_data,
        temp_layout_file,
        tmp_path,
    ):
        """Test exporting layer in bindings format."""
        mock_load.return_value = sample_layout_data
        mock_validate_exists.return_value = 0

        output_file = tmp_path / "exported_bindings.json"
        result = layer_service.export_layer(
            layout_file=temp_layout_file,
            layer_name="Base",
            output=output_file,
            format_type="bindings",
        )

        assert result["layer_name"] == "Base"
        assert result["output_file"] == output_file
        assert result["format"] == "bindings"
        assert result["binding_count"] == 2

        # Check that save_json_data was called with the right format
        args, _ = mock_save.call_args
        exported_data = args[0]
        assert isinstance(exported_data, list)
        assert len(exported_data) == 2

    @patch("glovebox.layout.layer.service.load_layout_file")
    @patch("glovebox.layout.layer.service.save_json_data")
    @patch("glovebox.layout.layer.service.validate_layer_exists")
    @patch("glovebox.layout.layer.service.validate_layer_has_bindings")
    @patch("glovebox.layout.layer.service.validate_output_path")
    def test_export_layer_layer_format(
        self,
        mock_validate_output,
        mock_validate_bindings,
        mock_validate_exists,
        mock_save,
        mock_load,
        layer_service,
        sample_layout_data,
        temp_layout_file,
        tmp_path,
    ):
        """Test exporting layer in layer format."""
        mock_load.return_value = sample_layout_data
        mock_validate_exists.return_value = 1

        output_file = tmp_path / "exported_layer.json"
        result = layer_service.export_layer(
            layout_file=temp_layout_file,
            layer_name="Lower",
            output=output_file,
            format_type="layer",
        )

        assert result["format"] == "layer"

        # Check that save_json_data was called with layer object format
        args, _ = mock_save.call_args
        exported_data = args[0]
        assert isinstance(exported_data, dict)
        assert "name" in exported_data
        assert "bindings" in exported_data
        assert exported_data["name"] == "Lower"

    @patch("glovebox.layout.layer.service.load_layout_file")
    @patch("glovebox.layout.layer.service.save_json_data")
    @patch("glovebox.layout.layer.service.validate_layer_exists")
    @patch("glovebox.layout.layer.service.validate_layer_has_bindings")
    @patch("glovebox.layout.layer.service.validate_output_path")
    def test_export_layer_full_format(
        self,
        mock_validate_output,
        mock_validate_bindings,
        mock_validate_exists,
        mock_save,
        mock_load,
        layer_service,
        sample_layout_data,
        temp_layout_file,
        tmp_path,
    ):
        """Test exporting layer in full layout format."""
        mock_load.return_value = sample_layout_data
        mock_validate_exists.return_value = 2

        output_file = tmp_path / "exported_full.json"
        result = layer_service.export_layer(
            layout_file=temp_layout_file,
            layer_name="Upper",
            output=output_file,
            format_type="full",
        )

        assert result["format"] == "full"

        # Check that save_json_data was called with full layout format
        args, _ = mock_save.call_args
        exported_data = args[0]
        assert isinstance(exported_data, dict)
        assert "keyboard" in exported_data
        assert "title" in exported_data
        assert "layer_names" in exported_data
        assert "layers" in exported_data
        assert exported_data["keyboard"] == "glove80"
        assert exported_data["layer_names"] == ["Upper"]

    def test_export_layer_invalid_format(
        self, layer_service, temp_layout_file, tmp_path
    ):
        """Test exporting layer with invalid format."""
        output_file = tmp_path / "exported.json"

        with (
            patch("glovebox.layout.layer.service.load_layout_file") as mock_load,
            patch(
                "glovebox.layout.layer.service.validate_layer_exists"
            ) as mock_validate_exists,
            patch(
                "glovebox.layout.layer.service.validate_layer_has_bindings"
            ) as mock_validate_bindings,
            patch(
                "glovebox.layout.layer.service.validate_output_path"
            ) as mock_validate_output,
        ):
            mock_load.return_value = LayoutData(
                keyboard="test",
                title="Test Layout",
                layer_names=["Base"],
                layers=[[LayoutBinding(value="&kp", params=[])]],
            )
            mock_validate_exists.return_value = 0

            # Test the actual _create_export_data method directly
            with pytest.raises(ValueError, match="Invalid format: invalid"):
                layer_service._create_export_data(
                    mock_load.return_value,
                    "Base",
                    [LayoutBinding(value="&kp", params=[])],
                    "invalid",
                )


class TestCreateLayerBindings:
    """Test _create_layer_bindings method."""

    def test_create_layer_bindings_default(self, layer_service, sample_layout_data):
        """Test creating default layer bindings."""
        bindings = layer_service._create_layer_bindings(
            sample_layout_data, None, None, None
        )

        assert len(bindings) == 80
        assert all(binding.value == "&none" for binding in bindings)
        assert all(binding.params == [] for binding in bindings)

    def test_create_layer_bindings_copy_from(self, layer_service, sample_layout_data):
        """Test creating layer bindings from copy_from."""
        with patch.object(layer_service, "_copy_layer_bindings") as mock_copy:
            expected_bindings = [LayoutBinding(value="&copied", params=[])]
            mock_copy.return_value = expected_bindings

            bindings = layer_service._create_layer_bindings(
                sample_layout_data, "Base", None, None
            )

            assert bindings == expected_bindings
            mock_copy.assert_called_once_with(sample_layout_data, "Base")

    def test_create_layer_bindings_import_from(
        self, layer_service, sample_layout_data, tmp_path
    ):
        """Test creating layer bindings from import_from."""
        import_file = tmp_path / "import.json"

        with patch.object(layer_service, "_import_layer_bindings") as mock_import:
            expected_bindings = [LayoutBinding(value="&imported", params=[])]
            mock_import.return_value = expected_bindings

            bindings = layer_service._create_layer_bindings(
                sample_layout_data, None, import_file, "TestLayer"
            )

            assert bindings == expected_bindings
            mock_import.assert_called_once_with(import_file, "TestLayer")


class TestImportLayerBindings:
    """Test _import_layer_bindings method."""

    def test_import_layer_bindings_file_not_found(self, layer_service, tmp_path):
        """Test importing from non-existent file."""
        non_existent_file = tmp_path / "missing.json"

        with pytest.raises(FileNotFoundError, match="Import file not found"):
            layer_service._import_layer_bindings(non_existent_file, None)

    def test_import_layer_bindings_list_format(self, layer_service, tmp_path):
        """Test importing from list format."""
        import_file = tmp_path / "list_import.json"
        import_data = [
            {"value": "&kp", "params": []},
            {"value": "&mt", "params": []},
        ]
        import_file.write_text(json.dumps(import_data))

        with patch.object(layer_service, "_convert_to_layout_bindings") as mock_convert:
            expected_bindings = [LayoutBinding(value="&converted", params=[])]
            mock_convert.return_value = expected_bindings

            bindings = layer_service._import_layer_bindings(import_file, None)

            assert bindings == expected_bindings
            mock_convert.assert_called_once_with(import_data)

    def test_import_layer_bindings_dict_with_bindings(self, layer_service, tmp_path):
        """Test importing from dict with bindings key."""
        import_file = tmp_path / "dict_import.json"
        import_data = {
            "name": "TestLayer",
            "bindings": [{"value": "&kp", "params": []}],
        }
        import_file.write_text(json.dumps(import_data))

        with patch.object(layer_service, "_convert_to_layout_bindings") as mock_convert:
            expected_bindings = [LayoutBinding(value="&converted", params=[])]
            mock_convert.return_value = expected_bindings

            bindings = layer_service._import_layer_bindings(import_file, None)

            assert bindings == expected_bindings
            mock_convert.assert_called_once_with(import_data["bindings"])

    def test_import_layer_bindings_dict_with_import_layer(
        self, layer_service, tmp_path
    ):
        """Test importing from dict with specific layer."""
        import_file = tmp_path / "full_import.json"
        import_data = {
            "layer_names": ["Base", "Lower"],
            "layers": [
                [{"value": "&kp", "params": []}],
                [{"value": "&trans", "params": []}],
            ],
        }
        import_file.write_text(json.dumps(import_data))

        with patch.object(
            layer_service, "_import_specific_layer"
        ) as mock_import_specific:
            expected_bindings = [LayoutBinding(value="&specific", params=[])]
            mock_import_specific.return_value = expected_bindings

            bindings = layer_service._import_layer_bindings(import_file, "Lower")

            assert bindings == expected_bindings
            mock_import_specific.assert_called_once_with(import_data, "Lower")

    def test_import_layer_bindings_dict_without_import_layer(
        self, layer_service, tmp_path
    ):
        """Test importing from dict without import_layer parameter."""
        import_file = tmp_path / "full_import.json"
        import_data = {
            "layer_names": ["Base", "Lower"],
            "layers": [
                [{"value": "&kp", "params": []}],
                [{"value": "&trans", "params": []}],
            ],
        }
        import_file.write_text(json.dumps(import_data))

        with pytest.raises(ValueError, match="Import file appears to be a full layout"):
            layer_service._import_layer_bindings(import_file, None)

    def test_import_layer_bindings_invalid_format(self, layer_service, tmp_path):
        """Test importing from invalid format."""
        import_file = tmp_path / "invalid_import.json"
        import_file.write_text('"invalid string format"')

        with pytest.raises(ValueError, match="Invalid import file format"):
            layer_service._import_layer_bindings(import_file, None)


class TestImportSpecificLayer:
    """Test _import_specific_layer method."""

    def test_import_specific_layer_invalid_layout(self, layer_service):
        """Test importing from invalid layout data."""
        invalid_data = {"not": "a layout"}

        with pytest.raises(ValueError, match="Import file is not a valid layout JSON"):
            layer_service._import_specific_layer(invalid_data, "TestLayer")

    def test_import_specific_layer_missing_layer(self, layer_service):
        """Test importing non-existent layer."""
        layout_data = {
            "layer_names": ["Base", "Lower"],
            "layers": [[], []],
        }

        with pytest.raises(
            ValueError, match="Layer 'Missing' not found in import file"
        ):
            layer_service._import_specific_layer(layout_data, "Missing")

    def test_import_specific_layer_no_binding_data(self, layer_service):
        """Test importing layer without binding data."""
        layout_data = {
            "layer_names": ["Base", "Lower", "Upper"],
            "layers": [[], []],  # Missing binding data for Upper
        }

        with pytest.raises(ValueError, match="Layer 'Upper' has no binding data"):
            layer_service._import_specific_layer(layout_data, "Upper")

    def test_import_specific_layer_success(self, layer_service):
        """Test successful specific layer import."""
        layout_data = {
            "layer_names": ["Base", "Lower"],
            "layers": [
                [{"value": "&kp", "params": []}],
                [{"value": "&trans", "params": []}],
            ],
        }

        with patch.object(layer_service, "_convert_to_layout_bindings") as mock_convert:
            expected_bindings = [LayoutBinding(value="&converted", params=[])]
            mock_convert.return_value = expected_bindings

            bindings = layer_service._import_specific_layer(layout_data, "Lower")

            assert bindings == expected_bindings
            mock_convert.assert_called_once_with(layout_data["layers"][1])  # type: ignore[index]


class TestCopyLayerBindings:
    """Test _copy_layer_bindings method."""

    @patch("glovebox.layout.layer.service.validate_layer_exists")
    @patch("glovebox.layout.layer.service.validate_layer_has_bindings")
    def test_copy_layer_bindings_success(
        self,
        mock_validate_bindings,
        mock_validate_exists,
        layer_service,
        sample_layout_data,
    ):
        """Test successful layer binding copy."""
        mock_validate_exists.return_value = 0

        bindings = layer_service._copy_layer_bindings(sample_layout_data, "Base")

        assert len(bindings) == 2
        assert bindings[0].value == "&kp"
        assert bindings[1].value == "&none"
        # Verify it's a deep copy
        assert bindings is not sample_layout_data.layers[0]
        assert bindings[0] is not sample_layout_data.layers[0][0]

        mock_validate_exists.assert_called_once_with(sample_layout_data, "Base")
        mock_validate_bindings.assert_called_once_with(sample_layout_data, "Base", 0)


class TestConvertToLayoutBindings:
    """Test _convert_to_layout_bindings method."""

    def test_convert_to_layout_bindings_dict_format(self, layer_service):
        """Test converting dict format bindings."""
        bindings_data = [
            {"value": "&kp", "params": []},
            {"value": "&mt", "params": []},
        ]

        bindings = layer_service._convert_to_layout_bindings(bindings_data)

        assert len(bindings) == 2
        assert bindings[0].value == "&kp"
        assert bindings[1].value == "&mt"

    def test_convert_to_layout_bindings_string_format(self, layer_service):
        """Test converting string format bindings."""
        bindings_data = ["&kp", "&mt"]

        bindings = layer_service._convert_to_layout_bindings(bindings_data)

        assert len(bindings) == 2
        assert bindings[0].value == "&kp"
        assert bindings[0].params == []
        assert bindings[1].value == "&mt"
        assert bindings[1].params == []

    def test_convert_to_layout_bindings_mixed_format(self, layer_service):
        """Test converting mixed format bindings."""
        bindings_data = [
            {"value": "&kp", "params": []},
            "&mt",
        ]

        bindings = layer_service._convert_to_layout_bindings(bindings_data)

        assert len(bindings) == 2
        assert bindings[0].value == "&kp"
        assert bindings[1].value == "&mt"
        assert bindings[1].params == []


class TestCreateExportData:
    """Test _create_export_data method."""

    def test_create_export_data_bindings_format(
        self, layer_service, sample_layout_data
    ):
        """Test creating export data in bindings format."""
        layer_bindings = sample_layout_data.layers[0]

        export_data = layer_service._create_export_data(
            sample_layout_data, "Base", layer_bindings, "bindings"
        )

        assert isinstance(export_data, list)
        assert len(export_data) == 2

    def test_create_export_data_layer_format(self, layer_service, sample_layout_data):
        """Test creating export data in layer format."""
        layer_bindings = sample_layout_data.layers[0]

        export_data = layer_service._create_export_data(
            sample_layout_data, "Base", layer_bindings, "layer"
        )

        assert isinstance(export_data, dict)
        assert export_data["name"] == "Base"
        assert "bindings" in export_data
        assert len(export_data["bindings"]) == 2

    def test_create_export_data_full_format(self, layer_service, sample_layout_data):
        """Test creating export data in full format."""
        layer_bindings = sample_layout_data.layers[0]

        export_data = layer_service._create_export_data(
            sample_layout_data, "Base", layer_bindings, "full"
        )

        assert isinstance(export_data, dict)
        assert export_data["keyboard"] == "glove80"
        assert export_data["title"] == "Exported layer: Base"
        assert export_data["layer_names"] == ["Base"]
        assert len(export_data["layers"]) == 1
        assert len(export_data["layers"][0]) == 2

    def test_create_export_data_invalid_format(self, layer_service, sample_layout_data):
        """Test creating export data with invalid format."""
        layer_bindings = sample_layout_data.layers[0]

        with pytest.raises(ValueError, match="Invalid format: invalid"):
            layer_service._create_export_data(
                sample_layout_data, "Base", layer_bindings, "invalid"
            )


class TestLayerServiceIntegration:
    """Integration tests for layer service operations."""

    def test_full_layer_lifecycle(self, layer_service, temp_layout_file, tmp_path):
        """Test complete layer lifecycle: add, move, export, remove."""
        # Add a new layer
        with (
            patch("glovebox.layout.layer.service.load_layout_file") as mock_load,
            patch("glovebox.layout.layer.service.save_layout_file") as mock_save,
            patch("glovebox.layout.layer.service.validate_layer_name_unique"),
            patch(
                "glovebox.layout.layer.service.validate_position_index"
            ) as mock_validate_pos,
            patch("glovebox.layout.layer.service.validate_output_path"),
        ):
            layout_data = LayoutData(
                keyboard="test",
                title="Test Layout",
                layer_names=["Base"],
                layers=[[LayoutBinding(value="&kp", params=[])]],
            )
            mock_load.return_value = layout_data
            mock_validate_pos.return_value = 1

            # Add layer
            result = layer_service.add_layer(temp_layout_file, "NewLayer", position=1)
            assert result["layer_name"] == "NewLayer"

        # Move the layer
        with (
            patch("glovebox.layout.layer.service.load_layout_file") as mock_load,
            patch("glovebox.layout.layer.service.save_layout_file") as mock_save,
            patch(
                "glovebox.layout.layer.service.validate_layer_exists"
            ) as mock_validate_exists,
            patch("glovebox.layout.layer.service.validate_output_path"),
        ):
            mock_load.return_value = layout_data
            mock_validate_exists.return_value = 1

            result = layer_service.move_layer(
                temp_layout_file, "NewLayer", new_position=0
            )
            assert result["moved"] is True

        # Export the layer
        with (
            patch("glovebox.layout.layer.service.load_layout_file") as mock_load,
            patch("glovebox.layout.layer.service.save_json_data") as mock_save_json,
            patch(
                "glovebox.layout.layer.service.validate_layer_exists"
            ) as mock_validate_exists,
            patch("glovebox.layout.layer.service.validate_layer_has_bindings"),
            patch("glovebox.layout.layer.service.validate_output_path"),
        ):
            mock_load.return_value = layout_data
            mock_validate_exists.return_value = 0

            export_file = tmp_path / "exported.json"
            result = layer_service.export_layer(
                temp_layout_file, "NewLayer", export_file, "bindings"
            )
            assert result["format"] == "bindings"

        # Remove the layer
        with (
            patch("glovebox.layout.layer.service.load_layout_file") as mock_load,
            patch("glovebox.layout.layer.service.save_layout_file") as mock_save,
            patch("glovebox.layout.layer.service.validate_output_path"),
        ):
            mock_load.return_value = layout_data

            result = layer_service.remove_layer(temp_layout_file, "NewLayer")
            assert result["removed_count"] == 1
            assert result["removed_layers"][0]["name"] == "NewLayer"
