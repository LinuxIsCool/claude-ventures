# web/ventures_backlog.py
"""Join backlog tasks to ventures/projects/milestones.

Tasks link via the `venture:` frontmatter field (live today) OR the composite
`parent_id` ("venture.project.milestone", parent_type set) when present.
Read-through to ~/.claude/local/backlog/*.md. No DB.

Performance: parsed results are cached in-memory per directory, invalidated by
mtime-signature (tuple of (filename, mtime_ns) pairs).  Steady-state cost is
O(n) signature scan instead of O(n) YAML parse.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path
from typing import Any
import yaml

import ventures_cache
from claude_backlog.venture_resolution import resolve_venture

_BACKLOG_DEFAULT = Path.home() / ".claude" / "local" / "backlog"
_PRIORITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
_ID_RE = re.compile(r"(?:task-)?(\d+)")

# module-level cache, keyed by resolved backlog dir
_CACHE: dict[str, dict[str, Any]] = {}


def _frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    data = yaml.safe_load(parts[1])
    return data if isinstance(data, dict) else {}


def _signature(d: Path) -> tuple:
    return ventures_cache.mtime_signature(d.glob("*.md"))


def _all_tasks(d: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for md in sorted(d.glob("*.md")):
        try:
            fm = _frontmatter(md.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"[ventures-web] skip backlog {md}: {exc}", file=sys.stderr)
            continue
        if not fm:
            continue
        m = _ID_RE.search(str(fm.get("id") or md.stem))
        resolution = resolve_venture(fm.get("venture"), project=fm.get("project"))
        out.append({
            "id": (m.group(1) if m else md.stem),
            "title": fm.get("title", md.stem),
            "status": fm.get("status", ""),
            "priority": str(fm.get("priority", "medium")),
            "venture": resolution.canonical,
            "venture_raw": fm.get("venture"),
            "venture_resolution": resolution.as_dict(),
            "program": fm.get("program") or resolution.program,
            "project": fm.get("project") or resolution.project,
            "due": str(fm.get("due") or ""),
            "blocked_by": fm.get("blocked_by") or [],
            "dependencies": fm.get("dependencies") or [],
            "_parent_id": str(fm.get("parent_id") or ""),
        })
    return out


def _cached_tasks(d: Path) -> list[dict[str, Any]]:
    return ventures_cache.cached(
        _CACHE, str(d.resolve()), _signature(d), lambda: _all_tasks(d)
    )


def all_tasks(backlog_dir: Path | None = None) -> list[dict[str, Any]]:
    """Return every parsed top-level backlog task without private join keys."""
    d = Path(backlog_dir) if backlog_dir else _BACKLOG_DEFAULT
    if not d.is_dir():
        return []
    return [{k: v for k, v in t.items() if not k.startswith("_")}
            for t in _cached_tasks(d)]


def _matches(t: dict, venture: str, project: str | None, milestone: str | None) -> bool:
    pid = t["_parent_id"]
    segs = pid.split(".") if pid else []
    if milestone:
        return len(segs) >= 1 and segs[0] == venture and segs[-1] == milestone
    if project:
        return len(segs) >= 2 and segs[0] == venture and segs[1] == project
    if segs and segs[0] == venture:
        return True
    return str(t.get("venture") or "").strip() == venture


def tasks_for(venture: str, project: str | None = None, milestone: str | None = None,
              backlog_dir: Path | None = None) -> list[dict[str, Any]]:
    d = Path(backlog_dir) if backlog_dir else _BACKLOG_DEFAULT
    if not d.is_dir():
        return []
    matched = [t for t in _cached_tasks(d) if _matches(t, venture, project, milestone)]
    matched.sort(key=lambda t: (_PRIORITY_RANK.get(t["priority"], 9), t["due"] or "9999"))
    # strip internal keys from the returned summaries
    return [{k: v for k, v in t.items() if not k.startswith("_")} for t in matched]
