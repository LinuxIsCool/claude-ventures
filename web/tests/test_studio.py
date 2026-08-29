# web/tests/test_studio.py
from __future__ import annotations
import http.client
import json
import subprocess
import threading
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import ventures_studio
from ventures_accessor import VenturesAccessor
from ventures_handler import VenturesKernel

MANIFEST = """---
slug: {slug}
name: {name}
venture: acme
kind: web
stage: active
repo:
  path: {repo}
environments:
  - name: dev
    url: https://dev.acme.test/app
  - name: prod
    url: https://acme.test
    status: live
  - name: staging
    url: https://staging.acme.test
    controllable: true
depends_on: []
---
"""


def _store(tmp_path: Path) -> tuple[Path, Path]:
    vroot = tmp_path / "ventures"
    (vroot / "active").mkdir(parents=True)
    (vroot / "active" / "acme.md").write_text("---\nid: acme\ntitle: Acme\nstage: active\npriority: high\napps: [site]\n---\n")
    repo = tmp_path / "repo"; repo.mkdir()
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x", "HOME": str(tmp_path)}
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True, env=env)
    (repo / "x").write_text("x"); subprocess.run(["git", "add", "x"], cwd=repo, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", "i"], cwd=repo, check=True, env=env)
    d = vroot / "acme" / "apps" / "site"; d.mkdir(parents=True)
    (d / "app.md").write_text(MANIFEST.format(slug="site", name="Site", repo=str(repo)))
    bl = tmp_path / "backlog"; bl.mkdir()
    return vroot, bl


def test_studio_document_shape(tmp_path: Path):
    vroot, bl = _store(tmp_path)
    doc = ventures_studio.studio("acme", ventures_root=vroot, backlog_dir=bl)
    assert doc["venture"] == {"slug": "acme", "title": "Acme", "lifecycle": "active", "priority": "high"}
    assert [a["slug"] for a in doc["apps"]] == ["site"]
    app = doc["apps"][0]
    assert app["git"]["ok"] is True and app["git"]["branch"] == "main"
    assert [(e["name"], e["controllable"]) for e in app["environments"]] == [("dev", True), ("prod", False), ("staging", True)]
    assert [(d["host"], d["env"]) for d in doc["domains"]] == [("acme.test", "prod"), ("dev.acme.test", "dev"), ("staging.acme.test", "staging")]
    assert doc["domains"][0]["status"] == "live" and doc["domains"][1]["status"] == "declared"
    assert doc["counts"] == {"apps": 1, "domains": 3, "controllable": 2}
    assert doc["errors"] == []
    assert doc["phase"]["meetings"] == "done"


def test_app_without_repo_path_has_git_none(tmp_path: Path):
    vroot, bl = _store(tmp_path)
    d = vroot / "acme" / "apps" / "planned"; d.mkdir()
    (d / "app.md").write_text("---\nslug: planned\nname: P\nventure: acme\nkind: web\nstage: planned\nrepo: {}\nenvironments: []\ndepends_on: []\n---\n")
    doc = ventures_studio.studio("acme", ventures_root=vroot, backlog_dir=bl)
    planned = next(a for a in doc["apps"] if a["slug"] == "planned")
    assert planned["git"] is None


def test_not_found(tmp_path: Path):
    vroot, bl = _store(tmp_path)
    assert ventures_studio.studio("nope", ventures_root=vroot, backlog_dir=bl) == {"error": "not found", "slug": "nope"}


def test_environment_entries_that_are_not_dicts_are_ignored(tmp_path: Path):
    vroot, bl = _store(tmp_path)
    d = vroot / "acme" / "apps" / "weird"; d.mkdir()
    (d / "app.md").write_text(
        "---\nslug: weird\nname: W\nventure: acme\nkind: web\nstage: active\n"
        "repo: {}\nenvironments:\n  - dev\n  - name: prod\n    url: https://weird.acme.test\n"
        "depends_on: []\n---\n"
    )
    doc = ventures_studio.studio("acme", ventures_root=vroot, backlog_dir=bl)
    weird = next(a for a in doc["apps"] if a["slug"] == "weird")
    assert [e["name"] for e in weird["environments"]] == ["prod"]


def test_environment_url_without_scheme_is_dropped_from_domains(tmp_path: Path):
    vroot, bl = _store(tmp_path)
    d = vroot / "acme" / "apps" / "local"; d.mkdir()
    (d / "app.md").write_text(
        "---\nslug: local\nname: L\nventure: acme\nkind: web\nstage: active\n"
        "repo: {}\nenvironments:\n  - name: dev\n    url: localhost:3000\n"
        "depends_on: []\n---\n"
    )
    doc = ventures_studio.studio("acme", ventures_root=vroot, backlog_dir=bl)
    assert all(d["app"] != "local" for d in doc["domains"])


def _serve(vroot: Path, bl: Path) -> int:
    accessor = VenturesAccessor(data_root=vroot)
    kernel = VenturesKernel(accessor=accessor, port=0, bind="127.0.0.1", signature_fn=accessor.signature,
                            poll_interval_s=2.0, mutation_catalog=None, ventures_root=vroot, backlog_dir=bl)
    srv = kernel.build_server()
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv.server_address[1]


def test_route_serves_document_and_detail_still_works(tmp_path: Path):
    vroot, bl = _store(tmp_path)
    port = _serve(vroot, bl)
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request("GET", "/api/venture/acme/studio"); r = c.getresponse()
    assert r.status == 200
    body = json.loads(r.read())
    assert body["counts"]["apps"] == 1
    c.request("GET", "/api/venture/acme"); r = c.getresponse()
    assert r.status == 200 and json.loads(r.read())["slug"] == "acme"


def test_venture_slugged_studio_still_gets_detail(tmp_path: Path):
    vroot, bl = _store(tmp_path)
    (vroot / "active" / "studio.md").write_text("---\nid: studio\ntitle: Studio Venture\nstage: active\npriority: high\n---\n")
    port = _serve(vroot, bl)
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request("GET", "/api/venture/studio"); r = c.getresponse()
    assert r.status == 200
    body = json.loads(r.read())
    assert body["slug"] == "studio" and body["title"] == "Studio Venture"
    c.request("GET", "/api/venture/studio/studio"); r = c.getresponse()
    assert r.status == 200
    body = json.loads(r.read())
    assert body["counts"]["apps"] == 0


def test_network_route(tmp_path: Path):
    vroot, bl = _store(tmp_path)
    (bl / "task-1.md").write_text("---\nid: 1\ntitle: a\nventure: acme\nstatus: To Do\n---\n")
    (bl / "task-2.md").write_text("---\nid: 2\ntitle: b\nventure: acme\nstatus: done\ndepends_on: [1]\n---\n")
    port = _serve(vroot, bl)
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request("GET", "/api/venture/acme/network"); r = c.getresponse()
    assert r.status == 200
    body = json.loads(r.read())
    assert {n["id"] for n in body["nodes"]} == {"1"}
    c.request("GET", "/api/venture/acme/network?done=1"); r = c.getresponse()
    body = json.loads(r.read())
    assert {n["id"] for n in body["nodes"]} == {"1", "2"} and body["counts"]["edges"] == 1


def test_meetings_route_unavailable_when_db_missing(tmp_path: Path, monkeypatch):
    import ventures_meetings
    monkeypatch.setattr(ventures_meetings, "_DB_DEFAULT", tmp_path / "nope.db")
    vroot, bl = _store(tmp_path)
    port = _serve(vroot, bl)
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request("GET", "/api/venture/acme/meetings?q=x"); r = c.getresponse()
    assert r.status == 200
    body = json.loads(r.read())
    assert body["available"] is False and body["query"] == "x"


def test_studio_merges_snapshot(tmp_path: Path):
    import studio_snapshot
    from datetime import datetime, timezone, timedelta
    vroot, bl = _store(tmp_path)
    snap = tmp_path / "snap.json"
    gen = datetime(2026, 8, 29, 17, 0, tzinfo=timezone.utc)
    studio_snapshot.write_snapshot({"generated_at": gen.isoformat(), "interval_s": 60, "apps": {
        "acme/site": {"git": {"ok": True, "branch": "main"}, "environments": {"dev": {"ok": True, "decided_by": "body", "status": 200, "elapsed_ms": 3.2, "checked_at": gen.isoformat(), "probe": "x", "error": None}},
                      "containers": [{"name": "c1", "env": "dev", "state": "running", "health": "healthy"}], "containers_error": None}},
        "certs": {"acme.test": {"not_after": "2026-11-08T01:20:21+00:00", "days_left": 71, "error": None, "checked_at": gen.isoformat()}},
        "fleet": [], "errors": []}, path=snap)
    doc = ventures_studio.studio("acme", ventures_root=vroot, backlog_dir=bl, snapshot_path=snap, now=gen + timedelta(seconds=30))
    assert doc["snapshot"]["present"] is True and doc["snapshot"]["stale"] is False
    app = doc["apps"][0]
    assert app["live"]["containers"][0]["health"] == "healthy"
    envs = {e["name"]: e for e in app["environments"]}
    assert envs["dev"]["live"]["ok"] is True and envs["prod"]["live"] is None
    domains = {d["host"]: d for d in doc["domains"]}
    assert domains["acme.test"]["cert"]["days_left"] == 71 and domains["dev.acme.test"]["cert"] is None
    assert doc["phase"]["live"] == "snapshot"


def test_studio_without_snapshot_is_stale_not_broken(tmp_path: Path):
    vroot, bl = _store(tmp_path)
    doc = ventures_studio.studio("acme", ventures_root=vroot, backlog_dir=bl, snapshot_path=tmp_path / "none.json")
    assert doc["snapshot"] == {"present": False, "generated_at": None, "age_s": None, "stale": True, "interval_s": 60}
    assert doc["apps"][0]["live"] is None and all(e["live"] is None for e in doc["apps"][0]["environments"])
