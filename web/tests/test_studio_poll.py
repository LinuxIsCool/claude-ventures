from __future__ import annotations
import json
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import studio_poll as P


class Boom(Exception):
    pass


def _fetch_factory(table):
    """table: url -> (status, body bytes) or an Exception instance to raise."""
    def fetch(url, headers, timeout):
        r = table[url]
        if isinstance(r, Exception):
            raise r
        return r
    return fetch


def test_probe_target_rules():
    assert P.probe_target({"url": "https://a.test", "healthz": "/healthz"}) == ("https://a.test/healthz", None)
    assert P.probe_target({"url": "https://a.test/dev/", "healthz": "/healthz"}) == ("https://a.test/dev/healthz", None)
    assert P.probe_target({"url": "https://a.test"}) == ("https://a.test", None)
    assert P.probe_target({"url": "https://a.test", "probe_url": "http://127.0.0.1:8180/healthz", "probe_host": "x.localhost"}) == ("http://127.0.0.1:8180/healthz", "x.localhost")
    assert P.probe_target({"name": "prod"}) == (None, None)


def test_probe_http_decisions():
    fetch = _fetch_factory({
        "u/ok": (200, b'{"ok": true}'), "u/bodyfalse": (200, b'{"ok": false}'), "u/plain": (204, b""),
        "u/gated": (401, b"Unauthorized"), "u/500": (500, b"x"), "u/err": Boom("connection refused"),
    })
    t = iter([0.0, 0.0123] * 10)
    clock = lambda: next(t)
    assert P.probe_http("u/ok", None, fetch, clock=clock)["decided_by"] == "body"
    assert P.probe_http("u/ok", None, fetch, clock=clock)["ok"] is True
    r = P.probe_http("u/bodyfalse", None, fetch, clock=clock); assert (r["ok"], r["decided_by"]) == (False, "body")
    r = P.probe_http("u/plain", None, fetch, clock=clock); assert (r["ok"], r["decided_by"], r["status"]) == (True, "status", 204)
    r = P.probe_http("u/gated", None, fetch, clock=clock); assert (r["ok"], r["decided_by"]) == (True, "gated")
    r = P.probe_http("u/500", None, fetch, clock=clock); assert (r["ok"], r["decided_by"]) == (False, "status")
    r = P.probe_http("u/err", None, fetch, clock=clock)
    assert (r["ok"], r["decided_by"], r["status"]) == (False, "error", None) and "connection refused" in r["error"]
    assert abs(r["elapsed_ms"] - 12.3) < 0.01


def test_probe_http_sends_host_header():
    seen = {}
    def fetch(url, headers, timeout):
        seen.update(headers); return (200, b"")
    P.probe_http("http://127.0.0.1:8888/", "fast-site.local.legion.localhost", fetch)
    assert seen["Host"] == "fast-site.local.legion.localhost"


