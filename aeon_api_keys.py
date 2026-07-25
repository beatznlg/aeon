"""
AEON OS Phase 2c — API Key Management & Rate Limiting
======================================================
Secure API key generation, hashed storage, workspace-scoped keys,
usage tracking, and per-key rate limiting.

Usage:
    from aeon_api_keys import ApiKeyManager
    mgr = ApiKeyManager(root)
    key, plaintext = mgr.create_key("My Key", workspace_id="ws-1", user_id="usr-1")
    # Give the user `plaintext` exactly once
    info = mgr.validate_key(plaintext)
    if info:
        print(f"Authenticated as workspace {info.workspace_id}")
"""

import os
import re
import json
import hashlib
import secrets
import time
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field


# === constants =============================================================

KEY_PREFIX = "aeo_"        # short, recognizable prefix
KEY_BYTES = 32             # 256-bit keys
KEY_RATE_DEFAULT = 100     # default requests per minute per key


# === helpers ===============================================================

def _random_key() -> str:
    """Generate a cryptographically random API key string."""
    return KEY_PREFIX + secrets.token_hex(KEY_BYTES)


def _hash_key(key: str) -> str:
    """Return a SHA-256 hex digest of the key (not reversible)."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _prefix_from_key(key: str) -> str:
    """Extract a short prefix for display purposes."""
    if key.startswith(KEY_PREFIX):
        return key[:len(KEY_PREFIX) + 8] + "..."
    return key[:12] + "..."


def _generate_id() -> str:
    return secrets.token_urlsafe(8)


def _now() -> float:
    return time.time()


# === models ================================================================

@dataclass
class ApiKey:
    id: str
    name: str
    key_hash: str
    prefix: str               # display-only prefix e.g. "aeo_a1b2c3d4..."
    workspace_id: str
    user_id: Optional[str] = None
    enabled: bool = True
    rate_limit_per_min: int = KEY_RATE_DEFAULT
    created_at: float = field(default_factory=_now)
    last_used_at: Optional[float] = None
    expires_at: Optional[float] = None  # None = never expires

    def to_dict(self, include_hash: bool = False) -> Dict[str, Any]:
        data = {
            "id": self.id,
            "name": self.name,
            "prefix": self.prefix,
            "workspace_id": self.workspace_id,
            "user_id": self.user_id,
            "enabled": self.enabled,
            "rate_limit_per_min": self.rate_limit_per_min,
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
            "expires_at": self.expires_at,
        }
        if include_hash:
            data["key_hash"] = self.key_hash
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ApiKey":
        return cls(
            id=data["id"],
            name=data.get("name", "Unnamed"),
            key_hash=data["key_hash"],
            prefix=data.get("prefix", ""),
            workspace_id=data.get("workspace_id", "default"),
            user_id=data.get("user_id"),
            enabled=data.get("enabled", True),
            rate_limit_per_min=data.get("rate_limit_per_min", KEY_RATE_DEFAULT),
            created_at=data.get("created_at", _now()),
            last_used_at=data.get("last_used_at"),
            expires_at=data.get("expires_at"),
        )


@dataclass
class KeyUsageEvent:
    key_id: str
    action: str
    timestamp: float
    ip: str = ""
    endpoint: str = ""
    status: int = 200


# === manager ===============================================================

class ApiKeyManager:
    """Create, revoke, list, and validate API keys with rate limiting."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.keys_dir = self.root / "api_keys"
        self.keys_dir.mkdir(parents=True, exist_ok=True)
        self.keys_file = self.keys_dir / "keys.json"
        self.usage_file = self.keys_dir / "usage.jsonl"
        self._keys: Dict[str, ApiKey] = {}  # key_hash -> ApiKey
        self._rate_buckets: Dict[str, List[float]] = {}  # key_hash -> timestamps
        self._load()

    # ── Persistence ─────────────────────────────────────────────────────

    def _load(self) -> None:
        if self.keys_file.exists():
            try:
                data = json.loads(self.keys_file.read_text(encoding="utf-8"))
                for item in data:
                    try:
                        k = ApiKey.from_dict(item)
                        self._keys[k.key_hash] = k
                    except Exception:
                        pass
            except Exception:
                pass

    def _save(self) -> None:
        self.keys_file.write_text(
            json.dumps([k.to_dict(include_hash=True) for k in self._keys.values()], indent=2),
            encoding="utf-8",
        )

    def _log_usage(self, event: KeyUsageEvent) -> None:
        with self.usage_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "key_id": event.key_id,
                "action": event.action,
                "timestamp": event.timestamp,
                "ip": event.ip,
                "endpoint": event.endpoint,
                "status": event.status,
            }, ensure_ascii=False) + "\n")

    # ── CRUD ────────────────────────────────────────────────────────────

    def create_key(
        self,
        name: str,
        workspace_id: str = "default",
        user_id: Optional[str] = None,
        rate_limit_per_min: int = KEY_RATE_DEFAULT,
        expires_at: Optional[float] = None,
    ) -> Tuple[ApiKey, str]:
        """Create a new API key and return (ApiKey, plaintext).
        The plaintext is only returned once — store it securely.
        """
        plaintext = _random_key()
        key_hash = _hash_key(plaintext)
        key = ApiKey(
            id=_generate_id(),
            name=name,
            key_hash=key_hash,
            prefix=_prefix_from_key(plaintext),
            workspace_id=workspace_id,
            user_id=user_id,
            rate_limit_per_min=rate_limit_per_min,
            expires_at=expires_at,
        )
        self._keys[key_hash] = key
        self._save()
        return key, plaintext

    def revoke_key(self, key_hash_or_id: str) -> bool:
        """Revoke (delete) a key by its hash or id."""
        # Try by hash first, then by id
        if key_hash_or_id in self._keys:
            del self._keys[key_hash_or_id]
            self._save()
            return True
        for k_hash, k in list(self._keys.items()):
            if k.id == key_hash_or_id:
                del self._keys[k_hash]
                self._save()
                return True
        return False

    def list_keys(self, workspace_id: Optional[str] = None) -> List[ApiKey]:
        keys = list(self._keys.values())
        if workspace_id:
            keys = [k for k in keys if k.workspace_id == workspace_id]
        # Sort by created_at descending
        keys.sort(key=lambda k: k.created_at, reverse=True)
        return keys

    def get_key_by_id(self, key_id: str) -> Optional[ApiKey]:
        for k in self._keys.values():
            if k.id == key_id:
                return k
        return None

    def update_key(
        self,
        key_id: str,
        name: Optional[str] = None,
        enabled: Optional[bool] = None,
        rate_limit_per_min: Optional[int] = None,
    ) -> Optional[ApiKey]:
        key = self.get_key_by_id(key_id)
        if not key:
            return None
        if name is not None:
            key.name = name
        if enabled is not None:
            key.enabled = enabled
        if rate_limit_per_min is not None:
            key.rate_limit_per_min = rate_limit_per_min
        key.last_used_at = _now()
        self._save()
        return key

    # ── Validation ──────────────────────────────────────────────────────

    def validate_key(self, plaintext: str) -> Optional[ApiKey]:
        """Validate an API key string. Returns the ApiKey if valid, None otherwise."""
        key_hash = _hash_key(plaintext)
        key = self._keys.get(key_hash)
        if not key:
            return None
        if not key.enabled:
            return None
        if key.expires_at and _now() > key.expires_at:
            return None
        return key

    def check_rate_limit(self, key_hash: str) -> bool:
        """Check if the key has exceeded its rate limit. Returns True if allowed."""
        key = self._keys.get(key_hash)
        if not key:
            return True  # default allow
        now = _now()
        window = 60  # 1-minute sliding window
        bucket = self._rate_buckets.setdefault(key_hash, [])
        # Prune old entries
        bucket[:] = [t for t in bucket if now - t < window]
        if len(bucket) >= key.rate_limit_per_min:
            return False
        bucket.append(now)
        return True

    def record_key_usage(
        self,
        key: ApiKey,
        action: str = "api_call",
        ip: str = "",
        endpoint: str = "",
        status: int = 200,
    ) -> None:
        key.last_used_at = _now()
        self._save()
        event = KeyUsageEvent(
            key_id=key.id,
            action=action,
            timestamp=_now(),
            ip=ip,
            endpoint=endpoint,
            status=status,
        )
        self._log_usage(event)

    def get_usage_stats(
        self,
        key_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Return usage statistics for keys, optionally filtered."""
        cutoff = _now() - (days * 24 * 3600)
        total_calls = 0
        errors = 0
        by_key: Dict[str, Dict[str, Any]] = {}
        by_endpoint: Dict[str, int] = {}

        if not self.usage_file.exists():
            return self._empty_stats(key_id, workspace_id, days)

        with self.usage_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                if ev.get("timestamp", 0) < cutoff:
                    continue

                # Filter by specific key_id
                if key_id and ev.get("key_id") != key_id:
                    continue

                # Filter by workspace
                if workspace_id:
                    k_obj = self.get_key_by_id(ev.get("key_id", ""))
                    if not k_obj or k_obj.workspace_id != workspace_id:
                        continue

                total_calls += 1
                if ev.get("status", 200) >= 400:
                    errors += 1

                kid = ev.get("key_id", "unknown")
                if kid not in by_key:
                    k_obj = self.get_key_by_id(kid)
                    by_key[kid] = {
                        "key_id": kid,
                        "name": k_obj.name if k_obj else "unknown",
                        "calls": 0,
                        "errors": 0,
                    }
                by_key[kid]["calls"] += 1
                if ev.get("status", 200) >= 400:
                    by_key[kid]["errors"] += 1

                ep = ev.get("endpoint", "unknown")
                by_endpoint[ep] = by_endpoint.get(ep, 0) + 1

        return {
            "period_days": days,
            "workspace_id": workspace_id,
            "key_id": key_id,
            "total_calls": total_calls,
            "errors": errors,
            "error_rate": round(errors / max(total_calls, 1) * 100, 2),
            "by_key": list(by_key.values()),
            "by_endpoint": dict(sorted(by_endpoint.items(), key=lambda x: -x[1])[:20]),
        }

    def _empty_stats(self, key_id: Optional[str], workspace_id: Optional[str], days: int) -> Dict[str, Any]:
        return {
            "period_days": days,
            "workspace_id": workspace_id,
            "key_id": key_id,
            "total_calls": 0,
            "errors": 0,
            "error_rate": 0.0,
            "by_key": [],
            "by_endpoint": {},
        }
