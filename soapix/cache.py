"""
WSDL parse result cache — avoids re-parsing on every client instantiation.

Two backends:
- MemoryCache: in-process dict, cleared when process exits
- FileCache: persists parsed results to disk as pickle (optional)
"""

from __future__ import annotations

import hashlib
import pickle
import threading
import time
from pathlib import Path
from typing import Any


class MemoryCache:
    """
    Simple in-memory LRU-like cache with optional TTL.

    Usage:
        cache = MemoryCache(ttl=300)   # 5 minute TTL
        cache.set("key", value)
        value = cache.get("key")       # None if expired or missing
    """

    def __init__(self, ttl: float | None = None, maxsize: int = 64) -> None:
        self._ttl = ttl
        self._maxsize = maxsize
        self._store: dict[str, tuple[Any, float]] = {}  # key → (value, timestamp)
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, ts = entry
            if self._ttl is not None and (time.monotonic() - ts) > self._ttl:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            # Purge expired entries first to reclaim space
            if self._ttl is not None:
                now = time.monotonic()
                expired = [k for k, (_, ts) in self._store.items() if (now - ts) > self._ttl]
                for k in expired:
                    del self._store[k]
            # Evict oldest entry if still at capacity
            if len(self._store) >= self._maxsize and key not in self._store:
                oldest = min(self._store, key=lambda k: self._store[k][1])
                del self._store[oldest]
            self._store[key] = (value, time.monotonic())

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)


class FileCache:
    """
    Disk-based cache that serializes WsdlDocument objects with pickle.

    Cache files are stored in a directory and keyed by URL/path hash.
    """

    def __init__(
        self,
        cache_dir: str | Path = ".soapix_cache",
        ttl: float | None = 3600,
    ) -> None:
        self._dir = Path(cache_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._ttl = ttl

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode()).hexdigest()[:16]
        return self._dir / f"{digest}.pkl"

    def get(self, key: str) -> Any | None:
        p = self._path(key)
        if not p.exists():
            return None
        # Ensure the resolved path stays within our cache directory
        try:
            p.resolve().relative_to(self._dir.resolve())
        except ValueError:
            return None
        if self._ttl is not None:
            age = time.time() - p.stat().st_mtime
            if age > self._ttl:
                p.unlink(missing_ok=True)
                return None
        try:
            return pickle.loads(p.read_bytes())
        except Exception:
            p.unlink(missing_ok=True)
            return None

    def set(self, key: str, value: Any) -> None:
        try:
            self._path(key).write_bytes(pickle.dumps(value))
        except Exception:
            pass  # cache write failure is non-fatal

    def clear(self) -> None:
        for p in self._dir.glob("*.pkl"):
            p.unlink(missing_ok=True)

    def __len__(self) -> int:
        return len(list(self._dir.glob("*.pkl")))


# Module-level default memory cache (shared across all SoapClient instances)
_default_cache: MemoryCache = MemoryCache(ttl=300)


def get_default_cache() -> MemoryCache:
    return _default_cache


def make_cache_key(location: str, strict: bool) -> str:
    return f"{location}|strict={strict}"
