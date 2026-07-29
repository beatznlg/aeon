"""
AEON OS Phase 43 — Pluggable Storage Abstraction
================================================
Provides a backend-agnostic file/object store so AEON can run statelessly
in multi-node Kubernetes deployments. Supports local filesystem (dev) and
S3-compatible object stores (production).

Usage:
    from aeon_storage import get_storage

    store = get_storage()
    store.write("agents/my-agent/state.json", b"{...}")
    data = store.read("agents/my-agent/state.json")
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class StorageBackend(ABC):
    """Abstract backend for reading, writing, and listing stored objects."""

    @abstractmethod
    def read(self, key: str) -> bytes:
        """Read the object at *key* and return raw bytes."""

    @abstractmethod
    def write(self, key: str, data: bytes) -> None:
        """Write *data* to *key*, overwriting if it exists."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete the object at *key*."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Return True if the object at *key* exists."""

    @abstractmethod
    def list_prefix(self, prefix: str) -> list[str]:
        """Return a list of keys starting with *prefix*."""


class LocalStorageBackend(StorageBackend):
    """Filesystem-backed storage rooted at a local directory."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # Basic sanitization: strip leading slashes, prevent traversal
        key = key.strip("/")
        if not key or ".." in key:
            raise ValueError(f"Invalid storage key: {key}")
        return self.root / key

    def read(self, key: str) -> bytes:
        path = self._path(key)
        if not path.exists():
            raise FileNotFoundError(key)
        return path.read_bytes()

    def write(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def list_prefix(self, prefix: str) -> list[str]:
        base = self._path(prefix)
        if not base.exists():
            return []
        if base.is_dir():
            return [str(p.relative_to(self.root)) for p in base.rglob("*") if p.is_file()]
        return [str(base.relative_to(self.root))]


class S3StorageBackend(StorageBackend):
    """S3-compatible object storage backend."""

    def __init__(  # noqa: PLR0913
        self,
        bucket: str,
        prefix: str = "",
        region: str | None = None,
        endpoint_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ) -> None:
        import boto3
        from botocore.config import Config

        self.bucket = bucket
        self.prefix = prefix.strip().rstrip("/")
        config = Config(region_name=region) if region else Config()
        client_kwargs: dict[str, Any] = {"config": config}
        if endpoint_url:
            client_kwargs["endpoint_url"] = endpoint_url
        if access_key_id and secret_access_key:
            client_kwargs["aws_access_key_id"] = access_key_id
            client_kwargs["aws_secret_access_key"] = secret_access_key
        self._client = boto3.client("s3", **client_kwargs)

    def _key(self, key: str) -> str:
        key = key.strip("/")
        if not key or ".." in key:
            raise ValueError(f"Invalid storage key: {key}")
        if self.prefix:
            return f"{self.prefix}/{key}"
        return key

    def read(self, key: str) -> bytes:
        s3_key = self._key(key)
        response = self._client.get_object(Bucket=self.bucket, Key=s3_key)
        return response["Body"].read()

    def write(self, key: str, data: bytes) -> None:
        s3_key = self._key(key)
        self._client.put_object(Bucket=self.bucket, Key=s3_key, Body=data)

    def delete(self, key: str) -> None:
        s3_key = self._key(key)
        self._client.delete_object(Bucket=self.bucket, Key=s3_key)

    def exists(self, key: str) -> bool:
        s3_key = self._key(key)
        try:
            self._client.head_object(Bucket=self.bucket, Key=s3_key)
            return True
        except Exception:
            return False

    def list_prefix(self, prefix: str) -> list[str]:
        s3_prefix = self._key(prefix)
        paginator = self._client.get_paginator("list_objects_v2")
        keys: list[str] = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=s3_prefix):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])
        return keys


def get_storage() -> StorageBackend:
    """Return the configured storage backend.

    Environment variables:
      AEON_STORAGE_BACKEND: "local" (default) or "s3"
      AEON_ROOT: root directory for local backend
      AEON_S3_BUCKET, AEON_S3_PREFIX, AEON_S3_REGION, AEON_S3_ENDPOINT_URL,
      AEON_S3_ACCESS_KEY_ID, AEON_S3_SECRET_ACCESS_KEY
    """
    backend = os.environ.get("AEON_STORAGE_BACKEND", "local").lower()
    if backend == "s3":
        return S3StorageBackend(
            bucket=os.environ["AEON_S3_BUCKET"],
            prefix=os.environ.get("AEON_S3_PREFIX", ""),
            region=os.environ.get("AEON_S3_REGION"),
            endpoint_url=os.environ.get("AEON_S3_ENDPOINT_URL"),
            access_key_id=os.environ.get("AEON_S3_ACCESS_KEY_ID"),
            secret_access_key=os.environ.get("AEON_S3_SECRET_ACCESS_KEY"),
        )
    if backend == "local":
        root = os.environ.get("AEON_ROOT", "./aeon_state")
        return LocalStorageBackend(root)
    raise ValueError(f"Unsupported AEON_STORAGE_BACKEND: {backend}")
