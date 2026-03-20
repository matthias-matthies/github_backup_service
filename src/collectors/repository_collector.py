"""
Repository collector — clones and mirrors GitHub organisation repositories.
"""

import os
from typing import Any, List

import git

from .base_collector import BaseCollector


class RepositoryCollector(BaseCollector):
    """Collects repository metadata and clones/mirrors all org repositories.

    Args:
        api_client:      GitHub API client instance.
        storage_manager: Storage manager instance.
        org_name:        GitHub organisation name.
    """

    def collect(self) -> List[dict]:
        """Fetch all repositories for the organisation.

        Returns:
            List of repository metadata dicts.
        """
        self.logger.info("Collecting repositories for org: %s", self.org_name)
        repos = self._paginate(
            f"/orgs/{self.org_name}/repos",
            params={"type": "all"},
        )
        self.logger.info("Found %d repositories.", len(repos))
        return repos

    def clone_repository(self, repo: dict, dest_path: str) -> None:
        """Clone or mirror a single repository to *dest_path*.

        Attempts a bare mirror clone (``--mirror``) first.  If the target
        directory already exists the remote is fetched instead.

        Args:
            repo:      Repository metadata dict containing at least
                       ``"clone_url"`` and ``"name"``.
            dest_path: Filesystem path where the repository will be stored.
        """
        clone_url: str = repo["clone_url"]
        repo_name: str = repo["name"]

        if os.path.exists(dest_path):
            self.logger.info(
                "Repository '%s' already exists at '%s' — fetching updates.",
                repo_name,
                dest_path,
            )
            try:
                existing_repo = git.Repo(dest_path)
                existing_repo.remotes.origin.fetch()
                self.logger.info("Fetched updates for '%s'.", repo_name)
            except Exception as exc:  # noqa: BLE001
                self.logger.warning(
                    "Failed to fetch updates for '%s': %s", repo_name, exc
                )
            return

        self.logger.info("Cloning '%s' from %s …", repo_name, clone_url)
        try:
            git.Repo.clone_from(clone_url, dest_path, mirror=True)
            self.logger.info("Mirror-cloned '%s'.", repo_name)
        except git.GitCommandError as exc:
            self.logger.warning(
                "Mirror clone failed for '%s' (%s); falling back to regular clone.",
                repo_name,
                exc,
            )
            try:
                git.Repo.clone_from(clone_url, dest_path)
                self.logger.info("Regular-cloned '%s'.", repo_name)
            except git.GitCommandError as fallback_exc:
                self.logger.error(
                    "Could not clone '%s': %s", repo_name, fallback_exc
                )

    def collect_and_clone(self, dest_path: str) -> List[dict]:
        """Collect all repositories and clone each one under *dest_path*.

        Each repository is cloned into ``<dest_path>/<repo_name>``.

        Args:
            dest_path: Root directory for cloned repositories.

        Returns:
            List of repository metadata dicts (same as :meth:`collect`).
        """
        repos = self.collect()
        for repo in repos:
            repo_dest = os.path.join(dest_path, repo["name"])
            self.clone_repository(repo, repo_dest)
        return repos

    def validate(self, data: Any) -> bool:
        """Validate that *data* is a non-empty list.

        Args:
            data: Value returned by :meth:`collect`.

        Returns:
            ``True`` if *data* is a list with at least one element.
        """
        return isinstance(data, list) and len(data) > 0
