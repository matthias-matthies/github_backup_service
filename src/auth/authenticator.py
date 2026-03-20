"""GitHub App authenticator using JWT and installation tokens."""

import logging
import time
from datetime import datetime, timezone

import jwt as pyjwt
import requests

logger = logging.getLogger(__name__)


class Authenticator:
    """Handles GitHub App authentication via JWT and installation access tokens."""

    def __init__(self, app_id: str, private_key_path: str, base_url: str = "https://api.github.com") -> None:
        """
        Initialise the Authenticator.

        Args:
            app_id: GitHub App ID.
            private_key_path: Filesystem path to the PEM private key file.
            base_url: GitHub API base URL (default: https://api.github.com).
        """
        self.app_id = app_id
        self.private_key_path = private_key_path
        self.base_url = base_url.rstrip("/")
        self._token_cache: dict[str, dict] = {}  # org_name -> {"token": ..., "expires_at": ...}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_private_key(self) -> str:
        """Read and return the RSA private key PEM string from disk."""
        with open(self.private_key_path, "r", encoding="utf-8") as fh:
            return fh.read()

    def _create_jwt(self) -> str:
        """
        Create a short-lived JWT for GitHub App authentication.

        The token is valid from (now - 60 s) to (now + 540 s) as recommended
        by GitHub to account for clock drift.

        Returns:
            Encoded JWT string.
        """
        now = int(time.time())
        payload = {
            "iat": now - 60,
            "exp": now + 540,
            "iss": self.app_id,
        }
        private_key = self._load_private_key()
        token = pyjwt.encode(payload, private_key, algorithm="RS256")
        # PyJWT >= 2.x returns str; older versions return bytes.
        if isinstance(token, bytes):
            token = token.decode("utf-8")
        return token

    def _is_token_expired(self, token_data: dict) -> bool:
        """
        Check whether a cached installation token has expired (or is within 5 minutes of expiry).

        Args:
            token_data: Dict with at least an ``expires_at`` key (ISO-8601 string).

        Returns:
            True if the token should be considered expired.
        """
        expires_at_str: str = token_data.get("expires_at", "")
        if not expires_at_str:
            return True
        # GitHub returns e.g. "2024-01-01T12:00:00Z"
        expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
        buffer_seconds = 5 * 60
        now = datetime.now(tz=timezone.utc)
        return (expires_at - now).total_seconds() < buffer_seconds

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_installation_id(self, org_name: str) -> int:
        """
        Retrieve the installation ID for a given GitHub organisation.

        Args:
            org_name: The organisation login name.

        Returns:
            The installation ID as an integer.

        Raises:
            ValueError: If no installation for *org_name* is found.
            requests.HTTPError: On non-2xx responses.
        """
        jwt_token = self._create_jwt()
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json",
        }
        url = f"{self.base_url}/app/installations"
        logger.debug("Fetching installations from %s", url)

        page = 1
        while True:
            response = requests.get(url, headers=headers, params={"per_page": 100, "page": page}, timeout=30)
            response.raise_for_status()
            installations = response.json()
            if not installations:
                break
            for installation in installations:
                account = installation.get("account", {})
                if account.get("login", "").lower() == org_name.lower():
                    installation_id: int = installation["id"]
                    logger.info("Found installation ID %d for org '%s'", installation_id, org_name)
                    return installation_id
            if len(installations) < 100:
                break
            page += 1

        raise ValueError(f"No GitHub App installation found for organisation '{org_name}'")

    def get_installation_token(self, installation_id: int) -> dict:
        """
        Request an installation access token from GitHub.

        Args:
            installation_id: The installation ID returned by :meth:`get_installation_id`.

        Returns:
            Dict containing ``token`` and ``expires_at`` keys.

        Raises:
            requests.HTTPError: On non-2xx responses.
        """
        jwt_token = self._create_jwt()
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json",
        }
        url = f"{self.base_url}/app/installations/{installation_id}/access_tokens"
        logger.debug("Requesting installation token from %s", url)

        response = requests.post(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        logger.info("Obtained installation token (expires at %s)", data.get("expires_at"))
        return {"token": data["token"], "expires_at": data["expires_at"]}

    def get_token_for_org(self, org_name: str) -> str:
        """
        Return a valid installation access token for the given organisation.

        The token is cached and reused until it is within 5 minutes of expiry,
        at which point a fresh token is obtained automatically.

        Args:
            org_name: The organisation login name.

        Returns:
            Installation access token string.
        """
        cached = self._token_cache.get(org_name)
        if cached and not self._is_token_expired(cached):
            logger.debug("Using cached token for org '%s'", org_name)
            return cached["token"]

        logger.info("Obtaining new installation token for org '%s'", org_name)
        installation_id = self.get_installation_id(org_name)
        token_data = self.get_installation_token(installation_id)
        self._token_cache[org_name] = token_data
        return token_data["token"]
