"""Tests for behavior decomposition and composition functionality."""

import json
from pathlib import Path

import pytest

from glovebox.layout.component_service import create_layout_component_service
from glovebox.layout.models import (
    BehaviorData,
    ComboBehavior,
    HoldTapBehavior,
    LayoutBinding,
    LayoutData,
    MacroBehavior,
)


@pytest.fixture
def sample_layout_with_behaviors():
    """Create a sample layout with various behavior definitions."""
    return LayoutData(
        keyboard="glove80",
        title="Test Layout with Behaviors",
        variables={
            "fast_timing": 130,
            "normal_timing": 190,
            "common_flavor": "tap-preferred",
        },
        holdTaps=[
            HoldTapBehavior(
                name="&fast_ht",
                description="Fast hold-tap for modifiers",
                tapping_term_ms=130,
                flavor="tap-preferred",
                bindings=["&kp", "&mo"],
            )
        ],
        combos=[
            ComboBehavior(
                name="esc_combo",
                description="Escape combo",
                timeoutMs=50,
                keyPositions=[0, 1],
                binding=LayoutBinding(value="&kp", params=[]),
            )
        ],
        macros=[
            MacroBehavior(
                name="test_macro",
                description="Test macro",
                waitMs=10,
                tapMs=10,
                bindings=[LayoutBinding(value="&kp", params=[])],
            )
        ],
        layer_names=["DEFAULT", "SYMBOLS"],
        layers=[
            [LayoutBinding(value="&kp", params=[]) for _ in range(80)],
            [LayoutBinding(value="&kp", params=[]) for _ in range(80)],
        ],
    )


@pytest.fixture
def sample_layout_without_behaviors():
    """Create a sample layout without behavior definitions."""
    return LayoutData(
        keyboard="glove80",
        title="Test Layout without Behaviors",
        layer_names=["DEFAULT"],
        layers=[[LayoutBinding(value="&kp", params=[]) for _ in range(80)]],
    )


class TestBehaviorData:
    """Test the BehaviorData model."""

    def test_behavior_data_creation(self):
        """Test creating BehaviorData with various behaviors."""
        behavior_data = BehaviorData(
            variables={"timing": 150},
            holdTaps=[
                HoldTapBehavior(
                    name="&ht_test", tapping_term_ms=150, bindings=["&kp", "&mo"]
                )
            ],
        )

        assert behavior_data.variables == {"timing": 150}
        assert len(behavior_data.hold_taps) == 1
        assert behavior_data.hold_taps[0].name == "&ht_test"
        assert len(behavior_data.combos) == 0

    def test_behavior_data_is_empty(self):
        """Test is_empty method for BehaviorData."""
        # Empty behavior data
        empty_behavior = BehaviorData()
        assert empty_behavior.is_empty()

        # Behavior data with variables
        with_variables = BehaviorData(variables={"test": "value"})
        assert not with_variables.is_empty()

        # Behavior data with hold taps
        with_hold_taps = BehaviorData(
            holdTaps=[HoldTapBehavior(name="&test", bindings=["&kp", "&mo"])]
        )
        assert not with_hold_taps.is_empty()

    def test_behavior_data_merge(self):
        """Test merging two BehaviorData instances."""
        behavior1 = BehaviorData(
            variables={"var1": "value1"},
            holdTaps=[HoldTapBehavior(name="&ht1", bindings=["&kp", "&mo"])],
        )

        behavior2 = BehaviorData(
            variables={
                "var2": "value2",
                "var1": "overridden",
            },  # var1 should be overridden
            combos=[
                ComboBehavior(
                    name="combo1",
                    keyPositions=[0, 1],
                    binding=LayoutBinding(value="&kp", params=[]),
                )
            ],
        )

        merged = behavior1.merge_with(behavior2)

        # Check variables merge (behavior2 takes precedence)
        assert merged.variables == {"var1": "overridden", "var2": "value2"}

        # Check lists are combined
        assert len(merged.hold_taps) == 1
        assert len(merged.combos) == 1
        assert merged.hold_taps[0].name == "&ht1"
        assert merged.combos[0].name == "combo1"

    def test_behavior_data_serialization(self):
        """Test BehaviorData serialization with aliases."""
        behavior_data = BehaviorData(
            holdTaps=[HoldTapBehavior(name="&test", bindings=["&kp", "&mo"])],
            inputListeners=[],
        )

        serialized = behavior_data.to_dict()

        # Check that aliases are used
        assert "holdTaps" in serialized
        assert "inputListeners" in serialized
        assert "hold_taps" not in serialized
        assert "input_listeners" not in serialized


