# web/ventures_backlog.py
"""Join backlog tasks to ventures/projects/milestones.

Tasks link via the `venture:` frontmatter field (live today) OR the composite
`parent_id` ("venture.project.milestone", parent_type set) when present.
Read-through to ~/.claude/local/backlog/*.md. No DB.
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


def _frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    data = yaml.safe_load(parts[1])
    return data if isinstance(data, dict) else {}


def _matches(fm: dict, venture: str, project: str | None, milestone: str | None) -> bool:
    pid = str(fm.get("parent_id") or "")
    segs = pid.split(".") if pid else []
    if milestone:
        return len(segs) >= 1 and segs[0] == venture and segs[-1] == milestone
    if project:
        return len(segs) >= 2 and segs[0] == venture and segs[1] == project
    if segs and segs[0] == venture:
        return True
    return str(fm.get("venture") or "").strip() == venture


def tasks_for(venture: str, project: str | None = None, milestone: str | None = None,
              backlog_dir: Path | None = None) -> list[dict[str, Any]]:
    d = Path(backlog_dir) if backlog_dir else _BACKLOG_DEFAULT
    if not d.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for md in sorted(d.glob("*.md")):
        try:
            fm = _frontmatter(md.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"[ventures-web] skip backlog {md}: {exc}", file=sys.stderr)
            continue
        if not fm or not _matches(fm, venture, project, milestone):
            continue
        m = _ID_RE.search(str(fm.get("id") or md.stem))
        out.append({
            "id": (m.group(1) if m else md.stem),
            "title": fm.get("title", md.stem),
            "status": fm.get("status", ""),
            "priority": str(fm.get("priority", "medium")),
            "venture": fm.get("venture"),
            "due": str(fm.get("due") or ""),
        })
    out.sort(key=lambda t: (_PRIORITY_RANK.get(t["priority"], 9), t["due"] or "9999"))
    return out
