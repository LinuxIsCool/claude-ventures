# plugins/claude-ventures/web/tests/test_endpoints.py
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent.parent  # web/
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from ventures_accessor import VenturesAccessor  # noqa: E402


def _make_store(tmp_path: Path) -> Path:
    root = tmp_path / "ventures"
    (root / "active").mkdir(parents=True)
    (root / "exploring").mkdir(parents=True)
    (root / "dormant").mkdir(parents=True)
    (root / "harvesting").mkdir(parents=True)
    (root / "active" / "alpha.md").write_text(
        "---\n"
        "id: alpha\n"
        "title: Alpha Venture\n"
        "description: First test venture.\n"
        "stage: active\n"
        "priority: critical\n"
        "co_venturers:\n"
        "  - name: Shawn Anderson\n"
        "    role: Lead\n"
        "deadlines:\n"
        "  - date: \"2026-04-01\"\n"
        "    label: Overdue milestone\n"
        "    type: hard\n"
        "  - date: \"2026-12-01\"\n"
        "    label: Future milestone\n"
        "    type: soft\n"
        "---\n\nBody text.\n"
    )
    (root / "exploring" / "beta.md").write_text(
        "---\nid: beta\ntitle: Beta Venture\nstage: exploring\npriority: medium\n---\n\nBody.\n"
    )
    return root


def test_list_returns_summaries_with_lifecycle_and_overdue(tmp_path: Path):
    root = _make_store(tmp_path)
    acc = VenturesAccessor(data_root=root, today=date(2026, 6, 1))
    items = acc.list({})
    by_slug = {i["slug"]: i for i in items}
    assert set(by_slug) == {"alpha", "beta"}
    assert by_slug["alpha"]["lifecycle"] == "active"
    assert by_slug["alpha"]["title"] == "Alpha Venture"
    assert by_slug["alpha"]["overdue_count"] == 1
    assert by_slug["beta"]["lifecycle"] == "exploring"
    assert by_slug["beta"]["overdue_count"] == 0


def test_detail_returns_full_record(tmp_path: Path):
    root = _make_store(tmp_path)
    acc = VenturesAccessor(data_root=root, today=date(2026, 6, 1))
    rec = acc.detail("alpha")
    assert rec["title"] == "Alpha Venture"
    assert rec["co_venturers"] == [{"name": "Shawn Anderson", "role": "Lead"}]
    assert len(rec["deadlines"]) == 2
    assert rec["overdue_count"] == 1


def test_detail_unknown_slug_returns_error(tmp_path: Path):
    root = _make_store(tmp_path)
    acc = VenturesAccessor(data_root=root, today=date(2026, 6, 1))
    rec = acc.detail("does-not-exist")
    assert rec == {"error": "not found", "slug": "does-not-exist"}


def test_stats_rolls_up_counts_and_overdue(tmp_path: Path):
    root = _make_store(tmp_path)
    acc = VenturesAccessor(data_root=root, today=date(2026, 6, 1))
    s = acc.stats()
    assert s["key_metric"] == 1
    assert s["key_metric_label"] == "active ventures"
    assert s["by_lifecycle"] == {"active": 1, "exploring": 1, "dormant": 0, "harvesting": 0}
    assert s["overdue_total"] == 1
    assert s["overdue_milestones"][0]["venture"] == "alpha"
    assert s["overdue_milestones"][0]["label"] == "Overdue milestone"
    assert s["overdue_milestones"][0]["days_overdue"] == 61


def test_healthz_and_feed_and_signature(tmp_path: Path):
    root = _make_store(tmp_path)
    acc = VenturesAccessor(data_root=root, today=date(2026, 6, 1))
    h = acc.healthz()
    assert h["ok"] is True
    assert h["namespace"] == "legion.claude-venture"
    assert h["stats"]["key_metric"] == 1
    feed = acc.feed({})
    assert feed[0]["slug"] == "alpha"
    sig1 = acc.signature()
    (root / "active" / "alpha.md").write_text("---\nid: alpha\ntitle: X\nstage: active\n---\n")
    assert acc.signature() != sig1


import http.client
import threading


def _serve(kernel):
    httpd = kernel.build_server()
    th = threading.Thread(target=httpd.serve_forever, daemon=True)
    th.start()
    return th


def test_build_kernel_serves_standard_routes(tmp_path: Path):
    root = _make_store(tmp_path)
    import server
    kernel = server.build_kernel(port=0, data_root=root)
    _serve(kernel)
    port = kernel._server.server_address[1]
    conn = http.client.HTTPConnection("127.0.0.1", port)
    conn.request("GET", "/api/stats")
    resp = conn.getresponse()
    assert resp.status == 200
    conn.request("POST", "/api/stats")
    assert conn.getresponse().status == 405
