# plugins/claude-cards/web/cards_accessor.py
"""CardsAccessor — read-through to the card graph in cards.db.

The card graph stores BOTH nodes and edges as rows in one `cards` table:
  - node cards: type in {transcript, decision, concept, action_item, ...}
  - edge cards: type == 'relationship', with metadata.source / metadata.target

This accessor projects that single graph into the views a venture workspace
needs. The base Accessor protocol (list/detail/stats/feed/healthz/signature)
serves the node-card grid; the handler subclass adds graph-aware routes
(edges / people / venture / backlog / journal) for the richer views.

Read-only. No webapp DB. One malformed row never takes the server down — the
metadata JSON is parsed defensively and falls back to {} on error.

Mode A standalone:  python web/server.py --port 8895
Mode B mount:       registered in claude-webui/scripts/webui_platform.py
"""
from __future__ import annotations

import json
import sqlite3
import time
from datetime import date
from pathlib import Path
from typing import Any

from claude_webui.healthz import healthz_response

NAMESPACE = "legion.claude-card"

_HOME = Path.home()
_DB_DEFAULT = _HOME / ".claude" / "local" / "cards" / "cards.db"

# Node-card types that get first-class views. Anything else still lists under
# "all" but has no dedicated tab.
NODE_TYPES = ("transcript", "decision", "concept", "action_item", "milestone", "person", "resource")
EDGE_TYPE = "relationship"


