# web/ventures_handler.py
"""VenturesHandler + VenturesKernel: 6 detail routes over the read-only kernel."""
from __future__ import annotations
from datetime import date
from threading import Thread
from urllib.parse import parse_qs, unquote, urlparse

from claude_webui import WebuiKernel
from claude_webui.kernel import WebuiHandler

import ventures_contract
import ventures_detail
import ventures_focus
import ventures_timeline
import ventures_priorities
import ventures_trends
import ventures_tasks
import ventures_portfolio
import ventures_studio
import ventures_network
import ventures_meetings
from ventures_scope import PortfolioScope


class VenturesHandler(WebuiHandler):
    ventures_root = None
    backlog_dir = None

    def _dispatch_get(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        scope = PortfolioScope.from_query(parse_qs(parsed.query))
        vroot = self.ventures_root
        bl = self.backlog_dir
        try:
            if path == "/api/bands":
                # The render manifest. Served from the same file the contract
                # test reads, so the page and the check cannot disagree.
                self._send_json(ventures_contract.load_manifest()); return
            if path == "/api/contract":
                self._send_json(ventures_contract.report(vroot)); return
            if path == "/api/focus":
                self._send_json(ventures_focus.buckets(vroot, bl, date.today(), scope)); return
            if path == "/api/tasks":
                self._send_json({"scope": scope.as_dict(), "records": ventures_tasks.records(vroot, bl, scope, date.today())}); return
            if path == "/api/card_metrics":
                self._send_json(ventures_tasks.card_metrics(vroot, bl, date.today())); return
            if path == "/api/portfolio":
                self._send_json(ventures_portfolio.data_view(vroot, bl, date.today(), parse_qs(parsed.query))); return
            if path in {"/api/widgets/active_tasks", "/api/widgets/active_tasks/records"}:
                self._send_json(ventures_tasks.widget(vroot, bl, scope, date.today(), "active", path.endswith("/records"))); return
            if path in {"/api/widgets/overdue_tasks", "/api/widgets/overdue_tasks/records"}:
                self._send_json(ventures_tasks.widget(vroot, bl, scope, date.today(), "overdue", path.endswith("/records"))); return
            if path == "/api/timeline":
                self._send_json(ventures_timeline.timeline(vroot, bl, date.today())); return
            if path == "/api/priorities":
                self._send_json(ventures_priorities.ranked(vroot, bl, date.today())); return
            if path == "/api/trends":
                self._send_json(ventures_trends.trends(vroot, bl, date.today())); return
            if path.startswith("/api/venture/"):
                rest = path[len("/api/venture/"):]
                if rest.endswith("/studio"):
                    slug = rest[:-len("/studio")]
                    if slug and "/" not in slug:
                        self._send_json(ventures_studio.studio(slug, ventures_root=vroot, backlog_dir=bl)); return
                if rest.endswith("/network"):
                    slug = rest[:-len("/network")]
                    if slug and "/" not in slug:
                        include_done = parse_qs(parsed.query).get("done", ["0"])[0] == "1"
                        self._send_json(ventures_network.network(slug, backlog_dir=bl, include_done=include_done)); return
                if rest.endswith("/meetings"):
                    slug = rest[:-len("/meetings")]
                    if slug and "/" not in slug:
                        q = parse_qs(parsed.query).get("q", [""])[0]
                        self._send_json(ventures_meetings.catalogue(slug, q=q)); return
                self._send_json(ventures_detail.venture(rest, ventures_root=vroot, backlog_dir=bl)); return
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
        # Prime the filesystem-backed indexes while the Hub is mounting its
        # satellites. The first human Portfolio request should never pay the
        # full YAML corpus parse cost.
        Thread(target=self._warm_portfolio, name="ventures-portfolio-warm", daemon=True).start()

    def _warm_portfolio(self) -> None:
        try:
            ventures_portfolio.data_view(
                self._ventures_root, self._backlog_dir, date.today(), {}
            )
        except Exception:
            pass  # normal request handling retains the truthful error path

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
