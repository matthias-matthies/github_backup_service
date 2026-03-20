"""ReviewsRestorer — restores pull-request reviews and review comments from backup."""

from __future__ import annotations

import os
from typing import Any

from .base_restorer import BaseRestorer


# Mapping from GitHub review state values to the API event parameter.
_STATE_TO_EVENT: dict[str, str] = {
    "APPROVED": "APPROVE",
    "CHANGES_REQUESTED": "REQUEST_CHANGES",
    "COMMENTED": "COMMENT",
}


class ReviewsRestorer(BaseRestorer):
    """Restores pull-request reviews and review comments from backup."""

    def restore(self) -> dict:
        """For each repo, call restore_reviews(repo_name).

        Returns:
            ``{"reviews_created": N, "review_comments_created": N}``
        """
        summary: dict[str, int] = {
            "reviews_created": 0,
            "review_comments_created": 0,
        }

        for repo_name in self._get_repo_names():
            try:
                reviews, comments = self.restore_reviews(repo_name)
                summary["reviews_created"] += reviews
                summary["review_comments_created"] += comments
            except Exception as exc:  # noqa: BLE001
                self.logger.error(
                    "restore_reviews failed for '%s': %s", repo_name, exc
                )

        return summary

    def restore_reviews(self, repo_name: str) -> tuple[int, int]:
        """Load reviews.json and recreate reviews and inline comments per PR.

        reviews.json is a list of ``{pr_number, reviews, review_comments}``
        entries.  For each PR:

        - POST each review to ``/repos/{org}/{repo}/pulls/{pr}/reviews``.
        - POST each inline comment to ``/repos/{org}/{repo}/pulls/{pr}/comments``.

        PRs whose number is missing from the target are skipped with a warning.

        Args:
            repo_name: Repository name (without org prefix).

        Returns:
            Tuple of (reviews_created, review_comments_created).
        """
        data = self.load_json(
            "repositories", self.org_name, repo_name, "reviews.json"
        )
        # reviews.json may be a list or a dict with a "reviews" key.
        entries: list[dict] = data if isinstance(data, list) else data.get("reviews", [])

        reviews_count = 0
        comments_count = 0

        for entry in entries:
            pr_number = entry.get("pr_number")
            if pr_number is None:
                self.logger.warning(
                    "reviews.json entry missing pr_number in '%s', skipping.", repo_name
                )
                continue

            # ── Reviews ────────────────────────────────────────────────────
            for review in entry.get("reviews", []):
                author_note = self._format_author_note(
                    review.get("user", {}).get("login", "unknown"),
                    review.get("submitted_at", ""),
                )
                body = author_note + (review.get("body") or "")
                state: str = review.get("state", "COMMENTED").upper()
                event = _STATE_TO_EVENT.get(state, "COMMENT")

                payload: dict[str, Any] = {
                    "body": body,
                    "event": event,
                }

                try:
                    if self.dry_run:
                        self.logger.info(
                            "[dry-run] Would create review on PR #%s in '%s'.",
                            pr_number,
                            repo_name,
                        )
                        reviews_count += 1
                        continue

                    self.api_client.post(
                        f"/repos/{self.org_name}/{repo_name}"
                        f"/pulls/{pr_number}/reviews",
                        payload,
                    )
                    reviews_count += 1

                except Exception as exc:  # noqa: BLE001
                    self.logger.error(
                        "Failed to create review on PR #%s in '%s': %s",
                        pr_number,
                        repo_name,
                        exc,
                    )

            # ── Inline review comments ──────────────────────────────────────
            for rc in entry.get("review_comments", []):
                author_note = self._format_author_note(
                    rc.get("user", {}).get("login", "unknown"),
                    rc.get("created_at", ""),
                )
                body = author_note + (rc.get("body") or "")

                rc_payload: dict[str, Any] = {
                    "body": body,
                    "path": rc.get("path", ""),
                }
                # Prefer line/side (new API) over position (deprecated).
                if rc.get("line") is not None:
                    rc_payload["line"] = rc["line"]
                    rc_payload["side"] = rc.get("side", "RIGHT")
                elif rc.get("position") is not None:
                    rc_payload["position"] = rc["position"]

                # commit_id is required for the PR comments endpoint.
                if rc.get("commit_id"):
                    rc_payload["commit_id"] = rc["commit_id"]

                try:
                    if self.dry_run:
                        self.logger.info(
                            "[dry-run] Would create review comment on PR #%s in '%s'.",
                            pr_number,
                            repo_name,
                        )
                        comments_count += 1
                        continue

                    self.api_client.post(
                        f"/repos/{self.org_name}/{repo_name}"
                        f"/pulls/{pr_number}/comments",
                        rc_payload,
                    )
                    comments_count += 1

                except Exception as exc:  # noqa: BLE001
                    self.logger.error(
                        "Failed to create review comment on PR #%s in '%s': %s",
                        pr_number,
                        repo_name,
                        exc,
                    )

        return reviews_count, comments_count

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
