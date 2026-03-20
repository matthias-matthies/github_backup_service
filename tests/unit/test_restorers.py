"""Unit tests for restore domain classes."""

import json
import os
import pytest
import requests
from unittest.mock import MagicMock, patch

from src.restore.base_restorer import BaseRestorer, ConflictError
from src.restore.repository_restorer import RepositoryRestorer
from src.restore.metadata_restorer import MetadataRestorer
from src.restore.issues_prs_restorer import IssuesPRsRestorer
from src.restore.reviews_restorer import ReviewsRestorer
from src.restore.releases_restorer import ReleasesRestorer
from src.restore.workflows_restorer import WorkflowsRestorer
from src.restore.org_settings_restorer import OrgSettingsRestorer
from src.restore.restore_manager import RestoreManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class ConcreteRestorer(BaseRestorer):
    """Minimal concrete subclass of BaseRestorer for testing abstract base."""

    def restore(self):
        return {}


def make_restorer(cls, tmp_path, api_client=None):
    """Factory that creates a restorer instance with test-friendly defaults.

    If no *api_client* is given a plain MagicMock is used so that every
    attribute access (e.g. ``.post().raise_for_status()``) works without
    raising errors.
    """
    if api_client is None:
        api_client = MagicMock()
    storage_manager = MagicMock()
    return cls(
        api_client=api_client,
        storage_manager=storage_manager,
        org_name="test-org",
        backup_path=str(tmp_path),
    )


# ---------------------------------------------------------------------------
# ConflictError tests
# ---------------------------------------------------------------------------

def test_conflict_error_message():
    err = ConflictError("repo", "my-repo")
    assert "my-repo" in str(err)


def test_conflict_error_attributes():
    err = ConflictError("repository", "acme-service")
    assert err.resource_type == "repository"
    assert err.name == "acme-service"


# ---------------------------------------------------------------------------
# BaseRestorer tests
# ---------------------------------------------------------------------------

def test_load_json_returns_data(tmp_path):
    data = {"key": "value", "count": 42}
    (tmp_path / "data.json").write_text(json.dumps(data), encoding="utf-8")

    restorer = make_restorer(ConcreteRestorer, tmp_path)
    result = restorer.load_json("data.json")

    assert result == data


def test_load_json_missing_file_returns_empty(tmp_path):
    restorer = make_restorer(ConcreteRestorer, tmp_path)
    result = restorer.load_json("nonexistent.json")
    assert result == {}


def test_format_author_note(tmp_path):
    restorer = make_restorer(ConcreteRestorer, tmp_path)
    note = restorer._format_author_note("testuser", "2024-01-15T10:00:00Z")
    assert "@testuser" in note


def test_report_conflict_raises(tmp_path):
    restorer = make_restorer(ConcreteRestorer, tmp_path)
    with pytest.raises(ConflictError):
        restorer.report_conflict("repository", "my-repo")


# ---------------------------------------------------------------------------
# RepositoryRestorer tests
# ---------------------------------------------------------------------------

def test_create_repo_success(tmp_path, mock_api_client):
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"full_name": "test-org/my-repo", "id": 1}
    mock_api_client.post.return_value = mock_response

    restorer = make_restorer(RepositoryRestorer, tmp_path, api_client=mock_api_client)
    result = restorer.create_repo({"name": "my-repo", "description": "Test", "private": False})

    assert result["full_name"] == "test-org/my-repo"
    mock_api_client.post.assert_called_once()
    endpoint = mock_api_client.post.call_args[0][0]
    assert "/orgs/test-org/repos" in endpoint


def test_create_repo_conflict(tmp_path, mock_api_client):
    mock_resp = MagicMock()
    mock_resp.status_code = 422
    http_error = requests.exceptions.HTTPError(response=mock_resp)
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = http_error
    mock_api_client.post.return_value = mock_response

    restorer = make_restorer(RepositoryRestorer, tmp_path, api_client=mock_api_client)
    with pytest.raises(ConflictError):
        restorer.create_repo({"name": "existing-repo"})


