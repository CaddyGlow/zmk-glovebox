"""MoErgo Cognito authentication module."""

import logging
from typing import Any

import requests

from glovebox.moergo.config import MoErgoCognitoConfig
from glovebox.services.base_service import BaseService


class CognitoAuth(BaseService):
    """Handles AWS Cognito authentication for MoErgo API."""

    def __init__(self, cognito_config: MoErgoCognitoConfig | None = None):
        super().__init__("CognitoAuth", "1.0.0")
        self.config = cognito_config or MoErgoCognitoConfig()

    def _get_headers(self, target: str) -> dict[str, str]:
        """Get headers for Cognito requests."""
        return {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "cache-control": "no-store",
            "content-type": "application/x-amz-json-1.1",
            "origin": self.config.origin_url,
            "referer": self.config.referer_url,
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "cross-site",
            "user-agent": self.config.user_agent,
            "x-amz-target": target,
            "x-amz-user-agent": self.config.aws_amplify_version,
        }

    def simple_login_attempt(
        self, username: str, password: str
    ) -> dict[str, Any] | None:
        """
        Attempt authentication using USER_PASSWORD_AUTH flow.

        Returns authentication result dict if successful, None otherwise.
        """
        headers = self._get_headers("AWSCognitoIdentityProviderService.InitiateAuth")

        payload = {
            "AuthFlow": "USER_PASSWORD_AUTH",
            "ClientId": self.config.client_id,
            "AuthParameters": {"USERNAME": username, "PASSWORD": password},
        }

        try:
            response = requests.post(
                self.config.cognito_url,
                headers=headers,
                json=payload,
                timeout=self.config.request_timeout,
            )
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]
        except (requests.exceptions.RequestException, ValueError) as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.warning(
                "cognito_authentication_failed", error=str(e), exc_info=exc_info
            )
            return None

    def refresh_token(self, refresh_token: str) -> dict[str, Any] | None:
        """
        Refresh access token using refresh token.

        Returns authentication result dict if successful, None otherwise.
        """
        headers = self._get_headers("AWSCognitoIdentityProviderService.InitiateAuth")

        payload = {
            "AuthFlow": "REFRESH_TOKEN_AUTH",
            "ClientId": self.config.client_id,
            "AuthParameters": {"REFRESH_TOKEN": refresh_token},
        }

        try:
            response = requests.post(
                self.config.cognito_url,
                headers=headers,
                json=payload,
                timeout=self.config.request_timeout,
            )
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]
        except (requests.exceptions.RequestException, ValueError) as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.warning(
                "cognito_token_refresh_failed", error=str(e), exc_info=exc_info
            )
            return None

    def initiate_auth(self, username: str) -> dict[str, Any] | None:
        """
        Initiate SRP authentication flow.

        This is for future SRP implementation.
        """
        headers = self._get_headers("AWSCognitoIdentityProviderService.InitiateAuth")

        payload = {
            "AuthFlow": "USER_SRP_AUTH",
            "ClientId": self.config.client_id,
            "AuthParameters": {"USERNAME": username},
        }

        try:
            response = requests.post(
                self.config.cognito_url,
                headers=headers,
                json=payload,
                timeout=self.config.request_timeout,
            )
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]
        except (requests.exceptions.RequestException, ValueError) as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.warning(
                "cognito_srp_initiation_failed", error=str(e), exc_info=exc_info
            )
            return None


def create_cognito_auth(
    cognito_config: MoErgoCognitoConfig | None = None,
) -> CognitoAuth:
    """Create a CognitoAuth instance with the given configuration.

    Factory function following CLAUDE.md patterns for creating
    CognitoAuth instances with proper configuration.

    Args:
        cognito_config: MoErgo Cognito configuration (defaults to default config)

    Returns:
        CognitoAuth: Configured Cognito authentication client
    """
    return CognitoAuth(cognito_config)


# Backward compatibility alias
Glove80Auth = CognitoAuth
