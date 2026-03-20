"""Manages reading and writing backup data to the filesystem."""

import glob as glob_module
import json
import os
import shutil
import tempfile
from typing import Union

from .backup_structure import BackupStructure


class StorageManager:
    """
    Handles all filesystem I/O for the backup service.

    All writes are performed *atomically*: data is first written to a
    temporary file in the same directory, then renamed to the final path
    via :func:`os.replace`, which is atomic on POSIX and best-effort on
    Windows.
    """

    def __init__(self, base_path: str, compress: bool = False) -> None:
        """
        Initialise the StorageManager.

        Args:
            base_path: Root directory for all backup data.
            compress: Reserved for future gzip compression support.
        """
        self.base_path = base_path
        self.compress = compress

    # ------------------------------------------------------------------
    # Directory helpers
    # ------------------------------------------------------------------

    def ensure_dir(self, path: str) -> None:
        """Create *path* (and any missing parents) if it does not exist.

        Args:
            path: Directory path to create.
        """
        os.makedirs(path, exist_ok=True)

    # ------------------------------------------------------------------
    # JSON I/O
    # ------------------------------------------------------------------

    def write_json(self, path: str, data: Union[dict, list], filename: str) -> None:
        """
        Serialise *data* to JSON and write it atomically to ``<path>/<filename>``.

        Args:
            path: Target directory (created if absent).
            data: Python dict or list to serialise.
            filename: Name of the output file (e.g. ``"repos.json"``).
        """
        self.ensure_dir(path)
        final_path = os.path.join(path, filename)
        # Write to a temp file in the same directory to ensure atomic rename.
        fd, tmp_path = tempfile.mkstemp(dir=path, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False, default=str)
            os.replace(tmp_path, final_path)
        except Exception:
            # Clean up the temp file if something went wrong.
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    def read_json(self, path: str, filename: str) -> Union[dict, list]:
        """
        Read and deserialise a JSON file from ``<path>/<filename>``.

        Args:
            path: Directory containing the file.
            filename: Name of the JSON file.

        Returns:
            Parsed Python object (dict or list).

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        file_path = os.path.join(path, filename)
        with open(file_path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    # ------------------------------------------------------------------
    # Text I/O
    # ------------------------------------------------------------------

    def write_text(self, path: str, filename: str, content: str) -> None:
        """
        Write *content* as a UTF-8 text file atomically to ``<path>/<filename>``.

        Args:
            path: Target directory (created if absent).
            filename: Name of the output file.
            content: String content to write.
        """
        self.ensure_dir(path)
        final_path = os.path.join(path, filename)
        fd, tmp_path = tempfile.mkstemp(dir=path, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(content)
            os.replace(tmp_path, final_path)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    # ------------------------------------------------------------------
    # File copying
    # ------------------------------------------------------------------

    def copy_file(self, src: str, dst_path: str, filename: str) -> None:
        """
        Copy *src* to ``<dst_path>/<filename>``.

        Args:
            src: Full path of the source file.
            dst_path: Destination directory (created if absent).
            filename: Name to give the copied file in *dst_path*.
        """
        self.ensure_dir(dst_path)
        dst = os.path.join(dst_path, filename)
        shutil.copy2(src, dst)

    # ------------------------------------------------------------------
    # Directory listing
    # ------------------------------------------------------------------

    def list_files(self, path: str, pattern: str = "*") -> list[str]:
        """
        Return a list of file paths inside *path* matching *pattern*.

        Args:
            path: Directory to search.
            pattern: Glob pattern (default ``"*"`` matches all files).

        Returns:
            Sorted list of matching file paths.
        """
        search = os.path.join(path, pattern)
        return sorted(glob_module.glob(search))

    # ------------------------------------------------------------------
    # Backup structure
    # ------------------------------------------------------------------

    def get_backup_structure(self) -> BackupStructure:
        """Return a :class:`BackupStructure` rooted at :attr:`base_path`.

        Returns:
            A configured :class:`BackupStructure` instance.
        """
        return BackupStructure(self.base_path)
