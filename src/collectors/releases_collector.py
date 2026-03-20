"""
Releases collector — release metadata and binary asset download with checksums.
"""

import os
from typing import Any, Dict, List

import requests

from .base_collector import BaseCollector
from ..utils.helpers import compute_checksum


class ReleasesCollector(BaseCollector):
    """Collects releases and downloads their binary assets.

    Args:
        api_client:      GitHub API client instance.
        storage_manager: Storage manager instance.
        org_name:        GitHub organisation name.
    """

    def collect(self, repo_name: str) -> List[dict]:
        """Fetch all releases for *repo_name*.

        Args:
            repo_name: Repository name within the organisation.

        Returns:
            List of release metadata dicts.
        """
        self.logger.info(
            "Collecting releases for %s/%s", self.org_name, repo_name
        )
        releases = self._paginate(f"/repos/{self.org_name}/{repo_name}/releases")
        self.logger.info(
            "Found %d release(s) for %s/%s.", len(releases), self.org_name, repo_name
        )
        return releases

    def download_assets(
        self, release: dict, dest_path: str
    ) -> List[Dict[str, Any]]:
        """Download all binary assets attached to *release*.

        Each asset is streamed to ``<dest_path>/<asset_name>`` and its
        SHA-256 checksum is computed after download.

        Args:
            release:   Release metadata dict containing an ``"assets"`` list.
            dest_path: Directory to write downloaded files into.

        Returns:
            List of dicts, each containing:

            * ``"name"``     — asset file name
            * ``"size"``     — expected size in bytes (from API metadata)
            * ``"checksum"`` — SHA-256 hex digest of the downloaded file
            * ``"path"``     — absolute path to the saved file
        """
        os.makedirs(dest_path, exist_ok=True)
        manifest: List[Dict[str, Any]] = []

        for asset in release.get("assets", []):
            asset_name: str = asset["name"]
            asset_url: str = asset["browser_download_url"]
            asset_size: int = asset.get("size", 0)
            dest_file = os.path.join(dest_path, asset_name)

            self.logger.info("Downloading asset '%s' from %s …", asset_name, asset_url)
            try:
                with requests.get(asset_url, stream=True, timeout=120) as resp:
                    resp.raise_for_status()
                    with open(dest_file, "wb") as fh:
                        for chunk in resp.iter_content(chunk_size=65536):
                            if chunk:
                                fh.write(chunk)

                checksum = compute_checksum(dest_file)
                manifest.append(
                    {
                        "name": asset_name,
                        "size": asset_size,
                        "checksum": checksum,
                        "path": dest_file,
                    }
                )
                self.logger.info(
                    "Downloaded '%s' (%d bytes), sha256=%s",
                    asset_name,
                    asset_size,
                    checksum,
                )
            except Exception as exc:  # noqa: BLE001
                self.logger.error(
                    "Failed to download asset '%s': %s", asset_name, exc
                )

        return manifest

    def collect_and_download(
        self, repo_name: str, dest_path: str
    ) -> Dict[str, Any]:
        """Collect releases and download all associated assets.

        Args:
            repo_name: Repository name within the organisation.
            dest_path: Root directory for downloaded assets; each release
                       gets its own subdirectory named after its tag.

        Returns:
            Dict with keys:

            * ``"releases"``        — list of release metadata dicts
            * ``"assets_manifest"`` — list of downloaded-asset dicts
        """
        releases = self.collect(repo_name)
        all_assets: List[Dict[str, Any]] = []

        for release in releases:
            tag: str = release.get("tag_name", str(release.get("id", "unknown")))
            release_dest = os.path.join(dest_path, tag)
            assets = self.download_assets(release, release_dest)
            all_assets.extend(assets)

        return {"releases": releases, "assets_manifest": all_assets}

    def validate(self, data: Any) -> bool:
        """Validate that *data* is a list.

        Args:
            data: Value returned by :meth:`collect`.

        Returns:
            ``True`` if *data* is a list.
        """
        return isinstance(data, list)
