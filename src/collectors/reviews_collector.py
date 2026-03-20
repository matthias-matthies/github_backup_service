"""
Reviews collector — pull-request reviews and review comments.
"""

from typing import Any, Dict, List

from .base_collector import BaseCollector


class ReviewsCollector(BaseCollector):
    """Collects pull-request reviews and review comments.

    Args:
        api_client:      GitHub API client instance.
        storage_manager: Storage manager instance.
        org_name:        GitHub organisation name.
    """

    def collect(self, repo_name: str, pr_number: int) -> Dict[str, List[dict]]:
        """Collect reviews and review comments for a single pull request.

        Args:
            repo_name: Repository name within the organisation.
            pr_number: Pull-request number.

        Returns:
            Dict with keys ``"reviews"`` and ``"review_comments"``.
        """
        self.logger.info(
            "Collecting reviews for %s/%s PR #%d",
            self.org_name,
            repo_name,
            pr_number,
        )
        base = f"/repos/{self.org_name}/{repo_name}/pulls/{pr_number}"

        reviews: List[dict] = self._paginate(f"{base}/reviews")
        review_comments: List[dict] = self._paginate(f"{base}/comments")

        return {"reviews": reviews, "review_comments": review_comments}

    def collect_all_pr_reviews(
        self, repo_name: str, prs: List[dict]
    ) -> List[Dict[str, Any]]:
        """Collect reviews for every pull request in *prs*.

        Args:
            repo_name: Repository name within the organisation.
            prs:       List of pull-request metadata dicts, each containing
                       at least the ``"number"`` key.

        Returns:
            List of dicts, each containing:

            * ``"pr_number"``     — the PR number
            * ``"reviews"``       — list of review dicts
            * ``"review_comments"`` — list of review-comment dicts
        """
        results: List[Dict[str, Any]] = []
        for pr in prs:
            pr_number: int = pr["number"]
            review_data = self.collect(repo_name, pr_number)
            results.append(
                {
                    "pr_number": pr_number,
                    "reviews": review_data["reviews"],
                    "review_comments": review_data["review_comments"],
                }
            )
        return results

    def validate(self, data: Any) -> bool:
        """Validate that *data* is a dict.

        Args:
            data: Value returned by :meth:`collect`.

        Returns:
            ``True`` if *data* is a dict.
        """
        return isinstance(data, dict)
