"""Schema-bearing Portfolio Data View projection.

The endpoint is deliberately domain-local while the contract stabilizes. It
returns exhaustive flattened venture properties plus task metrics, with query
state echoed for reproducibility. A later shared ``legion-data-view`` primitive
can consume this without learning Ventures' storage format.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from ventures_accessor import VenturesAccessor
import ventures_tasks
import ventures_projects
from ventures_scope import PortfolioScope

_CORE = [
    "selected", "starred", "emoji", "title", "status", "priority", "type",
    "task.today", "task.this_week", "task.soon", "task.backlog", "task.overdue",
    "description", "slug",
]
_DISPLAY_LIFECYCLE = {
    "seed": "exploring", "exploring": "exploring",
    "active": "active", "sustaining": "active",
    "harvesting": "complete", "dormant": "dormant",
}


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).startswith("_") or key == "record_fields":
                continue
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(child, dict):
                out.update(_flatten(child, path))
            elif isinstance(child, list):
                out[path] = json.dumps(child, ensure_ascii=False, separators=(",", ":"))
                out[f"{path}.__count"] = len(child)
            else:
                out[path] = child
    return out


def _type(values: list[Any]) -> str:
    present = [v for v in values if v is not None and v != ""]
    if not present:
        return "unknown"
    if all(isinstance(v, bool) for v in present):
        return "boolean"
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in present):
        return "number"
    return "text"


def _search_values(value: Any, key: str = "") -> list[str]:
    """Human-facing context only; local storage paths are not search meaning."""
    if isinstance(value, dict):
        out: list[str] = []
        for child_key, child in value.items():
            if str(child_key).startswith("_"):
                continue
            out.extend(_search_values(child, str(child_key)))
        return out
    if isinstance(value, list):
        return [part for child in value for part in _search_values(child, key)]
    text = str(value or "").strip()
    if not text:
        return []
    # legion-brain mount paths are provenance, not semantic venture context.
    if text.startswith(("~/", "/home/", "/tmp/")):
        return []
    return [text]


def _sort_value(value: Any) -> tuple:
    if value is None or value == "":
        return (1, "")
    if isinstance(value, bool):
        return (0, int(value))
    if isinstance(value, (int, float)):
        return (0, value)
    return (0, str(value).casefold())


def data_view(ventures_root: Path, backlog_dir: Path, today: date,
              query: dict[str, list[str]], identity: dict[str, dict] | None = None) -> dict:
    acc = VenturesAccessor(Path(ventures_root), today=today)
    summaries = acc.list({})
    venture_ids = {summary["slug"] for summary in summaries}
    task_records = ventures_tasks.records(
        Path(ventures_root), Path(backlog_dir), PortfolioScope(frozenset(venture_ids)), today
    )
    metrics = ventures_tasks.card_metrics(
        Path(ventures_root), Path(backlog_dir), today, task_records=task_records
    )["ventures"]
    tasks_by_venture: dict[str, list[dict[str, Any]]] = {slug: [] for slug in venture_ids}
    for task in task_records:
        tasks_by_venture.setdefault(task["venture"], []).append(task)
    projects_by_venture: dict[str, list[dict[str, Any]]] = {}
    title_to_slug = {summary["title"].strip().casefold(): summary["slug"] for summary in summaries}
    for project in ventures_projects.all_projects(Path(ventures_root)):
        owner = str(project.get("venture") or "").strip()
        slug = owner if owner in venture_ids else title_to_slug.get(owner.casefold())
        if slug:
            projects_by_venture.setdefault(slug, []).append(project)
    selected_raw = query.get("selected", query.get("ventures", []))
    selected = {part for raw in selected_raw for part in raw.split(",") if part}
    stars = {part for raw in query.get("stars", []) for part in raw.split(",") if part}
    status_raw = query.get("status", query.get("lifecycle", []))
    statuses = {part for raw in status_raw for part in raw.split(",") if part and part != "all"}
    scope_name = query.get("scope", ["starred" if query.get("stars_only", ["false"])[-1].lower() == "true" else "all"])[-1]
    if scope_name not in {"all", "starred"}:
        scope_name = "all"
    text = " ".join(query.get("q", [])).strip().casefold()
    selected_only = query.get("selected_only", ["false"])[-1].lower() == "true"
    legacy_work = query.get("work_only", ["false"])[-1].lower() == "true"
    work = query.get("work", ["has" if legacy_work else "any"])[-1]
    if work not in {"any", "has", "none"}:
        work = "any"
    facet_status = {"exploring": 0, "active": 0, "complete": 0}
    records: list[dict[str, Any]] = []
    for summary in summaries:
        slug = summary["slug"]
        display = _DISPLAY_LIFECYCLE.get(summary["lifecycle"], "dormant")
        if selected_only and slug not in selected:
            continue
        if scope_name == "starred" and slug not in stars:
            continue
        # The portfolio index searches the venture application context, not
        # merely its title: venture metadata, projects, milestones and linked
        # task records all contribute to the searchable document.
        detail = dict(acc.detail(slug))
        embedded_projects = detail.get("projects") if isinstance(detail.get("projects"), list) else []
        detail["projects"] = [*projects_by_venture.get(slug, []), *embedded_projects]
        detail["tasks"] = tasks_by_venture.get(slug, [])
        record = _flatten(detail)
        ident = (identity or {}).get(slug, {})
        record.update({
            "slug": slug,
            "status": display,
            "storage_lifecycle": summary["lifecycle"],
            "selected": slug in selected,
            "starred": slug in stars,
            "emoji": ident.get("emoji", ""),
            "identity_colour": ident.get("colour", ""),
            **{f"task.{key}": value for key, value in metrics.get(slug, {}).items()},
        })
        task_total = sum(int(record.get(f"task.{key}") or 0)
                         for key in ("today", "this_week", "soon", "backlog"))
        record["has_work"] = task_total > 0
        if work == "has" and not record["has_work"]:
            continue
        if work == "none" and record["has_work"]:
            continue
        search_document = " ".join(_search_values(detail) + _search_values(ident)).casefold()
        if text and text not in search_document:
            continue
        if display in facet_status:
            facet_status[display] += 1
        if statuses and display not in statuses:
            continue
        records.append(record)

    sort_specs = []
    for raw in query.get("sort", []):
        for spec in raw.split(","):
            key, _, direction = spec.partition(":")
            if key:
                sort_specs.append((key, direction if direction in {"asc", "desc"} else "asc"))
    for key, direction in reversed(sort_specs):
        records.sort(key=lambda row: _sort_value(row.get(key)), reverse=direction == "desc")

    keys = set().union(*(record.keys() for record in records)) if records else set(_CORE)
    ordered = [key for key in _CORE if key in keys] + sorted(keys - set(_CORE))
    columns = [{
        "key": key,
        "label": "Status" if key == "lifecycle" else key.replace("task.", "").replace(".__count", " count").replace("_", " ").replace(".", " › ").title(),
        "type": _type([record.get(key) for record in records]),
        "sortable": True,
        "filterable": True,
        "owner": "backlog" if key.startswith("task.") else "ventures",
    } for key in ordered]
    return {
        "records": records,
        "schema": {"version": 1, "columns": columns, "presets": {"core": _CORE, "all": ordered}},
        "page": {"cursor": None, "limit": len(records), "has_more": False, "total": len(records)},
        "query": {"text": text, "status": sorted(statuses), "scope": scope_name,
                  "selected_only": selected_only, "work": work,
                  "stars": sorted(stars),
                  "selected": sorted(selected), "sort": [{"key": k, "direction": d} for k, d in sort_specs]},
        "facets": {"status": facet_status, "starred": len(stars)},
        "as_of": today.isoformat(),
    }
