# plugins/claude-cards/web/cards_views.py
"""External-join view helpers for the venture workspace.

The card graph (cards.db) is the spine, but a venture workspace also surfaces
data that lives in other Legion stores: the backlog, the journal, and the
ventures markdown store (milestones / project / finance / links / team /
resources). These helpers read those stores read-only, filtered to one
venture, and shape them into the same card-ish view-model the frontend already
renders (title / summary / tags / created / priority).

All filtering keys off a venture slug + a set of match terms so the workspace
stays reusable: instantiate the satellite for any venture by changing the
VENTURE_SLUG / MATCH_TERMS wiring in server.py.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

_HOME = Path.home()
BACKLOG_DIR = _HOME / ".claude" / "local" / "backlog"
JOURNAL_DIR = _HOME / ".claude" / "local" / "journal"
VENTURES_DIR = _HOME / ".claude" / "local" / "ventures"


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        data = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return {}, parts[2]
    return (data if isinstance(data, dict) else {}), parts[2]


def _matches(haystack: str, terms: tuple[str, ...]) -> bool:
    """Term match. Short alpha tokens (<=4 chars, e.g. 'cie') match on word
    boundary so they don't fire inside 'spe**cie**s' / 'poli**cie**s'. Longer
    terms and any term with non-alpha chars match as a plain substring."""
    low = haystack.lower()
    for t in terms:
        tl = t.lower()
        if len(tl) <= 4 and tl.isalpha():
            if re.search(rf"\b{re.escape(tl)}\b", low):
                return True
        elif tl in low:
            return True
    return False


def _links_map(links: Any) -> dict[str, str]:
    """Normalize the venture `links` field to {label: url}. Accepts both the
    list-of-{label,url} form (live CIE file) and the legacy dict form."""
    out: dict[str, str] = {}
    if isinstance(links, dict):
        return {str(k): str(v) for k, v in links.items()}
    if isinstance(links, list):
        for i, item in enumerate(links):
            if isinstance(item, dict):
                label = str(item.get("label") or item.get("name") or f"link {i+1}")
                out[label] = str(item.get("url") or item.get("href") or "")
            else:
                out[f"link {i+1}"] = str(item)
    return out


# ---- backlog --------------------------------------------------------------
def backlog(venture_slug: str, terms: tuple[str, ...]) -> dict[str, Any]:
    """Backlog tasks linked to the venture. Match on `venture:` frontmatter
    field first, then fall back to slug/term mention in title or body."""
    items: list[dict[str, Any]] = []
    if not BACKLOG_DIR.is_dir():
        return {"items": [], "total": 0}
    for md in sorted(BACKLOG_DIR.glob("task-*.md")):
        try:
            fm, body = _split_frontmatter(md.read_text(encoding="utf-8"))
        except OSError:
            continue
        venture_field = str(fm.get("venture", "")).lower()
        hay = f"{md.stem} {fm.get('title','')} {body[:500]}"
        linked = venture_slug.lower() in venture_field or _matches(hay, terms)
        if not linked:
            continue
        items.append({
            "slug": str(fm.get("id") or md.stem),
            "type": "task",
            "title": fm.get("title") or md.stem,
            "summary": (fm.get("description") or body.strip().split("\n")[0] if body.strip() else "")[:240],
            "tags": fm.get("tags") or [],
            "created": str(fm.get("created") or fm.get("date") or ""),
            "priority": fm.get("priority", "medium"),
            "status": fm.get("status", "open"),
            "due": str(fm.get("due") or ""),
        })
    # priority then due
    rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    items.sort(key=lambda x: (rank.get(str(x["priority"]).lower(), 9), x["due"] or "9999"))
    return {"items": items, "total": len(items)}


# ---- journal --------------------------------------------------------------
def journal(terms: tuple[str, ...], limit: int = 60) -> dict[str, Any]:
    """Journal entries mentioning the venture, newest first."""
    items: list[dict[str, Any]] = []
    if not JOURNAL_DIR.is_dir():
        return {"items": [], "total": 0}
    for md in JOURNAL_DIR.rglob("*.md"):
        try:
            text = md.read_text(encoding="utf-8")
        except OSError:
            continue
        if not _matches(text, terms):
            continue
        fm, body = _split_frontmatter(text)
        first_line = next((ln.strip() for ln in body.splitlines() if ln.strip() and not ln.startswith("#")), "")
        # mtime as the temporal anchor (journal paths encode date but vary)
        try:
            mtime = datetime.fromtimestamp(md.stat().st_mtime).isoformat(timespec="seconds")
        except OSError:
            mtime = ""
        items.append({
            "slug": str(md.relative_to(JOURNAL_DIR)),
            "type": "journal",
            "title": fm.get("title") or md.stem,
            "summary": first_line[:240],
            "tags": fm.get("tags") or [],
            "created": str(fm.get("date") or "") or mtime[:10],
            "_mtime": mtime,
            "author": fm.get("author", ""),
            "path": str(md),
        })
    items.sort(key=lambda x: x["_mtime"], reverse=True)
    items = items[:limit]
    for it in items:
        it.pop("_mtime", None)
    return {"items": items, "total": len(items)}


# ---- venture store (milestones / project / finance / links / team) --------
def _venture_file(venture_slug: str) -> Path | None:
    for lifecycle in ("active", "exploring", "sustaining", "dormant", "harvesting", "seed"):
        p = VENTURES_DIR / lifecycle / f"{venture_slug}.md"
        if p.is_file():
            return p
    return None


def venture(venture_slug: str) -> dict[str, Any]:
    """The venture's own frontmatter: milestones, deliverables, financial,
    links/resources, team. Feeds the Milestones / Project / Finance /
    Resources views."""
    p = _venture_file(venture_slug)
    if p is None:
        return {"error": "venture not found", "slug": venture_slug}
    fm, body = _split_frontmatter(p.read_text(encoding="utf-8"))
    today = date.today()

    def _overdue(d: dict) -> bool:
        raw = str(d.get("date", "")).strip()
        if str(d.get("status", "")).lower() in {"complete", "completed", "done"}:
            return False
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date() < today
        except ValueError:
            return False

    deadlines = [d for d in (fm.get("deadlines") or []) if isinstance(d, dict)]
    for d in deadlines:
        d["overdue"] = _overdue(d)
    return {
        "slug": venture_slug,
        "title": fm.get("title", venture_slug),
        "description": fm.get("description", ""),
        "stage": fm.get("stage", ""),
        "priority": fm.get("priority", "medium"),
        "milestones": [m for m in (fm.get("milestones") or []) if isinstance(m, dict)],
        "deliverables": [d for d in (fm.get("deliverables") or []) if isinstance(d, dict)],
        "deadlines": deadlines,
        "financial": fm.get("financial") or {},
        "links": _links_map(fm.get("links")),
        "co_venturers": fm.get("co_venturers") or [],
        "body": body.strip(),
    }


# ---- resources (links from venture + url mentions) ------------------------
def resources(venture_slug: str, terms: tuple[str, ...]) -> dict[str, Any]:
    """Resource cards: every link/repo on the venture file, shaped as cards.
    Resource discovery from urls.jsonl can be layered in later; the venture
    `links` map is the reliable first source."""
    v = venture(venture_slug)
    if v.get("error"):
        return {"items": [], "total": 0}
    items: list[dict[str, Any]] = []
    for k, val in (v.get("links") or {}).items():
        url = str(val)
        kind = "repo" if re.search(r"github|gitlab", url, re.I) else (
            "doc" if re.search(r"docs?\.|notion|drive|paper", url, re.I) else "link")
        items.append({
            "slug": k,
            "type": kind,
            "title": k,
            "summary": url,
            "url": url if url.startswith("http") else "",
            "tags": [kind],
            "created": "",
            "priority": "medium",
        })
    return {"items": items, "total": len(items)}
