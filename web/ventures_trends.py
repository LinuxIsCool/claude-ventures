# web/ventures_trends.py
"""Assemble trend time-series for the ventures portfolio.

Two families of series:

DERIVABLE — computed directly from current venture data (no history needed):
  - milestones_reached_cumulative: cumulative count of COMPLETED milestones that
    carry a parseable date (`completed` date string or `date`), grouped by date,
    sorted ascending, with a running cumulative sum.
  - deadline_pressure: for the next 12 ISO weeks starting this week, the count of
    future (not-passed) deadlines whose date falls within each week. One point per
    week keyed by the week's Monday (ISO week start).

SNAPSHOT-BASED — read from the append-only JSONL snapshot rows (may be a single
point until history accrues):
  - tasks_open            <- row["tasks_open"]
  - deadlines_overdue     <- row["deadlines_overdue"]
  - milestones_complete   <- row["milestones_complete"]
  - ventures_by_stage     <- row["by_stage"] (value is the dict; frontend stacks it)

Behaviour: trends() first lazily ensures today's snapshot row exists (best-effort;
a write failure is logged to stderr and does not abort), then loads all rows for
the snapshot-based series. The derivable series are always served even if the
snapshot write fails.

Read-through to ~/.claude/local/ventures/ via VenturesAccessor. No DB.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import ventures_snapshot
from ventures_accessor import VenturesAccessor

_DERIVABLE = [
    "milestones_reached_cumulative",
    "deadline_pressure",
]
_SNAPSHOT_BASED = [
    "tasks_open",
    "deadlines_overdue",
    "milestones_complete",
    "ventures_by_stage",
]

_DONE_STATUSES = {"done", "complete", "completed", "closed", "cancelled"}


def _parse_date(raw: Any) -> str | None:
    """Return a normalized 'YYYY-MM-DD' string if parseable, else None."""
    s = str(raw or "").strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def _milestone_completed_date(m: dict[str, Any]) -> str | None:
    """Date a milestone was completed, if it is complete AND dated.

    A milestone counts when it is done (via `completed` truthy or a done
    `status`) and carries a parseable date. The `completed` field may itself be
    a date string; otherwise fall back to `date`.
    """
    completed = m.get("completed")
    status = str(m.get("status") or "").strip().lower()
    is_done = bool(completed) or status in _DONE_STATUSES
    if not is_done:
        return None
    # `completed` may be a date string; prefer it, else `date`.
    return _parse_date(completed) or _parse_date(m.get("date"))


def _milestones_reached_cumulative(acc: VenturesAccessor) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for v in acc.list({}):
        rec = acc.detail(v["slug"])
        for m in rec.get("milestones") or []:
            if not isinstance(m, dict):
                continue
            d = _milestone_completed_date(m)
            if d is None:
                continue
            counts[d] = counts.get(d, 0) + 1
    series: list[dict[str, Any]] = []
    running = 0
    for d in sorted(counts):
        running += counts[d]
        series.append({"date": d, "value": running})
    return series


def _deadline_pressure(acc: VenturesAccessor, today: date) -> list[dict[str, Any]]:
    # 12 ISO weeks starting this week (Monday of the current week).
    week_start = today - timedelta(days=today.weekday())
    bounds = [week_start + timedelta(weeks=i) for i in range(13)]  # 12 buckets

    # Collect future (not-passed) deadline dates across all ventures.
    deadline_dates: list[date] = []
    for v in acc.list({}):
        rec = acc.detail(v["slug"])
        for dl in rec.get("deadlines") or []:
            if not isinstance(dl, dict):
                continue
            iso = _parse_date(dl.get("date"))
            if iso is None:
                continue
            d = datetime.strptime(iso, "%Y-%m-%d").date()
            if d < today:
                continue  # passed
            deadline_dates.append(d)

    series: list[dict[str, Any]] = []
    for i in range(12):
        lo, hi = bounds[i], bounds[i + 1]
        count = sum(1 for d in deadline_dates if lo <= d < hi)
        series.append({"date": lo.isoformat(), "value": count})
    return series


def trends(ventures_root, backlog_dir, today: date, snapshot_path=None) -> dict:
    """Build derivable + snapshot-based trend series. See module docstring."""
    if snapshot_path is None:
        snapshot_path = ventures_snapshot._SNAPSHOT_PATH_DEFAULT
    snapshot_path = Path(snapshot_path)

    # 1. Lazily ensure today's snapshot row (best-effort; never abort on error).
    try:
        ventures_snapshot.ensure_today(snapshot_path, ventures_root, backlog_dir, today)
    except Exception as exc:  # noqa: BLE001
        print(f"[ventures-web] trends: snapshot ensure failed: {exc}", file=sys.stderr)

    # 2. Load snapshot rows for snapshot-based series. Sort by date so a
    # backfilled/replayed past date can't put the series out of time order
    # (lineChart plots by array index, and the "latest" label reads rows[-1]).
    rows = sorted(ventures_snapshot.load(snapshot_path), key=lambda r: r.get("date", ""))

    acc = VenturesAccessor(data_root=Path(ventures_root), today=today)

    series: dict[str, Any] = {
        "milestones_reached_cumulative": _milestones_reached_cumulative(acc),
        "deadline_pressure": _deadline_pressure(acc, today),
        "tasks_open": [
            {"date": r["date"], "value": r.get("tasks_open", 0)}
            for r in rows
            if r.get("date")
        ],
        "deadlines_overdue": [
            {"date": r["date"], "value": r.get("deadlines_overdue", 0)}
            for r in rows
            if r.get("date")
        ],
        "milestones_complete": [
            {"date": r["date"], "value": r.get("milestones_complete", 0)}
            for r in rows
            if r.get("date")
        ],
        "ventures_by_stage": [
            {"date": r["date"], "value": r.get("by_stage", {})}
            for r in rows
            if r.get("date")
        ],
    }

    return {
        "series": series,
        "derivable": list(_DERIVABLE),
        "snapshot_based": list(_SNAPSHOT_BASED),
    }
