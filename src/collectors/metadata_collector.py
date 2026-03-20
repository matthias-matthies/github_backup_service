"""
Metadata collector — members, teams, labels, collaborators, and repo metadata.
"""

from typing import Any, Dict, List

import requests

from .base_collector import BaseCollector


class MetadataCollector(BaseCollector):
    """Collects organisation- and repository-level metadata.

    Args:
        api_client:      GitHub API client instance.
        storage_manager: Storage manager instance.
        org_name:        GitHub organisation name.
    """

    def collect(self) -> Dict[str, List[dict]]:
        """Collect organisation-level metadata.

        Returns:
            Dict with keys ``"members"``, ``"teams"``, ``"labels"``, and
            ``"outside_collaborators"``.
        """
        self.logger.info("Collecting org metadata for: %s", self.org_name)

        members = self._paginate(f"/orgs/{self.org_name}/members")
        teams = self._paginate(f"/orgs/{self.org_name}/teams")
        outside_collaborators = self._paginate(
            f"/orgs/{self.org_name}/outside_collaborators"
        )

        # Org-level labels endpoint may not exist (404) — handle gracefully.
        try:
            labels: List[dict] = self._paginate(f"/orgs/{self.org_name}/labels")
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status == 404:
                self.logger.debug(
                    "Org-level labels endpoint returned 404 — skipping."
                )
                labels = []
            else:
                raise

        return {
            "members": members,
            "teams": teams,
            "labels": labels,
            "outside_collaborators": outside_collaborators,
        }

    def collect_repo_metadata(self, repo_name: str) -> Dict[str, Any]:
        """Collect metadata for a specific repository.

        Args:
            repo_name: Name of the repository within the organisation.

        Returns:
            Dict with keys ``"labels"``, ``"milestones"``, ``"topics"``, and
            ``"collaborators"``.
        """
        self.logger.info(
            "Collecting repo metadata for %s/%s", self.org_name, repo_name
        )
        base = f"/repos/{self.org_name}/{repo_name}"

        labels = self._paginate(f"{base}/labels")
        milestones = self._paginate(f"{base}/milestones", params={"state": "all"})
        topics: Any = self.api_client.get(f"{base}/topics")
        collaborators = self._paginate(f"{base}/collaborators")

        return {
            "labels": labels,
            "milestones": milestones,
            "topics": topics,
            "collaborators": collaborators,
        }

    def validate(self, data: Any) -> bool:
        """Validate that *data* is a dict with at least one non-empty value.

        Args:
            data: Value returned by :meth:`collect` or
                  :meth:`collect_repo_metadata`.

        Returns:
            ``True`` if *data* is a dict that contains at least one key whose
            value is truthy (non-empty).
        """
        if not isinstance(data, dict):
            return False
        return any(bool(v) for v in data.values())
