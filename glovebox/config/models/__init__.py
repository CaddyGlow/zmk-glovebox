"""Configuration models organized by domain with lazy loading."""

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    # Type checking imports only - not loaded at runtime
    from .behavior import BehaviorConfig, BehaviorMapping, ModifierMapping
    from .display import DisplayConfig, DisplayFormatting, LayoutStructure
    from .firmware import (
        BuildOptions,
        FirmwareConfig,
        FirmwareFlashConfig,
        KConfigOption,
        UserFirmwareConfig,
    )
    from .keyboard import FormattingConfig, KeyboardConfig, KeymapSection
    from .moergo import (
        MoErgoCognitoConfig,
        MoErgoCredentialConfig,
        MoErgoServiceConfig,
        create_default_moergo_config,
        create_moergo_cognito_config,
        create_moergo_credential_config,
    )
    from .user import UserConfigData
    from .zmk import (
        FileExtensions,
        ValidationLimits,
        ZmkCompatibleStrings,
        ZmkConfig,
        ZmkPatterns,
    )


def __getattr__(name: str) -> Any:
    """Lazy load config models on first access.

    This allows importing the module without loading all model dependencies upfront.
    Models are imported only when actually used.
    """
    # Behavior models
    if name == "BehaviorConfig":
        from .behavior import BehaviorConfig
        return BehaviorConfig
    elif name == "BehaviorMapping":
        from .behavior import BehaviorMapping
        return BehaviorMapping
    elif name == "ModifierMapping":
        from .behavior import ModifierMapping
        return ModifierMapping

    # Display models
    elif name == "DisplayConfig":
        from .display import DisplayConfig
        return DisplayConfig
    elif name == "DisplayFormatting":
        from .display import DisplayFormatting
        return DisplayFormatting
    elif name == "LayoutStructure":
        from .display import LayoutStructure
        return LayoutStructure

    # Firmware models
    elif name == "BuildOptions":
        from .firmware import BuildOptions
        return BuildOptions
    elif name == "FirmwareConfig":
        from .firmware import FirmwareConfig
        return FirmwareConfig
    elif name == "FirmwareFlashConfig":
        from .firmware import FirmwareFlashConfig
        return FirmwareFlashConfig
    elif name == "KConfigOption":
        from .firmware import KConfigOption
        return KConfigOption
    elif name == "UserFirmwareConfig":
        from .firmware import UserFirmwareConfig
        return UserFirmwareConfig

    # Keyboard models
    elif name == "FormattingConfig":
        from .keyboard import FormattingConfig
        return FormattingConfig
    elif name == "KeyboardConfig":
        from .keyboard import KeyboardConfig
        return KeyboardConfig
    elif name == "KeymapSection":
        from .keyboard import KeymapSection
        return KeymapSection

    # MoErgo models
    elif name == "MoErgoCognitoConfig":
        from .moergo import MoErgoCognitoConfig
        return MoErgoCognitoConfig
    elif name == "MoErgoCredentialConfig":
        from .moergo import MoErgoCredentialConfig
        return MoErgoCredentialConfig
    elif name == "MoErgoServiceConfig":
        from .moergo import MoErgoServiceConfig
        return MoErgoServiceConfig
    elif name == "create_default_moergo_config":
        from .moergo import create_default_moergo_config
        return create_default_moergo_config
    elif name == "create_moergo_cognito_config":
        from .moergo import create_moergo_cognito_config
        return create_moergo_cognito_config
    elif name == "create_moergo_credential_config":
        from .moergo import create_moergo_credential_config
        return create_moergo_credential_config

    # User models
    elif name == "UserConfigData":
        from .user import UserConfigData
        return UserConfigData

    # ZMK models
    elif name == "FileExtensions":
        from .zmk import FileExtensions
        return FileExtensions
    elif name == "ValidationLimits":
        from .zmk import ValidationLimits
        return ValidationLimits
    elif name == "ZmkCompatibleStrings":
        from .zmk import ZmkCompatibleStrings
        return ZmkCompatibleStrings
    elif name == "ZmkConfig":
        from .zmk import ZmkConfig
        return ZmkConfig
    elif name == "ZmkPatterns":
        from .zmk import ZmkPatterns
        return ZmkPatterns

    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BehaviorConfig",
    "BehaviorMapping",
    "BuildOptions",
    "DisplayConfig",
    "DisplayFormatting",
    "FileExtensions",
    "FirmwareConfig",
    "FirmwareFlashConfig",
    "FormattingConfig",
    "KConfigOption",
    "KeyboardConfig",
    "KeymapSection",
    "LayoutStructure",
    "ModifierMapping",
    "MoErgoCognitoConfig",
    "MoErgoCredentialConfig",
    "MoErgoServiceConfig",
    "UserConfigData",
    "UserFirmwareConfig",
    "ValidationLimits",
    "ZmkCompatibleStrings",
    "ZmkConfig",
    "ZmkPatterns",
    "create_default_moergo_config",
    "create_moergo_cognito_config",
    "create_moergo_credential_config",
]