class TestBehaviorDecomposition:
    """Test behavior decomposition functionality."""

    def test_decompose_layout_with_behaviors(
        self, sample_layout_with_behaviors, tmp_path
    ):
        """Test decomposing a layout that contains behavior definitions."""
        component_service = create_layout_component_service()

        result = component_service.decompose_components(
            sample_layout_with_behaviors, tmp_path
        )

        assert result.success

        # Check that behaviors.json was created
        behaviors_file = tmp_path / "behaviors.json"
        assert behaviors_file.exists()

        # Check behaviors.json content
        with behaviors_file.open() as f:
            behavior_data = json.load(f)

        assert "variables" in behavior_data
        assert behavior_data["variables"]["fast_timing"] == 130
        assert "holdTaps" in behavior_data
        assert len(behavior_data["holdTaps"]) == 1
        assert behavior_data["holdTaps"][0]["name"] == "&fast_ht"

    def test_decompose_layout_without_behaviors(
        self, sample_layout_without_behaviors, tmp_path
    ):
        """Test decomposing a layout that has no behavior definitions."""
        component_service = create_layout_component_service()

        result = component_service.decompose_components(
            sample_layout_without_behaviors, tmp_path
        )

        assert result.success

        # Check that behaviors.json was NOT created (since no behaviors exist)
        behaviors_file = tmp_path / "behaviors.json"
        assert not behaviors_file.exists()

    def test_metadata_excludes_behavior_fields(
        self, sample_layout_with_behaviors, tmp_path
    ):
        """Test that metadata.json excludes behavior fields."""
        component_service = create_layout_component_service()

        component_service.decompose_components(sample_layout_with_behaviors, tmp_path)

        # Check metadata.json content
        metadata_file = tmp_path / "metadata.json"
        assert metadata_file.exists()

        with metadata_file.open() as f:
            metadata = json.load(f)

        # Behavior fields should not be in metadata
        behavior_fields = [
            "variables",
            "holdTaps",
            "combos",
            "macros",
            "inputListeners",
        ]
        for field in behavior_fields:
            assert field not in metadata, (
                f"Field '{field}' should not be in metadata.json"
            )

        # Non-behavior metadata should be present
        assert metadata["keyboard"] == "glove80"
        assert metadata["title"] == "Test Layout with Behaviors"

    def test_decomposition_creates_expected_structure(
        self, sample_layout_with_behaviors, tmp_path
    ):
        """Test that decomposition creates the expected directory structure."""
        component_service = create_layout_component_service()

        component_service.decompose_components(sample_layout_with_behaviors, tmp_path)

        # Check expected files and directories
        assert (tmp_path / "metadata.json").exists()
        assert (tmp_path / "behaviors.json").exists()
        assert (tmp_path / "layers").is_dir()
        assert (tmp_path / "layers" / "DEFAULT.json").exists()
        assert (tmp_path / "layers" / "SYMBOLS.json").exists()


