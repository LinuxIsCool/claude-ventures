# web/ventures_meetings.py
"""A venture's meeting catalogue, read straight from meetings.db (read-only).

Join rule: a meeting belongs to venture V when any slug s in its venture_slugs
list equals V or is a dash-prefix of V (the meetings corpus says
"bcrg-avalanche" where the ventures store says "bcrg-avalanche-foundation").
Search uses the meetings_fts FTS5 table when present, LIKE otherwise.
Spec: backlog task-824 section 6.2, Phase 3.
"""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from typing import Any

_DB_DEFAULT = Path.home() / ".claude" / "local" / "meetings" / "meetings.db"
_EMPTY_AGG = {"meetings": 0, "decisions": 0, "risks": 0, "actions_open": 0}


def slug_matches(meeting_slug: str, venture_slug: str) -> bool:
    return meeting_slug == venture_slug or venture_slug.startswith(meeting_slug + "-")


def _unavailable(reason: str, q: str = "") -> dict[str, Any]:
    return {"available": False, "reason": reason, "items": [], "count": 0, "query": q, "fts": False,
            "aggregates": dict(_EMPTY_AGG), "untagged": 0}


def _slugs(raw: Any) -> list[str]:
    try:
        val = json.loads(raw) if isinstance(raw, str) else raw
    except ValueError:
        return []
    return [str(s) for s in val] if isinstance(val, list) else []


def _fts_query(q: str) -> str:
    tokens = [t.replace('"', "") for t in q.split()]
    return " OR ".join(f'"{t}"' for t in tokens if t)


def _search_rowids(conn: sqlite3.Connection, q: str) -> tuple[set[int] | None, bool]:
    """rowids matching q, and whether FTS answered. None means no filter."""
    if not q.strip():
        return None, True
    try:
        rows = conn.execute("SELECT rowid FROM meetings_fts WHERE meetings_fts MATCH ?", (_fts_query(q),)).fetchall()
        return {r[0] for r in rows}, True
    except sqlite3.OperationalError:
        like = f"%{q.strip()}%"
        rows = conn.execute("SELECT rowid FROM meetings WHERE title LIKE ? OR summary LIKE ? OR agenda LIKE ?", (like, like, like)).fetchall()
        return {r[0] for r in rows}, False


def _children(conn: sqlite3.Connection, meeting_id: str) -> tuple[list, list, list]:
    d = [{"id": r[0], "text": r[1], "type": r[2], "reversibility": r[3], "quote": r[4]} for r in conn.execute(
        "SELECT id, text, decision_type, reversibility, evidence_quote FROM meeting_decisions WHERE meeting_id=? ORDER BY rowid", (meeting_id,))]
    r_ = [{"id": r[0], "text": r[1], "severity": r[2], "likelihood": r[3], "mitigation": r[4], "quote": r[5]} for r in conn.execute(
        "SELECT id, text, severity, likelihood, mitigation, evidence_quote FROM meeting_risks WHERE meeting_id=? ORDER BY rowid", (meeting_id,))]
    a = [{"id": r[0], "text": r[1], "assignee": r[2], "deadline": r[3], "priority": r[4], "status": r[5], "quote": r[6], "backlog_task_id": r[7]} for r in conn.execute(
        "SELECT id, text, assignee, deadline, priority, status, evidence_quote, backlog_task_id FROM meeting_action_items WHERE meeting_id=? ORDER BY rowid", (meeting_id,))]
    return d, r_, a


def catalogue(slug: str, db_path: Path | None = None, q: str = "", limit: int = 100) -> dict[str, Any]:
    path = Path(db_path) if db_path else _DB_DEFAULT
    if not path.is_file():
        return _unavailable("meetings.db not found", q)
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        return _unavailable(f"meetings.db unreadable: {exc}", q)
    try:
        allowed, fts_ok = _search_rowids(conn, q)
        rows = conn.execute(
            "SELECT rowid, id, date, start_time, title, source, status, duration_seconds, transcript_id, venture_slugs, summary, tags "
            "FROM meetings ORDER BY date DESC, COALESCE(start_time, '') DESC").fetchall()
        untagged = sum(1 for r in rows if _slugs(r[9]) == [])
        matched = [r for r in rows if any(slug_matches(s, slug) for s in _slugs(r[9])) and (allowed is None or r[0] in allowed)]
        agg = dict(_EMPTY_AGG); agg["meetings"] = len(matched)
        items: list[dict[str, Any]] = []
        for r in matched:
            d, rk, a = _children(conn, r[1])
            agg["decisions"] += len(d); agg["risks"] += len(rk); agg["actions_open"] += sum(1 for x in a if x["status"] == "open")
            if len(items) >= limit:
                continue
            tid = r[8] or ""
            items.append({
                "id": r[1], "date": r[2], "start_time": r[3], "title": r[4], "source": r[5], "status": r[6],
                "duration_min": (int(r[7]) // 60) if r[7] else None,
                "transcript_id": tid or None,
                "transcript_href": f"/transcripts/?view=transcript&tx={tid}" if tid else None,
                "summary": r[10] or "", "tags": _slugs(r[11]),
                "decisions": d, "risks": rk, "actions": a,
                "counts": {"decisions": len(d), "risks": len(rk), "actions_open": sum(1 for x in a if x["status"] == "open"), "actions_total": len(a)},
            })
        return {"available": True, "query": q, "fts": fts_ok, "count": len(matched), "items": items, "aggregates": agg, "untagged": untagged}
    finally:
        conn.close()
