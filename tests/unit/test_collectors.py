"""Unit tests for the collector classes."""

from unittest.mock import MagicMock, patch

import pytest

from src.collectors.repository_collector import RepositoryCollector
from src.collectors.metadata_collector import MetadataCollector
from src.collectors.issues_prs_collector import IssuesPRsCollector
from src.collectors.reviews_collector import ReviewsCollector
from src.collectors.org_settings_collector import OrgSettingsCollector
from tests.fixtures.mock_responses import (
    SAMPLE_REPOS_RESPONSE,
    SAMPLE_ISSUES_RESPONSE,
    SAMPLE_PRS_RESPONSE,
    make_user,
)


@pytest.fixture
def api_client():
    client = MagicMock()
    client.get = MagicMock(return_value={})
    client.paginate = MagicMock(return_value=[])
    return client


@pytest.fixture
def storage(tmp_path):
    from src.storage.storage_manager import StorageManager
    return StorageManager(str(tmp_path))


def test_repository_collector_collect(api_client, storage):
    """collect() should return the list of repos returned by paginate()."""
    api_client.paginate.return_value = SAMPLE_REPOS_RESPONSE

    collector = RepositoryCollector(api_client, storage, "test-org")
    result = collector.collect()

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["name"] == "repo-alpha"
    api_client.paginate.assert_called_once()


def test_metadata_collector_collect(api_client, storage):
    """collect() should return a dict with 'members' and 'teams' keys."""
    members = [make_user("alice"), make_user("bob")]
    teams = [{"id": 1, "name": "devs"}]

    def paginate_side_effect(endpoint, **kwargs):
        if "members" in endpoint:
            return members
        if "teams" in endpoint:
            return teams
        return []

    api_client.paginate.side_effect = paginate_side_effect

    collector = MetadataCollector(api_client, storage, "test-org")
    result = collector.collect()

    assert isinstance(result, dict)
    assert "members" in result
    assert "teams" in result
    assert result["members"] == members
    assert result["teams"] == teams


def test_issues_prs_collector_collect(api_client, storage):
    """collect() should return dict with 'issues' and 'pull_requests' keys."""
    # Issues endpoint returns both plain issues and PRs; PRs have 'pull_request' key
    plain_issues = SAMPLE_ISSUES_RESPONSE  # no 'pull_request' key
    prs = SAMPLE_PRS_RESPONSE  # has 'pull_request' key

    def paginate_side_effect(endpoint, **kwargs):
        if "/issues" in endpoint:
            return plain_issues + prs  # mixed, as GitHub does
        if "/pulls" in endpoint:
            return prs
        return []

    api_client.paginate.side_effect = paginate_side_effect

    collector = IssuesPRsCollector(api_client, storage, "test-org")
    result = collector.collect("repo-alpha")

    assert isinstance(result, dict)
    assert "issues" in result
    assert "pull_requests" in result
    # PRs should be filtered out of the issues list
    assert all("pull_request" not in issue for issue in result["issues"])


def test_reviews_collector_collect(api_client, storage):
    """collect() should return a dict with 'reviews' and 'review_comments' keys."""
    fake_reviews = [{"id": 1, "state": "APPROVED"}]
    fake_comments = [{"id": 2, "body": "LGTM"}]

    def paginate_side_effect(endpoint, **kwargs):
        if "/reviews" in endpoint:
            return fake_reviews
        if "/comments" in endpoint:
            return fake_comments
        return []

    api_client.paginate.side_effect = paginate_side_effect

    collector = ReviewsCollector(api_client, storage, "test-org")
    result = collector.collect("repo-alpha", 10)

    assert isinstance(result, dict)
    assert "reviews" in result
    assert "review_comments" in result
    assert result["reviews"] == fake_reviews
    assert result["review_comments"] == fake_comments


def test_org_settings_collector_collect(api_client, storage):
    """collect() should return a dict containing 'org_info' key."""
    from tests.fixtures.mock_responses import SAMPLE_ORG_RESPONSE

    api_client.get.return_value = SAMPLE_ORG_RESPONSE
    api_client.paginate.return_value = []

    collector = OrgSettingsCollector(api_client, storage, "test-org")
    result = collector.collect()

    assert isinstance(result, dict)
    assert "org_info" in result
    assert result["org_info"] == SAMPLE_ORG_RESPONSE