class TestBehaviorComposition:
    """Test behavior composition functionality."""

    def test_compose_with_behaviors_file(
        self, sample_layout_without_behaviors, tmp_path
    ):
        """Test composing components including a behaviors.json file."""
        component_service = create_layout_component_service()

        # Set up component files
        layers_dir = tmp_path / "layers"
        layers_dir.mkdir()

        # Create metadata.json (without behaviors)
        metadata_file = tmp_path / "metadata.json"
        metadata_data = sample_layout_without_behaviors.model_dump(
            mode="json", by_alias=True
        )
        # Remove behavior fields from metadata
        behavior_fields = [
            "variables",
            "holdTaps",
            "combos",
            "macros",
            "inputListeners",
        ]
        for field in behavior_fields:
            metadata_data.pop(field, None)

        with metadata_file.open("w") as f:
            json.dump(metadata_data, f)

        # Create behaviors.json
        behaviors_file = tmp_path / "behaviors.json"
        behavior_data = BehaviorData(
            variables={"test_var": "test_value"},
            holdTaps=[HoldTapBehavior(name="&test_ht", bindings=["&kp", "&mo"])],
        )
        with behaviors_file.open("w") as f:
            json.dump(behavior_data.to_dict(), f)

        # Create layer file
        layer_file = layers_dir / "DEFAULT.json"
        layer_data = {
            "keyboard": "glove80",
            "title": "Layer: DEFAULT",
            "layer_names": ["DEFAULT"],
            "layers": [[{"value": "&kp", "params": []} for _ in range(80)]],
        }
        with layer_file.open("w") as f:
            json.dump(layer_data, f)

        # Load metadata and compose
        metadata_layout = LayoutData.model_validate(metadata_data)
        composed_layout = component_service.compose_components(
            metadata_layout, layers_dir
        )

        # Check that behavior data was restored
        assert composed_layout.variables == {"test_var": "test_value"}
        assert len(composed_layout.hold_taps) == 1
        assert composed_layout.hold_taps[0].name == "&test_ht"

    def test_compose_without_behaviors_file(
        self, sample_layout_without_behaviors, tmp_path
    ):
        """Test composing components when no behaviors.json file exists."""
        component_service = create_layout_component_service()

        # Set up component files without behaviors.json
        layers_dir = tmp_path / "layers"
        layers_dir.mkdir()

        # Create metadata.json
        metadata_file = tmp_path / "metadata.json"
        metadata_data = sample_layout_without_behaviors.model_dump(
            mode="json", by_alias=True
        )
        with metadata_file.open("w") as f:
            json.dump(metadata_data, f)

        # Create layer file
        layer_file = layers_dir / "DEFAULT.json"
        layer_data = {
            "keyboard": "glove80",
            "title": "Layer: DEFAULT",
            "layer_names": ["DEFAULT"],
            "layers": [[{"value": "&kp", "params": []} for _ in range(80)]],
        }
        with layer_file.open("w") as f:
            json.dump(layer_data, f)

        # Load metadata and compose
        metadata_layout = LayoutData.model_validate(metadata_data)
        composed_layout = component_service.compose_components(
            metadata_layout, layers_dir
        )

        # Check that empty behavior data was initialized
        assert composed_layout.variables == {}
        assert len(composed_layout.hold_taps) == 0
        assert len(composed_layout.combos) == 0

    def test_round_trip_behavior_decomposition_composition(
        self, sample_layout_with_behaviors, tmp_path
    ):
        """Test that decomposing and then composing preserves behavior data."""
        component_service = create_layout_component_service()

        # Decompose the layout
        decompose_result = component_service.decompose_components(
            sample_layout_with_behaviors, tmp_path
        )
        assert decompose_result.success

        # Load the metadata file
        metadata_file = tmp_path / "metadata.json"
        with metadata_file.open() as f:
            metadata_data = json.load(f)
        metadata_layout = LayoutData.model_validate(metadata_data)

        # Compose the layout back
        layers_dir = tmp_path / "layers"
        composed_layout = component_service.compose_components(
            metadata_layout, layers_dir
        )

        # Check that all behavior data was preserved
        assert composed_layout.variables == sample_layout_with_behaviors.variables
        assert len(composed_layout.hold_taps) == len(
            sample_layout_with_behaviors.hold_taps
        )
        assert len(composed_layout.combos) == len(sample_layout_with_behaviors.combos)
        assert len(composed_layout.macros) == len(sample_layout_with_behaviors.macros)

        # Check specific behavior details
        assert composed_layout.hold_taps[0].name == "&fast_ht"
        assert composed_layout.combos[0].name == "esc_combo"
        assert composed_layout.macros[0].name == "test_macro"

    def test_compose_with_invalid_behaviors_file(
        self, sample_layout_without_behaviors, tmp_path
    ):
        """Test composing when behaviors.json exists but contains invalid data."""
        component_service = create_layout_component_service()

        # Set up component files
        layers_dir = tmp_path / "layers"
        layers_dir.mkdir()

        # Create metadata.json
        metadata_file = tmp_path / "metadata.json"
        metadata_data = sample_layout_without_behaviors.model_dump(
            mode="json", by_alias=True
        )
        with metadata_file.open("w") as f:
            json.dump(metadata_data, f)

        # Create invalid behaviors.json
        behaviors_file = tmp_path / "behaviors.json"
        with behaviors_file.open("w") as f:
            f.write("invalid json content")

        # Create layer file
        layer_file = layers_dir / "DEFAULT.json"
        layer_data = {
            "keyboard": "glove80",
            "title": "Layer: DEFAULT",
            "layer_names": ["DEFAULT"],
            "layers": [[{"value": "&kp", "params": []} for _ in range(80)]],
        }
        with layer_file.open("w") as f:
            json.dump(layer_data, f)

        # Load metadata and compose - should not fail but continue without behavior data
        metadata_layout = LayoutData.model_validate(metadata_data)
        composed_layout = component_service.compose_components(
            metadata_layout, layers_dir
        )

        # Should have empty behavior data due to invalid file
        assert composed_layout.variables == {}
        assert len(composed_layout.hold_taps) == 0
