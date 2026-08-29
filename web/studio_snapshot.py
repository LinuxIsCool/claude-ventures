"""The Studio live-state snapshot file: one JSON document the poller writes
atomically and the webui reads with zero I/O beyond one file read.

Staleness is a rule, not a guess: missing, unreadable, or older than three
poll intervals is stale, and the page says so on every badge.
Spec: backlog task-824 section 6.3.
"""
from __future__ import annotations
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SNAPSHOT_DEFAULT = Path.home() / ".claude" / "local" / "ventures" / "runtime" / "studio-snapshot.json"
DEFAULT_INTERVAL_S = 60


def is_stale(age_s: float | None, interval_s: int) -> bool:
    return age_s is None or age_s > 3 * interval_s


def write_snapshot(data: dict[str, Any], path: Path | None = None) -> Path:
    target = Path(path) if path else SNAPSHOT_DEFAULT
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".studio-snapshot.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, separators=(",", ":"))
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return target


def read_snapshot(path: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    target = Path(path) if path else SNAPSHOT_DEFAULT
    empty = {"present": False, "data": None, "generated_at": None, "age_s": None, "stale": True, "interval_s": DEFAULT_INTERVAL_S}
    if not target.is_file():
        return empty
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        gen = datetime.fromisoformat(str(data["generated_at"]))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        return dict(empty, error=f"snapshot unreadable: {exc}")
    if gen.tzinfo is None:
        gen = gen.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    interval = int(data.get("interval_s") or DEFAULT_INTERVAL_S)
    age = (current - gen).total_seconds()
    return {"present": True, "data": data, "generated_at": gen.isoformat(), "age_s": age, "stale": is_stale(age, interval), "interval_s": interval}
