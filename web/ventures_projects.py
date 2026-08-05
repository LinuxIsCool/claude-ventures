# web/ventures_projects.py
"""Project discovery across BOTH project file formats.

There are two, and reading only one is why the detail page rendered
"Projects: none" for every venture that has projects:

  1. structured  ~/.claude/local/ventures/<venture>/projects/<slug>/project.md
                 YAML frontmatter: slug, name, venture, stage, priority, owner,
                 milestones: [slug, ...]; milestone bodies live alongside in
                 milestones/<slug>.md, each with its own frontmatter and a real
                 `deadline`. This is what the MCP writes and what bcrg,
                 indigenomics-ai and regen-ai actually use.

  2. prose       ~/.claude/local/ventures/project-mirror/projects/<slug>.md
                 '**Venture:** X', '**Objective:** ...', '- [ ]' checklists.
                 One file exists in this format.

Repointing the directory alone would have been worse than the bug: the prose
regexes match nothing in a YAML file, so every field would parse to empty and
six projects would render as six blank rows that look like data. Two formats,
two parsers, dispatched on whether the file opens with '---'.

Cached on mtime-signature via ventures_cache, since discovery now walks a tree
per request rather than globbing one flat directory.
"""
from __future__ import annotations
import re
from pathlib import Path
from typing import Any

import yaml

import ventures_cache

_VROOT_DEFAULT = Path.home() / ".claude" / "local" / "ventures"
_CACHE: dict[str, Any] = {}
_VENTURE_RE = re.compile(r"\*\*Venture:\*\*\s*(.+)")
_OBJECTIVE_RE = re.compile(r"\*\*Objective:\*\*\s*(.+)")
_MS_RE = re.compile(r"^\s*-\s*\[( |x|X)\]\s*(.+)$")
_BOLD_STRIP_RE = re.compile(r"^\*\*(.+?)\*\*")


def _projects_dir(ventures_root: Path | None) -> Path:
    root = Path(ventures_root) if ventures_root else _VROOT_DEFAULT
    return root / "project-mirror" / "projects"


def _frontmatter(text: str) -> dict[str, Any] | None:
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        data = yaml.safe_load(parts[1])
    except Exception:  # noqa: BLE001 -- malformed project file must not 500 the page
        return None
    return data if isinstance(data, dict) else None


def _body(text: str) -> str:
    """The first prose paragraph after the frontmatter, whitespace collapsed.

    Structured project files carry their description as body prose, not as a
    frontmatter field: not one of the 18 real projects in the store sets
    `target` or `notes`. Without this, `objective` fell back to `name` and every
    project on every venture detail page printed its own title twice.
    """
    parts = text.split("---", 2)
    body = parts[2] if len(parts) >= 3 else text
    for para in body.strip().split("\n\n"):
        collapsed = " ".join(para.split())
        if collapsed:
            return collapsed
    return ""


def _practices(fm: dict[str, Any]) -> list[dict[str, str]]:
    """`practices:` on a project, the third tier of the hierarchy.

    A practice is work that never completes: occurrences close, and a lapse in
    cadence is the alarm. claude-addr writes this key and resolves addresses
    like CIRCUS-CALISTHENICS.training.handstands from it; surfacing it here is
    what stops the resolver and this page from disagreeing about what exists.
    Entries may be a bare slug or a {slug, name} mapping.
    """
    out: list[dict[str, str]] = []
    for prac in fm.get("practices") or []:
        if isinstance(prac, str):
            prac = {"slug": prac}
        if not isinstance(prac, dict):
            continue
        slug = str(prac.get("slug") or "").strip()
        if not slug:
            continue
        out.append({"slug": slug, "name": str(prac.get("name") or slug)})
    return out


