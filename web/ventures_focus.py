# web/ventures_focus.py
"""Focus buckets — what needs attention, bucketed by time-to-date.

Collapses every dated, still-relevant item across the portfolio into four
time-relative buckets so the UI can answer "what do I look at right now?".

Read-through only: ventures come from `VenturesAccessor` (reusing its
`_is_overdue` exclusions so the "attention" deadline count stays in lockstep
with `stats()["overdue_total"]`), tasks from `ventures_backlog.tasks_for`. No DB.

Buckets, by `days = (item_date - today).days`:
  - days < 0           -> "attention"   (overdue / past due)
  - days == 0          -> "today"
  - 1 <= days <= 7     -> "this_week"
  - 8 <= days <= 30    -> "soon"
  - days > 30          -> dropped

Dated item sources:
  (a) venture `deadlines[]` with a parseable `date`, respecting the accessor's
      overdue exclusions: skip done-status + "reached"-type deadlines, and
      harvesting-lifecycle ventures contribute nothing to "attention". Future
      deadlines (>= today) still surface in today/this_week/soon.
  (b) venture `milestones[]` with a parseable `date` that are not complete
      (`completed` falsy and status not in {done, complete, completed}).
  (c) backlog tasks with a parseable `due` and open status (status NOT in
      {done, complete, completed, closed, cancelled}), venture-linked
      (`tasks_for` covers both the `venture:` field and composite `parent_id`).

ref shape per kind:
  deadline  -> {"v": venture_slug}
  milestone -> {"v": slug, "m": milestone_id}
  task      -> {"task": task_id, "v": venture_slug}

Each bucket is sorted by date ascending; "attention" is sorted most-overdue
first (most negative `days` first).
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

import ventures_backlog
from ventures_accessor import VenturesAccessor

_CLOSED_TASK_STATUSES = {"done", "complete", "completed", "closed", "cancelled"}
_MILESTONE_DONE_STATUSES = {"done", "complete", "completed"}


def _parse_date(raw: Any) -> date | None:
    s = str(raw or "").strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def _bucket_for(days: int) -> str | None:
    if days < 0:
        return "attention"
    if days == 0:
        return "today"
    if 1 <= days <= 7:
        return "this_week"
    if 8 <= days <= 30:
        return "soon"
    return None  # days > 30 -> dropped


def buckets(ventures_root, backlog_dir, today: date) -> dict:
    ventures_root = Path(ventures_root)
    backlog_dir = Path(backlog_dir)
    acc = VenturesAccessor(data_root=ventures_root, today=today)

    out: dict[str, list[dict[str, Any]]] = {
        "today": [],
        "this_week": [],
        "soon": [],
        "attention": [],
    }

    def _add(item: dict[str, Any]) -> None:
        bucket = _bucket_for(item["days"])
        if bucket is not None:
            out[bucket].append(item)

    for lifecycle, md in acc._iter_files():
        v = acc._parse(lifecycle, md)
        if v is None:
            continue
        slug = v["slug"]

        # (a) venture deadlines — reuse the accessor's exclusions verbatim so
        # the overdue (attention) subset matches stats()["overdue_total"].
        for dl in v["deadlines"]:
            d = _parse_date(dl.get("date"))
            if d is None:
                continue
            days = (d - today).days
            # Honour overdue exclusions for the "attention" bucket: a deadline
            # that the accessor would NOT count as overdue must not appear in
            # attention. _is_overdue encodes done/reached + the date test;
            # harvesting ventures contribute no overdue (mirrors _parse, which
            # zeroes _overdue for harvesting).
            if days < 0:
                if lifecycle == "harvesting" or not acc._is_overdue(dl):
                    continue
            _add({
                "kind": "deadline",
                "venture": slug,
                "title": str(dl.get("label") or ""),
                "date": d.isoformat(),
                "days": days,
                "priority": str(v.get("priority", "medium")),
                "ref": {"v": slug},
            })

        # (b) venture milestones — dated and not complete
        for ms in v["milestones"]:
            if not isinstance(ms, dict):
                continue
            d = _parse_date(ms.get("date"))
            if d is None:
                continue
            if ms.get("completed"):
                continue
            if str(ms.get("status", "")).strip().lower() in _MILESTONE_DONE_STATUSES:
                continue
            days = (d - today).days
            _add({
                "kind": "milestone",
                "venture": slug,
                "title": str(ms.get("title") or ""),
                "date": d.isoformat(),
                "days": days,
                "priority": str(ms.get("priority") or v.get("priority", "medium")),
                "ref": {"v": slug, "m": str(ms.get("id") or "")},
            })

        # (c) venture-linked backlog tasks — open and dated
        for t in ventures_backlog.tasks_for(slug, backlog_dir=backlog_dir):
            if str(t.get("status", "")).strip().lower() in _CLOSED_TASK_STATUSES:
                continue
            d = _parse_date(t.get("due"))
            if d is None:
                continue
            days = (d - today).days
            _add({
                "kind": "task",
                "venture": slug,
                "title": str(t.get("title") or ""),
                "date": d.isoformat(),
                "days": days,
                "priority": str(t.get("priority", "medium")),
                "ref": {"task": t.get("id"), "v": slug},
            })

    for key in ("today", "this_week", "soon"):
        out[key].sort(key=lambda i: i["date"])
    # attention: most-overdue first => most negative days first
    out["attention"].sort(key=lambda i: i["days"])
    return out
