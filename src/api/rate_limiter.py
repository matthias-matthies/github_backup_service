"""
GitHub REST API rate-limit management for the GitHub Backup Service.

Parses rate-limit headers returned by the GitHub API and transparently
sleeps the calling thread whenever the remaining quota drops too low.
"""

import time
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class RateLimiter:
    """Monitor GitHub API rate-limit headers and pause when necessary.

    GitHub returns ``X-RateLimit-Remaining`` and ``X-RateLimit-Reset``
    headers with every response.  :meth:`check_and_wait` reads those values
    and sleeps until the reset epoch (plus a small safety buffer) whenever
    the remaining quota falls at or below *min_remaining*.

    Args:
        min_remaining: Minimum number of API calls to keep in reserve before
                       sleeping.  Defaults to 100.
        sleep_buffer:  Extra seconds added on top of the reset timestamp to
                       avoid waking up a fraction of a second too early.
                       Defaults to 1.1.

    Example::

        limiter = RateLimiter(min_remaining=50)
        response = requests.get(url, headers=headers)
        limiter.check_and_wait(dict(response.headers))
    """

    def __init__(self, min_remaining: int = 100, sleep_buffer: float = 1.1) -> None:
        self._min_remaining: int = min_remaining
        self._sleep_buffer: float = sleep_buffer

        # State updated from response headers.
        self._remaining: Optional[int] = None
        self._reset_at: Optional[int] = None  # Unix epoch seconds.

        # Internal counter of total requests recorded.
        self._request_count: int = 0

    # ── Public API ────────────────────────────────────────────────────────

    def check_and_wait(self, response_headers: Dict[str, str]) -> None:
        """Inspect *response_headers* and sleep if the rate limit is low.

        Parses ``X-RateLimit-Remaining`` and ``X-RateLimit-Reset`` from the
        supplied header dict (case-insensitive lookup via lower-casing).

        Args:
            response_headers: Mapping of HTTP response header names to values,
                               as returned by ``requests.Response.headers``.
        """
        # Normalise header names to lower-case for case-insensitive lookup.
        headers_lower = {k.lower(): v for k, v in response_headers.items()}

        remaining_str = headers_lower.get("x-ratelimit-remaining")
        reset_str = headers_lower.get("x-ratelimit-reset")

        if remaining_str is not None:
            try:
                self._remaining = int(remaining_str)
            except ValueError:
                logger.warning("Could not parse X-RateLimit-Remaining: %r", remaining_str)

        if reset_str is not None:
            try:
                self._reset_at = int(reset_str)
            except ValueError:
                logger.warning("Could not parse X-RateLimit-Reset: %r", reset_str)

        if self._remaining is not None and self._remaining <= self._min_remaining:
            if self._reset_at is not None:
                sleep_seconds = (self._reset_at + self._sleep_buffer) - time.time()
                if sleep_seconds > 0:
                    logger.warning(
                        "Rate limit low (remaining=%d). Sleeping %.1f seconds until reset.",
                        self._remaining,
                        sleep_seconds,
                    )
                    time.sleep(sleep_seconds)
            else:
                # No reset time available — apply a conservative default sleep.
                logger.warning(
                    "Rate limit low (remaining=%d) but no reset time available. "
                    "Sleeping 60 seconds.",
                    self._remaining,
                )
                time.sleep(60)

    def get_status(self) -> Dict[str, Optional[int]]:
        """Return the last observed rate-limit state.

        Returns:
            A dictionary with keys ``"remaining"``, ``"reset_at"``, and
            ``"request_count"``.
        """
        return {
            "remaining": self._remaining,
            "reset_at": self._reset_at,
            "request_count": self._request_count,
        }

    def record_request(self) -> None:
        """Increment the internal request counter by one."""
        self._request_count += 1

    # ── Dunder helpers ────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"RateLimiter(min_remaining={self._min_remaining}, "
            f"sleep_buffer={self._sleep_buffer})"
        )
