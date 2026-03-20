"""WorkflowsRestorer — restores GitHub Actions workflow definitions from backup."""

from __future__ import annotations

import base64
import os
from typing import Any

import requests

from .base_restorer import BaseRestorer


class WorkflowsRestorer(BaseRestorer):
    """Restores GitHub Actions workflow YAML files from backup."""

    def restore(self) -> dict:
        """For each repo, call restore_workflows(repo_name).

        Returns:
            ``{"workflows_restored": N}``
        """
        summary: dict[str, int] = {"workflows_restored": 0}

        for repo_name in self._get_repo_names():
            try:
                count = self.restore_workflows(repo_name)
                summary["workflows_restored"] += count
            except Exception as exc:  # noqa: BLE001
                self.logger.error(
                    "restore_workflows failed for '%s': %s", repo_name, exc
                )

        return summary

    def restore_workflows(self, repo_name: str) -> int:
        """Load workflows.json and commit each workflow YAML to the repository.

        For each workflow that has a ``path`` field:

        1. Look up the YAML content stored in workflows.json under the path key.
        2. GET /repos/{org}/{repo}/contents/{path} to check for an existing file
           (to obtain its SHA for an update).
        3. PUT /repos/{org}/{repo}/contents/{path} with base64-encoded content.

        Args:
            repo_name: Repository name (without org prefix).

        Returns:
            Number of workflow files successfully committed.
        """
        data = self.load_json(
            "repositories", self.org_name, repo_name, "workflows.json"
        )
        workflows: list[dict] = data.get("workflows", [])
        # Content map: path → YAML string
        content_map: dict[str, str] = data.get("content", {})

        restored = 0

        for workflow in workflows:
            wf_path: str = workflow.get("path", "")
            if not wf_path:
                self.logger.debug(
                    "Workflow entry has no path in '%s', skipping.", repo_name
                )
                continue

            yaml_content: str | None = content_map.get(wf_path)
            if yaml_content is None:
                self.logger.warning(
                    "No content found for workflow '%s' in '%s', skipping.",
                    wf_path,
                    repo_name,
                )
                continue

            encoded = base64.b64encode(yaml_content.encode("utf-8")).decode("ascii")
            payload: dict[str, Any] = {
                "message": f"restore: workflow {wf_path}",
                "content": encoded,
            }

            # Check if the file already exists so we can supply the SHA.
            if not self.dry_run:
                try:
                    existing = self.api_client.get(
                        f"/repos/{self.org_name}/{repo_name}/contents/{wf_path}"
                    )
                    if isinstance(existing, dict) and existing.get("sha"):
                        payload["sha"] = existing["sha"]
                except requests.exceptions.HTTPError as exc:
                    if exc.response is None or exc.response.status_code != 404:
                        self.logger.warning(
                            "Could not check existing workflow '%s' in '%s': %s",
                            wf_path,
                            repo_name,
                            exc,
                        )
                except Exception:  # noqa: BLE001
                    pass  # Treat any other error as file-not-found and proceed.

            try:
                if self.dry_run:
                    self.logger.info(
                        "[dry-run] Would restore workflow '%s' in '%s'.",
                        wf_path,
                        repo_name,
                    )
                    restored += 1
                    continue

                self.api_client.put(
                    f"/repos/{self.org_name}/{repo_name}/contents/{wf_path}",
                    payload,
                )
                self.logger.debug(
                    "Restored workflow '%s' in '%s'.", wf_path, repo_name
                )
                restored += 1

            except Exception as exc:  # noqa: BLE001
                self.logger.error(
                    "Failed to restore workflow '%s' in '%s': %s",
                    wf_path,
                    repo_name,
                    exc,
                )

        return restored

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
