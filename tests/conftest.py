"""Shared pytest fixtures for the GitHub Backup Service test suite."""

import pytest
from unittest.mock import MagicMock

from src.storage.storage_manager import StorageManager


@pytest.fixture
def tmp_backup_dir(tmp_path):
    """Return a temporary directory path string for backup output."""
    return str(tmp_path)


@pytest.fixture
def sample_config(tmp_backup_dir):
    """Return a sample configuration dictionary for tests."""
    return {
        "github": {
            "app_id": "123",
            "private_key_path": "/fake/key.pem",
            "org_name": "test-org",
        },
        "output": {
            "base_path": tmp_backup_dir,
        },
    }


@pytest.fixture
def mock_api_client():
    """Return a MagicMock API client with common methods."""
    client = MagicMock()
    client.get = MagicMock(return_value={})
    client.paginate = MagicMock(return_value=[])
    client.post = MagicMock(return_value={})
    client.graphql = MagicMock(return_value={})
    return client


@pytest.fixture
def mock_storage_manager(tmp_backup_dir):
    """Return a StorageManager backed by a temporary directory."""
    return StorageManager(tmp_backup_dir)
