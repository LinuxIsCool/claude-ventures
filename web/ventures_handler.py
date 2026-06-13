# web/ventures_handler.py
"""VenturesHandler + VenturesKernel.

Two surfaces on one kernel:
  1. Portfolio (existing): /, /api/list, /api/stats, the 3 detail routes,
     and the Phase-B overview routes (focus/timeline/priorities/trends).
  2. Per-venture **workspace** (new): /<alias>/ serves a youtube-style card
     workspace over the card graph (cards.db) joined with backlog / journal /
     venture stores. Reachable in Mode B at /ventures/<alias>/.

The workspace alias registry (WORKSPACES) maps a short URL segment to a
venture slug + match terms. The card graph is read via WorkspaceAccessor;
external joins via workspace_views. Adding a venture workspace = one registry
entry, no new code.
"""
from __future__ import annotations
from datetime import date
from urllib.parse import unquote, urlparse, parse_qs

from claude_webui import WebuiKernel
from claude_webui.kernel import WebuiHandler

import ventures_detail
import ventures_focus
import ventures_timeline
import ventures_priorities
import ventures_trends

import workspace_views
from workspace_accessor import WorkspaceAccessor

# Per-venture workspace registry. segment -> {slug, terms, title}. Short
# aliases live here; ANY real venture slug also resolves (fallback below), so
# every venture gets a workspace at /ventures/<slug>/ — Phase 1 of task-4101.
WORKSPACES: dict[str, dict] = {
    "cie": {
        "slug": "civic-intelligence-engine",
        "terms": ("civic intelligence engine", "cie", "civic-intelligence-engine"),
        "title": "CIE Workspace",
    },
}
# Accept the full slug as an alias for each registered workspace.
for _cfg in list(WORKSPACES.values()):
    WORKSPACES.setdefault(_cfg["slug"], _cfg)

# Reserved first-segments that are NOT venture aliases (portfolio's own routes).
_RESERVED_SEGMENTS = {"api", "static", "healthz", "favicon.ico", "vendor", "media"}


def _resolve_workspace(alias: str) -> dict | None:
    """Map a URL segment to a workspace config. Registered aliases win; any
    real venture slug (a file in the ventures store) resolves generically with
    slug-derived match terms. Returns None for reserved/unknown segments."""
    if not alias or alias in _RESERVED_SEGMENTS:
        return None
    cfg = WORKSPACES.get(alias)
    if cfg is not None:
        return cfg
    # Generic fallback: is this a real venture slug?
    if workspace_views._venture_file(alias) is not None:
        words = alias.replace("-", " ")
        return {"slug": alias, "terms": (alias, words), "title": alias}
    return None


# One shared accessor over the card graph (cheap, read-only, mtime-cached).
_WS_ACCESSOR = WorkspaceAccessor()


class VenturesHandler(WebuiHandler):
    ventures_root = None
    backlog_dir = None

    # ---- per-venture workspace surface ------------------------------------
    def _try_workspace(self, path: str) -> bool:
        """Route /<alias>/... to the card workspace. Returns True if handled."""
        seg = path.strip("/").split("/", 1)
        alias = seg[0]
        cfg = _resolve_workspace(alias)
        if cfg is None:
            return False
        rest = "/" + seg[1] if len(seg) > 1 else "/"
        slug, terms = cfg["slug"], cfg["terms"]
        acc = _WS_ACCESSOR
        try:
            if rest in ("/", ""):
                return self._serve_workspace_index()
            if rest == "/healthz":
                self._send_json(acc.healthz()); return True
            if rest == "/api/stats":
                self._send_json(acc.stats()); return True
            if rest == "/api/list":
                params = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
                self._send_json(acc.list(params)); return True
            if rest.startswith("/api/detail/"):
                self._send_json(acc.detail(unquote(rest[len("/api/detail/"):]))); return True
            if rest == "/api/edges":
                self._send_json(acc.edges()); return True
            if rest == "/api/people":
                self._send_json(acc.people()); return True
            if rest == "/api/venture":
                self._send_json(workspace_views.venture(slug)); return True
            if rest == "/api/backlog":
                self._send_json(workspace_views.backlog(slug, terms)); return True
            if rest == "/api/journal":
                self._send_json(workspace_views.journal(terms)); return True
            if rest == "/api/resources":
                self._send_json(workspace_views.resources(slug, terms)); return True
        except Exception as exc:  # noqa: BLE001
            self._send_json({"error": str(exc)}, status=500); return True
        # unknown sub-path under a real workspace alias -> 404 (handled here so
        # it never falls through to the portfolio router)
        self._send_json({"error": f"unknown workspace path: {rest}"}, status=404)
        return True

    def _serve_workspace_index(self) -> bool:
        if self.static_dir is None:
            self._send_json({"error": "no static_dir"}, status=500); return True
        f = self.static_dir / "workspace.html"
        if not f.is_file():
            self._send_json({"error": "workspace.html missing"}, status=500); return True
        self._send_bytes(f.read_bytes(), content_type="text/html; charset=utf-8")
        return True

    # ---- dispatch ----------------------------------------------------------
    def _dispatch_get(self) -> None:
        path = unquote(urlparse(self.path).path)
        vroot = self.ventures_root
        bl = self.backlog_dir
        try:
            if self._try_workspace(path):
                return
            if path == "/api/focus":
                self._send_json(ventures_focus.buckets(vroot, bl, date.today())); return
            if path == "/api/timeline":
                self._send_json(ventures_timeline.timeline(vroot, bl, date.today())); return
            if path == "/api/priorities":
                self._send_json(ventures_priorities.ranked(vroot, bl, date.today())); return
            if path == "/api/trends":
                self._send_json(ventures_trends.trends(vroot, bl, date.today())); return
            if path.startswith("/api/venture/"):
                self._send_json(ventures_detail.venture(path[len("/api/venture/"):], ventures_root=vroot, backlog_dir=bl)); return
            if path.startswith("/api/project/"):
                self._send_json(ventures_detail.project(path[len("/api/project/"):], ventures_root=vroot, backlog_dir=bl)); return
            if path.startswith("/api/milestone/"):
                rest = path[len("/api/milestone/"):].split("/", 1)
                if len(rest) == 2:
                    self._send_json(ventures_detail.milestone(rest[0], rest[1], ventures_root=vroot, backlog_dir=bl)); return
        except Exception as exc:  # noqa: BLE001
            self._send_json({"error": str(exc)}, status=500); return
        super()._dispatch_get()


class VenturesKernel(WebuiKernel):
    def __init__(self, *args, ventures_root=None, backlog_dir=None, **kwargs):
        self._ventures_root = ventures_root
        self._backlog_dir = backlog_dir
        super().__init__(*args, **kwargs)

    def _make_handler_class(self) -> type[WebuiHandler]:
        accessor = self.accessor
        static_dir = self.static_dir
        event_bus = self._event_bus
        mutation_catalog = self._mutation_catalog
        vroot = self._ventures_root
        bl = self._backlog_dir

        class _Handler(VenturesHandler):
            pass
        _Handler.accessor = accessor
        _Handler.static_dir = static_dir
        _Handler.event_bus = event_bus
        _Handler.mutation_catalog = mutation_catalog
        _Handler.ventures_root = vroot
        _Handler.backlog_dir = bl
        return _Handler
