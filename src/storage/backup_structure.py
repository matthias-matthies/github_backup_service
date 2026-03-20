"""Defines the canonical directory layout for a GitHub organisation backup."""

import os


class BackupStructure:
    """
    Describes and creates the directory hierarchy used when storing backups.

    Layout::

        <base_path>/
            organizations/<org_name>/
            repositories/<org_name>/<repo_name>/
            metadata/<org_name>/<category>/
            assets/<org_name>/<repo_name>/
    """

    def __init__(self, base_path: str) -> None:
        """
        Initialise the BackupStructure.

        Args:
            base_path: Root directory under which all backup data is stored.
        """
        self.base_path = base_path

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def org_path(self, org_name: str) -> str:
        """Return the directory path for an organisation's top-level data.

        Args:
            org_name: GitHub organisation login.

        Returns:
            Absolute (or relative) path string.
        """
        return os.path.join(self.base_path, "organizations", org_name)

    def repo_path(self, org_name: str, repo_name: str) -> str:
        """Return the directory path for a specific repository backup.

        Args:
            org_name: GitHub organisation login.
            repo_name: Repository name.

        Returns:
            Path string for the repository backup directory.
        """
        return os.path.join(self.base_path, "repositories", org_name, repo_name)

    def metadata_path(self, org_name: str, category: str) -> str:
        """Return the directory path for a metadata category of an organisation.

        Args:
            org_name: GitHub organisation login.
            category: Metadata category (e.g. ``"members"``, ``"teams"``).

        Returns:
            Path string for the metadata directory.
        """
        return os.path.join(self.base_path, "metadata", org_name, category)

    def assets_path(self, org_name: str, repo_name: str) -> str:
        """Return the directory path for binary assets of a repository.

        Args:
            org_name: GitHub organisation login.
            repo_name: Repository name.

        Returns:
            Path string for the assets directory.
        """
        return os.path.join(self.base_path, "assets", org_name, repo_name)

    # ------------------------------------------------------------------
    # Directory management
    # ------------------------------------------------------------------

    def ensure_directories(self, org_name: str, repo_names: list[str]) -> None:
        """
        Create all backup directories for *org_name* and each repository in *repo_names*.

        Existing directories are left untouched (``exist_ok=True``).

        Args:
            org_name: GitHub organisation login.
            repo_names: List of repository names belonging to the organisation.
        """
        # Organisation-level directory
        os.makedirs(self.org_path(org_name), exist_ok=True)

        for repo_name in repo_names:
            os.makedirs(self.repo_path(org_name, repo_name), exist_ok=True)
            os.makedirs(self.assets_path(org_name, repo_name), exist_ok=True)

        # Common metadata categories
        for category in ("members", "teams", "settings", "webhooks"):
            os.makedirs(self.metadata_path(org_name, category), exist_ok=True)