def test_restore_skips_missing_metadata(tmp_path):
    # Create repo directory without repo_metadata.json
    repo_dir = tmp_path / "repositories" / "test-org" / "empty-repo"
    repo_dir.mkdir(parents=True)

    restorer = make_restorer(RepositoryRestorer, tmp_path)
    summary = restorer.restore()

    assert summary["skipped"] == 1
    assert summary["created"] == 0


# ---------------------------------------------------------------------------
# MetadataRestorer tests
# ---------------------------------------------------------------------------

def test_restore_org_labels(tmp_path, mock_api_client):
    metadata = {
        "labels": [
            {"name": "bug", "color": "ee0701", "description": "Something broken"},
            {"name": "enhancement", "color": "84b6eb", "description": ""},
        ]
    }
    (tmp_path / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_api_client.post.return_value = mock_response

    restorer = make_restorer(MetadataRestorer, tmp_path, api_client=mock_api_client)
    count = restorer.restore_org_labels()

    assert count == 2
    assert mock_api_client.post.call_count == 2


def test_restore_milestones(tmp_path, mock_api_client):
    repo_meta = {
        "milestones": [
            {"title": "v1.0", "state": "open", "description": "First release"},
            {"title": "v2.0", "state": "open", "description": "Second release"},
        ]
    }
    repo_dir = tmp_path / "repositories" / "test-org" / "my-repo"
    repo_dir.mkdir(parents=True)
    (repo_dir / "repo_metadata.json").write_text(json.dumps(repo_meta), encoding="utf-8")

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_api_client.post.return_value = mock_response

    restorer = make_restorer(MetadataRestorer, tmp_path, api_client=mock_api_client)
    count = restorer.restore_milestones("my-repo")

    assert count == 2
    assert mock_api_client.post.call_count == 2


def test_restore_members_logs_warning(tmp_path):
    metadata = {"members": [{"login": "alice"}, {"login": "bob"}]}
    (tmp_path / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")

    # Use a plain MagicMock so put().raise_for_status() auto-succeeds.
    api_client = MagicMock()
    restorer = make_restorer(MetadataRestorer, tmp_path, api_client=api_client)

    # Replace the logger so we can assert warning was called.
    restorer.logger = MagicMock()
    count = restorer.restore_members()

    assert count == 2
    assert api_client.put.call_count == 2
    restorer.logger.warning.assert_called()


# ---------------------------------------------------------------------------
# IssuesPRsRestorer tests
# ---------------------------------------------------------------------------

def test_restore_issues_prepends_author_note(tmp_path):
    issues_data = {
        "issues": [
            {
                "title": "Test issue",
                "body": "Original body",
                "user": {"login": "alice"},
                "created_at": "2024-01-01T00:00:00Z",
                "labels": [],
                "comments": [],
            }
        ],
        "pull_requests": [],
    }
    repo_dir = tmp_path / "repositories" / "test-org" / "my-repo"
    repo_dir.mkdir(parents=True)
    (repo_dir / "issues_prs.json").write_text(json.dumps(issues_data), encoding="utf-8")

    api_client = MagicMock()
    # restore_issues treats the return value as a dict directly
    api_client.post.return_value = {"number": 1}

    restorer = make_restorer(IssuesPRsRestorer, tmp_path, api_client=api_client)
    issues_count, _ = restorer.restore_issues("my-repo")

    assert issues_count == 1
    api_client.post.assert_called()
    posted_payload = api_client.post.call_args[0][1]
    assert "Originally by" in posted_payload["body"]


def test_restore_prs_skips_on_422(tmp_path):
    prs_data = {
        "issues": [],
        "pull_requests": [
            {
                "title": "Add feature",
                "body": "PR body",
                "user": {"login": "bob"},
                "created_at": "2024-01-02T00:00:00Z",
                "head": {"ref": "feature-branch"},
                "base": {"ref": "main"},
                "draft": False,
            }
        ],
    }
    repo_dir = tmp_path / "repositories" / "test-org" / "my-repo"
    repo_dir.mkdir(parents=True)
    (repo_dir / "issues_prs.json").write_text(json.dumps(prs_data), encoding="utf-8")

    mock_resp = MagicMock()
    mock_resp.status_code = 422
    http_error = requests.exceptions.HTTPError(response=mock_resp)

    api_client = MagicMock()
    api_client.post.side_effect = http_error

    restorer = make_restorer(IssuesPRsRestorer, tmp_path, api_client=api_client)
    # Must not raise — 422 is silently warned and skipped.
    prs_count, _ = restorer.restore_prs("my-repo")
    assert prs_count == 0


# ---------------------------------------------------------------------------
# ReviewsRestorer tests
# ---------------------------------------------------------------------------

def test_restore_reviews_maps_state(tmp_path):
    reviews_data = [
        {
            "pr_number": 1,
            "reviews": [
                {
                    "state": "APPROVED",
                    "body": "Looks good",
                    "user": {"login": "reviewer"},
                    "submitted_at": "2024-01-03T10:00:00Z",
                }
            ],
            "review_comments": [],
        }
    ]
    repo_dir = tmp_path / "repositories" / "test-org" / "my-repo"
    repo_dir.mkdir(parents=True)
    (repo_dir / "reviews.json").write_text(json.dumps(reviews_data), encoding="utf-8")

    api_client = MagicMock()
    restorer = make_restorer(ReviewsRestorer, tmp_path, api_client=api_client)
    reviews_count, _ = restorer.restore_reviews("my-repo")

    assert reviews_count == 1
    posted_payload = api_client.post.call_args[0][1]
    assert posted_payload["event"] == "APPROVE"


# ---------------------------------------------------------------------------
# ReleasesRestorer tests
# ---------------------------------------------------------------------------

def test_upload_asset_returns_false_on_failure(tmp_path):
    # Provide a real file so os.path.isfile() passes.
    asset_file = tmp_path / "myasset.zip"
    asset_file.write_bytes(b"fake asset content")

    api_client = MagicMock()
    api_client._token = "fake-token"
    restorer = make_restorer(ReleasesRestorer, tmp_path, api_client=api_client)

    asset_info = {
        "name": "myasset.zip",
        "path": str(asset_file),
        "size": 18,
    }

    with patch("requests.post", side_effect=Exception("network error")):
        result = restorer.upload_asset(
            release_id=42, repo_name="my-repo", asset_info=asset_info
        )

    assert result is False


# ---------------------------------------------------------------------------
# RestoreManager tests
# ---------------------------------------------------------------------------

def test_should_run_none_filter():
    manager = RestoreManager(
        api_client=MagicMock(),
        storage_manager=MagicMock(),
        org_name="test-org",
        backup_path="/fake/path",
        only=None,
    )
    assert manager._should_run("repositories") is True
    assert manager._should_run("metadata") is True
    assert manager._should_run("org_settings") is True


def test_should_run_filtered():
    manager = RestoreManager(
        api_client=MagicMock(),
        storage_manager=MagicMock(),
        org_name="test-org",
        backup_path="/fake/path",
        only=["repos"],
    )
    assert manager._should_run("repos") is True
    assert manager._should_run("metadata") is False
    assert manager._should_run("repositories") is False


def test_handle_conflict_non_interactive():
    manager = RestoreManager(
        api_client=MagicMock(),
        storage_manager=MagicMock(),
        org_name="test-org",
        backup_path="/fake/path",
        non_interactive=True,
    )
    error = ConflictError("repository", "existing-repo")
    result = manager._handle_conflict(error)
    assert result == "abort"
