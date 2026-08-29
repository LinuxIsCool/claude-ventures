"""Studio poller: collect live state for every app manifest and write one
snapshot. The only process in the ventures plugin that touches the network,
Docker or TLS. Every collector takes its I/O as an injected callable so tests
run without any of them.

    python studio_poll.py --once            # one pass (what the systemd timer runs)
    python studio_poll.py --interval 60     # loop forever

Spec: backlog task-824 section 6.3.
"""
from __future__ import annotations
import argparse
import json
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import studio_snapshot
import ventures_apps
import ventures_git

HTTP_TIMEOUT_S = 6.0
DOCKER_TIMEOUT_S = 8.0
CERT_TTL_S = 3600
FLEET_DEFAULT = Path.home() / ".claude" / "local" / "fleet" / "webui-registry.json"


# ---- default I/O seams ------------------------------------------------------

def default_fetch(url: str, headers: dict[str, str], timeout: float) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(65536)
    except urllib.error.HTTPError as exc:  # any HTTP status is an answer, not a failure
        return exc.code, exc.read(65536) if hasattr(exc, "read") else b""


def default_run(argv: list[str], timeout: float) -> str:
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=True).stdout


def default_tls(host: str) -> str:
    ctx = ssl.create_default_context()
    with socket.create_connection((host, 443), timeout=6) as sock, ctx.wrap_socket(sock, server_hostname=host) as tls:
        return str(tls.getpeercert()["notAfter"])


# ---- collectors ---------------------------------------------------------------

def probe_target(env: dict[str, Any]) -> tuple[str | None, str | None]:
    if env.get("probe_url"):
        return str(env["probe_url"]), (str(env["probe_host"]) if env.get("probe_host") else None)
    url = env.get("url")
    if not url:
        return None, None
    url = str(url)
    if env.get("healthz"):
        base = url if url.endswith("/") else url + "/"
        return urljoin(base, str(env["healthz"]).lstrip("/")), None
    return url, None


def probe_http(target: str, host_header: str | None, fetch: Callable, timeout_s: float = HTTP_TIMEOUT_S, clock=time.perf_counter) -> dict[str, Any]:
    headers = {"User-Agent": "legion-studio-poll/1"}
    if host_header:
        headers["Host"] = host_header
    t0 = clock()
    try:
        status, body = fetch(target, headers, timeout_s)
    except Exception as exc:  # noqa: BLE001 -- transport failure is a result, not a crash
        return {"probe": target, "status": None, "ok": False, "decided_by": "error", "elapsed_ms": round((clock() - t0) * 1000, 3), "error": f"{type(exc).__name__}: {exc}"}
    elapsed = round((clock() - t0) * 1000, 3)
    if status in (401, 403):
        return {"probe": target, "status": status, "ok": True, "decided_by": "gated", "elapsed_ms": elapsed, "error": None}
    try:
        parsed = json.loads(body.decode("utf-8", "replace")) if body else None
    except ValueError:
        parsed = None
    if isinstance(parsed, dict) and isinstance(parsed.get("ok"), bool):
        return {"probe": target, "status": status, "ok": parsed["ok"], "decided_by": "body", "elapsed_ms": elapsed, "error": None}
    return {"probe": target, "status": status, "ok": 200 <= int(status) < 300, "decided_by": "status", "elapsed_ms": elapsed, "error": None}


