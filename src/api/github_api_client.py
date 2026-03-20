"""
GitHub REST & GraphQL API client for the GitHub Backup Service.

Wraps the ``requests`` library with rate-limit awareness, automatic
pagination via Link headers, and configurable error/retry handling.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Union

import requests

from .rate_limiter import RateLimiter
from .error_handler import ErrorHandler

logger = logging.getLogger(__name__)

# Regex that parses a single entry from the RFC 5988 Link header.
# e.g.  <https://api.github.com/repos?page=2>; rel="next"
_LINK_RE = re.compile(r'<([^>]+)>;\s*rel="([^"]+)"')


class GitHubAPIClient:
    """Thin wrapper around the GitHub REST and GraphQL APIs.

    Args:
        token:         A GitHub personal access token or installation token.
        base_url:      Base URL for the GitHub API.  Override for GitHub
                       Enterprise Server deployments.
        rate_limiter:  Optional :class:`~src.api.rate_limiter.RateLimiter`
                       instance.  A default one is created if not supplied.
        error_handler: Optional :class:`~src.api.error_handler.ErrorHandler`
                       instance.  A default one is created if not supplied.

    Example::

        client = GitHubAPIClient(token="ghp_…")
        repos = client.paginate("/orgs/my-org/repos")
    """

    def __init__(
        self,
        token: str,
        base_url: str = "https://api.github.com",
        rate_limiter: Optional[RateLimiter] = None,
        error_handler: Optional[ErrorHandler] = None,
    ) -> None:
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._rate_limiter: RateLimiter = rate_limiter or RateLimiter()
        self._error_handler: ErrorHandler = error_handler or ErrorHandler()
        self._session = requests.Session()
        self._session.headers.update(self._headers())

    # ── Headers ───────────────────────────────────────────────────────────

    def _headers(self) -> Dict[str, str]:
        """Build the default request headers.

        Returns:
            A dict containing the ``Authorization`` and ``Accept`` headers
            required by the GitHub API v3.
        """
        return {
            "Authorization": f"token {self._token}",
            "Accept": "application/vnd.github.v3+json",
        }

    # ── Core HTTP verbs ───────────────────────────────────────────────────

    def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Union[Dict[str, Any], List[Any]]:
        """Perform a GET request and return the parsed JSON response body.

        Rate-limit headers are inspected after every successful response and
        the thread may sleep if the quota is running low.

        Args:
            endpoint: API path relative to *base_url*, e.g.
                      ``"/orgs/my-org/repos"``.
            params:   Optional query-string parameters.

        Returns:
            Parsed JSON response (dict or list depending on the endpoint).

        Raises:
            requests.exceptions.HTTPError: On 4xx/5xx responses after retries
                                           are exhausted.
        """
        url = self._build_url(endpoint)

        def _do_get() -> Union[Dict[str, Any], List[Any]]:
            self._rate_limiter.record_request()
            response = self._session.get(url, params=params)
            response.raise_for_status()
            self._rate_limiter.check_and_wait(dict(response.headers))
            return response.json()

        return self._error_handler.execute_with_retry(_do_get)

    def post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform a POST request and return the parsed JSON response body.

        Args:
            endpoint: API path relative to *base_url*.
            data:     Request body serialised as JSON.

        Returns:
            Parsed JSON response dict.

        Raises:
            requests.exceptions.HTTPError: On 4xx/5xx responses after retries
                                           are exhausted.
        """
        url = self._build_url(endpoint)

        def _do_post() -> Dict[str, Any]:
            self._rate_limiter.record_request()
            response = self._session.post(url, json=data)
            response.raise_for_status()
            self._rate_limiter.check_and_wait(dict(response.headers))
            return response.json()

        return self._error_handler.execute_with_retry(_do_post)

    # ── Pagination ────────────────────────────────────────────────────────

    def paginate(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Any]:
        """Fetch *all* pages for a list endpoint and return a merged list.

        Follows the ``next`` relation in the ``Link`` response header as
        specified by RFC 5988.

        Args:
            endpoint: API path relative to *base_url*.
            params:   Optional query-string parameters for the first request.
                      ``per_page`` defaults to 100 unless already set.

        Returns:
            A flat list containing all items from all pages.
        """
        merged_params: Dict[str, Any] = {"per_page": 100}
        if params:
            merged_params.update(params)

        results: List[Any] = []
        url: Optional[str] = self._build_url(endpoint)

        while url:
            self._rate_limiter.record_request()

            def _do_page(page_url: str = url) -> requests.Response:  # type: ignore[assignment]
                response = self._session.get(page_url, params=merged_params)
                response.raise_for_status()
                return response

            response: requests.Response = self._error_handler.execute_with_retry(_do_page)
            self._rate_limiter.check_and_wait(dict(response.headers))

            page_data = response.json()
            if isinstance(page_data, list):
                results.extend(page_data)
            else:
                # Some endpoints wrap items in a sub-key; return as-is.
                results.append(page_data)

            # After the first request, params are already embedded in the
            # next-page URL returned by GitHub, so clear them.
            merged_params = {}
            url = self._parse_next_link(response.headers.get("Link", ""))

        return results

    # ── GraphQL ───────────────────────────────────────────────────────────

    def graphql(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a GraphQL query against the GitHub GraphQL API.

        Args:
            query:     GraphQL query or mutation string.
            variables: Optional variable bindings for the query.

        Returns:
            The ``"data"`` key from the GraphQL response envelope.

        Raises:
            requests.exceptions.HTTPError: On HTTP-level errors.
            ValueError: If the response contains GraphQL-level ``"errors"``.
        """
        url = f"{self._base_url}/graphql"
        payload: Dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        def _do_graphql() -> Dict[str, Any]:
            self._rate_limiter.record_request()
            response = self._session.post(url, json=payload)
            response.raise_for_status()
            self._rate_limiter.check_and_wait(dict(response.headers))
            body: Dict[str, Any] = response.json()
            if "errors" in body:
                errors = body["errors"]
                messages = "; ".join(e.get("message", str(e)) for e in errors)
                raise ValueError(f"GraphQL errors: {messages}")
            return body.get("data", {})

        return self._error_handler.execute_with_retry(_do_graphql)

    # ── Internal helpers ──────────────────────────────────────────────────

    def _build_url(self, endpoint: str) -> str:
        """Prepend *base_url* to *endpoint* if it is not already absolute.

        Args:
            endpoint: Relative (``/repos``) or absolute URL.

        Returns:
            A fully qualified URL string.
        """
        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            return endpoint
        return f"{self._base_url}/{endpoint.lstrip('/')}"

    @staticmethod
    def _parse_next_link(link_header: str) -> Optional[str]:
        """Extract the ``next`` URL from an RFC 5988 Link header value.

        Args:
            link_header: Raw value of the ``Link`` response header.

        Returns:
            The URL for the next page, or ``None`` if not present.
        """
        for match in _LINK_RE.finditer(link_header):
            url, rel = match.group(1), match.group(2)
            if rel == "next":
                return url
        return None

    # ── Dunder helpers ────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return f"GitHubAPIClient(base_url={self._base_url!r})"
