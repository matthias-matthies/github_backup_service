"""Unit tests for src.config.config_manager.ConfigManager."""

import os

import pytest
import yaml

from src.config.config_manager import ConfigManager


VALID_CONFIG = {
    "github": {
        "app_id": "123",
        "private_key_path": "/path/to/key.pem",
        "org_name": "my-org",
    },
    "output": {
        "base_path": "/tmp/backup",
    },
}


@pytest.fixture
def valid_config_file(tmp_path):
    """Write a valid YAML config to a temp file and return its path."""
    config_path = tmp_path / "config.yml"
    config_path.write_text(yaml.dump(VALID_CONFIG), encoding="utf-8")
    return str(config_path)


def test_load_valid_config(valid_config_file):
    """load() should return a dict with the expected keys."""
    manager = ConfigManager(valid_config_file)
    config = manager.load()

    assert isinstance(config, dict)
    assert "github" in config
    assert "output" in config
    assert config["github"]["app_id"] == "123"
    assert config["github"]["org_name"] == "my-org"


def test_load_missing_file(tmp_path):
    """load() raises FileNotFoundError for a non-existent config path."""
    manager = ConfigManager(str(tmp_path / "nonexistent.yml"))
    with pytest.raises(FileNotFoundError):
        manager.load()


def test_get_nested_key(valid_config_file):
    """get() with dot-notation should retrieve nested values."""
    manager = ConfigManager(valid_config_file)
    manager.load()

    assert manager.get("github.app_id") == "123"
    assert manager.get("output.base_path") == "/tmp/backup"
    assert manager.get("does.not.exist", default="fallback") == "fallback"


def test_validate_missing_required_keys(tmp_path):
    """validate() raises ValueError when required keys are missing."""
    incomplete = {"github": {"app_id": "123"}}
    config_path = tmp_path / "incomplete.yml"
    config_path.write_text(yaml.dump(incomplete), encoding="utf-8")

    manager = ConfigManager(str(config_path))
    manager.load()

    with pytest.raises(ValueError, match="validation failed"):
        manager.validate()


def test_env_override(valid_config_file, monkeypatch):
    """GITHUB_APP_ID env var should override the value from the config file."""
    monkeypatch.setenv("GITHUB_APP_ID", "overridden-id")

    manager = ConfigManager(valid_config_file)
    manager.load()

    assert manager.get("github.app_id") == "overridden-id"
