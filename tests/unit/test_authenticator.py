"""Unit tests for src.auth.authenticator."""

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, mock_open, patch

import pytest

from src.auth.authenticator import Authenticator


@pytest.fixture
def authenticator():
    return Authenticator(app_id="42", private_key_path="/fake/key.pem")


def test_create_jwt_returns_string(authenticator):
    """_create_jwt() should return a non-empty string."""
    fake_key = (
        "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA\n-----END RSA PRIVATE KEY-----\n"
    )
    with patch.object(authenticator, "_load_private_key", return_value=fake_key):
        import jwt as pyjwt

        with patch.object(pyjwt, "encode", return_value="fake.jwt.token") as mock_encode:
            result = authenticator._create_jwt()
            assert isinstance(result, str)
            assert len(result) > 0
            mock_encode.assert_called_once()


def test_get_installation_id_found(authenticator):
    """get_installation_id() returns the ID when the org is found."""
    fake_installations = [
        {"id": 99, "account": {"login": "test-org"}},
        {"id": 100, "account": {"login": "other-org"}},
    ]
    mock_response = MagicMock()
    mock_response.json.return_value = fake_installations
    mock_response.raise_for_status = MagicMock()

    with patch.object(authenticator, "_create_jwt", return_value="fake.jwt"):
        with patch("requests.get", return_value=mock_response):
            installation_id = authenticator.get_installation_id("test-org")
            assert installation_id == 99


def test_get_installation_id_not_found(authenticator):
    """get_installation_id() raises ValueError when the org is not found."""
    mock_response = MagicMock()
    mock_response.json.return_value = []
    mock_response.raise_for_status = MagicMock()

    with patch.object(authenticator, "_create_jwt", return_value="fake.jwt"):
        with patch("requests.get", return_value=mock_response):
            with pytest.raises(ValueError, match="No GitHub App installation found"):
                authenticator.get_installation_id("missing-org")


def test_token_expiry_check_future(authenticator):
    """_is_token_expired() returns False when token expires in the future."""
    future = datetime.now(tz=timezone.utc) + timedelta(hours=1)
    token_data = {"expires_at": future.strftime("%Y-%m-%dT%H:%M:%SZ")}
    assert authenticator._is_token_expired(token_data) is False


def test_token_expiry_check_past(authenticator):
    """_is_token_expired() returns True when token is expired."""
    past = datetime.now(tz=timezone.utc) - timedelta(hours=1)
    token_data = {"expires_at": past.strftime("%Y-%m-%dT%H:%M:%SZ")}
    assert authenticator._is_token_expired(token_data) is True
