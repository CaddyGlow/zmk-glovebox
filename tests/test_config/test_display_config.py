"""Tests for display configuration models."""

import pytest
from pydantic import ValidationError

from glovebox.config.models import DisplayConfig, DisplayFormatting, LayoutStructure


class TestLayoutStructure:
    """Tests for LayoutStructure model."""

    def test_valid_layout_structure(self):
        """Test valid layout structure creation."""
        rows_data = {
            "row0": [[0, 1, 2], [3, 4, 5]],
            "row1": [[6, 7, 8], [9, 10, 11]],
        }

        layout = LayoutStructure(rows=rows_data)

        assert layout.rows == rows_data
        assert len(layout.rows) == 2
        assert layout.rows["row0"] == [[0, 1, 2], [3, 4, 5]]

    def test_complex_layout_structure(self):
        """Test complex layout structure like Glove80."""
        glove80_style = {
            "row0": [[0, 1, 2, 3, 4], [5, 6, 7, 8, 9]],
            "row1": [[10, 11, 12, 13, 14, 15], [16, 17, 18, 19, 20, 21]],
            "row2": [[22, 23, 24, 25, 26, 27], [28, 29, 30, 31, 32, 33]],
            "row3": [[34, 35, 36, 37, 38, 39], [40, 41, 42, 43, 44, 45]],
            "row4": [[46, 47, 48, 49, 50, 51], [58, 59, 60, 61, 62, 63]],
            "row5": [[64, 65, 66, 67, 68], [75, 76, 77, 78, 79]],
            "thumb1": [[69, 52], [57, 74]],
            "thumb2": [[70, 53], [56, 73]],
            "thumb3": [[71, 54], [55, 72]],
        }

        layout = LayoutStructure(rows=glove80_style)

        assert len(layout.rows) == 9
        assert layout.rows["row0"] == [[0, 1, 2, 3, 4], [5, 6, 7, 8, 9]]
        assert layout.rows["thumb1"] == [[69, 52], [57, 74]]

    def test_layout_structure_validation_empty(self):
        """Test that empty row structure is invalid."""
        with pytest.raises(ValidationError, match="Row structure cannot be empty"):
            LayoutStructure(rows={})

    def test_layout_structure_validation_invalid_segment(self):
        """Test validation of invalid segments."""
        # Non-list segment
        with pytest.raises(ValidationError, match="Input should be a valid list"):
            LayoutStructure(rows={"row0": ["invalid", [1, 2]]})  # type: ignore

    def test_layout_structure_validation_negative_positions(self):
        """Test validation of negative key positions."""
        with pytest.raises(ValidationError, match="must be a non-negative integer"):
            LayoutStructure(rows={"row0": [[0, -1, 2]]})

    def test_layout_structure_validation_non_integer_positions(self):
        """Test validation of non-integer positions."""
        with pytest.raises(ValidationError, match="Input should be a valid integer"):
            LayoutStructure(rows={"row0": [[0, "invalid", 2]]})  # type: ignore


class TestDisplayFormatting:
    """Tests for DisplayFormatting model."""

    def test_default_display_formatting(self):
        """Test display formatting with defaults."""
        formatting = DisplayFormatting()

        assert formatting.header_width == 80
        assert formatting.none_display == "&none"
        assert formatting.trans_display == "▽"
        assert formatting.key_width == 8
        assert formatting.center_small_rows is True
        assert formatting.horizontal_spacer == " | "

    def test_custom_display_formatting(self):
        """Test display formatting with custom values."""
        formatting = DisplayFormatting(
            header_width=100,
            none_display="NONE",
            trans_display="TRANS",
            key_width=12,
            center_small_rows=False,
            horizontal_spacer=" │ ",
        )

        assert formatting.header_width == 100
        assert formatting.none_display == "NONE"
        assert formatting.trans_display == "TRANS"
        assert formatting.key_width == 12
        assert formatting.center_small_rows is False
        assert formatting.horizontal_spacer == " │ "

    def test_display_formatting_validation(self):
        """Test display formatting validation."""
        # header_width must be positive
        with pytest.raises(ValidationError):
            DisplayFormatting(header_width=0)

        with pytest.raises(ValidationError):
            DisplayFormatting(header_width=-10)

        # key_width must be positive
        with pytest.raises(ValidationError):
            DisplayFormatting(key_width=0)

        with pytest.raises(ValidationError):
            DisplayFormatting(key_width=-5)

    def test_display_formatting_serialization(self):
        """Test display formatting serialization."""
        formatting = DisplayFormatting(
            header_width=120, none_display="---", trans_display="~~~"
        )

        formatting_dict = formatting.model_dump(by_alias=True, mode="json")

        assert formatting_dict["header_width"] == 120
        assert formatting_dict["none_display"] == "---"
        assert formatting_dict["trans_display"] == "~~~"
        assert formatting_dict["key_width"] == 8  # Default
        assert formatting_dict["center_small_rows"] is True  # Default