def _parse_structured(md: Path, fm: dict[str, Any], text: str = "") -> dict[str, Any]:
    """Format 1: <venture>/projects/<slug>/project.md with a milestones/ dir."""
    milestones: list[dict[str, Any]] = []
    ms_dir = md.parent / "milestones"
    if ms_dir.is_dir():
        for ms in sorted(ms_dir.glob("*.md")):
            ms_fm = _frontmatter(ms.read_text(encoding="utf-8")) or {}
            status = str(ms_fm.get("stage", "")).lower()
            milestones.append({
                "slug": ms_fm.get("slug", ms.stem),
                "title": ms_fm.get("name") or ms_fm.get("slug") or ms.stem,
                "done": status in {"harvesting", "complete", "completed", "done"},
                "stage": ms_fm.get("stage"),
                "priority": ms_fm.get("priority"),
                "deadline": str(ms_fm.get("deadline") or "") or None,
                "target": ms_fm.get("target"),
                "notes": ms_fm.get("notes"),
            })
    return {
        "slug": str(fm.get("slug") or md.parent.name),
        "venture": str(fm.get("venture") or ""),
        "name": fm.get("name"),
        # `name` stays the last resort so a project with no prose still renders
        # something, but body prose comes first because that is where every
        # real project in the store actually keeps its description.
        "objective": str(
            fm.get("target") or fm.get("notes") or _body(text) or fm.get("name") or ""
        ),
        "stage": fm.get("stage"),
        "priority": fm.get("priority"),
        "owner": fm.get("owner"),
        "milestones": milestones,
        "practices": _practices(fm),
        "format": "structured",
        "source": str(md),
    }


def _parse(md: Path) -> dict[str, Any]:
    text = md.read_text(encoding="utf-8")
    fm = _frontmatter(text)
    if fm is not None:
        return _parse_structured(md, fm, text)
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
        # The prose format has no practices concept. Present and empty rather
        # than absent, so a consumer never has to know which parser produced
        # the row -- the two formats already differ enough.
        "practices": [],
        "body": text,
        "format": "prose",
        "source": str(md),
    }


def _project_files(ventures_root: Path | None) -> list[Path]:
    """Every project file, both formats, across the store."""
    root = Path(ventures_root) if ventures_root else _VROOT_DEFAULT
    files: list[Path] = []
    if not root.is_dir():
        return files
    # Format 1: <venture>/projects/<slug>/project.md
    for projects_dir in sorted(root.glob("*/projects")):
        files.extend(sorted(projects_dir.glob("*/project.md")))
    # Format 2: the legacy flat mirror
    mirror = _projects_dir(ventures_root)
    if mirror.is_dir():
        files.extend(sorted(mirror.glob("*.md")))
    return files


def _all_projects(ventures_root: Path | None) -> list[dict[str, Any]]:
    out = []
    for md in _project_files(ventures_root):
        try:
            out.append(_parse(md))
        except OSError:
            continue  # vanished mid-scan; the signature already changed
    return out


def _cached_projects(ventures_root: Path | None) -> list[dict[str, Any]]:
    root = Path(ventures_root) if ventures_root else _VROOT_DEFAULT
    files = _project_files(ventures_root)
    return ventures_cache.cached(
        _CACHE,
        str(root),
        ventures_cache.mtime_signature(files),
        lambda: _all_projects(ventures_root),
    )


def get(slug: str, ventures_root: Path | None = None) -> dict[str, Any] | None:
    if not slug or "/" in slug or "\\" in slug or slug.startswith(".") or ".." in slug:
        return None
    # Structured tree first, then the legacy flat mirror. Traversal is blocked
    # by the slug guard above plus the containment check below.
    for p in _cached_projects(ventures_root):
        if p["slug"] == slug and p.get("format") == "structured":
            return p
    base = _projects_dir(ventures_root).resolve()
    f = (base / f"{slug}.md").resolve()
    if base not in f.parents:
        return None
    return _parse(f) if f.is_file() else None


def list_for(venture_title_or_slug: str, ventures_root: Path | None = None) -> list[dict[str, Any]]:
    key = venture_title_or_slug.strip().lower()
    out = []
    for p in _cached_projects(ventures_root):
        if p["venture"].strip().lower() != key:
            continue
        out.append({
            "slug": p["slug"],
            "venture": p["venture"],
            "name": p.get("name"),
            "objective": p["objective"],
            "stage": p.get("stage"),
            "priority": p.get("priority"),
            "owner": p.get("owner"),
            "milestone_count": len(p.get("milestones") or []),
            "milestones": p.get("milestones") or [],
            "practice_count": len(p.get("practices") or []),
            "practices": p.get("practices") or [],
            "format": p.get("format"),
        })
    return out
