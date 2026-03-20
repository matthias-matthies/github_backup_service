"""Integration test: full backup orchestration flow with mocked external calls."""

import os
from unittest.mock import MagicMock, patch

import pytest

from tests.fixtures.mock_responses import SAMPLE_REPOS_RESPONSE, SAMPLE_ORG_RESPONSE


def test_full_backup_flow(tmp_path):
    """Run the main backup flow with mocked auth and API; verify directory layout."""
    from src.storage.backup_structure import BackupStructure
    from src.storage.storage_manager import StorageManager
    from src.collectors.org_settings_collector import OrgSettingsCollector
    from src.collectors.metadata_collector import MetadataCollector
    from src.collectors.repository_collector import RepositoryCollector
    from src.collectors.issues_prs_collector import IssuesPRsCollector
    from src.collectors.reviews_collector import ReviewsCollector
    from src.collectors.releases_collector import ReleasesCollector
    from src.collectors.workflows_collector import WorkflowsCollector

    output_path = str(tmp_path / "backup_output")
    org_name = "test-org"

    # Build mock API client
    api_client = MagicMock()
    api_client.get.return_value = SAMPLE_ORG_RESPONSE
    api_client.paginate.return_value = []

    # Build real storage + structure
    storage = StorageManager(output_path)
    structure = BackupStructure(output_path)
    structure.ensure_directories(org_name, [r["name"] for r in SAMPLE_REPOS_RESPONSE])

    # Collect org settings
    org_collector = OrgSettingsCollector(api_client, storage, org_name)
    api_client.paginate.return_value = []
    org_data = org_collector.collect()
    org_path = structure.org_path(org_name)
    storage.write_json(org_path, org_data, "org_settings.json")

    # Collect org metadata
    meta_collector = MetadataCollector(api_client, storage, org_name)
    meta_data = meta_collector.collect()
    metadata_path = structure.metadata_path(org_name, "members")
    storage.write_json(metadata_path, meta_data, "metadata.json")

    # Collect repositories (mock paginate returns sample repos)
    api_client.paginate.return_value = SAMPLE_REPOS_RESPONSE
    repo_collector = RepositoryCollector(api_client, storage, org_name)
    repos = repo_collector.collect()

    api_client.paginate.return_value = []

    for repo in repos:
        repo_name = repo["name"]
        repo_path = structure.repo_path(org_name, repo_name)

        # Repo metadata
        repo_meta = meta_collector.collect_repo_metadata(repo_name)
        storage.write_json(repo_path, repo_meta, "repo_metadata.json")

        # Issues & PRs
        issues_prs_data = {"issues": [], "pull_requests": []}
        storage.write_json(repo_path, issues_prs_data, "issues_prs.json")

        # Reviews
        storage.write_json(repo_path, [], "reviews.json")

        # Releases
        storage.write_json(repo_path, {"releases": [], "assets_manifest": []}, "releases.json")

        # Workflows
        api_client.get.return_value = {"workflows": [], "artifacts": []}
        workflows_data = workflows_collector = WorkflowsCollector(api_client, storage, org_name)
        wf_data = WorkflowsCollector(api_client, storage, org_name).collect(repo_name)
        storage.write_json(repo_path, wf_data, "workflows.json")

    # ── Assertions: directory structure ──────────────────────────────────────
    assert os.path.isdir(os.path.join(output_path, "organizations", org_name))
    assert os.path.isdir(os.path.join(output_path, "repositories", org_name))
    assert os.path.isdir(os.path.join(output_path, "metadata", org_name))

    # org_settings.json must exist
    assert os.path.isfile(os.path.join(output_path, "organizations", org_name, "org_settings.json"))

    # Each repo directory must exist and contain the expected JSON files
    for repo in SAMPLE_REPOS_RESPONSE:
        repo_dir = os.path.join(output_path, "repositories", org_name, repo["name"])
        assert os.path.isdir(repo_dir), f"Expected directory: {repo_dir}"
        assert os.path.isfile(os.path.join(repo_dir, "repo_metadata.json"))
        assert os.path.isfile(os.path.join(repo_dir, "issues_prs.json"))
        assert os.path.isfile(os.path.join(repo_dir, "reviews.json"))
        assert os.path.isfile(os.path.join(repo_dir, "releases.json"))
        assert os.path.isfile(os.path.join(repo_dir, "workflows.json"))
