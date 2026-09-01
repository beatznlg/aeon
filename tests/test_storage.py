"""Tests for aeon_storage abstraction."""

import os
import sys
import tempfile
import types

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


# ── GCS backend (mocked google.cloud — no credentials/network) ───────────────

def _install_fake_gcs(monkeypatch: pytest.MonkeyPatch, calls: list) -> None:
    """Inject a fake ``google.cloud.storage`` module recording blob calls."""

    class FakeBlob:
        def __init__(self, bucket: object, name: str) -> None:
            self.bucket = bucket
            self.name = name

        def download_as_bytes(self) -> bytes:
            calls.append(("read", self.name))
            return b"gcs-bytes"

        def upload_from_string(self, data: bytes) -> None:
            calls.append(("write", self.name, data))

        def delete(self) -> None:
            calls.append(("delete", self.name))

        def exists(self) -> bool:
            calls.append(("exists", self.name))
            return True

    class FakeBucket:
        def __init__(self, name: str) -> None:
            self.name = name

        def blob(self, key: str) -> FakeBlob:
            return FakeBlob(self, key)

    class FakeClient:
        def __init__(self) -> None:
            calls.append(("client_init",))

        def bucket(self, name: str) -> FakeBucket:
            calls.append(("bucket", name))
            return FakeBucket(name)

        def list_blobs(self, bucket: str, prefix: str = "") -> list:
            calls.append(("list", bucket, prefix))
            return []

    fake_storage = types.ModuleType("google.cloud.storage")
    fake_storage.Client = FakeClient
    fake_cloud = types.ModuleType("google.cloud")
    fake_cloud.storage = fake_storage
    fake_google = types.ModuleType("google")
    fake_google.cloud = fake_cloud
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.cloud", fake_cloud)
    monkeypatch.setitem(sys.modules, "google.cloud.storage", fake_storage)


def test_gcs_backend_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    from aeon_storage import GCSStorageBackend

    calls: list = []
    _install_fake_gcs(monkeypatch, calls)
    store = GCSStorageBackend(bucket="aeon-test", prefix="state")
    assert store.bucket_name == "aeon-test"
    store.write("agents/x.json", b"{\"ok\":1}")
    assert store.read("agents/x.json") == b"gcs-bytes"
    assert store.exists("agents/x.json") is True
    store.delete("agents/x.json")
    # Bucket wired once; key paths carry the prefix
    assert ("bucket", "aeon-test") in calls
    assert ("write", "state/agents/x.json", b"{\"ok\":1}") in calls
    assert ("read", "state/agents/x.json") in calls


def test_gcs_backend_key_sanitization(monkeypatch: pytest.MonkeyPatch) -> None:
    from aeon_storage import GCSStorageBackend

    calls: list = []
    _install_fake_gcs(monkeypatch, calls)
    store = GCSStorageBackend(bucket="aeon-test")
    with pytest.raises(ValueError):
        store.write("../escape", b"bad")
    with pytest.raises(ValueError):
        store.read("../escape")


def test_get_storage_gcs_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    from aeon_storage import get_storage

    calls: list = []
    _install_fake_gcs(monkeypatch, calls)
    old_backend = os.environ.get("AEON_STORAGE_BACKEND")
    old_bucket = os.environ.get("AEON_GCS_BUCKET")
    try:
        os.environ["AEON_STORAGE_BACKEND"] = "gcs"
        os.environ["AEON_GCS_BUCKET"] = "aeon-bucket-env"
        store = get_storage()
        assert type(store).__name__ == "GCSStorageBackend"
        assert ("bucket", "aeon-bucket-env") in calls
    finally:
        if old_backend is not None:
            os.environ["AEON_STORAGE_BACKEND"] = old_backend
        else:
            os.environ.pop("AEON_STORAGE_BACKEND", None)
        if old_bucket is not None:
            os.environ["AEON_GCS_BUCKET"] = old_bucket
        else:
            os.environ.pop("AEON_GCS_BUCKET", None)


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
