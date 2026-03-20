"""
Base restorer module providing the abstract base class and ConflictError
for all domain-specific restorers in the restore package.
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Union

from ..utils.logger import setup_logger


class ConflictError(Exception):
    """Raised when a resource already exists and conflicts with backup data."""

    def __init__(self, resource_type: str, name: str) -> None:
        self.resource_type = resource_type
        self.name = name
        super().__init__(f"Conflict: {resource_type} '{name}' already exists.")


class BaseRestorer(ABC):
    """Abstract base for all domain restorers.

    Subclasses must implement :meth:`restore` which executes the full restore
    logic for a single backup domain and returns a summary dict.
    """

    def __init__(
        self,
        api_client: Any,
        storage_manager: Any,
        org_name: str,
        backup_path: str,
        dry_run: bool = False,
    ) -> None:
        """Initialise the restorer.

        Args:
            api_client: Authenticated GitHub API client instance.
            storage_manager: Storage manager used to access backup artefacts.
            org_name: GitHub organisation name that is being restored.
            backup_path: Absolute path to the root of the backup snapshot.
            dry_run: When *True* no mutating API calls are made; all write
                operations are only logged.
        """
        self.api_client = api_client
        self.storage_manager = storage_manager
        self.org_name = org_name
        self.backup_path = backup_path
        self.dry_run = dry_run
        self.logger: logging.Logger = setup_logger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def restore(self) -> dict:
        """Execute restore for this domain.

        Returns:
            A summary dict with at minimum the keys ``created``, ``skipped``
            and ``failed`` (integer counts).
        """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def load_json(self, *path_parts: str) -> Union[dict, list]:
        """Load a JSON file from the backup directory tree.

        *path_parts* are joined with :func:`os.path.join` relative to
        :attr:`backup_path`.

        Returns:
            Parsed JSON content (``dict`` or ``list``).  Returns an empty
            ``dict`` when the file does not exist (a warning is logged).
        """
        full_path = os.path.join(self.backup_path, *path_parts)
        try:
            with open(full_path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except FileNotFoundError:
            self.logger.warning("Backup file not found, skipping: %s", full_path)
            return {}

    def report_conflict(
        self,
        resource_type: str,
        name: str,
        existing: Any = None,
        incoming: Any = None,
    ) -> None:
        """Log a warning about a conflicting resource and raise
        :class:`ConflictError`.

        Args:
            resource_type: Human-readable type label (e.g. ``"repository"``).
            name: Identifier / name of the conflicting resource.
            existing: Optional current state of the resource for the log.
            incoming: Optional backup state of the resource for the log.

        Raises:
            ConflictError: Always raised after the warning is logged.
        """
        self.logger.warning(
            "Conflict detected — %s '%s' already exists. "
            "existing=%r  incoming=%r",
            resource_type,
            name,
            existing,
            incoming,
        )
        raise ConflictError(resource_type, name)

    def _format_author_note(self, login: str, created_at: str) -> str:
        """Return a Markdown block-quote crediting the original author.

        Args:
            login: GitHub username of the original author.
            created_at: ISO-8601 timestamp string of the original creation.

        Returns:
            A string of the form ``'> Originally by @{login} on {created_at}\\n\\n'``.
        """
        return f"> Originally by @{login} on {created_at}\n\n"
