"""IssuesPRsRestorer — restores issues and pull requests from backup."""

from __future__ import annotations

import os
from typing import Any

import requests

from .base_restorer import BaseRestorer


class IssuesPRsRestorer(BaseRestorer):
    """Restores issues and pull requests from backup."""

    def restore(self) -> dict:
        """For each repo in backup, call restore_issues() then restore_prs().

        Returns:
            ``{"issues_created": N, "prs_created": N, "comments_created": N}``
        """
        summary: dict[str, int] = {
            "issues_created": 0,
            "prs_created": 0,
            "comments_created": 0,
        }

        for repo_name in self._get_repo_names():
            try:
                issues_count, comments_count = self.restore_issues(repo_name)
                summary["issues_created"] += issues_count
                summary["comments_created"] += comments_count
            except Exception as exc:  # noqa: BLE001
                self.logger.error(
                    "restore_issues failed for '%s': %s", repo_name, exc
                )

            try:
                prs_count, pr_comments_count = self.restore_prs(repo_name)
                summary["prs_created"] += prs_count
                summary["comments_created"] += pr_comments_count
            except Exception as exc:  # noqa: BLE001
                self.logger.error(
                    "restore_prs failed for '%s': %s", repo_name, exc
                )

        return summary

    def restore_issues(self, repo_name: str) -> tuple[int, int]:
        """Load issues_prs.json["issues"] and recreate each issue with comments.

        For each issue:
        - Prepend body with author note.
        - POST /repos/{org}/{repo}/issues with title, body, labels, milestone.
        - POST each comment to /repos/{org}/{repo}/issues/{num}/comments.

        Args:
            repo_name: Repository name (without org prefix).

        Returns:
            Tuple of (issues_created, comments_created).
        """
        data = self.load_json(
            "repositories", self.org_name, repo_name, "issues_prs.json"
        )
        issues: list[dict] = data.get("issues", [])
        issues_count = 0
        comments_count = 0

        for issue in issues:
            author_note = self._format_author_note(
                issue.get("user", {}).get("login", "unknown"),
                issue.get("created_at", ""),
            )
            body = author_note + (issue.get("body") or "")
            label_names = [lbl["name"] for lbl in issue.get("labels", [])]

            payload: dict[str, Any] = {
                "title": issue.get("title", ""),
                "body": body,
                "labels": label_names,
            }
            milestone = issue.get("milestone")
            if milestone and milestone.get("number") is not None:
                payload["milestone"] = milestone["number"]

            try:
                if self.dry_run:
                    self.logger.info(
                        "[dry-run] Would create issue '%s' in '%s'.",
                        issue.get("title"),
                        repo_name,
                    )
                    issues_count += 1
                    continue

                created = self.api_client.post(
                    f"/repos/{self.org_name}/{repo_name}/issues", payload
                )
                new_number = created.get("number") if isinstance(created, dict) else None
                self.logger.debug(
                    "Created issue #%s in '%s'.", new_number, repo_name
                )
                issues_count += 1

                if new_number:
                    for comment in issue.get("comments", []):
                        note = self._format_author_note(
                            comment.get("user", {}).get("login", "unknown"),
                            comment.get("created_at", ""),
                        )
                        comment_body = note + (comment.get("body") or "")
                        self.api_client.post(
                            f"/repos/{self.org_name}/{repo_name}"
                            f"/issues/{new_number}/comments",
                            {"body": comment_body},
                        )
                        comments_count += 1

            except Exception as exc:  # noqa: BLE001
                self.logger.error(
                    "Failed to create issue '%s' in '%s': %s",
                    issue.get("title"),
                    repo_name,
                    exc,
                )

        return issues_count, comments_count

    def restore_prs(self, repo_name: str) -> tuple[int, int]:
        """Load issues_prs.json["pull_requests"] and recreate each PR.

        For each PR:
        - Prepend body with author note.
        - POST /repos/{org}/{repo}/pulls with title, body, head, base, draft.
        - On 422: log warning and skip.

        Args:
            repo_name: Repository name (without org prefix).

        Returns:
            Tuple of (prs_created, comments_created).
        """
        data = self.load_json(
            "repositories", self.org_name, repo_name, "issues_prs.json"
        )
        prs: list[dict] = data.get("pull_requests", [])
        prs_count = 0
        comments_count = 0

        for pr in prs:
            author_note = self._format_author_note(
                pr.get("user", {}).get("login", "unknown"),
                pr.get("created_at", ""),
            )
            body = author_note + (pr.get("body") or "")

            # Support both flat fields and nested head/base objects.
            head_ref = pr.get("head_ref") or (
                pr.get("head", {}).get("ref", "") if isinstance(pr.get("head"), dict) else ""
            )
            base_ref = pr.get("base_ref") or (
                pr.get("base", {}).get("ref", "main") if isinstance(pr.get("base"), dict) else "main"
            )

            payload: dict[str, Any] = {
                "title": pr.get("title", ""),
                "body": body,
                "head": head_ref,
                "base": base_ref,
                "draft": pr.get("draft", False),
            }

            try:
                if self.dry_run:
                    self.logger.info(
                        "[dry-run] Would create PR '%s' in '%s'.",
                        pr.get("title"),
                        repo_name,
                    )
                    prs_count += 1
                    continue

                self.api_client.post(
                    f"/repos/{self.org_name}/{repo_name}/pulls", payload
                )
                prs_count += 1

            except requests.exceptions.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 422:
                    self.logger.warning(
                        "Skipping PR '%s' in '%s': head branch missing or PR already exists.",
                        pr.get("title"),
                        repo_name,
                    )
                else:
                    self.logger.error(
                        "Failed to create PR '%s' in '%s': %s",
                        pr.get("title"),
                        repo_name,
                        exc,
                    )
            except Exception as exc:  # noqa: BLE001
                self.logger.error(
                    "Failed to create PR '%s' in '%s': %s",
                    pr.get("title"),
                    repo_name,
                    exc,
                )

        return prs_count, comments_count

    def _get_repo_names(self) -> list[str]:
        """List subdirectories of backup_path/repositories/org_name/.

        Returns:
            Sorted list of repository name strings.
        """
        repos_root = os.path.join(self.backup_path, "repositories", self.org_name)
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
