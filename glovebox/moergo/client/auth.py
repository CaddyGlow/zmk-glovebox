"""MoErgo Cognito authentication module."""

from typing import Any

import requests


class CognitoAuth:
    """Handles AWS Cognito authentication for MoErgo API."""

    def __init__(self) -> None:
        self.client_id = "3hvr36st4kdb6p7kasi1cdnson"
        self.cognito_url = "https://cognito-idp.us-east-1.amazonaws.com/"

    def _get_headers(self, target: str) -> dict[str, str]:
        """Get headers for Cognito requests."""
        return {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "cache-control": "no-store",
            "content-type": "application/x-amz-json-1.1",
            "origin": "https://my.glove80.com",
            "referer": "https://my.glove80.com/",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "cross-site",
            "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            "x-amz-target": target,
            "x-amz-user-agent": "aws-amplify/5.0.4 js",
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
            "ClientId": self.client_id,
            "AuthParameters": {"USERNAME": username, "PASSWORD": password},
        }

        try:
            response = requests.post(
                self.cognito_url, headers=headers, json=payload, timeout=30
            )
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]
        except (requests.exceptions.RequestException, ValueError):
            # Silently fail for now - caller will handle the None return
            return None

    def refresh_token(self, refresh_token: str) -> dict[str, Any] | None:
        """
        Refresh access token using refresh token.

        Returns authentication result dict if successful, None otherwise.
        """
        headers = self._get_headers("AWSCognitoIdentityProviderService.InitiateAuth")

        payload = {
            "AuthFlow": "REFRESH_TOKEN_AUTH",
            "ClientId": self.client_id,
            "AuthParameters": {"REFRESH_TOKEN": refresh_token},
        }

        try:
            response = requests.post(
                self.cognito_url, headers=headers, json=payload, timeout=30
            )
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]
        except (requests.exceptions.RequestException, ValueError):
            # Silently fail for now - caller will handle the None return
            return None

    def initiate_auth(self, username: str) -> dict[str, Any] | None:
        """
        Initiate SRP authentication flow.

        This is for future SRP implementation.
        """
        headers = self._get_headers("AWSCognitoIdentityProviderService.InitiateAuth")

        payload = {
            "AuthFlow": "USER_SRP_AUTH",
            "ClientId": self.client_id,
            "AuthParameters": {"USERNAME": username},
        }

        try:
            response = requests.post(
                self.cognito_url, headers=headers, json=payload, timeout=30
            )
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]
        except (requests.exceptions.RequestException, ValueError):
            return None


# Backward compatibility alias
Glove80Auth = CognitoAuth
