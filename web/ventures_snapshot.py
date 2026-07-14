# plugins/claude-ventures/web/ventures_snapshot.py
"""Daily ventures metrics snapshot — append-only JSONL time-series.

Computes one snapshot row over the read-through ventures store
(VenturesAccessor) + venture-linked backlog tasks (ventures_backlog).
No webui DB — the JSONL file IS the store (one row per day).

Contract:
  compute(ventures_root, backlog_dir, today) -> dict   (one row)
  load(path) -> list[dict]                              ([] if missing)
  append(path, row) -> None                             (append one line)
  ensure_today(path, ventures_root, backlog_dir, today) -> dict
      idempotent per-date: re-running the same day yields exactly one row.

A "venture-linked" task has a non-empty `venture` field OR a non-empty
`_parent_id`. Done-set: {done, complete, completed, closed, cancelled}.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from ventures_accessor import VenturesAccessor
from ventures_backlog import _cached_tasks

_DONE_STATUSES = {"done", "complete", "completed", "closed", "cancelled"}

_SNAPSHOT_PATH_DEFAULT = (
    Path.home() / ".claude" / "local" / "ventures" / "metrics" / "snapshots.jsonl"
)


def _is_done(status: Any) -> bool:
    return str(status or "").strip().lower() in _DONE_STATUSES


def _milestone_complete(m: dict[str, Any]) -> bool:
    if m.get("completed"):
        return True
    return _is_done(m.get("status"))


def compute(ventures_root, backlog_dir, today: date) -> dict[str, Any]:
    """Build a single snapshot row for `today`."""
    acc = VenturesAccessor(data_root=Path(ventures_root), today=today)
    stats = acc.stats()

    # by_stage: prefer accessor's lifecycle rollup (zero counts dropped so the
    # row stays compact), falling back to the stage field is unnecessary since
    # stats() already buckets by lifecycle dir.
    by_stage = {stage: n for stage, n in stats["by_lifecycle"].items() if n}

    ventures_total = sum(stats["by_lifecycle"].values())

    milestones_total = 0
    milestones_complete = 0
    revenue_total = 0.0
    for v in acc.list({}):
        rec = acc.detail(v["slug"])
        for m in rec.get("milestones") or []:
            if not isinstance(m, dict):
                continue
            milestones_total += 1
            if _milestone_complete(m):
                milestones_complete += 1
        fin = rec.get("financial") or {}
        if isinstance(fin, dict):
            # Coerce string-valued revenue ("10000") consistently with
            # ventures_priorities / ventures_trends — same field, same signal.
            try:
                revenue_total += float(fin.get("revenue_to_date") or 0)
            except (TypeError, ValueError):
                pass

    tasks_open = 0
    tasks_completed_total = 0
    bdir = Path(backlog_dir)
    if bdir.is_dir():
        for t in _cached_tasks(bdir):
            linked = bool(str(t.get("venture") or "").strip()) or bool(
                str(t.get("_parent_id") or "").strip()
            )
            if not linked:
                continue
            if _is_done(t.get("status")):
                tasks_completed_total += 1
            else:
                tasks_open += 1

    return {
        "date": today.isoformat(),
        "ventures_total": ventures_total,
        "by_stage": by_stage,
        "deadlines_overdue": stats["overdue_total"],
        "tasks_open": tasks_open,
        "tasks_completed_total": tasks_completed_total,
        "milestones_total": milestones_total,
        "milestones_complete": milestones_complete,
        "revenue_total": revenue_total,
    }


def load(path: Path) -> list[dict[str, Any]]:
    """Parse JSONL; return [] if the file is missing."""
    path = Path(path)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def append(path: Path, row: dict[str, Any]) -> None:
    """Create parent dirs and append one JSON line."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def ensure_today(path, ventures_root, backlog_dir, today: date) -> dict[str, Any]:
    """Idempotent: ensure exactly one row exists for `today`.

    Short-circuit: if a row for `today` already exists, return it WITHOUT
    recomputing or rewriting the file. Only compute+write when today's row is
    absent. Re-running on the same day leaves exactly one row for that date.
    On any write error the computed row is still returned (best-effort
    persistence).
    """
    path = Path(path)
    iso = today.isoformat()
    existing = load(path)
    for r in existing:
        if r.get("date") == iso:
            return r

    row = compute(ventures_root, backlog_dir, today)
    try:
        # `existing` (loaded above) has no row for today, so just append.
        rows = existing + [row]
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
    except Exception as exc:  # noqa: BLE001
        print(f"[ventures-web] snapshot write failed: {exc}", file=sys.stderr)
    return row
