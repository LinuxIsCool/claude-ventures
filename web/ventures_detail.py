# web/ventures_detail.py
"""Assemble rich, single-call detail objects for venture / project / milestone."""
from __future__ import annotations
from pathlib import Path
from typing import Any

import ventures_backlog
import ventures_projects
from ventures_accessor import VenturesAccessor


def _venture_record(slug: str, ventures_root: Path | None):
    # Use the accessor's cached _records() rather than re-globbing and
    # re-parsing every venture file on every detail request, which is what the
    # previous _iter_files()/_parse() loop did.
    acc = VenturesAccessor(data_root=ventures_root)
    for v in acc._records():
        if v["slug"] == slug:
            return v
    return None


def venture(slug: str, ventures_root: Path | None = None, backlog_dir: Path | None = None) -> dict[str, Any]:
    v = _venture_record(slug, ventures_root)
    if v is None:
        return {"error": "not found", "slug": slug}
    # Return the whole record (the accessor now passes frontmatter through)
    # plus the two joins. Enumerating keys here is what silently dropped
    # `deadlines`; a field should be absent from this payload only because the
    # venture file does not have it.
    out = {k: val for k, val in v.items() if not str(k).startswith("_")}
    projects = ventures_projects.list_for(slug, ventures_root=ventures_root) \
        + ventures_projects.list_for(v["title"], ventures_root=ventures_root)
    seen: set[str] = set()
    deduped = []
    for p in projects:  # title and slug can both match the same project file
        if p["slug"] in seen:
            continue
        seen.add(p["slug"])
        deduped.append(p)
    out["projects"] = deduped
    out["tasks"] = ventures_backlog.tasks_for(slug, backlog_dir=backlog_dir)
    return out


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
