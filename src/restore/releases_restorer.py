"""ReleasesRestorer — restores GitHub releases and their assets from backup."""

from __future__ import annotations

import os
from typing import Any

import requests

from .base_restorer import BaseRestorer, ConflictError


class ReleasesRestorer(BaseRestorer):
    """Restores GitHub releases and release assets from backup."""

    def restore(self) -> dict:
        """For each repo, call restore_releases(repo_name).

        Returns:
            ``{"releases_created": N, "assets_uploaded": N}``
        """
        summary: dict[str, int] = {"releases_created": 0, "assets_uploaded": 0}

        for repo_name in self._get_repo_names():
            try:
                releases, assets = self.restore_releases(repo_name)
                summary["releases_created"] += releases
                summary["assets_uploaded"] += assets
            except Exception as exc:  # noqa: BLE001
                self.logger.error(
                    "restore_releases failed for '%s': %s", repo_name, exc
                )

        return summary

    def restore_releases(self, repo_name: str) -> tuple[int, int]:
        """Load releases.json and recreate each release with its assets.

        For each release:
        - POST /repos/{org}/{repo}/releases.
        - Upload each matching asset via :meth:`upload_asset`.
        - On 422: call report_conflict().

        Args:
            repo_name: Repository name (without org prefix).

        Returns:
            Tuple of (releases_created, assets_uploaded).
        """
        data = self.load_json(
            "repositories", self.org_name, repo_name, "releases.json"
        )
        releases: list[dict] = data.get("releases", [])
        assets_manifest: list[dict] = data.get("assets_manifest", [])
        releases_count = 0
        assets_count = 0

        for release in releases:
            tag_name: str = release.get("tag_name", "")
            payload: dict[str, Any] = {
                "tag_name": tag_name,
                "name": release.get("name", tag_name),
                "body": release.get("body", ""),
                "draft": release.get("draft", False),
                "prerelease": release.get("prerelease", False),
                "target_commitish": release.get("target_commitish", "main"),
            }

            try:
                if self.dry_run:
                    self.logger.info(
                        "[dry-run] Would create release '%s' in '%s'.",
                        tag_name,
                        repo_name,
                    )
                    releases_count += 1
                    continue

                created = self.api_client.post(
                    f"/repos/{self.org_name}/{repo_name}/releases", payload
                )
                release_id: int = (
                    created.get("id") if isinstance(created, dict) else None
                )
                self.logger.debug(
                    "Created release '%s' (id=%s) in '%s'.",
                    tag_name,
                    release_id,
                    repo_name,
                )
                releases_count += 1

            except requests.exceptions.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 422:
                    self.report_conflict("release", tag_name, incoming=payload)
                else:
                    self.logger.error(
                        "Failed to create release '%s' in '%s': %s",
                        tag_name,
                        repo_name,
                        exc,
                    )
                continue
            except ConflictError:
                continue

            # ── Upload assets for this release ──────────────────────────────
            if release_id:
                matching_assets = [
                    a for a in assets_manifest if a.get("tag_name") == tag_name
                ]
                for asset_info in matching_assets:
                    if self.upload_asset(release_id, repo_name, asset_info):
                        assets_count += 1

        return releases_count, assets_count

    def upload_asset(
        self, release_id: int, repo_name: str, asset_info: dict
    ) -> bool:
        """Upload a release asset file to GitHub.

        Args:
            release_id: Numeric ID of the newly created GitHub release.
            repo_name: Repository name (without org prefix).
            asset_info: Dict with keys ``name``, ``path`` (local file path),
                and ``size``.

        Returns:
            ``True`` on success, ``False`` on any failure.
        """
        asset_name: str = asset_info.get("name", "")
        local_path: str = asset_info.get("path", "")

        if not os.path.isfile(local_path):
            self.logger.error(
                "Asset file not found, cannot upload '%s': %s",
                asset_name,
                local_path,
            )
            return False

        upload_url = (
            f"https://uploads.github.com/repos/{self.org_name}/{repo_name}"
            f"/releases/{release_id}/assets?name={asset_name}"
        )

        if self.dry_run:
            self.logger.info(
                "[dry-run] Would upload asset '%s' to release %s.",
                asset_name,
                release_id,
            )
            return True

        try:
            with open(local_path, "rb") as fh:
                resp = requests.post(
                    upload_url,
                    headers={
                        "Authorization": f"token {self.api_client._token}",  # noqa: SLF001
                        "Content-Type": "application/octet-stream",
                    },
                    data=fh,
                    stream=True,
                    timeout=120,
                )
            resp.raise_for_status()
            self.logger.debug(
                "Uploaded asset '%s' to release %s.", asset_name, release_id
            )
            return True
        except Exception as exc:  # noqa: BLE001
            self.logger.error(
                "Failed to upload asset '%s' to release %s: %s",
                asset_name,
                release_id,
                exc,
            )
            return False

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
