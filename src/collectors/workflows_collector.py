"""
Workflows collector — GitHub Actions workflows, runs, artifacts, and workflow files.
"""

import base64
from typing import Any, Dict, List

from .base_collector import BaseCollector


class WorkflowsCollector(BaseCollector):
    """Collects GitHub Actions workflows, runs, and artifact metadata.

    Args:
        api_client:      GitHub API client instance.
        storage_manager: Storage manager instance.
        org_name:        GitHub organisation name.
    """

    def collect(self, repo_name: str) -> Dict[str, Any]:
        """Collect workflows, runs, and artifact metadata for *repo_name*.

        The GitHub Actions API wraps list results in envelope keys
        (``"workflows"``, ``"workflow_runs"``, ``"artifacts"``).  This
        method unwraps those keys automatically.

        Args:
            repo_name: Repository name within the organisation.

        Returns:
            Dict with keys ``"workflows"``, ``"runs"``, and
            ``"artifacts_metadata"``.
        """
        self.logger.info(
            "Collecting workflows for %s/%s", self.org_name, repo_name
        )
        base = f"/repos/{self.org_name}/{repo_name}/actions"

        # Workflows — single-page envelope response
        workflows_resp: Any = self.api_client.get(f"{base}/workflows")
        workflows: List[dict] = (
            workflows_resp.get("workflows", [])
            if isinstance(workflows_resp, dict)
            else workflows_resp
        )

        # Runs — paginated, each page is an envelope dict
        runs_pages: List[Any] = self._paginate(f"{base}/runs")
        runs: List[dict] = []
        for page in runs_pages:
            if isinstance(page, dict):
                runs.extend(page.get("workflow_runs", []))
            elif isinstance(page, list):
                runs.extend(page)

        # Artifacts metadata — single-page envelope response
        artifacts_resp: Any = self.api_client.get(f"{base}/artifacts")
        artifacts_metadata: List[dict] = (
            artifacts_resp.get("artifacts", [])
            if isinstance(artifacts_resp, dict)
            else artifacts_resp
        )

        self.logger.info(
            "%s/%s: %d workflow(s), %d run(s), %d artifact(s).",
            self.org_name,
            repo_name,
            len(workflows),
            len(runs),
            len(artifacts_metadata),
        )
        return {
            "workflows": workflows,
            "runs": runs,
            "artifacts_metadata": artifacts_metadata,
        }

    def collect_workflow_file(self, repo_name: str, workflow_path: str) -> str:
        """Fetch and decode the YAML source of a workflow file.

        Uses the Contents API which returns base64-encoded file content.

        Args:
            repo_name:     Repository name within the organisation.
            workflow_path: Path to the workflow file relative to the repo
                           root, e.g. ``".github/workflows/ci.yml"``.

        Returns:
            Decoded UTF-8 string containing the workflow YAML.
        """
        self.logger.info(
            "Fetching workflow file '%s' from %s/%s",
            workflow_path,
            self.org_name,
            repo_name,
        )
        response: Any = self.api_client.get(
            f"/repos/{self.org_name}/{repo_name}/contents/{workflow_path}"
        )
        encoded_content: str = response.get("content", "")
        # GitHub adds newlines inside the base64 payload — strip them.
        decoded_bytes = base64.b64decode(encoded_content.replace("\n", ""))
        return decoded_bytes.decode("utf-8")

    def validate(self, data: Any) -> bool:
        """Validate that *data* is a dict.

        Args:
            data: Value returned by :meth:`collect`.

        Returns:
            ``True`` if *data* is a dict.
        """
        return isinstance(data, dict)
