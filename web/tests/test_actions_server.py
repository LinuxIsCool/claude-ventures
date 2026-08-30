from __future__ import annotations
import http.client, json, threading
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import actions_server
import studio_actions as A
from test_studio_actions import _root, _root_no_controllable, _Fake  # noqa: E402  (fixtures from Task 1)


def _serve(tmp_path: Path, run, shells=None, vroot=None):
    if vroot is None:
        vroot = _root(tmp_path)
    k = actions_server.build_kernel(port=0, ventures_root=vroot, log_path=tmp_path / "actions.log",
                                    shells_path=tmp_path / "shells.json", run=run, shells=shells,
                                    audit_dir=tmp_path / "audit")
    srv = k.build_server()
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv.server_address[1]


def _post(port, tool, args):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request("POST", "/api/mutate", body=json.dumps({"tool": tool, "args": args}), headers={"Content-Type": "application/json"})
    r = c.getresponse(); return r.status, json.loads(r.read())


def test_status_and_start_over_http(tmp_path: Path):
    run = lambda argv, timeout, cwd: (0, '{"Name":"acme-site-web-1","State":"running","Health":""}\n' if argv[-2:] == ["--format", "json"] else "started\n")
    port = _serve(tmp_path, run)
    st, body = _post(port, "studio_status", {"venture": "acme", "app": "site", "env": "dev"})
    assert st == 200 and body["result"]["containers"][0]["name"] == "acme-site-web-1"
    st, body = _post(port, "studio_start", {"venture": "acme", "app": "site", "env": "dev"})
    assert st == 200 and body["result"]["ok"] is True
    assert len((tmp_path / "actions.log").read_text().splitlines()) == 2


def test_refusals_map_to_mutation_errors(tmp_path: Path):
    port = _serve(tmp_path, lambda *a: (0, ""))
    st, body = _post(port, "studio_stop", {"venture": "acme", "app": "site", "env": "staging"})
    assert st >= 400 and body.get("code") == "NOT_CONTROLLABLE"
    st, body = _post(port, "studio_start", {"venture": "acme", "app": "site", "env": "x/y"})
    assert st >= 400 and body.get("code") == "BAD_ARG"
    st, body = _post(port, "studio_down", {})
    assert st == 404


def test_shell_tools_over_http(tmp_path: Path):
    f = _Fake()
    shells = A.Shells(tmp_path / "shells.json", popen=f.popen, kill=f.kill, alive=f.alive, which=f.which, free_port=f.free_port, now=f.now, log_path=tmp_path / "actions.log")
    port = _serve(tmp_path, lambda *a: (0, ""), shells=shells)
    st, body = _post(port, "studio_shell_open", {"venture": "acme", "app": "site"})
    assert st == 200 and body["result"]["url"] == "http://127.0.0.1:8901/"
    st, body = _post(port, "studio_shells", {})
    assert st == 200 and len(body["result"]["shells"]) == 1
    st, body = _post(port, "studio_shell_close", {"venture": "acme", "app": "site"})
    assert st == 200 and body["result"]["closed"] == 1


def test_get_surfaces(tmp_path: Path):
    port = _serve(tmp_path, lambda *a: (0, ""))
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request("GET", "/healthz"); r = c.getresponse(); h = json.loads(r.read())
    assert r.status == 200 and h["ok"] is True and h["namespace"] == "legion.studio-actions"
    c.request("GET", "/"); r = c.getresponse(); assert r.status == 200 and b"ventures" in r.read()
    c.request("GET", "/api/list"); r = c.getresponse(); assert r.status == 200


def test_shell_open_refuses_when_no_controllable_environment(tmp_path: Path):
    vroot = _root_no_controllable(tmp_path)
    f = _Fake()
    shells = A.Shells(tmp_path / "shells.json", popen=f.popen, kill=f.kill, alive=f.alive, which=f.which, free_port=f.free_port, now=f.now, log_path=tmp_path / "actions.log")
    port = _serve(tmp_path, lambda *a: (0, ""), shells=shells, vroot=vroot)
    st, body = _post(port, "studio_shell_open", {"venture": "acme", "app": "site"})
    assert st >= 400 and body.get("code") == "NOT_CONTROLLABLE"
    assert f.spawned == []
