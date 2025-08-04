"""Tests for configurable display functionality."""

import pytest

from glovebox.config.models import (
    DisplayConfig,
    DisplayFormatting,
    KeyboardConfig,
    LayoutStructure,
)
from glovebox.layout import GridLayoutFormatter, LayoutDisplayService
from glovebox.layout.models import LayoutBinding, LayoutData


class TestConfigurableDisplay:
    """Tests for configurable display functionality."""

    def create_test_layout_data(self, keyboard_name="test_display", bindings=None):
        """Create test layout data with proper structure."""
        if bindings is None:
            bindings = ["&kp A", "&kp B", "&none", "&trans"]

        # Convert string bindings to LayoutBinding objects
        layout_bindings = [LayoutBinding(value=binding) for binding in bindings]

        return LayoutData(
            keyboard=keyboard_name,
            title="Test Layout",
            layer_names=["Base"],
            layers=[layout_bindings],
        )

    def create_test_profile(self, display_config=None):
        """Create a test keyboard profile with optional display configuration."""
        from glovebox.config.profile import KeyboardProfile

        keyboard_config_data = {
            "keyboard": "test_display",
            "description": "Test keyboard for display",
            "vendor": "Test Vendor",
            "key_count": 20,
        }

        if display_config:
            keyboard_config_data["display"] = display_config

        keyboard_config = KeyboardConfig.model_validate(keyboard_config_data)

        # Create minimal profile for testing
        profile = KeyboardProfile(
            keyboard_config=keyboard_config,
            firmware_version=None,
        )

        return profile

    def test_display_service_uses_configured_formatting(self):
        """Test that display service uses configured formatting options."""
        # Create custom display configuration
        display_config = {
            "formatting": {
                "header_width": 100,
                "none_display": "EMPTY",
                "trans_display": "PASSTHROUGH",
                "key_width": 10,
                "center_small_rows": False,
                "horizontal_spacer": " ║ ",
            }
        }

        profile = self.create_test_profile(display_config)
        display_service = LayoutDisplayService()

        # Create simple layout data
        layout_data = self.create_test_layout_data()

        result = display_service.show(layout_data, profile)

        # Verify custom formatting is accessible through profile
        assert profile.keyboard_config.display.formatting.none_display == "EMPTY"
        assert profile.keyboard_config.display.formatting.trans_display == "PASSTHROUGH"
        assert profile.keyboard_config.display.formatting.header_width == 100

        # Basic display functionality should work
        assert "test_display" in result
        assert "Test Layout" in result

    def test_display_service_with_custom_layout_structure(self):
        """Test display service with custom layout structure."""
        # Create custom layout structure
        display_config = {
            "layout_structure": {
                "rows": {
                    "top_row": [[0, 1, 2, 3, 4], [5, 6, 7, 8, 9]],
                    "bottom_row": [[10, 11, 12, 13, 14], [15, 16, 17, 18, 19]],
                }
            },
            "formatting": {
                "header_width": 80,
                "key_width": 6,
                "horizontal_spacer": " | ",
            },
        }

        profile = self.create_test_profile(display_config)
        display_service = LayoutDisplayService()

        # Create layout data matching our structure
        bindings = [
            "&kp Q",
            "&kp W",
            "&kp E",
            "&kp R",
            "&kp T",
            "&kp Y",
            "&kp U",
            "&kp I",
            "&kp O",
            "&kp P",
            "&kp A",
            "&kp S",
            "&kp D",
            "&kp F",
            "&kp G",
            "&kp H",
            "&kp J",
            "&kp K",
            "&kp L",
            "&kp ENTER",
        ]
        layout_data = self.create_test_layout_data(bindings=bindings)

        result = display_service.show(layout_data, profile)

        # Verify that the display configuration is properly set
        assert profile.keyboard_config.display.layout_structure is not None
        assert len(profile.keyboard_config.display.layout_structure.rows) == 2
        assert "top_row" in profile.keyboard_config.display.layout_structure.rows
        assert profile.keyboard_config.display.formatting.horizontal_spacer == " | "

        # Basic display functionality should work
        assert "Q" in result
        assert "test_display" in result

    def test_grid_formatter_uses_configured_base_indent(self):
        """Test that GridLayoutFormatter uses configured base indent."""
        # Create custom formatting configuration
        display_config = {
            "formatting": {
                "key_width": 8,
                "horizontal_spacer": "  ",
            }
        }

        profile = self.create_test_profile(display_config)
        formatter = GridLayoutFormatter()

        # Test with custom base indent
        bindings = ["&kp A", "&kp B", "&kp C", "&kp D"]
        result = formatter.generate_layer_layout(
            bindings,
            profile,
            base_indent="    ",  # Custom indent
        )

        # Verify custom base indent is applied
        for line in result:
            if line.strip():  # Skip empty lines
                assert line.startswith("    ")  # Should use custom indent

    def test_grid_formatter_fallback_to_profile_base_indent(self):
        """Test that GridLayoutFormatter falls back to profile base indent."""
        # Create configuration with base indent in formatting
        from glovebox.config.models import FormattingConfig, KeymapSection

        keymap_section = KeymapSection(
            header_includes=[],
            formatting=FormattingConfig(
                key_gap="  ",
                base_indent="  ",  # Profile indent
                rows=[[0, 1]],  # Simple row structure for 2 bindings
            ),
            system_behaviors=[],
            kconfig_options={},
        )

        keyboard_config_data = {
            "keyboard": "test_display",
            "description": "Test keyboard for display",
            "vendor": "Test Vendor",
            "key_count": 10,
            "keymap": keymap_section,
        }

        keyboard_config = KeyboardConfig.model_validate(keyboard_config_data)

        from glovebox.config.profile import KeyboardProfile

        profile = KeyboardProfile(
            keyboard_config=keyboard_config,
            firmware_version=None,
        )

        formatter = GridLayoutFormatter()

        # Test without custom base indent (should use profile's)
        bindings = ["&kp A", "&kp B"]
        result = formatter.generate_layer_layout(bindings, profile)

        # Verify profile base indent is used
        for line in result:
            if line.strip():  # Skip empty lines
                assert line.startswith("  ")  # Should use profile indent

    def test_display_service_default_configuration(self):
        """Test display service works with default configuration."""
        # Create profile with default display configuration
        profile = self.create_test_profile()

        display_service = LayoutDisplayService()

        # Create simple layout data
        layout_data = self.create_test_layout_data(
            bindings=["&kp A", "&none", "&trans"]
        )

        result = display_service.show(layout_data, profile)

        # Verify default values are used
        assert "&none" in result  # Default none display
        assert "▽" in result  # Default trans display
        assert "=" in result  # Default header separator

    def test_grid_formatter_with_configured_key_gap(self):
        """Test GridLayoutFormatter with configured key gap."""
        from glovebox.config.models import FormattingConfig, KeymapSection

        # Create profile with custom key gap
        keymap_section = KeymapSection(
            header_includes=[],
            formatting=FormattingConfig(
                key_gap="--",
                base_indent="",
                rows=[[0, 1, 2]],  # Simple row structure for 3 bindings
            ),
            system_behaviors=[],
            kconfig_options={},
        )

        keyboard_config_data = {
            "keyboard": "test_display",
            "description": "Test keyboard for display",
            "vendor": "Test Vendor",
            "key_count": 10,
            "keymap": keymap_section,
        }

        keyboard_config = KeyboardConfig.model_validate(keyboard_config_data)

        from glovebox.config.profile import KeyboardProfile

        profile = KeyboardProfile(
            keyboard_config=keyboard_config,
            firmware_version=None,
        )

        formatter = GridLayoutFormatter()

        # Test with configured key gap
        bindings = ["&kp A", "&kp B", "&kp C"]
        result = formatter.generate_layer_layout(bindings, profile)

        # Verify custom key gap is used
        joined_result = "\n".join(result)
        assert "--" in joined_result  # Custom key gap should appear

    def test_layout_structure_validation(self):
        """Test that layout structure validation works correctly."""
        # Test valid layout structure
        valid_structure = {
            "rows": {
                "main": [[0, 1, 2], [3, 4, 5]],
                "thumbs": [[6, 7]],
            }
        }

        layout_structure = LayoutStructure.model_validate(valid_structure)
        assert len(layout_structure.rows) == 2
        assert "main" in layout_structure.rows

        # Test invalid layout structure (negative key position)
        with pytest.raises(ValueError):  # Should raise validation error
            invalid_structure = {
                "rows": {
                    "main": [[0, 1, -1]],  # Invalid negative position
                }
            }
            LayoutStructure.model_validate(invalid_structure)

    def test_display_formatting_validation(self):
        """Test that display formatting validation works correctly."""
        # Test valid formatting
        valid_formatting = {
            "header_width": 100,
            "none_display": "NONE",
            "trans_display": "TRANS",
            "key_width": 8,
            "center_small_rows": True,
            "horizontal_spacer": " | ",
        }

        formatting = DisplayFormatting.model_validate(valid_formatting)
        assert formatting.header_width == 100
        assert formatting.none_display == "NONE"

        # Test invalid formatting (zero header width)
        with pytest.raises(ValueError):  # Should raise validation error
            invalid_formatting = {
                "header_width": 0,  # Invalid zero width
            }
            DisplayFormatting.model_validate(invalid_formatting)

    def test_display_config_with_partial_configuration(self):
        """Test display configuration with only some fields customized."""
        # Only customize some formatting fields
        partial_config = {
            "formatting": {
                "header_width": 120,
                "none_display": "EMPTY",
                # Other fields should use defaults
            }
        }

        display_config = DisplayConfig.model_validate(partial_config)

        # Verify customized fields
        assert display_config.formatting.header_width == 120
        assert display_config.formatting.none_display == "EMPTY"

        # Verify defaults for non-customized fields
        assert display_config.formatting.trans_display == "▽"  # Default
        assert display_config.formatting.key_width == 8  # Default
        assert display_config.layout_structure is None  # Default

    def test_integration_with_keyboard_profile(self):
        """Test integration of display configuration with keyboard profile."""
        # Create comprehensive display configuration
        display_config = {
            "layout_structure": {
                "rows": {
                    "alphas": [[0, 1, 2, 3, 4], [5, 6, 7, 8, 9]],
                    "mods": [[10, 11], [12, 13]],
                }
            },
            "formatting": {
                "header_width": 90,
                "none_display": "___",
                "trans_display": "^^^",
                "key_width": 7,
                "center_small_rows": True,
                "horizontal_spacer": " ┃ ",
            },
        }

        profile = self.create_test_profile(display_config)

        # Verify all configuration is accessible through profile
        assert profile.keyboard_config.display.layout_structure is not None
        assert len(profile.keyboard_config.display.layout_structure.rows) == 2
        assert "alphas" in profile.keyboard_config.display.layout_structure.rows
        assert profile.keyboard_config.display.formatting.header_width == 90
        assert profile.keyboard_config.display.formatting.none_display == "___"
        assert profile.keyboard_config.display.formatting.horizontal_spacer == " ┃ "

    def test_backward_compatibility_without_display_config(self):
        """Test that components work without display configuration (backward compatibility)."""
        # Create profile without display configuration (should use defaults)
        keyboard_config_data = {
            "keyboard": "backward_compat",
            "description": "Backward compatibility test",
            "vendor": "Test Vendor",
            "key_count": 10,
        }

        keyboard_config = KeyboardConfig.model_validate(keyboard_config_data)

        from glovebox.config.profile import KeyboardProfile

        profile = KeyboardProfile(
            keyboard_config=keyboard_config,
            firmware_version=None,
        )

        # Should create default display configuration
        assert profile.keyboard_config.display is not None
        assert profile.keyboard_config.display.layout_structure is None  # Default
        assert profile.keyboard_config.display.formatting.header_width == 80  # Default

        # Components should work with defaults
        display_service = LayoutDisplayService()
        layout_data = self.create_test_layout_data(
            keyboard_name="backward_compat", bindings=["&kp A", "&none"]
        )

        result = display_service.show(layout_data, profile)
        assert "backward_compat" in result
        assert "&none" in result

    def test_complex_layout_structure_processing(self):
        """Test processing of complex layout structures."""
        # Create a complex layout structure resembling an ergonomic keyboard
        complex_display_config = {
            "layout_structure": {
                "rows": {
                    "left_top": [[0, 1, 2, 3, 4]],
                    "left_home": [[5, 6, 7, 8, 9]],
                    "left_bottom": [[10, 11, 12, 13, 14]],
                    "right_top": [[15, 16, 17, 18, 19]],
                    "right_home": [[20, 21, 22, 23, 24]],
                    "right_bottom": [[25, 26, 27, 28, 29]],
                    "thumbs": [[30, 31], [32, 33]],
                }
            },
            "formatting": {
                "header_width": 140,
                "key_width": 5,
                "horizontal_spacer": " ╎ ",
            },
        }

        profile = self.create_test_profile(complex_display_config)

        # Verify complex structure is properly stored and accessible
        layout_structure = profile.keyboard_config.display.layout_structure
        assert layout_structure is not None
        assert len(layout_structure.rows) == 7
        assert "left_top" in layout_structure.rows
        assert "thumbs" in layout_structure.rows
        assert layout_structure.rows["left_top"] == [[0, 1, 2, 3, 4]]
        assert layout_structure.rows["thumbs"] == [[30, 31], [32, 33]]
