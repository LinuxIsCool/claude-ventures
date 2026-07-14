# web/ventures_projects.py
"""Parse prose project files at ~/.claude/local/ventures/project-mirror/projects/*.md.

Format: '**Venture:** X', '**Objective:** ...', '## Milestones' checklist.
Sparse today; degrade gracefully. No DB.
"""
from __future__ import annotations
import re
from pathlib import Path
from typing import Any

_VROOT_DEFAULT = Path.home() / ".claude" / "local" / "ventures"
_VENTURE_RE = re.compile(r"\*\*Venture:\*\*\s*(.+)")
_OBJECTIVE_RE = re.compile(r"\*\*Objective:\*\*\s*(.+)")
_MS_RE = re.compile(r"^\s*-\s*\[( |x|X)\]\s*(.+)$")
_BOLD_STRIP_RE = re.compile(r"^\*\*(.+?)\*\*")


def _projects_dir(ventures_root: Path | None) -> Path:
    root = Path(ventures_root) if ventures_root else _VROOT_DEFAULT
    return root / "project-mirror" / "projects"


def _parse(md: Path) -> dict[str, Any]:
    text = md.read_text(encoding="utf-8")
    vm = _VENTURE_RE.search(text)
    om = _OBJECTIVE_RE.search(text)
    milestones = []
    for line in text.splitlines():
        m = _MS_RE.match(line)
        if m:
            raw_title = m.group(2).strip()
            bold_m = _BOLD_STRIP_RE.match(raw_title)
            title = bold_m.group(1) if bold_m else raw_title
            milestones.append({"done": m.group(1).lower() == "x", "title": title})
    return {
        "slug": md.stem,
        "venture": vm.group(1).strip() if vm else "",
        "objective": om.group(1).strip() if om else "",
        "milestones": milestones,
        "body": text,
    }


def get(slug: str, ventures_root: Path | None = None) -> dict[str, Any] | None:
    if not slug or "/" in slug or "\\" in slug or slug.startswith(".") or ".." in slug:
        return None
    base = _projects_dir(ventures_root).resolve()
    f = (base / f"{slug}.md").resolve()
    if base not in f.parents:
        return None
    return _parse(f) if f.is_file() else None


def list_for(venture_title_or_slug: str, ventures_root: Path | None = None) -> list[dict[str, Any]]:
    d = _projects_dir(ventures_root)
    if not d.is_dir():
        return []
    key = venture_title_or_slug.strip().lower()
    out = []
    for md in sorted(d.glob("*.md")):
        p = _parse(md)
        if p["venture"].strip().lower() == key:
            out.append({"slug": p["slug"], "venture": p["venture"], "objective": p["objective"]})
    return out
