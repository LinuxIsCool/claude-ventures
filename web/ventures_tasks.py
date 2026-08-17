"""Truthful task projections for portfolio focus and linked counters."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import ventures_backlog
from ventures_accessor import VenturesAccessor
from ventures_scope import PortfolioScope

_TERMINAL = {"done", "complete", "completed", "closed", "cancelled", "canceled"}
_PRIORITY = {"critical": 0, "urgent": 0, "high": 1, "medium": 2, "low": 3}


def _date(raw: Any) -> date | None:
    try:
        return datetime.strptime(str(raw or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def _venture_id(task: dict) -> str:
    direct = str(task.get("venture") or "").strip()
    if direct:
        return direct
    return str(task.get("_parent_id") or "").split(".", 1)[0]


def _blocked(task: dict) -> bool:
    return bool(task.get("blocked_by") or task.get("dependencies")) or \
        str(task.get("status", "")).strip().lower() == "blocked"


def records(ventures_root: Path, backlog_dir: Path, scope: PortfolioScope,
            today: date) -> list[dict[str, Any]]:
    lifecycles = {v["slug"]: v["lifecycle"]
                  for v in VenturesAccessor(ventures_root, today=today)._records()}
    out = []
    # Internal parent_id is needed to infer older composite-linked records.
    d = Path(backlog_dir)
    source = ventures_backlog._cached_tasks(d) if d.is_dir() else []
    for task in source:
        venture = _venture_id(task)
        lifecycle = lifecycles.get(venture)
        if lifecycle is None or not scope.includes(venture, lifecycle):
            continue
        status = str(task.get("status") or "").strip()
        due = _date(task.get("due"))
        out.append({
            "id": str(task.get("id") or ""),
            "title": str(task.get("title") or ""),
            "status": status,
            "priority": str(task.get("priority") or "medium").lower(),
            "venture": venture,
            "due": due.isoformat() if due else "",
            "days": (due - today).days if due else None,
            "blocked": _blocked(task),
            "active": status.lower() not in _TERMINAL,
            "overdue": status.lower() not in _TERMINAL and due is not None and due < today,
            "href": f"/backlog/tasks/{task.get('id')}",
        })
    return out


def _rank(task: dict) -> tuple:
    # Overdue first, then oldest due date, then explicit priority, then stable ID.
    return (0 if task["overdue"] else 1, task["due"] or "9999-12-31",
            _PRIORITY.get(task["priority"], 9), task["id"])


def _group(tasks: list[dict[str, Any]], today: date) -> dict[str, list[dict[str, Any]]]:
    """Apply the exact focus projection to already-normalized task records."""
    active = [t for t in tasks if t["active"]]
    sunday = today + timedelta(days=(6 - today.weekday()))
    soon_end = today + timedelta(days=30)
    eligible = [t for t in active if not t["blocked"]]
    today_pool = sorted([t for t in eligible if t["days"] is not None and t["days"] <= 0], key=_rank)
    week_pool = sorted([t for t in eligible if t["due"] and today < _date(t["due"]) <= sunday], key=_rank)
    soon_pool = sorted([t for t in eligible if t["due"] and sunday < _date(t["due"]) <= soon_end], key=_rank)
    chosen = {t["id"] for t in today_pool[:2] + week_pool[:3] + soon_pool[:3]}
    return {
        "today": today_pool[:2],
        "this_week": week_pool[:3],
        "soon": soon_pool[:3],
        "backlog": sorted([t for t in active if t["id"] not in chosen], key=_rank),
    }


def focus(ventures_root: Path, backlog_dir: Path, scope: PortfolioScope,
          today: date) -> dict:
    return {"scope": scope.as_dict(), **_group(records(ventures_root, backlog_dir, scope, today), today)}


def card_metrics(ventures_root: Path, backlog_dir: Path, today: date,
                 task_records: list[dict[str, Any]] | None = None) -> dict:
    """Per-venture counts reconciled to the same capped focus projection."""
    venture_ids = {v["slug"] for v in VenturesAccessor(ventures_root, today=today)._records()}
    all_scope = PortfolioScope(frozenset(venture_ids))
    by_venture: dict[str, list[dict[str, Any]]] = {slug: [] for slug in venture_ids}
    for task in task_records if task_records is not None else records(ventures_root, backlog_dir, all_scope, today):
        by_venture[task["venture"]].append(task)
    metrics = {}
    for slug, tasks in by_venture.items():
        grouped = _group(tasks, today)
        metrics[slug] = {
            "today": len(grouped["today"]),
            "this_week": len(grouped["this_week"]),
            "soon": len(grouped["soon"]),
            "backlog": len(grouped["backlog"]),
            # Overdue is an orthogonal warning and may overlap Today.
            "overdue": sum(1 for task in tasks if task["overdue"]),
        }
    return {"as_of": today.isoformat(), "ventures": metrics}


def widget(ventures_root: Path, backlog_dir: Path, scope: PortfolioScope,
           today: date, kind: str, include_records: bool = False) -> dict:
    tasks = records(ventures_root, backlog_dir, scope, today)
    matching = [t for t in tasks if t["active"] and (kind == "active" or t["overdue"])]
    matching.sort(key=_rank)
    payload = {"scope": scope.as_dict(), "kind": kind, "count": len(matching)}
    if include_records:
        payload["records"] = matching
    return payload
