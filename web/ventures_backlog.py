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

_BACKLOG_DEFAULT = Path.home() / ".claude" / "local" / "backlog"
_PRIORITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
_ID_RE = re.compile(r"(?:task-)?(\d+)")

# Per-file parse cache: str(path) -> (mtime_ns, parsed_task | None). A single
# backlog edit re-parses only that one file instead of the whole directory.
_FILE_CACHE: dict[str, tuple[int, dict[str, Any] | None]] = {}


def _frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    data = yaml.safe_load(parts[1])
    return data if isinstance(data, dict) else {}


def _parse_one(md: Path) -> dict[str, Any] | None:
    """Parse a single backlog file into a task summary, or None if unusable."""
    try:
        fm = _frontmatter(md.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"[ventures-web] skip backlog {md}: {exc}", file=sys.stderr)
        return None
    if not fm:
        return None
    m = _ID_RE.search(str(fm.get("id") or md.stem))
    return {
        "id": (m.group(1) if m else md.stem),
        "title": fm.get("title", md.stem),
        "status": fm.get("status", ""),
        "priority": str(fm.get("priority", "medium")),
        "venture": fm.get("venture"),
        "due": str(fm.get("due") or ""),
        "_parent_id": str(fm.get("parent_id") or ""),
    }


def _cached_tasks(d: Path) -> list[dict[str, Any]]:
    """All backlog tasks, parsed at most once per (file, mtime).

    Per-file memoization: a single backlog edit re-parses only that one file,
    not the whole directory. Cold start parses everything once; steady state is
    a stat() per file plus parses for only the files that actually changed.
    """
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for md in sorted(d.glob("*.md")):
        key = str(md)
        seen.add(key)
        try:
            mtime = md.stat().st_mtime_ns
        except OSError:
            continue
        cached = _FILE_CACHE.get(key)
        if cached is None or cached[0] != mtime:
            cached = (mtime, _parse_one(md))
            _FILE_CACHE[key] = cached
        if cached[1] is not None:
            out.append(cached[1])
    # evict cache entries for files removed from this directory
    for stale in [k for k in _FILE_CACHE if k.startswith(str(d)) and k not in seen]:
        del _FILE_CACHE[stale]
    return out


def tasks_by_venture(backlog_dir: Path | None = None) -> dict[str, list[dict[str, Any]]]:
    """All venture-linked tasks grouped by venture slug, in ONE cached pass.

    Lets a caller (e.g. the timeline) join the whole backlog once instead of
    scanning it per venture.

    Invariant: a task belongs to exactly ONE venture — the `parent_id` head
    segment when present, otherwise the flat `venture:` field. When `parent_id`
    is present the flat field is ignored. (The old per-venture scan could list a
    task whose `parent_id` head and `venture:` field disagreed under BOTH
    ventures; single membership is the cleaner, intended rule.)
    """
    d = Path(backlog_dir) if backlog_dir else _BACKLOG_DEFAULT
    if not d.is_dir():
        return {}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for t in _cached_tasks(d):
        pid = t["_parent_id"]
        slug = pid.split(".")[0] if pid else str(t.get("venture") or "").strip()
        if not slug:
            continue
        grouped.setdefault(slug, []).append({k: v for k, v in t.items() if not k.startswith("_")})
    return grouped


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
