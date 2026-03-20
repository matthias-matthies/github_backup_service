"""
Configuration manager for the GitHub Backup Service.

Loads YAML configuration from disk and merges any environment variable
overrides on top before exposing values through a convenient dot-notation
getter.
"""

import os
from typing import Any, Dict, Optional

import yaml

from src.utils.validators import validate_config


class ConfigManager:
    """Load, merge, and validate application configuration.

    Configuration is read from a YAML file.  Selected keys can be
    overridden at runtime via environment variables (useful for CI/CD and
    containerised deployments).

    Supported environment variable overrides:
        - ``GITHUB_APP_ID``          → ``github.app_id``
        - ``GITHUB_PRIVATE_KEY_PATH`` → ``github.private_key_path``
        - ``GITHUB_ORG_NAME``        → ``github.org_name``
        - ``BACKUP_OUTPUT_PATH``     → ``output.base_path``

    Example::

        manager = ConfigManager("/etc/backup/config.yml")
        manager.load()
        manager.validate()
        app_id = manager.get("github.app_id")
    """

    def __init__(self, config_path: str) -> None:
        """Initialise the manager with the path to the YAML config file.

        Args:
            config_path: Filesystem path (absolute or relative) to the
                         YAML configuration file.
        """
        self._config_path: str = config_path
        self._config: Dict[str, Any] = {}

    # ── Public API ────────────────────────────────────────────────────────

    def load(self) -> Dict[str, Any]:
        """Load the YAML configuration file and apply env-var overrides.

        Returns:
            The merged configuration dictionary.

        Raises:
            FileNotFoundError: If *config_path* does not exist.
            yaml.YAMLError:    If the file cannot be parsed as valid YAML.
        """
        if not os.path.isfile(self._config_path):
            raise FileNotFoundError(
                f"Configuration file not found: '{self._config_path}'"
            )

        with open(self._config_path, "r", encoding="utf-8") as fh:
            raw: Dict[str, Any] = yaml.safe_load(fh) or {}

        self._config = self._apply_env_overrides(raw)
        return self._config

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a value using dot-notation.

        Args:
            key:     Dot-separated key path, e.g. ``"github.app_id"``.
            default: Value to return when the key is not found.

        Returns:
            The configuration value, or *default* if not found.
        """
        parts = key.split(".")
        node: Any = self._config
        for part in parts:
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def validate(self) -> bool:
        """Validate the loaded configuration.

        Returns:
            ``True`` when the configuration is valid.

        Raises:
            ValueError: With all validation error messages joined by newlines
                        if any required key is missing or invalid.
        """
        errors = validate_config(self._config)
        if errors:
            raise ValueError(
                "Configuration validation failed:\n" + "\n".join(f"  • {e}" for e in errors)
            )
        return True

    # ── Internal helpers ──────────────────────────────────────────────────

    def _apply_env_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Merge environment variable overrides into *config*.

        Only env vars that are actually set (non-empty strings) are applied.

        Args:
            config: Base configuration dictionary loaded from YAML.

        Returns:
            Updated configuration dictionary (modified in-place and returned).
        """
        overrides = {
            "GITHUB_APP_ID": ("github", "app_id"),
            "GITHUB_PRIVATE_KEY_PATH": ("github", "private_key_path"),
            "GITHUB_ORG_NAME": ("github", "org_name"),
            "BACKUP_OUTPUT_PATH": ("output", "base_path"),
        }

        for env_var, (section, field) in overrides.items():
            value = os.environ.get(env_var, "").strip()
            if value:
                if section not in config or not isinstance(config[section], dict):
                    config[section] = {}
                config[section][field] = value

        return config

    # ── Dunder helpers ────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return f"ConfigManager(config_path={self._config_path!r})"
