"""
General-purpose helper utilities for the GitHub Backup Service.
"""

import hashlib
import json
import math
from datetime import datetime, timezone
from typing import Any, Iterator, List, Optional


def format_datetime(dt: Optional[datetime]) -> str:
    """Serialise a :class:`~datetime.datetime` to an ISO 8601 string.

    If *dt* is ``None`` the empty string ``""`` is returned so callers do
    not need to guard against ``None`` values when building JSON payloads.

    Naive datetimes (those without timezone info) are treated as UTC and
    the ``+00:00`` suffix is appended.

    Args:
        dt: The datetime object to format, or ``None``.

    Returns:
        An ISO 8601 string such as ``"2024-01-15T08:30:00+00:00"``,
        or ``""`` when *dt* is ``None``.
    """
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def chunk_list(lst: List[Any], size: int) -> List[List[Any]]:
    """Split *lst* into successive sublists each of at most *size* items.

    Args:
        lst:  The list to split.
        size: Maximum number of elements per chunk.  Must be a positive int.

    Returns:
        A list of lists.  The last chunk may be smaller than *size*.
        Returns an empty list when *lst* is empty.

    Raises:
        ValueError: If *size* is less than 1.
    """
    if size < 1:
        raise ValueError(f"chunk size must be >= 1, got {size!r}")
    return [lst[i : i + size] for i in range(0, len(lst), size)]


class _DatetimeEncoder(json.JSONEncoder):
    """JSON encoder that handles :class:`~datetime.datetime` objects."""

    def default(self, obj: Any) -> Any:  # noqa: ANN401
        if isinstance(obj, datetime):
            return format_datetime(obj)
        return super().default(obj)


def safe_json_dump(obj: Any) -> str:
    """Serialise *obj* to a pretty-printed JSON string.

    :class:`~datetime.datetime` objects are converted to ISO 8601 strings
    automatically.  Any other non-serialisable type falls back to its
    ``str()`` representation so that the function never raises on common
    Python objects.

    Args:
        obj: The Python object to serialise.

    Returns:
        A JSON string with 2-space indentation.
    """

    class _SafeEncoder(_DatetimeEncoder):
        def default(self, obj: Any) -> Any:  # noqa: ANN401
            try:
                return super().default(obj)
            except TypeError:
                return str(obj)

    return json.dumps(obj, cls=_SafeEncoder, indent=2, ensure_ascii=False)


def compute_checksum(file_path: str, algo: str = "sha256") -> str:
    """Compute the hex-digest checksum of the file at *file_path*.

    The file is read in 64 KB chunks so arbitrarily large files can be
    checksummed without loading them entirely into memory.

    Args:
        file_path: Absolute or relative path to the file.
        algo:      Hash algorithm name accepted by :mod:`hashlib`
                   (e.g. ``"sha256"``, ``"md5"``).  Defaults to ``"sha256"``.

    Returns:
        The lowercase hex-digest string of the computed hash.

    Raises:
        FileNotFoundError: If *file_path* does not exist.
        ValueError:        If *algo* is not supported by :mod:`hashlib`.
    """
    try:
        h = hashlib.new(algo)
    except ValueError as exc:
        raise ValueError(f"Unsupported hash algorithm: '{algo}'") from exc

    chunk_size = 64 * 1024  # 64 KB
    with open(file_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            h.update(chunk)

    return h.hexdigest()
