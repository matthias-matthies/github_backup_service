"""Integration tests for the GitHub API client behaviour."""

import time
from unittest.mock import MagicMock, patch, call

import pytest
import requests

from src.api.github_api_client import GitHubAPIClient
from src.api.rate_limiter import RateLimiter
from src.api.error_handler import ErrorHandler


def _make_response(json_data, status_code=200, headers=None):
    """Helper to build a mock requests.Response."""
    response = MagicMock(spec=requests.Response)
    response.status_code = status_code
    response.json.return_value = json_data
    response.headers = headers or {}
    response.raise_for_status = MagicMock()
    if status_code >= 400:
        http_error = requests.exceptions.HTTPError(response=response)
        response.raise_for_status.side_effect = http_error
    return response


def test_pagination_follows_link_header():
    """paginate() should follow Link headers and merge all pages."""
    page1_items = [{"id": 1}, {"id": 2}]
    page2_items = [{"id": 3}]

    page1_url = "https://api.github.com/orgs/test-org/repos"
    page2_url = "https://api.github.com/orgs/test-org/repos?page=2"

    page1_response = _make_response(
        page1_items,
        headers={"Link": f'<{page2_url}>; rel="next"', "X-RateLimit-Remaining": "4999"},
    )
    page2_response = _make_response(
        page2_items,
        headers={"X-RateLimit-Remaining": "4998"},
    )

    client = GitHubAPIClient(token="fake-token")

    with patch.object(client._session, "get", side_effect=[page1_response, page2_response]):
        result = client.paginate("/orgs/test-org/repos")

    assert result == page1_items + page2_items
    assert len(result) == 3


def test_rate_limiter_sleeps_when_low():
    """check_and_wait() should call time.sleep when remaining quota is low."""
    limiter = RateLimiter(min_remaining=100)
    future_reset = int(time.time()) + 60

    with patch("time.sleep") as mock_sleep:
        limiter.check_and_wait({
            "X-RateLimit-Remaining": "50",   # below min_remaining=100
            "X-RateLimit-Reset": str(future_reset),
        })
        mock_sleep.assert_called_once()
        sleep_seconds = mock_sleep.call_args[0][0]
        assert sleep_seconds > 0


def test_error_handler_retries_on_500():
    """execute_with_retry() should retry on HTTP 500 and return on success."""
    handler = ErrorHandler(max_retries=3, base_delay=0.01)

    call_count = 0

    def flaky_function():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            error_response = MagicMock()
            error_response.status_code = 500
            raise requests.exceptions.HTTPError(response=error_response)
        return {"success": True}

    result = handler.execute_with_retry(flaky_function)

    assert result == {"success": True}
    assert call_count == 3
