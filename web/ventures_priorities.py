# web/ventures_priorities.py
"""Cross-venture priority ranking — a transparent, explainable score.

Combines open venture-linked backlog tasks and live venture deadlines into a
single ranked feed. The score is intentionally simple and additive so the UI
can show *why* something ranks where it does (score_parts always sum to score).

Read-through only: ventures come from `VenturesAccessor`, tasks from
`ventures_backlog._cached_tasks`. No DB.

Scoring formula (score = urgency + manual + stage, 0-90)
---------------------------------------------------------------------
urgency   (0-50): from the item's own date (task `due`, deadline `date`) vs today
                  - overdue (days < 0)            -> 50
                  - due today (days == 0)         -> 45
                  - 1..30 days out                -> max(0, round(45 * (1 - days/30)))
                  - >30 days out, or no date      -> 0
manual    (0-30): item priority band
                  - critical=30, high=22, medium=12, low=4 (default medium)
stage     (0-10): the VENTURE's stage
                  - active=10, exploring=6, sustaining=6, seed=4, dormant=2, harvesting=0

Sort: score DESC, tie-break by due ASC. An empty due ("") sorts last.

Items
-----
(a) Open venture-linked backlog tasks. "Open" = status NOT in
    {done, complete, completed, closed, cancelled}. A task is venture-linked
    when `ventures_backlog.tasks_for(slug)` returns it (covers both the
    `venture:` field and the composite `parent_id`). ref = {"task": id, "v": slug}.
(b) Venture deadlines, with the same overdue exclusions the accessor applies
    (harvesting ventures skipped; per-deadline "reached"/complete skipped).
    ref = {"v": slug}.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from ventures_accessor import VenturesAccessor
from ventures_backlog import tasks_for

_CLOSED_STATUSES = {"done", "complete", "completed", "closed", "cancelled"}

_MANUAL_BAND = {"critical": 30, "high": 22, "medium": 12, "low": 4}
_STAGE_BAND = {
    "active": 10,
    "exploring": 6,
    "sustaining": 6,
    "seed": 4,
    "dormant": 2,
    "harvesting": 0,
}


def _parse_date(raw: str) -> date | None:
    raw = str(raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _urgency(item_date: date | None, today: date) -> int:
    if item_date is None:
        return 0
    days = (item_date - today).days
    if days < 0:
        return 50
    if days == 0:
        return 45
    if days <= 30:
        return max(0, round(45 * (1 - days / 30)))
    return 0


def _manual(priority: str) -> int:
    return _MANUAL_BAND.get(str(priority or "medium").strip().lower(), _MANUAL_BAND["medium"])


def _stage(stage: str) -> int:
    return _STAGE_BAND.get(str(stage or "").strip().lower(), 0)


def _score(item_date: date | None, priority: str, venture: dict[str, Any], today: date) -> dict[str, int]:
    parts = {
        "urgency": _urgency(item_date, today),
        "manual": _manual(priority),
        "stage": _stage(venture.get("stage", "")),
    }
    return parts


def ranked(ventures_root, backlog_dir, today: date) -> dict:
    ventures_root = Path(ventures_root)
    backlog_dir = Path(backlog_dir)
    acc = VenturesAccessor(data_root=ventures_root, today=today)

    items: list[dict[str, Any]] = []

    # detail() returns the full parsed record (incl. stage, financial, _overdue
    # via deadlines). We re-derive overdue via the accessor's own _parse to
    # honour the same exclusions, so iterate files through the accessor.
    for lifecycle, md in acc._iter_files():
        v = acc._parse(lifecycle, md)
        if v is None:
            continue
        slug = v["slug"]

        # (a) open venture-linked backlog tasks
        for t in tasks_for(slug, backlog_dir=backlog_dir):
            if str(t.get("status", "")).strip().lower() in _CLOSED_STATUSES:
                continue
            due = str(t.get("due") or "")
            d = _parse_date(due)
            priority = str(t.get("priority", "medium"))
            parts = _score(d, priority, v, today)
            items.append({
                "kind": "task",
                "venture": slug,
                "title": t.get("title", ""),
                "due": due,
                "priority": priority,
                "score": sum(parts.values()),
                "score_parts": parts,
                "ref": {"task": t.get("id"), "v": slug},
            })

        # (b) venture deadlines (respect overdue exclusions: harvesting skipped,
        # reached/complete skipped). We surface ALL still-relevant deadlines, not
        # only overdue ones, scoring urgency from the deadline date.
        if lifecycle == "harvesting":
            deadlines = []
        else:
            deadlines = [dl for dl in v["deadlines"] if not _deadline_excluded(dl)]
        for dl in deadlines:
            raw = str(dl.get("date", "")).strip()
            d = _parse_date(raw)
            # venture priority drives the manual band for deadlines
            priority = str(v.get("priority", "medium"))
            parts = _score(d, priority, v, today)
            items.append({
                "kind": "deadline",
                "venture": slug,
                "title": dl.get("label", ""),
                "due": raw,
                "priority": priority,
                "score": sum(parts.values()),
                "score_parts": parts,
                "ref": {"v": slug},
            })

    # sort: score DESC, then due ASC with "" last
    items.sort(key=lambda it: (-it["score"], it["due"] or "9999-99-99"))
    return {
        "items": items,
        "formula_version": 2,
        "signals_available": {"urgency": True, "manual": True, "stage": True, "financial": False},
    }


def _deadline_excluded(dl: dict[str, Any]) -> bool:
    """Mirror VenturesAccessor._is_overdue exclusions (minus the date test):
    skip deadlines marked complete/done or of a 'reached' type."""
    status = str(dl.get("status", "")).strip().lower()
    if status in {"complete", "completed", "done"}:
        return True
    if "reached" in str(dl.get("type", "")).strip().lower():
        return True
    return False
