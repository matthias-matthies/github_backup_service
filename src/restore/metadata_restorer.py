"""
Metadata restorer — recreates org-level labels, teams, members and per-repo
labels/milestones from backup.
"""

from __future__ import annotations

import os
from typing import Any

import requests

from .base_restorer import BaseRestorer, ConflictError


class MetadataRestorer(BaseRestorer):
    """Restores organisation and repository metadata from backup."""

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def restore(self) -> dict:
        """Run all metadata restores in order.

        1. :meth:`restore_org_labels`
        2. :meth:`restore_teams`
        3. :meth:`restore_members`
        4. For every repository: :meth:`restore_repo_labels` and
           :meth:`restore_milestones`

        Returns:
            A summary dict with keys: ``org_labels``, ``teams``,
            ``members``, ``repo_labels``, ``milestones``, ``failed``.
        """
        summary: dict[str, int] = {
            "org_labels": 0,
            "teams": 0,
            "members": 0,
            "repo_labels": 0,
            "milestones": 0,
            "failed": 0,
        }

        # org-level metadata
        try:
            summary["org_labels"] = self.restore_org_labels()
        except Exception as exc:  # noqa: BLE001
            self.logger.error("restore_org_labels failed: %s", exc)
            summary["failed"] += 1

        try:
            summary["teams"] = self.restore_teams()
        except Exception as exc:  # noqa: BLE001
            self.logger.error("restore_teams failed: %s", exc)
            summary["failed"] += 1

        try:
            summary["members"] = self.restore_members()
        except Exception as exc:  # noqa: BLE001
            self.logger.error("restore_members failed: %s", exc)
            summary["failed"] += 1

        # per-repo metadata
        for repo_name in self._get_repo_names():
            try:
                summary["repo_labels"] += self.restore_repo_labels(repo_name)
            except Exception as exc:  # noqa: BLE001
                self.logger.error(
                    "restore_repo_labels failed for '%s': %s", repo_name, exc
                )
                summary["failed"] += 1

            try:
                summary["milestones"] += self.restore_milestones(repo_name)
            except Exception as exc:  # noqa: BLE001
                self.logger.error(
                    "restore_milestones failed for '%s': %s", repo_name, exc
                )
                summary["failed"] += 1

        return summary

    # ------------------------------------------------------------------
    # Org-level restorers
    # ------------------------------------------------------------------

    def restore_org_labels(self) -> int:
        """Restore organisation-level labels from ``metadata.json``.

        Returns:
            Number of labels created.

        Raises:
            ConflictError: When a label already exists (HTTP 422).
        """
        metadata = self.load_json("metadata.json")
        labels: list[dict] = metadata.get("labels", [])
        created = 0

        for label in labels:
            name: str = label.get("name", "")
            payload = {
                "name": name,
                "color": label.get("color", "ffffff"),
                "description": label.get("description", ""),
            }
            try:
                if self.dry_run:
                    self.logger.info("[dry-run] Would create org label: %s", name)
                    created += 1
                    continue
                response = self.api_client.post(
                    f"/orgs/{self.org_name}/labels", json=payload
                )
                response.raise_for_status()
                self.logger.debug("Created org label: %s", name)
                created += 1
            except requests.exceptions.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 422:
                    self.report_conflict("org_label", name, incoming=payload)
                else:
                    self.logger.error(
                        "Failed to create org label '%s': %s", name, exc
                    )

        return created

    def restore_teams(self) -> int:
        """Restore organisation teams and their memberships from ``metadata.json``.

        Returns:
            Number of teams created.

        Raises:
            ConflictError: When a team already exists (HTTP 422).
        """
        metadata = self.load_json("metadata.json")
        teams: list[dict] = metadata.get("teams", [])
        created = 0

        for team in teams:
            team_name: str = team.get("name", "")
            team_slug: str = team.get("slug", team_name.lower().replace(" ", "-"))
            payload = {
                "name": team_name,
                "description": team.get("description", ""),
                "privacy": team.get("privacy", "secret"),
                "permission": team.get("permission", "pull"),
            }

            try:
                if self.dry_run:
                    self.logger.info("[dry-run] Would create team: %s", team_name)
                    created += 1
                else:
                    response = self.api_client.post(
                        f"/orgs/{self.org_name}/teams", json=payload
                    )
                    response.raise_for_status()
                    self.logger.debug("Created team: %s", team_name)
                    created += 1
            except requests.exceptions.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 422:
                    self.report_conflict("team", team_name, incoming=payload)
                else:
                    self.logger.error(
                        "Failed to create team '%s': %s", team_name, exc
                    )
                    continue

            # add members to team
            for member in team.get("members", []):
                username: str = (
                    member if isinstance(member, str) else member.get("login", "")
                )
                if not username:
                    continue
                try:
                    if not self.dry_run:
                        mem_resp = self.api_client.put(
                            f"/orgs/{self.org_name}/teams/{team_slug}"
                            f"/memberships/{username}",
                            json={"role": "member"},
                        )
                        mem_resp.raise_for_status()
                        self.logger.debug(
                            "Added '%s' to team '%s'.", username, team_name
                        )
                    else:
                        self.logger.info(
                            "[dry-run] Would add '%s' to team '%s'.",
                            username,
                            team_name,
                        )
                except Exception as mem_exc:  # noqa: BLE001
                    self.logger.warning(
                        "Failed to add '%s' to team '%s': %s",
                        username,
                        team_name,
                        mem_exc,
                    )

        return created

    def restore_members(self) -> int:
        """Invite organisation members listed in ``metadata.json``.

        Note:
            GitHub membership invitations require acceptance by the invitee.
            A warning is logged to remind operators of this.

        Returns:
            Number of membership invitations sent.
        """
        metadata = self.load_json("metadata.json")
        members: list[dict] = metadata.get("members", [])
        invited = 0

        self.logger.warning(
            "Restoring org members sends *invitations* — each user must "
            "accept before they are active members of '%s'.",
            self.org_name,
        )

        for member in members:
            login: str = (
                member if isinstance(member, str) else member.get("login", "")
            )
            if not login:
                continue
            try:
                if self.dry_run:
                    self.logger.info("[dry-run] Would invite member: %s", login)
                    invited += 1
                    continue
                response = self.api_client.put(
                    f"/orgs/{self.org_name}/memberships/{login}",
                    json={"role": "member"},
                )
                response.raise_for_status()
                self.logger.debug("Invited member: %s", login)
                invited += 1
            except Exception as exc:  # noqa: BLE001
                self.logger.error("Failed to invite member '%s': %s", login, exc)

        return invited

    # ------------------------------------------------------------------
    # Per-repo restorers
    # ------------------------------------------------------------------

    def restore_repo_labels(self, repo_name: str) -> int:
        """Restore labels for a single repository.

        Labels that already exist (HTTP 422) are silently skipped because
        GitHub auto-creates default labels on new repositories.

        Args:
            repo_name: Repository name (without org prefix).

        Returns:
            Number of labels created.
        """
        repo_meta = self.load_json(
            "repositories", self.org_name, repo_name, "repo_metadata.json"
        )
        labels: list[dict] = repo_meta.get("labels", [])
        created = 0

        for label in labels:
            name: str = label.get("name", "")
            payload = {
                "name": name,
                "color": label.get("color", "ffffff"),
                "description": label.get("description", ""),
            }
            try:
                if self.dry_run:
                    self.logger.info(
                        "[dry-run] Would create label '%s' in repo '%s'.",
                        name,
                        repo_name,
                    )
                    created += 1
                    continue
                response = self.api_client.post(
                    f"/repos/{self.org_name}/{repo_name}/labels", json=payload
                )
                response.raise_for_status()
                created += 1
            except requests.exceptions.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 422:
                    # Label already exists — likely auto-created by GitHub.
                    self.logger.debug(
                        "Label '%s' already exists in '%s', skipping.",
                        name,
                        repo_name,
                    )
                else:
                    self.logger.error(
                        "Failed to create label '%s' in '%s': %s",
                        name,
                        repo_name,
                        exc,
                    )

        return created

    def restore_milestones(self, repo_name: str) -> int:
        """Restore milestones for a single repository.

        Args:
            repo_name: Repository name (without org prefix).

        Returns:
            Number of milestones created.

        Raises:
            ConflictError: When a milestone already exists (HTTP 422).
        """
        repo_meta = self.load_json(
            "repositories", self.org_name, repo_name, "repo_metadata.json"
        )
        milestones: list[dict] = repo_meta.get("milestones", [])
        created = 0

        for ms in milestones:
            title: str = ms.get("title", "")
            payload: dict[str, Any] = {
                "title": title,
                "state": ms.get("state", "open"),
                "description": ms.get("description", ""),
            }
            if ms.get("due_on"):
                payload["due_on"] = ms["due_on"]

            try:
                if self.dry_run:
                    self.logger.info(
                        "[dry-run] Would create milestone '%s' in '%s'.",
                        title,
                        repo_name,
                    )
                    created += 1
                    continue
                response = self.api_client.post(
                    f"/repos/{self.org_name}/{repo_name}/milestones",
                    json=payload,
                )
                response.raise_for_status()
                self.logger.debug(
                    "Created milestone '%s' in '%s'.", title, repo_name
                )
                created += 1
            except requests.exceptions.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 422:
                    self.report_conflict("milestone", title, incoming=payload)
                else:
                    self.logger.error(
                        "Failed to create milestone '%s' in '%s': %s",
                        title,
                        repo_name,
                        exc,
                    )

        return created

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_repo_names(self) -> list[str]:
        """Return the names of all repository directories in the backup.

        Returns:
            Sorted list of repository name strings.
        """
        repos_root = os.path.join(
            self.backup_path, "repositories", self.org_name
        )
        if not os.path.isdir(repos_root):
            self.logger.warning(
                "Repository backup directory not found: %s", repos_root
            )
            return []
        return sorted(
            entry
            for entry in os.listdir(repos_root)
            if os.path.isdir(os.path.join(repos_root, entry))
        )
