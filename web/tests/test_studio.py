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
    assert doc["phase"]["meetings"] == "later"


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
