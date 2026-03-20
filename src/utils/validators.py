"""
Input-validation helpers for the GitHub Backup Service.

All public functions are pure (no side-effects) and designed to be
imported and used across the codebase for consistent input checking.
"""

import re
from typing import Any, Dict, List


# Only letters, digits, and hyphens — matching GitHub's own org-name rules.
_ORG_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-]*$")

# Required dot-notation keys that must be present (and non-empty) in a config.
_REQUIRED_CONFIG_KEYS: List[str] = [
    "github.app_id",
    "github.private_key_path",
    "github.org_name",
    "output.base_path",
]


def validate_org_name(name: str) -> bool:
    """Return ``True`` when *name* is a valid GitHub organisation name.

    Rules:
    - Must be a non-empty string.
    - May only contain ASCII letters, digits, and hyphens.
    - Must not start with a hyphen (GitHub enforces this as well).

    Args:
        name: The organisation name to validate.

    Returns:
        ``True`` if valid, ``False`` otherwise.
    """
    if not isinstance(name, str) or not name:
        return False
    return bool(_ORG_NAME_RE.match(name))


def validate_path(path: str) -> bool:
    """Return ``True`` when *path* is a usable (non-empty string) path value.

    This is an intentionally lightweight check — it does **not** verify that
    the path exists on disk, only that a meaningful value was supplied.

    Args:
        path: The filesystem path to validate.

    Returns:
        ``True`` if *path* is a non-empty string, ``False`` otherwise.
    """
    return isinstance(path, str) and bool(path.strip())


def _get_nested(config: Dict[str, Any], dotted_key: str) -> Any:
    """Retrieve a value from a nested dict using a dot-separated key string.

    Args:
        config:     The (possibly nested) configuration dictionary.
        dotted_key: A key like ``"github.app_id"`` that maps to
                    ``config["github"]["app_id"]``.

    Returns:
        The value found, or ``None`` if any intermediate key is missing.
    """
    parts = dotted_key.split(".")
    node: Any = config
    for part in parts:
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def validate_config(config: Dict[str, Any]) -> List[str]:
    """Validate a configuration dictionary and return a list of error messages.

    Checks that every required key exists and has a non-empty value.

    Required keys (dot-notation):
        - ``github.app_id``
        - ``github.private_key_path``
        - ``github.org_name``
        - ``output.base_path``

    Args:
        config: The configuration dictionary to validate (may be nested).

    Returns:
        A list of human-readable error strings.  An empty list means the
        configuration is valid.
    """
    errors: List[str] = []

    if not isinstance(config, dict):
        return ["Configuration must be a dictionary."]

    for key in _REQUIRED_CONFIG_KEYS:
        value = _get_nested(config, key)
        if value is None:
            errors.append(f"Missing required configuration key: '{key}'.")
        elif not str(value).strip():
            errors.append(f"Configuration key '{key}' must not be empty.")

    # Additional semantic validation for org_name.
    org_name = _get_nested(config, "github.org_name")
    if org_name and not validate_org_name(str(org_name)):
        errors.append(
            f"'github.org_name' value '{org_name}' is not a valid GitHub "
            "organisation name (letters, digits, and hyphens only)."
        )

    return errors
