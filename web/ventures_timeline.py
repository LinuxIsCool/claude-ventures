# web/ventures_timeline.py
"""Assemble a per-venture timeline of dated items.

Read-through to ~/.claude/local/ventures/ (venture frontmatter) +
~/.claude/local/backlog/*.md (tasks). No DB. Reuses VenturesAccessor for the
venture parse (slug/title/milestones/deadlines) and ventures_backlog for the
venture-linked task join.

Dated items collected per venture:
  - milestones with a parseable `date` (YYYY-MM-DD)  -> type "milestone"
  - deadlines  with a parseable `date` (YYYY-MM-DD)  -> type "deadline"
  - backlog tasks with a parseable `due` (YYYY-MM-DD) -> type "task"
    (a task lands in the lane of the venture it is linked to via `venture:`)

A lane is emitted only for ventures that have >= 1 dated item. Ventures with NO
dated items are OMITTED entirely (no empty lanes). Each lane's `items` are sorted
by date ascending. `range` is the min/max date across ALL items in ALL lanes, or
{"min": None, "max": None} when nothing is dated anywhere.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

import ventures_backlog
from ventures_accessor import VenturesAccessor


def _parse_date(raw: Any) -> str | None:
    """Return a normalized 'YYYY-MM-DD' string if parseable, else None."""
    s = str(raw or "").strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def timeline(ventures_root, backlog_dir, today: date) -> dict:
    acc = VenturesAccessor(data_root=Path(ventures_root), today=today)
    # Join the whole backlog ONCE (cached, per-file), grouped by venture, instead
    # of re-scanning all backlog files per venture.
    tasks_by_venture = ventures_backlog.tasks_by_venture(Path(backlog_dir))

    lanes: list[dict[str, Any]] = []
    all_dates: list[str] = []

    for v in acc.list({}):
        slug = v["slug"]
        rec = acc.detail(slug)
        items: list[dict[str, Any]] = []

        for ms in rec.get("milestones", []):
            if not isinstance(ms, dict):
                continue
            d = _parse_date(ms.get("date"))
            if d is None:
                continue
            items.append({
                "type": "milestone",
                "id": str(ms.get("id") or ""),
                "title": str(ms.get("title") or ""),
                "date": d,
                "status": str(ms.get("status") or ""),
                "priority": str(ms.get("priority") or ""),
            })

        for dl in rec.get("deadlines", []):
            if not isinstance(dl, dict):
                continue
            d = _parse_date(dl.get("date"))
            if d is None:
                continue
            items.append({
                "type": "deadline",
                "id": str(dl.get("id") or ""),
                "title": str(dl.get("label") or ""),
                "date": d,
                "status": str(dl.get("status") or ""),
                "priority": str(dl.get("priority") or ""),
            })

        for t in tasks_by_venture.get(slug, []):
            d = _parse_date(t.get("due"))
            if d is None:
                continue
            items.append({
                "type": "task",
                "id": str(t.get("id") or ""),
                "title": str(t.get("title") or ""),
                "date": d,
                "status": str(t.get("status") or ""),
                "priority": str(t.get("priority") or ""),
            })

        if not items:
            continue

        items.sort(key=lambda i: i["date"])
        all_dates.extend(i["date"] for i in items)
        lanes.append({"venture": slug, "title": rec.get("title", slug), "items": items})

    rng = (
        {"min": min(all_dates), "max": max(all_dates)}
        if all_dates
        else {"min": None, "max": None}
    )
    return {"lanes": lanes, "range": rng}
