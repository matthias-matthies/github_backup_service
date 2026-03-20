"""
Issues & Pull Requests collector — issues, PRs, comments, and events.
"""

from typing import Any, Dict, List

from .base_collector import BaseCollector


class IssuesPRsCollector(BaseCollector):
    """Collects issues, pull requests, comments, and events for a repository.

    Args:
        api_client:      GitHub API client instance.
        storage_manager: Storage manager instance.
        org_name:        GitHub organisation name.
    """

    def collect(self, repo_name: str) -> Dict[str, List[dict]]:
        """Collect all issues and pull requests for *repo_name*.

        The GitHub Issues API returns pull requests as issues too, so pull
        requests are filtered out of the ``"issues"`` list by checking for
        the ``"pull_request"`` key.

        Args:
            repo_name: Name of the repository within the organisation.

        Returns:
            Dict with keys ``"issues"`` and ``"pull_requests"``.
        """
        self.logger.info(
            "Collecting issues & PRs for %s/%s", self.org_name, repo_name
        )
        base = f"/repos/{self.org_name}/{repo_name}"

        all_issues: List[dict] = self._paginate(
            f"{base}/issues", params={"state": "all"}
        )
        # Filter out entries that are actually pull requests.
        issues = [i for i in all_issues if "pull_request" not in i]

        pull_requests: List[dict] = self._paginate(
            f"{base}/pulls", params={"state": "all"}
        )

        self.logger.info(
            "%s/%s: %d issues, %d PRs",
            self.org_name,
            repo_name,
            len(issues),
            len(pull_requests),
        )
        return {"issues": issues, "pull_requests": pull_requests}

    def collect_issue_comments(
        self, repo_name: str, issue_number: int
    ) -> List[dict]:
        """Collect all comments for a specific issue.

        Args:
            repo_name:    Repository name.
            issue_number: Issue number.

        Returns:
            List of comment dicts.
        """
        return self._paginate(
            f"/repos/{self.org_name}/{repo_name}/issues/{issue_number}/comments"
        )

    def collect_pr_comments(
        self, repo_name: str, pr_number: int
    ) -> List[dict]:
        """Collect all review comments for a specific pull request.

        Args:
            repo_name: Repository name.
            pr_number: Pull-request number.

        Returns:
            List of comment dicts.
        """
        return self._paginate(
            f"/repos/{self.org_name}/{repo_name}/pulls/{pr_number}/comments"
        )

    def collect_events(
        self, repo_name: str, issue_number: int
    ) -> List[dict]:
        """Collect all events for a specific issue.

        Args:
            repo_name:    Repository name.
            issue_number: Issue number.

        Returns:
            List of event dicts.
        """
        return self._paginate(
            f"/repos/{self.org_name}/{repo_name}/issues/{issue_number}/events"
        )

    def validate(self, data: Any) -> bool:
        """Validate that *data* is a dict.

        Args:
            data: Value returned by :meth:`collect`.

        Returns:
            ``True`` if *data* is a dict (may be empty).
        """
        return isinstance(data, dict)
