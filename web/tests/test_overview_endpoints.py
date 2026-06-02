from __future__ import annotations

import http.client
import json as _json
import sys
import threading
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent.parent  # web/
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import ventures_snapshot  # noqa: E402
from ventures_handler import VenturesKernel  # noqa: E402
from ventures_accessor import VenturesAccessor  # noqa: E402


def _mk_store(tmp_path: Path) -> tuple[Path, Path]:
    vroot = tmp_path / "ventures"
    (vroot / "active").mkdir(parents=True)
    (vroot / "active" / "bcrg.md").write_text(
        "---\nid: bcrg\ntitle: BCRG\nstage: active\npriority: critical\n"
        "description: Validator research.\n"
        "co_venturers:\n  - name: Shawn\n    role: Lead\n"
        "milestones:\n  - id: ms1\n    title: Phase 2\n    status: in_progress\n    date: \"2026-07-01\"\n"
        "financial:\n  revenue_to_date: 50000\n  currency: CAD\n"
        "deadlines:\n  - date: \"2026-06-10\"\n    label: Soon thing\n    type: hard\n"
        "---\nbody\n"
    )
    bl = tmp_path / "backlog"
    bl.mkdir()
    (bl / "task-1.md").write_text(
        "---\nid: 1\ntitle: Do thing\nstatus: To Do\npriority: high\nventure: bcrg\ndue: 2026-06-05\n---\n"
    )
    return vroot, bl


def _serve(tmp_path: Path) -> int:
    vroot, bl = _mk_store(tmp_path)
    accessor = VenturesAccessor(data_root=vroot)
    kernel = VenturesKernel(
        accessor=accessor,
        port=0,
        bind="127.0.0.1",
        signature_fn=accessor.signature,
        poll_interval_s=2.0,
        mutation_catalog=None,
        ventures_root=vroot,
        backlog_dir=bl,
    )
    srv = kernel.build_server()
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv.server_address[1]


_EXPECTED_KEYS = {
    "/api/focus": {"today", "this_week", "soon", "attention"},
    "/api/timeline": {"lanes", "range"},
    "/api/priorities": {"items"},
    "/api/trends": {"series", "derivable", "snapshot_based"},
}


@pytest.fixture(autouse=True)
def _isolate_snapshot(tmp_path: Path, monkeypatch):
    """Redirect the trends lazy-snapshot default away from the real metrics file."""
    snap = tmp_path / "metrics" / "snapshots.jsonl"
    monkeypatch.setattr(ventures_snapshot, "_SNAPSHOT_PATH_DEFAULT", snap)
    yield


@pytest.mark.parametrize("path", sorted(_EXPECTED_KEYS))
def test_overview_endpoint_get_200_with_keys(tmp_path: Path, path: str):
    port = _serve(tmp_path)
    conn = http.client.HTTPConnection("127.0.0.1", port)
    conn.request("GET", path)
    r = conn.getresponse()
    assert r.status == 200, f"{path} -> {r.status}"
    body = _json.loads(r.read())
    assert _EXPECTED_KEYS[path].issubset(body.keys()), f"{path} missing keys: {body.keys()}"


@pytest.mark.parametrize("path", sorted(_EXPECTED_KEYS))
def test_overview_endpoint_post_405(tmp_path: Path, path: str):
    port = _serve(tmp_path)
    conn = http.client.HTTPConnection("127.0.0.1", port)
    conn.request("POST", path)
    assert conn.getresponse().status == 405, f"{path} POST not 405"


def test_list_still_served(tmp_path: Path):
    """Regression: fallthrough to the kernel's standard routes still works."""
    port = _serve(tmp_path)
    conn = http.client.HTTPConnection("127.0.0.1", port)
    conn.request("GET", "/api/list")
    assert conn.getresponse().status == 200


def test_trends_does_not_write_real_metrics(tmp_path: Path):
    """The lazy snapshot write must land under the monkeypatched tmp path."""
    real = Path.home() / ".claude" / "local" / "ventures" / "metrics" / "snapshots.jsonl"
    existed = real.exists()
    before = real.stat().st_mtime if existed else None
    port = _serve(tmp_path)
    conn = http.client.HTTPConnection("127.0.0.1", port)
    conn.request("GET", "/api/trends")
    assert conn.getresponse().status == 200
    if existed:
        assert real.stat().st_mtime == before, "trends polluted the real metrics file"
    else:
        assert not real.exists(), "trends created the real metrics file"
    # the tmp snapshot is where the write should have gone
    assert (tmp_path / "metrics" / "snapshots.jsonl").exists()
