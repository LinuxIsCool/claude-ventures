# web/ventures_handler.py
"""VenturesHandler + VenturesKernel: 3 detail routes over the read-only kernel."""
from __future__ import annotations
from datetime import date
from urllib.parse import unquote, urlparse

from claude_webui import WebuiKernel
from claude_webui.kernel import WebuiHandler

import ventures_detail
import ventures_focus
import ventures_timeline
import ventures_priorities
import ventures_trends


class VenturesHandler(WebuiHandler):
    ventures_root = None
    backlog_dir = None

    def _dispatch_get(self) -> None:
        path = unquote(urlparse(self.path).path)
        vroot = self.ventures_root
        bl = self.backlog_dir
        try:
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