def _loads(raw: Any) -> Any:
    """Parse a JSON column defensively. Returns {} / [] fallbacks, never raises."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


class WorkspaceAccessor:
    """Reads the card graph. Implements the Accessor protocol + graph helpers."""

    def __init__(self, db_path: Path | None = None, today: date | None = None):
        self.db_path = Path(db_path) if db_path else _DB_DEFAULT
        self._today = today or date.today()

    # ---- low-level ---------------------------------------------------------
    def _conn(self) -> sqlite3.Connection:
        # read-only URI so the satellite can never mutate the graph
        uri = f"file:{self.db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=2.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _signature(self) -> tuple:
        """mtime + size of the db file. Cheap; the kernel polls this to decide
        whether to push a refresh to connected browsers."""
        try:
            st = self.db_path.stat()
            return (str(self.db_path), st.st_mtime_ns, st.st_size)
        except OSError:
            return (str(self.db_path), 0, 0)

    def signature(self) -> tuple:
        return self._signature()

    # ---- row → view-model --------------------------------------------------
    @staticmethod
    def _provenance(meta: dict[str, Any]) -> dict[str, Any]:
        """Normalize a card's provenance for the UI. Pre-Phase-0 cards have no
        provenance block; they were all lens-extracted, so default to the
        'inferred' tier rather than claiming curation we can't prove."""
        p = meta.get("provenance")
        if not isinstance(p, dict):
            p = {}
        tier = p.get("tier")
        if tier not in ("curated", "inferred", "unverified"):
            tier = "curated" if p.get("verified_by") else "inferred"
        return {
            "tier": tier,
            "source_type": p.get("source_type"),
            "extracted_by": p.get("extracted_by"),
            "lens": p.get("lens"),
            "extracted_at": p.get("extracted_at"),
            "source_mtime": p.get("source_mtime"),
            "verified_by": p.get("verified_by"),
            "verified_at": p.get("verified_at"),
        }

    def _node_card(self, row: sqlite3.Row, *, full: bool) -> dict[str, Any]:
        meta = _loads(row["metadata"]) or {}
        tags = _loads(row["tags"]) or []
        prov = self._provenance(meta)
        card = {
            "slug": row["id"],
            "type": row["type"],
            "title": row["title"],
            "summary": meta.get("summary", ""),
            "tags": tags if isinstance(tags, list) else [],
            "created": row["created"],
            "priority": row["priority"],
            "level": meta.get("level"),
            "xp": meta.get("xp"),
            "participants": meta.get("participants") or [],
            "mention_count": meta.get("mentions"),
            "tier": prov["tier"],
        }
        if full:
            card.update({
                "body": row["body"],
                "description": meta.get("description") or meta.get("summary", ""),
                "location": row["location"],
                "sources": meta.get("sources") or [],
                "key_outcomes": meta.get("key_outcomes") or [],
                "project": meta.get("project"),
                "client": meta.get("client"),
                "provenance": prov,
                "metadata": meta,
            })
        return card

    # ---- Accessor protocol -------------------------------------------------
    def list(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """All node cards (edges excluded). Optional ?type= filter; the
        frontend also filters client-side, but server-side keeps payloads
        small as the graph grows."""
        want_type = (params or {}).get("type")
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM cards WHERE type != ? ORDER BY created DESC",
                (EDGE_TYPE,),
            ).fetchall()
        out = [self._node_card(r, full=False) for r in rows]
        if want_type and want_type != "all":
            out = [c for c in out if c["type"] == want_type]
        return out

    def detail(self, item_id: str) -> dict[str, Any]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM cards WHERE id = ?", (item_id,)).fetchone()
            if row is None:
                return {"error": "not found", "slug": item_id}
            card = self._node_card(row, full=True)
            # attach incident edges (incidence = the card's neighbourhood)
            card["edges"] = self._edges_for(conn, item_id)
        return card

    def _edges_for(self, conn: sqlite3.Connection, node_id: str) -> list[dict[str, Any]]:
        rows = conn.execute("SELECT id, title, metadata FROM cards WHERE type = ?", (EDGE_TYPE,)).fetchall()
        title_by_id = {
            r["id"]: r["title"]
            for r in conn.execute("SELECT id, title FROM cards WHERE type != ?", (EDGE_TYPE,)).fetchall()
        }
        out = []
        for r in rows:
            m = _loads(r["metadata"]) or {}
            src, tgt = m.get("source"), m.get("target")
            if node_id not in (src, tgt):
                continue
            other = tgt if src == node_id else src
            out.append({
                "direction": "out" if src == node_id else "in",
                "rel_type": m.get("relationship_type", ""),
                "strength": m.get("strength"),
                "summary": m.get("summary", ""),
                "other_id": other,
                "other_title": title_by_id.get(other, other),
            })
        return out

    def stats(self) -> dict[str, Any]:
        with self._conn() as conn:
            by_type: dict[str, int] = {}
            for r in conn.execute("SELECT type, COUNT(*) n FROM cards GROUP BY type").fetchall():
                by_type[r["type"]] = r["n"]
            node_rows = conn.execute(
                "SELECT metadata FROM cards WHERE type != ?", (EDGE_TYPE,)
            ).fetchall()
        edges = by_type.get(EDGE_TYPE, 0)
        nodes = sum(n for t, n in by_type.items() if t != EDGE_TYPE)
        people: set[str] = set()
        for r in node_rows:
            m = _loads(r["metadata"]) or {}
            for p in (m.get("participants") or []):
                if p:
                    people.add(str(p))
        return {
            "key_metric": nodes,
            "key_metric_label": "cards",
            "nodes": nodes,
            "edges": edges,
            "people": len(people),
            "by_type": {t: n for t, n in by_type.items() if t != EDGE_TYPE},
            # alias kept so the shared overview chrome (expects overdue_total) never KeyErrors
            "overdue_total": 0,
        }

    def feed(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        return self.list(params)  # already created-desc

    def healthz(self) -> dict[str, Any]:
        t0 = time.perf_counter()
        try:
            s = self.stats()
            ok = True
        except Exception:  # noqa: BLE001
            s, ok = {"key_metric": 0, "key_metric_label": "cards"}, False
        resp = healthz_response(
            namespace=NAMESPACE,
            database=str(self.db_path),
            elapsed_ms=(time.perf_counter() - t0) * 1000.0,
            ok=ok,
        )
        resp["stats"] = {"key_metric": s.get("key_metric", 0), "key_metric_label": s.get("key_metric_label", "cards")}
        return resp

    # ---- graph-aware view helpers (used by the handler subclass) -----------
    def edges(self) -> dict[str, Any]:
        """Full edge list with resolved endpoint titles + a node index, so the
        frontend can draw the incidence view and a D3 graph directly."""
        with self._conn() as conn:
            nodes = [self._node_card(r, full=False)
                     for r in conn.execute("SELECT * FROM cards WHERE type != ? ORDER BY created DESC", (EDGE_TYPE,)).fetchall()]
            title_by_id = {n["slug"]: n["title"] for n in nodes}
            type_by_id = {n["slug"]: n["type"] for n in nodes}
            edge_rows = conn.execute("SELECT metadata FROM cards WHERE type = ?", (EDGE_TYPE,)).fetchall()
        links = []
        for r in edge_rows:
            m = _loads(r["metadata"]) or {}
            src, tgt = m.get("source"), m.get("target")
            if not src or not tgt:
                continue
            links.append({
                "source": src, "target": tgt,
                "source_title": title_by_id.get(src, src),
                "target_title": title_by_id.get(tgt, tgt),
                "rel_type": m.get("relationship_type", ""),
                "strength": m.get("strength"),
                "summary": m.get("summary", ""),
            })
        return {
            "nodes": [{"id": n["slug"], "title": n["title"], "type": n["type"]} for n in nodes],
            "links": links,
            "node_types": type_by_id,
        }

    def people(self) -> dict[str, Any]:
        """Aggregate participants across node cards into a people view."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, title, type, created, metadata FROM cards WHERE type != ? ORDER BY created DESC",
                (EDGE_TYPE,),
            ).fetchall()
        agg: dict[str, dict[str, Any]] = {}
        for r in rows:
            m = _loads(r["metadata"]) or {}
            for p in (m.get("participants") or []):
                name = str(p).strip()
                if not name:
                    continue
                e = agg.setdefault(name, {"name": name, "count": 0, "cards": []})
                e["count"] += 1
                e["cards"].append({"id": r["id"], "title": r["title"], "type": r["type"], "created": r["created"]})
        items = sorted(agg.values(), key=lambda x: x["count"], reverse=True)
        return {"items": items, "total": len(items)}
