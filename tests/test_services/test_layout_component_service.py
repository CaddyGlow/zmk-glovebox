"""Tests for LayoutComponentService."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.core.errors import LayoutError
from glovebox.layout.component_service import (
    LayoutComponentService,
    create_layout_component_service,
)
from glovebox.layout.models import (
    LayoutBinding,
    LayoutData,
    LayoutMetadata,
    LayoutParam,
)
from glovebox.protocols.file_adapter_protocol import FileAdapterProtocol


class TestLayoutComponentService:
    """Test LayoutComponentService functionality."""

    @pytest.fixture
    def mock_file_adapter(self):
        """Create a mock file adapter for testing."""
        adapter = Mock(spec=FileAdapterProtocol)
        adapter.create_directory.return_value = None
        adapter.is_dir.return_value = True
        adapter.is_file.return_value = True
        adapter.sanitize_filename = lambda s: s.replace(" ", "_").lower()

        # Configure mock read_json to return different data based on path
        def mock_read_json(path):
            if path.name == "metadata.json":
                return {
                    "keyboard": "test_keyboard",
                    "title": "Test Keymap",
                    "notes": "Test notes",
                    "tags": ["test"],
                    "layer_names": ["DEFAULT", "LOWER", "UPPER"],
                    "uuid": "test-uuid",
                    "date": "2025-01-01T00:00:00",
                    "creator": "test",
                }
            elif "default.json" in str(path):
                return {
                    "layer_names": ["DEFAULT"],
                    "layers": [
                        [
                            {"value": "&kp", "params": [{"value": "A"}]}
                            for _ in range(80)
                        ]
                    ],
                }
            elif "lower.json" in str(path):
                return {
                    "layer_names": ["LOWER"],
                    "layers": [
                        [
                            {"value": "&kp", "params": [{"value": "1"}]}
                            for _ in range(80)
                        ]
                    ],
                }
            elif "upper.json" in str(path):
                return {
                    "layer_names": ["UPPER"],
                    "layers": [
                        [
                            {"value": "&kp", "params": [{"value": "F1"}]}
                            for _ in range(80)
                        ]
                    ],
                }
            return {}

        adapter.read_json.side_effect = mock_read_json
        adapter.read_text.return_value = "// Test DTSI content"

        return adapter

    @pytest.fixture
    def service(self, mock_file_adapter):
        """Create a LayoutComponentService for testing."""
        return LayoutComponentService(mock_file_adapter)

    @pytest.fixture
    def sample_keymap_data(self, sample_keymap_json):
        """Create a sample LayoutData model for testing."""
        return LayoutData.model_validate(sample_keymap_json)

    @pytest.fixture
    def output_dir(self, tmp_path):
        """Create a temporary output directory."""
        output_dir = tmp_path / "output"
        layers_dir = output_dir / "layers"
        output_dir.mkdir(exist_ok=True)
        layers_dir.mkdir(exist_ok=True)
        return output_dir

    def test_initialization(self, mock_file_adapter):
        """Test LayoutComponentService initialization."""
        service = LayoutComponentService(mock_file_adapter)
        assert service._file_adapter == mock_file_adapter
        assert service._service_name == "LayoutComponentService"
        assert service._service_version == "1.0.0"

    def test_split_components_success(self, service, sample_keymap_data, output_dir):
        """Test successful extraction of keymap components."""
        result = service.split_components(sample_keymap_data, output_dir)

        assert result.success is True
        assert result.layer_count == len(sample_keymap_data.layers)

        # Verify directory creation
        service._file_adapter.create_directory.assert_any_call(output_dir)
        service._file_adapter.create_directory.assert_any_call(output_dir / "layers")

        # Verify metadata extraction - behavior fields are excluded
        behavior_fields = {
            "variables",
            "holdTaps",
            "combos",
            "macros",
            "inputListeners",
            "config_parameters",
            "hold_taps",
            "input_listeners",
        }
        metadata_fields = set(LayoutMetadata.model_fields.keys()) - behavior_fields
        service._file_adapter.write_json.assert_any_call(
            output_dir / "metadata.json",
            sample_keymap_data.model_dump(
                mode="json",
                by_alias=True,
                include=metadata_fields,
            ),
        )

        # Verify layer extraction
        assert (
            service._file_adapter.write_json.call_count
            >= len(sample_keymap_data.layer_names) + 1
        )  # +1 for metadata.json

    def test_split_components_error(self, service, sample_keymap_data, output_dir):
        """Test error handling in split_components."""
        # Make the file adapter's write_json method raise an exception
        service._file_adapter.write_json.side_effect = Exception("Write error")

        with pytest.raises(LayoutError, match="Layer extraction failed"):
            service.split_components(sample_keymap_data, output_dir)

    def test_extract_dtsi_snippets(self, service, sample_keymap_data, output_dir):
        """Test extraction of DTSI snippets."""
        # Set custom devicetree content
        sample_keymap_data.custom_devicetree = "// Custom device tree"
        sample_keymap_data.custom_defined_behaviors = "// Custom behaviors"

        service._extract_dtsi_snippets(sample_keymap_data, output_dir)

        # Verify file writes
        service._file_adapter.write_text.assert_any_call(
            output_dir / "device.dtsi", "// Custom device tree"
        )
        service._file_adapter.write_text.assert_any_call(
            output_dir / "keymap.dtsi", "// Custom behaviors"
        )

    def test_extract_metadata_config(self, service, sample_keymap_data, output_dir):
        """Test extraction of metadata configuration."""
        service._extract_metadata_config(sample_keymap_data, output_dir)

        # Verify metadata extraction - behavior fields are excluded
        behavior_fields = {
            "variables",
            "holdTaps",
            "combos",
            "macros",
            "inputListeners",
            "config_parameters",
            "hold_taps",
            "input_listeners",
        }
        metadata_fields = set(LayoutMetadata.model_fields.keys()) - behavior_fields
        service._file_adapter.write_json.assert_called_once_with(
            output_dir / "metadata.json",
            sample_keymap_data.model_dump(
                mode="json",
                by_alias=True,
                include=metadata_fields,
            ),
        )

    def test_extract_individual_layers(self, service, sample_keymap_data, output_dir):
        """Test extraction of individual layers."""
        layers_dir = output_dir / "layers"

        service._extract_individual_layers(sample_keymap_data, layers_dir)

        # Verify write_json was called the right number of times for layers
        assert service._file_adapter.write_json.call_count >= len(
            sample_keymap_data.layer_names
        )

        # Verify at least one layer file was written to the expected directory
        calls = service._file_adapter.write_json.call_args_list
        layer_writes = [
            call
            for call in calls
            if str(layers_dir) in str(call[0][0]) and ".json" in str(call[0][0])
        ]
        assert len(layer_writes) >= 1

    def test_merge_components_success(self, service, sample_keymap_data, output_dir):
        """Test successful combination of keymap components."""
        # Create a metadata keymap with matching number of layers and layer names
        empty_binding = LayoutBinding(value="&none", params=[])
        # Create 3 identical layers to match 3 layer names
        empty_layers = [
            [empty_binding for _ in range(80)],
            [empty_binding for _ in range(80)],
            [empty_binding for _ in range(80)],
        ]
        metadata_keymap = LayoutData(
            keyboard="test_keyboard",
            title="Test Keymap",
            layer_names=["DEFAULT", "LOWER", "UPPER"],
            layers=empty_layers,
        )

        # Set up the mock behavior to make compose_components work with our test
        def mock_process_layers(keymap, layers_dir):
            # Mock implementation of _process_layers_for_merging
            keymap.layers = [
                [
                    LayoutBinding(value="&kp", params=[LayoutParam(value="A")])
                    for _ in range(80)
                ],
                [
                    LayoutBinding(value="&kp", params=[LayoutParam(value="1")])
                    for _ in range(80)
                ],
                [
                    LayoutBinding(value="&kp", params=[LayoutParam(value="F1")])
                    for _ in range(80)
                ],
            ]

        with patch.object(
            service, "_process_layers_for_merging", side_effect=mock_process_layers
        ):
            layers_dir = output_dir / "layers"

            # Mock file operations
            with patch.object(service._file_adapter, "is_dir", return_value=True):
                combined_keymap = service.merge_components(metadata_keymap, layers_dir)

            # Verify that layers were combined
            assert isinstance(combined_keymap, LayoutData)
            assert len(combined_keymap.layer_names) == 3
            assert len(combined_keymap.layers) == 3

            # Verify DTSI content from files
            service._file_adapter.is_file.assert_any_call(output_dir / "device.dtsi")
            service._file_adapter.is_file.assert_any_call(output_dir / "keymap.dtsi")

    def test_merge_components_directory_not_found(self, service, sample_keymap_data):
        """Test error handling when layers directory is not found."""
        # Create a metadata keymap with minimal layer data to pass validation
        empty_binding = LayoutBinding(value="&none", params=[])
        metadata_keymap = LayoutData(
            keyboard="test_keyboard",
            title="Test Keymap",
            layer_names=["DEFAULT"],
            layers=[
                [empty_binding for _ in range(80)]
            ],  # One empty layer to pass validation
        )

        non_existent_dir = Path("/non/existent/directory")

        # Mock directory check to return False
        with (
            patch.object(service._file_adapter, "is_dir", return_value=False),
            pytest.raises(LayoutError, match="Layers directory not found"),
        ):
            service.merge_components(metadata_keymap, non_existent_dir)

    def test_process_layers_for_merging(self, service, sample_keymap_data, output_dir):
        """Test processing and combining layer files."""
        # Create a starting keymap with matching layer_names and layers
        empty_binding = LayoutBinding(value="&none", params=[])
        # Create 3 identical layers to match 3 layer names
        empty_layers = [
            [empty_binding for _ in range(80)],
            [empty_binding for _ in range(80)],
            [empty_binding for _ in range(80)],
        ]
        combined_keymap = LayoutData(
            keyboard="test_keyboard",
            title="Test Keymap",
            layer_names=["DEFAULT", "LOWER", "UPPER"],
            layers=empty_layers,
        )

        layers_dir = output_dir / "layers"

        # Mock the behavior of read_json for layer files
        def mock_read_json(path):
            if "default.json" in str(path.name).lower():
                return {
                    "layers": [
                        [
                            {"value": "&kp", "params": [{"value": "A"}]}
                            for _ in range(80)
                        ]
                    ]
                }
            elif "lower.json" in str(path.name).lower():
                return {
                    "layers": [
                        [
                            {"value": "&kp", "params": [{"value": "1"}]}
                            for _ in range(80)
                        ]
                    ]
                }
            elif "upper.json" in str(path.name).lower():
                return {
                    "layers": [
                        [
                            {"value": "&kp", "params": [{"value": "F1"}]}
                            for _ in range(80)
                        ]
                    ]
                }
            return {}

        with (
            patch.object(
                service._file_adapter, "read_json", side_effect=mock_read_json
            ),
            patch.object(service._file_adapter, "is_file", return_value=True),
        ):
            service._process_layers_for_merging(combined_keymap, layers_dir)

        # Verify that layers were added to the combined keymap
        assert len(combined_keymap.layers) == 3
        assert all(isinstance(layer, list) for layer in combined_keymap.layers)
        assert all(len(layer) > 0 for layer in combined_keymap.layers)

    def test_add_dtsi_content_from_files(self, service, sample_keymap_data, output_dir):
        """Test adding DTSI content from files to a combined keymap."""
        combined_keymap = LayoutData(
            keyboard="test_keyboard",
            title="Test Keymap",
            layer_names=["DEFAULT"],
            layers=[
                [
                    LayoutBinding(value="&kp", params=[LayoutParam(value="A")])
                    for _ in range(80)
                ]
            ],
        )

        # Mock file existence
        with patch.object(service._file_adapter, "is_file", return_value=True):
            service._add_dtsi_content_from_files(combined_keymap, output_dir)

        # Verify DTSI content was added
        assert combined_keymap.custom_devicetree == "// Test DTSI content"
        assert combined_keymap.custom_defined_behaviors == "// Test DTSI content"

    def test_create_layout_component_service(self, mock_file_adapter):
        """Test factory function for creating LayoutComponentService."""
        # Test with provided file adapter
        service = create_layout_component_service(mock_file_adapter)
        assert isinstance(service, LayoutComponentService)
        assert service._file_adapter == mock_file_adapter

        # Test with default file adapter
        with patch("glovebox.adapters.file_adapter.create_file_adapter") as mock_create:
            default_adapter = Mock(spec=FileAdapterProtocol)
            mock_create.return_value = default_adapter

            service = create_layout_component_service(default_adapter)
            assert isinstance(service, LayoutComponentService)
            assert service._file_adapter == default_adapter