def _labels(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in str(raw or "").split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def containers_for(venture: str, app: str, run: Callable) -> tuple[list[dict[str, Any]], str | None]:
    argv = ["docker", "ps", "-a", "--filter", f"label=legion.venture={venture}", "--filter", f"label=legion.app={app}", "--format", "{{json .}}"]
    try:
        out = run(argv, DOCKER_TIMEOUT_S)
    except Exception as exc:  # noqa: BLE001
        return [], f"{type(exc).__name__}: {exc}"
    rows: list[dict[str, Any]] = []
    for line in str(out).splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        labels = _labels(row.get("Labels", ""))
        health, started = "none", None
        try:
            state = json.loads(run(["docker", "inspect", "--format", "{{json .State}}", str(row.get("ID"))], DOCKER_TIMEOUT_S) or "{}")
            health = (state.get("Health") or {}).get("Status") or "none"
            started = state.get("StartedAt")
        except Exception:  # noqa: BLE001 -- health is optional detail
            pass
        rows.append({"name": row.get("Names"), "env": labels.get("legion.env"), "state": row.get("State"), "health": health,
                     "status": row.get("Status"), "project": labels.get("com.docker.compose.project"), "started_at": started})
    return rows, None


def cert_for(host: str, probe: Callable[[str], str], now: datetime | None = None) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    try:
        raw = probe(host)
        not_after = datetime.strptime(raw, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    except Exception as exc:  # noqa: BLE001
        return {"not_after": None, "days_left": None, "error": f"{type(exc).__name__}: {exc}"}
    return {"not_after": not_after.isoformat(), "days_left": (not_after - current).days, "error": None}


def fleet_entries(path: Path | None = None) -> list[dict[str, Any]]:
    p = Path(path) if path else FLEET_DEFAULT
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = raw.values() if isinstance(raw, dict) else raw
    return [r for r in rows if isinstance(r, dict)]


# ---- assembly -----------------------------------------------------------------

def _venture_slugs(ventures_root: Path) -> list[str]:
    return sorted(d.name for d in ventures_root.iterdir() if d.is_dir() and (d / "apps").is_dir())


def build_snapshot(ventures_root: Path, *, fetch: Callable, run: Callable, tls: Callable, previous: dict | None,
                   now: datetime, interval_s: int = 60, fleet_path: Path | None = None) -> dict[str, Any]:
    t0 = time.perf_counter()
    stamp = now.isoformat()
    prev_certs = (previous or {}).get("certs") or {}
    apps: dict[str, Any] = {}
    certs: dict[str, Any] = {}
    errors: list[str] = []
    for venture in _venture_slugs(ventures_root):
        for app in ventures_apps.list_for(venture, ventures_root=ventures_root):
            key = f"{venture}/{app['slug']}"
            repo = app.get("repo") if isinstance(app.get("repo"), dict) else {}
            git = ventures_git.repo_state(repo["path"]) if repo.get("path") else None
            envs: dict[str, Any] = {}
            for env in app.get("environments") or []:
                if not isinstance(env, dict) or not env.get("name"):
                    continue
                target, host_header = probe_target(env)
                if not target:
                    continue
                envs[str(env["name"])] = dict(probe_http(target, host_header, fetch), checked_at=stamp)
                host = urlparse(str(env.get("url") or "")).hostname
                if host and str(env.get("url", "")).startswith("https://") and host not in certs:
                    old = prev_certs.get(host)
                    fresh = False
                    if old and old.get("checked_at"):
                        try:
                            fresh = (now - datetime.fromisoformat(old["checked_at"])).total_seconds() < CERT_TTL_S
                        except ValueError:
                            fresh = False
                    certs[host] = old if fresh else dict(cert_for(host, tls, now=now), checked_at=stamp)
            containers, cerr = containers_for(venture, str(app["slug"]), run)
            apps[key] = {"git": git, "environments": envs, "containers": containers, "containers_error": cerr}
        for e in ventures_apps.errors_for(venture, ventures_root=ventures_root):
            errors.append(f"{venture}: unreadable manifest {e}")
    return {"generated_at": stamp, "interval_s": interval_s, "elapsed_ms": round((time.perf_counter() - t0) * 1000, 3),
            "apps": apps, "certs": certs, "fleet": fleet_entries(fleet_path), "errors": errors}


def run_once(snapshot_path: Path | None, ventures_root: Path | None, interval_s: int) -> dict[str, Any]:
    vroot = Path(ventures_root) if ventures_root else ventures_apps._VROOT_DEFAULT
    previous = studio_snapshot.read_snapshot(snapshot_path).get("data")
    snap = build_snapshot(vroot, fetch=default_fetch, run=default_run, tls=default_tls, previous=previous,
                          now=datetime.now(timezone.utc), interval_s=interval_s)
    studio_snapshot.write_snapshot(snap, path=snapshot_path)
    return snap


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Studio live-state poller")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="one pass (default when neither flag is given)")
    mode.add_argument("--interval", type=int, default=None, help="loop every N seconds")
    ap.add_argument("--snapshot", default=None)
    ap.add_argument("--ventures-root", default=None)
    args = ap.parse_args(argv)
    snap_path = Path(args.snapshot) if args.snapshot else None
    vroot = Path(args.ventures_root) if args.ventures_root else None
    interval = args.interval if args.interval else studio_snapshot.DEFAULT_INTERVAL_S
    while True:
        snap = run_once(snap_path, vroot, interval)
        print(f"studio-poll: {len(snap['apps'])} apps, {len(snap['certs'])} certs, {snap['elapsed_ms']:.0f} ms", file=sys.stderr)
        if not args.interval:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
