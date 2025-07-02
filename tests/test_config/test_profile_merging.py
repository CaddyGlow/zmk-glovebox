"""Tests for KeyboardProfile merging of firmware and kconfig options."""

import pytest


pytestmark = [pytest.mark.network, pytest.mark.integration]

from glovebox.config.models import (
    BuildOptions,
    FirmwareConfig,
    FormattingConfig,
    KConfigOption,
    KeyboardConfig,
    KeymapSection,
)
from glovebox.config.models.behavior import BehaviorConfig
from glovebox.config.models.display import DisplayConfig
from glovebox.config.models.zmk import ZmkConfig, ZmkPatterns
from glovebox.config.profile import KeyboardProfile
from glovebox.core.errors import ConfigError
from glovebox.layout.behavior.models import SystemBehavior


@pytest.fixture
def base_keyboard_config() -> KeyboardConfig:
    """Create a base keyboard configuration with system behaviors and kconfig."""
    keyboard_system_behaviors = [
        SystemBehavior(
            code="&kb_behavior1",
            name="keyboard_behavior_1",
            description="System behavior from keyboard config",
            expected_params=1,
            origin="keyboard",
            params=[],
        ),
        SystemBehavior(
            code="&kb_behavior2",
            name="keyboard_behavior_2",
            description="Another keyboard behavior",
            expected_params=0,
            origin="keyboard",
            params=[],
        ),
    ]

    keyboard_kconfig_options = {
        "kb_option1": KConfigOption(
            name="CONFIG_KB_OPTION1",
            type="bool",
            default=True,
            description="Keyboard-specific kconfig option 1",
        ),
        "kb_option2": KConfigOption(
            name="CONFIG_KB_OPTION2",
            type="int",
            default=42,
            description="Keyboard-specific kconfig option 2",
        ),
        "shared_option": KConfigOption(
            name="CONFIG_SHARED_OPTION",
            type="string",
            default="keyboard_default",
            description="Option that exists in both keyboard and firmware",
        ),
    }

    keymap_section = KeymapSection(
        header_includes=["dt-bindings/zmk/keys.h"],
        formatting=FormattingConfig(key_gap="  "),
        system_behaviors=keyboard_system_behaviors,
        kconfig_options=keyboard_kconfig_options,
        keymap_dtsi="#include <zmk.dtsi>",
    )

    return KeyboardConfig(
        keyboard="test_keyboard",
        description="Test keyboard for profile merging",
        vendor="TestVendor",
        key_count=42,  # Required field
        keymap=keymap_section,
        behavior=BehaviorConfig(),
        display=DisplayConfig(),
        zmk=ZmkConfig(
            patterns=ZmkPatterns(
                kconfig_prefix="CONFIG_",
                layer_define="LAYER_{}",
            )
        ),
        firmwares={},
    )


@pytest.fixture
def firmware_config() -> FirmwareConfig:
    """Create a firmware configuration with system behaviors and kconfig."""
    firmware_system_behaviors = [
        SystemBehavior(
            code="&fw_behavior1",
            name="firmware_behavior_1",
            description="System behavior from firmware config",
            expected_params=2,
            origin="firmware",
            params=[],
        ),
        SystemBehavior(
            code="&fw_behavior2",
            name="firmware_behavior_2",
            description="Another firmware behavior",
            expected_params=1,
            origin="firmware",
            params=[],
        ),
    ]

    firmware_kconfig_options = {
        "fw_option1": KConfigOption(
            name="CONFIG_FW_OPTION1",
            type="bool",
            default=False,
            description="Firmware-specific kconfig option 1",
        ),
        "fw_option2": KConfigOption(
            name="CONFIG_FW_OPTION2",
            type="hex",
            default="0x1234",
            description="Firmware-specific kconfig option 2",
        ),
        "shared_option": KConfigOption(
            name="CONFIG_SHARED_OPTION",
            type="string",
            default="firmware_override",
            description="Option that overrides keyboard default",
        ),
    }

    return FirmwareConfig(
        version="v1.0.0",
        description="Test firmware for profile merging",
        build_options=BuildOptions(
            repository="https://github.com/zmkfirmware/zmk",
            branch="main",
        ),
        kconfig=firmware_kconfig_options,
        system_behaviors=firmware_system_behaviors,
    )


