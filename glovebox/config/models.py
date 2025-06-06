"""
Type definitions for keyboard configuration.

This module provides dataclasses for representing keyboard configuration data
that is loaded from YAML files. These dataclasses provide type safety, validation,
and help with IDE autocompletion.
"""

from dataclasses import dataclass, field
from typing import Any, TypeAlias

# Import consolidated behavior models
from glovebox.models.behavior import (
    BehaviorCommand,
    ParameterType,
    SystemBehavior,
)
from glovebox.models.behavior import (
    BehaviorParameter as Parameter,
)


# KConfig type definitions
@dataclass
class KConfigOption:
    """Definition of a KConfig option."""

    name: str
    type: str
    default: Any
    description: str


# Flash configuration
@dataclass
class FlashConfig:
    """Flash configuration for a keyboard."""

    method: str
    query: str
    usb_vid: str
    usb_pid: str


# Build configuration
@dataclass
class BuildConfig:
    """Build configuration for a keyboard."""

    method: str
    docker_image: str
    repository: str
    branch: str


# Visual layout configuration
@dataclass
class VisualLayout:
    """Visual layout for a keyboard."""

    rows: list[list[int]]


# Formatting configuration
@dataclass
class FormattingConfig:
    """Formatting configuration for a keyboard."""

    default_key_width: int
    key_gap: str
    base_indent: str = ""
    rows: list[list[int]] | None = None


# Firmware build options
@dataclass
class BuildOptions:
    """Build options for a firmware."""

    repository: str
    branch: str


# Firmware configuration
@dataclass
class FirmwareConfig:
    """Firmware configuration for a keyboard."""

    version: str
    description: str
    build_options: BuildOptions
    kconfig: dict[str, KConfigOption] | None = None


# Keymap section
@dataclass
class KeymapSection:
    """Keymap section of a keyboard configuration."""

    includes: list[str]
    formatting: FormattingConfig
    system_behaviors: list[SystemBehavior]
    kconfig_options: dict[str, KConfigOption]
    keymap_dtsi: str | None = None
    system_behaviors_dts: str | None = None
    key_position_header: str | None = None


# Complete keyboard configuration
@dataclass
class KeyboardConfig:
    """Complete keyboard configuration."""

    keyboard: str
    description: str
    vendor: str
    key_count: int
    flash: FlashConfig
    build: BuildConfig
    firmwares: dict[str, FirmwareConfig]
    keymap: KeymapSection

    def __post_init__(self) -> None:
        """Convert nested dictionaries to proper dataclasses."""
        # Convert flash config
        if isinstance(self.flash, dict):
            self.flash = FlashConfig(**self.flash)

        # Convert build config
        if isinstance(self.build, dict):
            self.build = BuildConfig(**self.build)

        # Convert firmwares
        if isinstance(self.firmwares, dict):
            converted_firmwares = {}
            for firmware_name, firmware_data in self.firmwares.items():
                # Cast to dict for type safety
                firmware_dict = firmware_data if isinstance(firmware_data, dict) else {}

                # Convert build options
                build_options_dict = firmware_dict.get("build_options", {})
                if isinstance(build_options_dict, dict):
                    build_options = BuildOptions(**build_options_dict)
                else:
                    build_options = BuildOptions(repository="", branch="")

                # Convert kconfig options
                kconfig_dict = firmware_dict.get("kconfig", {})
                if isinstance(kconfig_dict, dict):
                    converted_kconfig = {}
                    for k_name, k_data in kconfig_dict.items():
                        if isinstance(k_data, dict):
                            converted_kconfig[k_name] = KConfigOption(**k_data)
                    kconfig = converted_kconfig
                else:
                    kconfig = None

                # Create firmware config
                converted_firmwares[firmware_name] = FirmwareConfig(
                    version=firmware_dict.get("version", ""),
                    description=firmware_dict.get("description", ""),
                    build_options=build_options,
                    kconfig=kconfig,
                )
            self.firmwares = converted_firmwares

        # Convert keymap section
        if isinstance(self.keymap, dict):
            # Convert system behaviors
            system_behaviors = []
            for behavior_data in self.keymap.get("system_behaviors", []):
                # Convert commands
                commands = None
                if "commands" in behavior_data:
                    commands = []
                    for cmd_data in behavior_data["commands"]:
                        # Convert additional params
                        additional_params = None
                        if "additionalParams" in cmd_data:
                            additional_params = []
                            for param_data in cmd_data["additionalParams"]:
                                additional_params.append(Parameter(**param_data))

                        commands.append(
                            BehaviorCommand(
                                code=cmd_data.get("code", ""),
                                name=cmd_data.get("name"),
                                description=cmd_data.get("description"),
                                flatten=cmd_data.get("flatten", False),
                                additional_params=additional_params,
                            )
                        )

                # Convert params
                params = []
                for param_data in behavior_data.get("params", []):
                    if isinstance(param_data, dict):
                        params.append(Parameter(**param_data))
                    else:
                        params.append(param_data)

                system_behaviors.append(
                    SystemBehavior(
                        code=behavior_data.get("code", ""),
                        name=behavior_data.get("name", ""),
                        description=behavior_data.get("description", ""),
                        expected_params=behavior_data.get("expected_params", 0),
                        origin=behavior_data.get("origin", ""),
                        params=params,
                        url=behavior_data.get("url"),
                        is_macro_control_behavior=behavior_data.get(
                            "isMacroControlBehavior", False
                        ),
                        includes=behavior_data.get("includes"),
                        commands=commands,
                    )
                )

            # Convert kconfig options
            kconfig_options = {}
            for option_name, option_data in self.keymap.get(
                "kconfig_options", {}
            ).items():
                kconfig_options[option_name] = KConfigOption(**option_data)

            # Convert formatting config
            formatting_data = self.keymap.get("formatting", {})
            if isinstance(formatting_data, dict):
                formatting = FormattingConfig(
                    default_key_width=formatting_data.get("default_key_width", 8),
                    key_gap=formatting_data.get("key_gap", "  "),
                    base_indent=formatting_data.get("base_indent", ""),
                    rows=formatting_data.get("rows", []),
                )
            else:
                formatting = FormattingConfig(default_key_width=8, key_gap="  ")

            # Create keymap section
            self.keymap = KeymapSection(
                includes=self.keymap.get("includes", []),
                formatting=formatting,
                system_behaviors=system_behaviors,
                kconfig_options=kconfig_options,
                keymap_dtsi=self.keymap.get("keymap_dtsi"),
                system_behaviors_dts=self.keymap.get("system_behaviors_dts"),
                key_position_header=self.keymap.get("key_position_header"),
            )
