# web/ventures_detail.py
"""Assemble rich, single-call detail objects for venture / project / milestone."""
from __future__ import annotations
from pathlib import Path
from typing import Any

import ventures_backlog
import ventures_projects
from ventures_accessor import VenturesAccessor


def _venture_record(slug: str, ventures_root: Path | None):
    acc = VenturesAccessor(data_root=ventures_root)
    for lifecycle, md in acc._iter_files():
        v = acc._parse(lifecycle, md)
        if v and v["slug"] == slug:
            return v
    return None


def venture(slug: str, ventures_root: Path | None = None, backlog_dir: Path | None = None) -> dict[str, Any]:
    v = _venture_record(slug, ventures_root)
    if v is None:
        return {"error": "not found", "slug": slug}
    return {
        "slug": v["slug"], "title": v["title"], "description": v.get("description", ""),
        "stage": v.get("stage"), "priority": v.get("priority"), "lifecycle": v.get("lifecycle"),
        "milestones": v.get("milestones", []),
        "financial": v.get("financial", {}),
        "links": v.get("links", {}),
        "co_venturers": v.get("co_venturers", []),
        "related_ventures": v.get("related_ventures", []),
        "projects": ventures_projects.list_for(slug, ventures_root=ventures_root)
                    + ventures_projects.list_for(v["title"], ventures_root=ventures_root),
        "tasks": ventures_backlog.tasks_for(slug, backlog_dir=backlog_dir),
    }


def project(slug: str, ventures_root: Path | None = None, backlog_dir: Path | None = None) -> dict[str, Any]:
    p = ventures_projects.get(slug, ventures_root=ventures_root)
    if p is None:
        return {"error": "not found", "slug": slug}
    p = dict(p)
    p["tasks"] = ventures_backlog.tasks_for(p.get("venture", ""), project=slug, backlog_dir=backlog_dir)
    return p


def milestone(venture_slug: str, ms_id: str, ventures_root: Path | None = None,
              backlog_dir: Path | None = None) -> dict[str, Any]:
    v = _venture_record(venture_slug, ventures_root)
    if v is None:
        return {"error": "not found", "venture": venture_slug, "milestone": ms_id}
    ms = next((m for m in v.get("milestones", []) if isinstance(m, dict) and str(m.get("id")) == ms_id), None)
    if ms is None:
        return {"error": "not found", "venture": venture_slug, "milestone": ms_id}
    out = dict(ms)
    out["venture"] = venture_slug
    out["venture_title"] = v["title"]
    out["tasks"] = ventures_backlog.tasks_for(venture_slug, milestone=ms_id, backlog_dir=backlog_dir)
    return out
