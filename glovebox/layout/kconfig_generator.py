"""Kconfig generation for ZMK firmware configuration."""

import logging
from typing import TYPE_CHECKING, TypeAlias


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile
    from glovebox.layout.models import LayoutData


logger = logging.getLogger(__name__)

# Type alias for kconfig settings
KConfigSettings: TypeAlias = dict[str, str]


class KConfigGenerator:
    """Generator for ZMK Kconfig files from layout data."""

    def __init__(self) -> None:
        """Initialize the Kconfig generator."""
        logger.debug("KConfigGenerator initialized")

    def generate_kconfig_conf(
        self,
        keymap_data: "LayoutData",
        profile: "KeyboardProfile",
    ) -> tuple[str, KConfigSettings]:
        """Generate kconfig content and settings from keymap data.

        Args:
            keymap_data: Keymap data with configuration parameters
            profile: Keyboard profile with kconfig options

        Returns:
            Tuple of (kconfig_content, kconfig_settings)
        """
        logger.info("Generating kconfig configuration")

        kconfig_options = profile.kconfig_options
        user_options: dict[str, str] = {}

        lines = []

        # Extract user config_parameters (kconfig) options from LayoutData
        for opt in keymap_data.config_parameters:
            line = ""
            if opt.param_name in kconfig_options:
                # get the real option name
                name = kconfig_options[opt.param_name].name
                if opt.value == kconfig_options[opt.param_name].default:
                    # check if the user is setting same value as default
                    # in that case, we set it but in comment
                    # that allows the user to switch more easily firmware
                    # without changing the kconfig
                    line = "# "
            else:
                name = opt.param_name
                if not name.startswith("CONFIG_"):
                    name = "CONFIG_" + name

            line += f"{name}={opt.value}"
            lines.append(line)

        # Generate formatted kconfig content
        lines.append("# Generated ZMK configuration")
        lines.append("")

        kconfig_content = "\n".join(lines)
        return kconfig_content, user_options


def create_kconfig_generator() -> KConfigGenerator:
    """Create a new KConfigGenerator instance.

    Returns:
        Configured KConfigGenerator instance
    """
    return KConfigGenerator()
