"""
HTTP error handling and retry logic for the GitHub Backup Service.

Provides :class:`ErrorHandler` which wraps callable API calls with
configurable exponential-backoff retry behaviour and error classification.
"""

import logging
import time
from typing import Any, Callable

import requests

logger = logging.getLogger(__name__)

# HTTP status codes that are considered transient and worth retrying.
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class ErrorHandler:
    """Wrap API calls with retry logic and classify failures.

    Args:
        max_retries: Maximum number of retry attempts before re-raising the
                     last exception.  Defaults to 3.
        base_delay:  Initial delay in seconds before the first retry.
                     Subsequent delays double with each attempt.  Defaults
                     to 1.0.
        max_delay:   Upper bound on the computed delay, in seconds.
                     Defaults to 60.0.

    Example::

        handler = ErrorHandler(max_retries=5, base_delay=2.0)
        data = handler.execute_with_retry(client.get, "/repos")
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
    ) -> None:
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay

    # ── Public API ────────────────────────────────────────────────────────

    def is_retryable(self, exception: Exception) -> bool:
        """Decide whether *exception* warrants a retry attempt.

        Retryable conditions:
        - :class:`requests.exceptions.ConnectionError`
        - :class:`requests.exceptions.Timeout`
        - :class:`requests.exceptions.HTTPError` with status 429, 500, 502,
          503, or 504.

        Args:
            exception: The exception to inspect.

        Returns:
            ``True`` if the call should be retried, ``False`` otherwise.
        """
        if isinstance(exception, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
            return True
        if isinstance(exception, requests.exceptions.HTTPError):
            response = getattr(exception, "response", None)
            if response is not None and response.status_code in _RETRYABLE_STATUS_CODES:
                return True
        return False

    def execute_with_retry(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Call *func* and retry on retryable failures with exponential backoff.

        Args:
            func:    The callable to invoke.
            *args:   Positional arguments forwarded to *func*.
            **kwargs: Keyword arguments forwarded to *func*.

        Returns:
            The return value of *func* on success.

        Raises:
            The last exception raised by *func* after all retry attempts are
            exhausted.
        """
        last_exception: Exception = RuntimeError("No attempts were made.")

        for attempt in range(self._max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001
                last_exception = exc

                if not self.is_retryable(exc):
                    logger.error(
                        "Non-retryable error encountered: %s — %s",
                        type(exc).__name__,
                        exc,
                    )
                    raise

                if attempt < self._max_retries:
                    delay = min(self._base_delay * (2 ** attempt), self._max_delay)
                    logger.warning(
                        "Retryable error (attempt %d/%d): %s — %s. "
                        "Retrying in %.1f seconds.",
                        attempt + 1,
                        self._max_retries,
                        type(exc).__name__,
                        exc,
                        delay,
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        "All %d retry attempts exhausted. Last error: %s — %s",
                        self._max_retries,
                        type(exc).__name__,
                        exc,
                    )

        raise last_exception

    def classify_error(self, exception: Exception) -> str:
        """Classify *exception* into a broad error category string.

        Categories:
        - ``"auth"``         — HTTP 401 or 403 (authentication / authorisation).
        - ``"rate_limit"``   — HTTP 429 (Too Many Requests).
        - ``"not_found"``    — HTTP 404 (resource does not exist).
        - ``"server_error"`` — HTTP 5xx or connection-level failures.
        - ``"unknown"``      — Anything else.

        Args:
            exception: The exception to classify.

        Returns:
            One of the category strings listed above.
        """
        if isinstance(exception, requests.exceptions.HTTPError):
            response = getattr(exception, "response", None)
            if response is not None:
                status = response.status_code
                if status in (401, 403):
                    return "auth"
                if status == 429:
                    return "rate_limit"
                if status == 404:
                    return "not_found"
                if status >= 500:
                    return "server_error"

        if isinstance(
            exception,
            (requests.exceptions.ConnectionError, requests.exceptions.Timeout),
        ):
            return "server_error"

        return "unknown"

    # ── Dunder helpers ────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"ErrorHandler(max_retries={self._max_retries}, "
            f"base_delay={self._base_delay}, max_delay={self._max_delay})"
        )