class TestKeyboardProfileMerging:
    """Test keyboard profile merging of firmware and kconfig options."""

    def test_keyboard_only_profile(self, base_keyboard_config: KeyboardConfig):
        """Test profile with no firmware specified returns only keyboard behaviors and empty kconfig."""
        profile = KeyboardProfile(base_keyboard_config, firmware_version=None)

        # Should only have keyboard system behaviors
        assert len(profile.system_behaviors) == 2
        assert profile.system_behaviors[0].code == "&kb_behavior1"
        assert profile.system_behaviors[1].code == "&kb_behavior2"

        # Should have keyboard kconfig options
        kconfig = profile.kconfig_options
        assert len(kconfig) == 3
        assert "kb_option1" in kconfig
        assert "kb_option2" in kconfig
        assert "shared_option" in kconfig
        assert kconfig["shared_option"].default == "keyboard_default"

    def test_firmware_profile_system_behaviors_merging(
        self, base_keyboard_config: KeyboardConfig, firmware_config: FirmwareConfig
    ):
        """Test that system behaviors from keyboard and firmware are correctly merged."""
        # Add firmware to keyboard config
        base_keyboard_config.firmwares["v1.0.0"] = firmware_config

        profile = KeyboardProfile(base_keyboard_config, firmware_version="v1.0.0")

        # Should have all system behaviors (keyboard + firmware)
        system_behaviors = profile.system_behaviors
        assert len(system_behaviors) == 4

        # Verify keyboard behaviors come first
        assert system_behaviors[0].code == "&kb_behavior1"
        assert system_behaviors[0].origin == "keyboard"
        assert system_behaviors[1].code == "&kb_behavior2"
        assert system_behaviors[1].origin == "keyboard"

        # Verify firmware behaviors come after
        assert system_behaviors[2].code == "&fw_behavior1"
        assert system_behaviors[2].origin == "firmware"
        assert system_behaviors[3].code == "&fw_behavior2"
        assert system_behaviors[3].origin == "firmware"

    def test_firmware_profile_kconfig_merging(
        self, base_keyboard_config: KeyboardConfig, firmware_config: FirmwareConfig
    ):
        """Test that kconfig options from keyboard and firmware are correctly merged."""
        # Add firmware to keyboard config
        base_keyboard_config.firmwares["v1.0.0"] = firmware_config

        profile = KeyboardProfile(base_keyboard_config, firmware_version="v1.0.0")

        kconfig = profile.kconfig_options

        # Should have all kconfig options (keyboard + firmware)
        assert len(kconfig) == 5

        # Verify keyboard-only options are present
        assert "kb_option1" in kconfig
        assert kconfig["kb_option1"].name == "CONFIG_KB_OPTION1"
        assert kconfig["kb_option1"].default is True

        assert "kb_option2" in kconfig
        assert kconfig["kb_option2"].name == "CONFIG_KB_OPTION2"
        assert kconfig["kb_option2"].default == 42

        # Verify firmware-only options are present
        assert "fw_option1" in kconfig
        assert kconfig["fw_option1"].name == "CONFIG_FW_OPTION1"
        assert kconfig["fw_option1"].default is False

        assert "fw_option2" in kconfig
        assert kconfig["fw_option2"].name == "CONFIG_FW_OPTION2"
        assert kconfig["fw_option2"].default == "0x1234"

        # Verify firmware options override keyboard options
        assert "shared_option" in kconfig
        assert (
            kconfig["shared_option"].default == "firmware_override"
        )  # Not "keyboard_default"
        assert (
            kconfig["shared_option"].description
            == "Option that overrides keyboard default"
        )

    def test_firmware_version_not_found(self, base_keyboard_config: KeyboardConfig):
        """Test that specifying non-existent firmware version raises ConfigError."""
        with pytest.raises(ConfigError, match="Firmware 'nonexistent' not found"):
            KeyboardProfile(base_keyboard_config, firmware_version="nonexistent")

    def test_firmware_config_none_when_no_kconfig(
        self, base_keyboard_config: KeyboardConfig
    ):
        """Test behavior when firmware has no kconfig defined."""
        # Create firmware config without kconfig
        firmware_no_kconfig = FirmwareConfig(
            version="v2.0.0",
            description="Firmware without kconfig",
            build_options=BuildOptions(
                repository="https://github.com/zmkfirmware/zmk",
                branch="main",
            ),
            kconfig=None,  # No kconfig defined
            system_behaviors=[],
        )

        base_keyboard_config.firmwares["v2.0.0"] = firmware_no_kconfig
        profile = KeyboardProfile(base_keyboard_config, firmware_version="v2.0.0")

        # Should only have keyboard kconfig options
        kconfig = profile.kconfig_options
        assert len(kconfig) == 3  # Only keyboard options
        assert "kb_option1" in kconfig
        assert "kb_option2" in kconfig
        assert "shared_option" in kconfig
        assert kconfig["shared_option"].default == "keyboard_default"

    def test_firmware_config_empty_kconfig(self, base_keyboard_config: KeyboardConfig):
        """Test behavior when firmware has empty kconfig dict."""
        # Create firmware config with empty kconfig
        firmware_empty_kconfig = FirmwareConfig(
            version="v3.0.0",
            description="Firmware with empty kconfig",
            build_options=BuildOptions(
                repository="https://github.com/zmkfirmware/zmk",
                branch="main",
            ),
            kconfig={},  # Empty kconfig
            system_behaviors=[
                SystemBehavior(
                    code="&empty_fw_behavior",
                    name="empty_firmware_behavior",
                    description="Behavior from firmware with empty kconfig",
                    expected_params=0,
                    origin="firmware",
                    params=[],
                )
            ],
        )

        base_keyboard_config.firmwares["v3.0.0"] = firmware_empty_kconfig
        profile = KeyboardProfile(base_keyboard_config, firmware_version="v3.0.0")

        # Should only have keyboard kconfig options
        kconfig = profile.kconfig_options
        assert len(kconfig) == 3  # Only keyboard options

        # But should still have firmware system behaviors
        system_behaviors = profile.system_behaviors
        assert len(system_behaviors) == 3  # 2 keyboard + 1 firmware
        assert system_behaviors[2].code == "&empty_fw_behavior"

    def test_merging_preserves_all_attributes(
        self, base_keyboard_config: KeyboardConfig, firmware_config: FirmwareConfig
    ):
        """Test that merging preserves all attributes of SystemBehavior and KConfigOption objects."""
        base_keyboard_config.firmwares["v1.0.0"] = firmware_config
        profile = KeyboardProfile(base_keyboard_config, firmware_version="v1.0.0")

        # Test SystemBehavior attributes are preserved
        fw_behavior = None
        for behavior in profile.system_behaviors:
            if behavior.code == "&fw_behavior1":
                fw_behavior = behavior
                break

        assert fw_behavior is not None
        assert fw_behavior.name == "firmware_behavior_1"
        assert fw_behavior.description == "System behavior from firmware config"
        assert fw_behavior.expected_params == 2
        assert fw_behavior.origin == "firmware"
        assert fw_behavior.params == []

        # Test KConfigOption attributes are preserved
        fw_option = profile.kconfig_options["fw_option2"]
        assert fw_option.name == "CONFIG_FW_OPTION2"
        assert fw_option.type == "hex"
        assert fw_option.default == "0x1234"
        assert fw_option.description == "Firmware-specific kconfig option 2"
