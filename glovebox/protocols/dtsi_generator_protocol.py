"""Protocol definition for DTSI generator."""

from collections.abc import Sequence
from typing import Protocol, TypeAlias, runtime_checkable

from glovebox.layout.models import (
    ComboBehavior,
    HoldTapBehavior,
    InputListener,
    LayerBindings,
    MacroBehavior,
)


# Type alias for kconfig settings
KConfigSettings: TypeAlias = dict[str, str]


@runtime_checkable
class DtsiGeneratorProtocol(Protocol):
    """Protocol for DTSI generator."""

    def generate_layer_defines(
        self, profile: "KeyboardProfile", layer_names: list[str]
    ) -> str:
        """Generate layer define statements."""
        ...

    def generate_keymap_node(
        self,
        profile: "KeyboardProfile",
        layer_names: list[str],
        layers_data: list[LayerBindings],
    ) -> str:
        """Generate keymap node DTSI content."""
        ...

    def generate_behaviors_dtsi(
        self, profile: "KeyboardProfile", hold_taps_data: Sequence[HoldTapBehavior]
    ) -> str:
        """Generate behaviors DTSI content."""
        ...

    def generate_macros_dtsi(
        self, profile: "KeyboardProfile", macros_data: Sequence[MacroBehavior]
    ) -> str:
        """Generate macros DTSI content."""
        ...

    def generate_combos_dtsi(
        self,
        profile: "KeyboardProfile",
        combos_data: Sequence[ComboBehavior],
        layer_names: list[str],
    ) -> str:
        """Generate combos DTSI content."""
        ...

    def generate_input_listeners_node(
        self, profile: "KeyboardProfile", input_listeners_data: Sequence[InputListener]
    ) -> str:
        """Generate input listeners DTSI content."""
        ...

    def generate_kconfig_conf(
        self,
        keymap_data: "LayoutData",
        profile: "KeyboardProfile",
    ) -> tuple[str, KConfigSettings]:
        """Generate kconfig configuration."""
        ...


# Avoid circular imports with TYPE_CHECKING
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile
    from glovebox.layout.models import LayoutData