class TestDisplayConfig:
    """Tests for DisplayConfig model."""

    def test_default_display_config(self):
        """Test display config with defaults."""
        config = DisplayConfig()

        assert config.layout_structure is None
        assert config.formatting is not None
        assert config.formatting.header_width == 80
        assert config.formatting.none_display == "&none"

    def test_display_config_with_layout_structure(self):
        """Test display config with layout structure."""
        layout_structure = LayoutStructure(
            rows={
                "row0": [[0, 1, 2], [3, 4, 5]],
                "row1": [[6, 7, 8], [9, 10, 11]],
            }
        )

        config = DisplayConfig(layout_structure=layout_structure)

        assert config.layout_structure is not None
        assert len(config.layout_structure.rows) == 2
        assert config.formatting.header_width == 80  # Default

    def test_display_config_with_custom_formatting(self):
        """Test display config with custom formatting."""
        formatting = DisplayFormatting(
            header_width=100, key_width=10, horizontal_spacer=" ║ "
        )

        config = DisplayConfig(formatting=formatting)

        assert config.layout_structure is None
        assert config.formatting.header_width == 100
        assert config.formatting.key_width == 10
        assert config.formatting.horizontal_spacer == " ║ "

    def test_complete_display_config(self):
        """Test complete display config with all components."""
        layout_structure = LayoutStructure(
            rows={
                "main": [[0, 1, 2, 3, 4], [5, 6, 7, 8, 9]],
                "thumbs": [[10, 11], [12, 13]],
            }
        )

        formatting = DisplayFormatting(
            header_width=90,
            none_display="EMPTY",
            trans_display="PASS",
            key_width=6,
            center_small_rows=False,
            horizontal_spacer=" ┃ ",
        )

        config = DisplayConfig(layout_structure=layout_structure, formatting=formatting)

        assert config.layout_structure is not None
        assert len(config.layout_structure.rows) == 2
        assert config.layout_structure.rows["main"] == [
            [0, 1, 2, 3, 4],
            [5, 6, 7, 8, 9],
        ]
        assert config.formatting.header_width == 90
        assert config.formatting.none_display == "EMPTY"
        assert config.formatting.center_small_rows is False

    def test_display_config_from_dict(self):
        """Test display config creation from dictionary."""
        config_dict = {
            "layout_structure": {
                "rows": {
                    "row0": [[0, 1, 2], [3, 4, 5]],
                    "row1": [[6, 7, 8], [9, 10, 11]],
                }
            },
            "formatting": {
                "header_width": 120,
                "none_display": "NULL",
                "trans_display": "THRU",
                "key_width": 10,
                "center_small_rows": True,
                "horizontal_spacer": " ⏐ ",
            },
        }

        config = DisplayConfig.model_validate(config_dict)

        assert config.layout_structure is not None
        assert len(config.layout_structure.rows) == 2
        assert config.layout_structure.rows["row0"] == [[0, 1, 2], [3, 4, 5]]
        assert config.formatting.header_width == 120
        assert config.formatting.none_display == "NULL"
        assert config.formatting.horizontal_spacer == " ⏐ "

    def test_display_config_serialization(self):
        """Test display config serialization."""
        layout_structure = LayoutStructure(
            rows={
                "test": [[0, 1], [2, 3]],
            }
        )

        config = DisplayConfig(layout_structure=layout_structure)

        config_dict = config.model_dump(by_alias=True, mode="json")

        assert "layout_structure" in config_dict
        assert "formatting" in config_dict
        assert config_dict["layout_structure"]["rows"]["test"] == [[0, 1], [2, 3]]
        assert config_dict["formatting"]["header_width"] == 80

    def test_display_config_without_layout_structure(self):
        """Test display config without layout structure is valid."""
        config = DisplayConfig(formatting=DisplayFormatting(header_width=60))

        assert config.layout_structure is None
        assert config.formatting.header_width == 60


class TestDisplayConfigIntegration:
    """Integration tests for display configuration."""

    def test_realistic_keyboard_display_config(self):
        """Test a realistic keyboard display configuration."""
        # Simulate a 60% keyboard layout
        sixty_percent_layout = {
            "number_row": [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]],
            "top_row": [[14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27]],
            "home_row": [[28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40]],
            "bottom_row": [[41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52]],
            "space_row": [[53, 54, 55, 56, 57]],
        }

        config_data = {
            "layout_structure": {"rows": sixty_percent_layout},
            "formatting": {
                "header_width": 100,
                "none_display": "___",
                "trans_display": "===",
                "key_width": 6,
                "center_small_rows": True,
                "horizontal_spacer": " ┃ ",
            },
        }

        config = DisplayConfig.model_validate(config_data)

        # Verify layout structure
        assert config.layout_structure is not None
        assert len(config.layout_structure.rows) == 5
        assert len(config.layout_structure.rows["number_row"][0]) == 14
        assert len(config.layout_structure.rows["space_row"][0]) == 5

        # Verify formatting
        assert config.formatting.header_width == 100
        assert config.formatting.none_display == "___"
        assert config.formatting.trans_display == "==="
        assert config.formatting.key_width == 6
        assert config.formatting.horizontal_spacer == " ┃ "

    def test_split_keyboard_display_config(self):
        """Test display config for split keyboard."""
        # Simulate a split keyboard like Glove80
        split_layout = {
            "top_left": [[0, 1, 2, 3, 4]],
            "top_right": [[5, 6, 7, 8, 9]],
            "middle_left": [[10, 11, 12, 13, 14, 15]],
            "middle_right": [[16, 17, 18, 19, 20, 21]],
            "bottom_left": [[22, 23, 24, 25, 26]],
            "bottom_right": [[27, 28, 29, 30, 31]],
            "thumb_left": [[32, 33, 34]],
            "thumb_right": [[35, 36, 37]],
        }

        config = DisplayConfig(
            layout_structure=LayoutStructure(rows=split_layout),
            formatting=DisplayFormatting(
                header_width=120,
                key_width=8,
                center_small_rows=True,
                horizontal_spacer=" │ ",
            ),
        )

        # Verify split layout structure
        assert config.layout_structure is not None
        assert len(config.layout_structure.rows) == 8
        assert len(config.layout_structure.rows["top_left"][0]) == 5
        assert len(config.layout_structure.rows["thumb_left"][0]) == 3

        # Verify formatting suitable for split keyboard
        assert config.formatting.header_width == 120  # Wider for split display
        assert config.formatting.key_width == 8
        assert config.formatting.center_small_rows is True  # Good for thumb rows