def test_default_fetch_does_not_follow_redirects():
    class RedirectingHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/r":
                self.send_response(302)
                self.send_header("Location", "/elsewhere")
                self.end_headers()
            elif self.path == "/elsewhere":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, fmt, *args):  # noqa: A003 -- quiet the test run
            pass

    server = HTTPServer(("127.0.0.1", 0), RedirectingHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, _body = P.default_fetch(f"http://127.0.0.1:{port}/r", {}, 5)
        assert status == 302
    finally:
        server.shutdown()
        thread.join()


def test_containers_for_parses_docker_output():
    calls = []
    def run(argv, timeout):
        calls.append(argv)
        if argv[:2] == ["docker", "ps"]:
            return '{"ID":"abc","Names":"indigenomics-dev-nginx-1","State":"running","Status":"Up 11 hours","Labels":"legion.env=dev,com.docker.compose.project=indigenomics-dev,legion.app=living-library"}\n'
        return '{"Status":"running","Health":{"Status":"healthy"},"StartedAt":"2026-08-25T20:21:37Z"}'
    rows, err = P.containers_for("indigenomics-ai", "living-library", run)
    assert err is None and rows == [{"name": "indigenomics-dev-nginx-1", "env": "dev", "state": "running", "health": "healthy",
                                      "status": "Up 11 hours", "project": "indigenomics-dev", "started_at": "2026-08-25T20:21:37Z"}]
    assert "label=legion.venture=indigenomics-ai" in calls[0] and "label=legion.app=living-library" in calls[0]


def test_containers_for_tolerates_failures():
    def run(argv, timeout):
        raise Boom("docker not available")
    rows, err = P.containers_for("v", "a", run)
    assert rows == [] and "docker not available" in err
    def run2(argv, timeout):
        return "" if argv[:2] == ["docker", "ps"] else "{}"
    assert P.containers_for("v", "a", run2) == ([], None)


def test_cert_for_parses_and_counts_days():
    now = datetime(2026, 8, 29, 0, 0, tzinfo=timezone.utc)
    r = P.cert_for("civicintelligence.xyz", lambda h: "Nov  8 01:20:21 2026 GMT", now=now)
    assert r["not_after"].startswith("2026-11-08T01:20:21") and r["days_left"] == 71 and r["error"] is None
    r = P.cert_for("nope.example", lambda h: (_ for _ in ()).throw(Boom("gaierror")), now=now)
    assert r["not_after"] is None and r["days_left"] is None and "gaierror" in r["error"]


def _vroot(tmp_path: Path) -> Path:
    vroot = tmp_path / "ventures"
    d = vroot / "acme" / "apps" / "site"; d.mkdir(parents=True)
    (d / "app.md").write_text("---\nslug: site\nname: Site\nventure: acme\nkind: web\nstage: active\nrepo: {}\n"
                              "environments:\n  - name: dev\n    url: https://dev.acme.test\n    healthz: /healthz\n"
                              "  - name: prod\n    url: https://acme.test\n  - name: planned\n"
                              "depends_on: []\n---\n")
    (vroot / "acme" / "projects").mkdir()
    return vroot


def test_build_snapshot_shape_and_cert_reuse(tmp_path: Path):
    vroot = _vroot(tmp_path)
    fetch = _fetch_factory({"https://dev.acme.test/healthz": (200, b'{"ok":true}'), "https://acme.test": (401, b"")})
    run = lambda argv, timeout: "" if argv[:2] == ["docker", "ps"] else "{}"
    tls_calls = []
    def tls(host):
        tls_calls.append(host); return "Nov  8 01:20:21 2026 GMT"
    now = datetime(2026, 8, 29, 17, 0, tzinfo=timezone.utc)
    snap = P.build_snapshot(vroot, fetch=fetch, run=run, tls=tls, previous=None, now=now, interval_s=60)
    assert snap["generated_at"] == now.isoformat() and snap["interval_s"] == 60 and snap["elapsed_ms"] >= 0
    app = snap["apps"]["acme/site"]
    assert app["git"] is None
    assert set(app["environments"]) == {"dev", "prod"}  # planned has no url, no probe
    assert app["environments"]["dev"]["ok"] is True and app["environments"]["prod"]["decided_by"] == "gated"
    assert app["environments"]["dev"]["checked_at"] == now.isoformat()
    assert app["containers"] == [] and app["containers_error"] is None
    assert set(snap["certs"]) == {"dev.acme.test", "acme.test"} and sorted(tls_calls) == ["acme.test", "dev.acme.test"]
    # second run 10 minutes later reuses cert entries (no TLS calls), reprobes health
    tls_calls.clear()
    snap2 = P.build_snapshot(vroot, fetch=fetch, run=run, tls=tls, previous=snap, now=now + timedelta(minutes=10), interval_s=60)
    assert tls_calls == [] and snap2["certs"]["acme.test"]["checked_at"] == snap["certs"]["acme.test"]["checked_at"]
    snap3 = P.build_snapshot(vroot, fetch=fetch, run=run, tls=tls, previous=snap, now=now + timedelta(hours=2), interval_s=60)
    assert sorted(tls_calls) == ["acme.test", "dev.acme.test"]


def test_build_snapshot_collector_failure_is_recorded_not_raised(tmp_path: Path):
    vroot = _vroot(tmp_path)
    def fetch(url, headers, timeout): raise Boom("net down")
    def run(argv, timeout): raise Boom("no docker")
    def tls(host): raise Boom("no tls")
    snap = P.build_snapshot(vroot, fetch=fetch, run=run, tls=tls, previous=None, now=datetime.now(timezone.utc))
    app = snap["apps"]["acme/site"]
    assert app["environments"]["dev"]["decided_by"] == "error"
    assert app["containers"] == [] and "no docker" in app["containers_error"]
    assert snap["certs"]["acme.test"]["error"]


def test_main_once_writes_snapshot(tmp_path: Path, monkeypatch):
    vroot = _vroot(tmp_path)
    monkeypatch.setattr(P, "default_fetch", lambda url, headers, timeout: (200, b"{}"))
    monkeypatch.setattr(P, "default_run", lambda argv, timeout: "")
    monkeypatch.setattr(P, "default_tls", lambda host: "Nov  8 01:20:21 2026 GMT")
    out = tmp_path / "snap.json"
    rc = P.main(["--once", "--snapshot", str(out), "--ventures-root", str(vroot)])
    assert rc == 0 and json.loads(out.read_text())["apps"]["acme/site"]["environments"]["dev"]["ok"] is True
