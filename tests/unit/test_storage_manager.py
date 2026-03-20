"""Unit tests for src.storage.storage_manager.StorageManager."""

import os
import json

import pytest

from src.storage.storage_manager import StorageManager


@pytest.fixture
def storage(tmp_path):
    return StorageManager(str(tmp_path))


def test_write_and_read_json(storage, tmp_path):
    """write_json() followed by read_json() should return identical data."""
    data = {"key": "value", "number": 42, "list": [1, 2, 3]}
    target_dir = str(tmp_path / "subdir")

    storage.write_json(target_dir, data, "test.json")
    result = storage.read_json(target_dir, "test.json")

    assert result == data


def test_atomic_write_creates_file(storage, tmp_path):
    """write_json() should leave no .tmp files behind."""
    target_dir = str(tmp_path / "output")
    data = {"hello": "world"}

    storage.write_json(target_dir, data, "data.json")

    # The final file must exist
    assert os.path.isfile(os.path.join(target_dir, "data.json"))

    # No temporary files should remain
    tmp_files = [f for f in os.listdir(target_dir) if f.endswith(".tmp")]
    assert tmp_files == []


def test_ensure_dir_creates_directory(storage, tmp_path):
    """ensure_dir() should create the directory including nested parents."""
    new_dir = str(tmp_path / "a" / "b" / "c")
    assert not os.path.exists(new_dir)

    storage.ensure_dir(new_dir)

    assert os.path.isdir(new_dir)


def test_list_files(storage, tmp_path):
    """list_files() should return paths of all files matching the pattern."""
    target_dir = str(tmp_path / "files")
    storage.ensure_dir(target_dir)

    storage.write_json(target_dir, {"a": 1}, "file_a.json")
    storage.write_json(target_dir, {"b": 2}, "file_b.json")

    files = storage.list_files(target_dir, "*.json")

    assert len(files) == 2
    basenames = [os.path.basename(f) for f in files]
    assert "file_a.json" in basenames
    assert "file_b.json" in basenames
