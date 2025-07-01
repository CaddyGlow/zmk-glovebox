"""MoErgo service configuration models.

Re-exports configuration models from the MoErgo domain module,
following domain-driven design where domains own their configuration.
"""

# Import from the MoErgo domain module where these models now live
from glovebox.moergo.config import (
    MoErgoCognitoConfig,
    MoErgoCredentialConfig,
    MoErgoServiceConfig,
    create_default_moergo_config,
    create_moergo_cognito_config,
    create_moergo_credential_config,
)


__all__ = [
    "MoErgoCognitoConfig",
    "MoErgoCredentialConfig",
    "MoErgoServiceConfig",
    "create_default_moergo_config",
    "create_moergo_cognito_config",
    "create_moergo_credential_config",
]
