# web/ventures_cache.py
"""One mtime-signature cache, shared by every read-through module.

Three modules independently reimplemented the same eight lines: build a
signature from file mtimes, compare it against a stored one, rebuild only on
change. This is that pattern, once.

Contract:
  - `mtime_signature(paths)` is a stable, order-independent fingerprint of a
    set of files. Equal signature => none of those files changed.
  - `cached(store, key, signature, build)` returns the memoized value for
    `key`, rebuilding via `build()` only when the signature differs.
  - Callers must not mutate returned values; they are shared.

Robustness note: a path that disappears between glob and stat is skipped
rather than raised. A vanished file legitimately changes the signature (it
drops out), so the next call rebuilds. The previous per-module implementations
would have raised OSError mid-request instead.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Hashable, Iterable

Signature = tuple[tuple[str, int], ...]


def mtime_signature(paths: Iterable[Path]) -> Signature:
    """Order-independent (path, mtime_ns) fingerprint over `paths`."""
    out: list[tuple[str, int]] = []
    for p in paths:
        try:
            out.append((str(p), p.stat().st_mtime_ns))
        except OSError:
            continue  # vanished mid-scan; its absence is itself a change
    return tuple(sorted(out))


def cached(
    store: dict[Any, dict[str, Any]],
    key: Hashable,
    signature: Signature,
    build: Callable[[], Any],
) -> Any:
    """Memoize `build()` under `key`, invalidated when `signature` changes.

    `store` is a caller-owned module-level dict, so each module keeps its own
    namespace and its own lifetime while sharing this logic.
    """
    entry = store.get(key)
    if entry is None or entry["sig"] != signature:
        store[key] = {"sig": signature, "value": build()}
    return store[key]["value"]
