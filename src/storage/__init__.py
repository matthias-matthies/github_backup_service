"""Storage package for persisting backup data."""

from .backup_structure import BackupStructure
from .storage_manager import StorageManager

__all__ = ["StorageManager", "BackupStructure"]
