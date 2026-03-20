"""
Repository restorer — recreates GitHub repositories from bare-mirror backups.
"""

from __future__ import annotations

import os
from typing import Any

import git
import requests

from .base_restorer import BaseRestorer, ConflictError


class RepositoryRestorer(BaseRestorer):
    """Restores GitHub repositories (metadata + git history) from backup."""

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def restore(self) -> dict:
        """Restore all repositories found in the backup.

        For each repository directory under
        ``backup_path/repositories/{org_name}/``:

        1. Load ``repo_metadata.json`` to obtain repository settings.
        2. Call :meth:`create_repo` — skip silently when the repo already
           exists (conflict is logged).
        3. Call :meth:`push_mirror` to push the full git history.

        Returns:
            ``{"created": N, "skipped": N, "failed": N}``
        """
        summary: dict[str, int] = {"created": 0, "skipped": 0, "failed": 0}

        repos_root = os.path.join(
            self.backup_path, "repositories", self.org_name
        )

        if not os.path.isdir(repos_root):
            self.logger.warning(
                "Repository backup directory not found: %s", repos_root
            )
            return summary

        for repo_name in os.listdir(repos_root):
            repo_dir = os.path.join(repos_root, repo_name)
            if not os.path.isdir(repo_dir):
                continue

            repo_meta = self.load_json(
                "repositories", self.org_name, repo_name, "repo_metadata.json"
            )

            if not repo_meta:
                self.logger.warning(
                    "repo_metadata.json missing or empty for %s — skipping.",
                    repo_name,
                )
                summary["skipped"] += 1
                continue

            # ── create repository ──────────────────────────────────────
            try:
                if not self.dry_run:
                    self.create_repo(repo_meta)
                else:
                    self.logger.info("[dry-run] Would create repo: %s", repo_name)
                summary["created"] += 1
            except ConflictError:
                summary["skipped"] += 1
            except Exception as exc:  # noqa: BLE001
                self.logger.error(
                    "Failed to create repository '%s': %s", repo_name, exc
                )
                summary["failed"] += 1
                continue

            # ── push git mirror ────────────────────────────────────────
            git_dir = os.path.join(repo_dir, f"{repo_name}.git")
            if os.path.isdir(git_dir):
                try:
                    if not self.dry_run:
                        self.push_mirror(repo_name, git_dir)
                    else:
                        self.logger.info(
                            "[dry-run] Would push mirror for: %s", repo_name
                        )
                except Exception as exc:  # noqa: BLE001
                    self.logger.error(
                        "Failed to push mirror for '%s': %s", repo_name, exc
                    )
                    summary["failed"] += 1
            else:
                self.logger.warning(
                    "Bare git directory not found for '%s': %s", repo_name, git_dir
                )

        return summary

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def create_repo(self, repo_meta: dict) -> dict:
        """Create a repository inside the organisation via the GitHub API.

        Args:
            repo_meta: Repository metadata dict (as stored in
                ``repo_metadata.json``).  The following keys are used:
                ``name``, ``description``, ``private``, ``has_issues``,
                ``has_projects``, ``has_wiki``.

        Returns:
            The GitHub API response dict for the newly created repository.

        Raises:
            ConflictError: When the repository already exists (HTTP 422).
            requests.exceptions.HTTPError: For other HTTP errors.
        """
        payload = {
            "name": repo_meta.get("name"),
            "description": repo_meta.get("description", ""),
            "private": repo_meta.get("private", False),
            "has_issues": repo_meta.get("has_issues", True),
            "has_projects": repo_meta.get("has_projects", True),
            "has_wiki": repo_meta.get("has_wiki", True),
        }

        try:
            response = self.api_client.post(
                f"/orgs/{self.org_name}/repos", json=payload
            )
            response.raise_for_status()
            created: dict = response.json()
            self.logger.info("Created repository: %s", created.get("full_name"))
            return created
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 422:
                self.report_conflict(
                    "repository",
                    str(payload.get("name")),
                    incoming=payload,
                )
            raise

    def push_mirror(self, repo_name: str, git_dir: str) -> None:
        """Push the bare mirror backup to the GitHub remote.

        Uses *GitPython* to push all refs from the local bare clone to the
        GitHub repository that was just created.

        Args:
            repo_name: Name of the repository (without org prefix).
            git_dir: Absolute path to the local bare git directory
                (e.g. ``…/my-repo.git``).

        Raises:
            git.exc.GitCommandError: On push failure.
        """
        token: str = self.api_client._token  # noqa: SLF001
        remote_url = (
            f"https://x-access-token:{token}@github.com"
            f"/{self.org_name}/{repo_name}.git"
        )

        self.logger.info(
            "Pushing mirror for '%s/%s' from %s",
            self.org_name,
            repo_name,
            git_dir,
        )
        repo = git.Repo(git_dir)
        repo.git.push("--mirror", remote_url)
        self.logger.info("Mirror push complete for '%s'.", repo_name)
