"""
Abstract base class for all GitHub backup collectors.

All concrete collectors inherit from BaseCollector and must implement
the ``collect`` and ``validate`` abstract methods.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, List, Optional

from ..utils.logger import setup_logger


class BaseCollector(ABC):
    """Abstract base class for GitHub data collectors.

    Args:
        api_client:      An instance of :class:`~src.api.GitHubAPIClient`.
        storage_manager: An instance of :class:`~src.storage.StorageManager`.
        org_name:        The GitHub organisation name to collect data for.
    """

    def __init__(self, api_client: Any, storage_manager: Any, org_name: str) -> None:
        self.api_client = api_client
        self.storage_manager = storage_manager
        self.org_name = org_name
        self.logger: logging.Logger = setup_logger(self.__class__.__name__)

    # ── Abstract interface ─────────────────────────────────────────────────

    @abstractmethod
    def collect(self, *args: Any, **kwargs: Any) -> Any:
        """Collect data from the GitHub API.

        Returns:
            Collected data (type depends on the concrete implementation).
        """

    @abstractmethod
    def validate(self, data: Any) -> bool:
        """Validate that *data* is not ``None`` and not empty.

        Args:
            data: The data structure returned by :meth:`collect`.

        Returns:
            ``True`` if the data is considered valid, ``False`` otherwise.
        """

    # ── Concrete helpers ───────────────────────────────────────────────────

    def save(self, data: Any, path: str, filename: str) -> None:
        """Serialise *data* to JSON and write it to ``<path>/<filename>``.

        Delegates to :meth:`~src.storage.StorageManager.write_json`.

        Args:
            data:     Python dict or list to persist.
            path:     Target directory path.
            filename: Output file name (e.g. ``"repos.json"``).
        """
        self.storage_manager.write_json(path, data, filename)

    def _paginate(self, endpoint: str, params: Optional[dict] = None) -> List[Any]:
        """Fetch all pages for a list endpoint via the API client.

        Delegates to :meth:`~src.api.GitHubAPIClient.paginate`.

        Args:
            endpoint: API path relative to the base URL.
            params:   Optional query-string parameters.

        Returns:
            A flat list of all items across all pages.
        """
        return self.api_client.paginate(endpoint, params=params)
