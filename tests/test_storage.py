"""Tests for aeon_storage abstraction."""

import os
import tempfile

import pytest

from aeon_storage import LocalStorageBackend


@pytest.fixture
def temp_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield LocalStorageBackend(tmpdir)


def test_read_write_bytes(temp_store: LocalStorageBackend) -> None:
    temp_store.write("agents/test/state.json", b'{"ok":true}')
    assert temp_store.read("agents/test/state.json") == b'{"ok":true}'


def test_exists(temp_store: LocalStorageBackend) -> None:
    assert not temp_store.exists("missing.txt")
    temp_store.write("present.txt", b"data")
    assert temp_store.exists("present.txt")


def test_delete(temp_store: LocalStorageBackend) -> None:
    temp_store.write("to_delete.txt", b"data")
    temp_store.delete("to_delete.txt")
    assert not temp_store.exists("to_delete.txt")


def test_list_prefix(temp_store: LocalStorageBackend) -> None:
    temp_store.write("agents/a/state.json", b"1")
    temp_store.write("agents/b/state.json", b"2")
    keys = temp_store.list_prefix("agents")
    assert len(keys) == 2
    assert all(k.startswith("agents") for k in keys)


def test_invalid_key_rejected(temp_store: LocalStorageBackend) -> None:
    with pytest.raises(ValueError):
        temp_store.write("../etc/passwd", b"bad")


def test_get_storage_default_local():
    from aeon_storage import get_storage

    with tempfile.TemporaryDirectory() as tmpdir:
        old_root = os.environ.get("AEON_ROOT")
        old_backend = os.environ.get("AEON_STORAGE_BACKEND")
        try:
            os.environ["AEON_ROOT"] = tmpdir
            os.environ["AEON_STORAGE_BACKEND"] = "local"
            store = get_storage()
            store.write("test.txt", b"hello")
            assert store.read("test.txt") == b"hello"
        finally:
            if old_root is not None:
                os.environ["AEON_ROOT"] = old_root
            else:
                os.environ.pop("AEON_ROOT", None)
            if old_backend is not None:
                os.environ["AEON_STORAGE_BACKEND"] = old_backend
            else:
                os.environ.pop("AEON_STORAGE_BACKEND", None)
