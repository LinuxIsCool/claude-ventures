# web/studio_actions.py
"""Declared-only runtime actions for the Studio.

Policy lives here and nowhere else: an action may run exactly the compose file
and project an app manifest names, only on an environment marked
controllable, and only as one of four fixed command shapes. Every attempt,
refused or not, is appended to the action log. All process I/O is injected
so tests never touch Docker or spawn anything.
Spec: backlog task-824 sections 6.5 and 6.6.
"""
from __future__ import annotations
import json
import os
import re
import socket
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import ventures_apps

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
ACTION_LOG_DEFAULT = Path.home() / ".claude" / "local" / "fleet" / "logs" / "studio-actions.log"
SHELLS_DEFAULT = Path.home() / ".claude" / "local" / "ventures" / "runtime" / "studio-shells.json"
INSTALL_TTYD = "~/.claude/local/scripts/install-ttyd.sh"
SHELL_TTL_S = 1800
SHELL_LIMIT = 2
TIMEOUTS = {"start": 60, "stop": 60, "logs": 15, "status": 15}


class ActionRefused(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code, self.message = code, message


@dataclass(frozen=True)
class Resolved:
    venture: str
    app: str
    env: str
    project: str
    file: str
    cwd: str
    controllable: bool


def _slug(value: Any, what: str) -> str:
    s = str(value or "")
    if not SLUG_RE.match(s):
        raise ActionRefused("BAD_ARG", f"{what} must match {SLUG_RE.pattern}")
    return s


def _controllable(env: dict[str, Any]) -> bool:
    flag = env.get("controllable")
    return flag if isinstance(flag, bool) else str(env.get("name")) == "dev"


def resolve(venture: str, app: str, env: str, ventures_root: Path | None = None) -> Resolved:
    v, a, e = _slug(venture, "venture"), _slug(app, "app"), _slug(env, "env")
    manifest = ventures_apps.get(v, a, ventures_root=ventures_root)
    if not manifest:
        raise ActionRefused("NOT_DECLARED", f"no app manifest for {v}/{a}")
    envs = [x for x in (manifest.get("environments") or []) if isinstance(x, dict) and str(x.get("name")) == e]
    if not envs:
        raise ActionRefused("NOT_DECLARED", f"environment {e} is not declared for {v}/{a}")
    runtime = manifest.get("runtime") if isinstance(manifest.get("runtime"), dict) else {}
    if runtime.get("kind") != "compose" or not runtime.get("file") or not runtime.get("project"):
        raise ActionRefused("NOT_DECLARED", f"{v}/{a} declares no compose runtime (kind, file, project)")
    repo = manifest.get("repo") if isinstance(manifest.get("repo"), dict) else {}
    cwd = os.path.expanduser(str(repo.get("path") or "")) or os.getcwd()
    file = os.path.expanduser(str(runtime["file"]))
    if not os.path.isabs(file):
        file = os.path.join(cwd, file)
    if not os.path.isfile(file):
        raise ActionRefused("NOT_DECLARED", f"compose file not found: {file}")
    return Resolved(v, a, e, _slug(runtime["project"], "runtime.project"), file, cwd, _controllable(envs[0]))


def command(action: str, r: Resolved) -> list[str]:
    base = ["docker", "compose", "-p", r.project, "-f", r.file]
    if action == "start":
        return base + ["start"]
    if action == "stop":
        return base + ["stop"]
    if action == "logs":
        return base + ["logs", "--tail", "200", "--no-color"]
    if action == "status":
        return base + ["ps", "--format", "json"]
    raise ActionRefused("BAD_ARG", f"unknown action {action!r}")


def _log(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, separators=(",", ":")) + "\n")


def default_run(argv: list[str], timeout: float, cwd: str) -> tuple[int, str]:
    p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, cwd=cwd)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def perform(action: str, venture: str, app: str, env: str, *, run: Callable, log_path: Path | None = None,
            ventures_root: Path | None = None, clock=time.perf_counter, now: datetime | None = None) -> dict[str, Any]:
    log = Path(log_path) if log_path else ACTION_LOG_DEFAULT
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    base = {"ts": stamp, "venture": str(venture), "app": str(app), "env": str(env), "action": action}
    try:
        r = resolve(venture, app, env, ventures_root=ventures_root)
        if not r.controllable:
            raise ActionRefused("NOT_CONTROLLABLE", f"{r.venture}/{r.app} {r.env} is not controllable from the Studio")
        argv = command(action, r)
    except ActionRefused as exc:
        _log(log, dict(base, argv=None, exit=None, elapsed_ms=0, ok=False, refused=exc.code))
        raise
    t0 = clock()
    try:
        code, out = run(argv, TIMEOUTS[action], r.cwd)
        error = None
    except Exception as exc:  # noqa: BLE001 -- a hung or missing docker is a result
        code, out, error = None, "", f"{type(exc).__name__}: {exc}"
    elapsed = round((clock() - t0) * 1000, 3)
    ok = code == 0
    _log(log, dict(base, argv=argv, exit=code, elapsed_ms=elapsed, ok=ok, error=error))
    lines = [ln for ln in str(out).splitlines() if ln.strip()]
    if action == "status":
        containers = []
        for ln in lines:
            try:
                row = json.loads(ln)
            except ValueError:
                continue
            containers.append({"name": row.get("Name"), "state": row.get("State"), "health": row.get("Health", "")})
        return {"ok": ok, "exit": code, "containers": containers, "raw": lines[-50:], "error": error}
    if action == "logs":
        return {"ok": ok, "exit": code, "lines": lines[-200:], "error": error}
    return {"ok": ok, "exit": code, "elapsed_ms": elapsed, "output_tail": "\n".join(lines[-20:]), "error": error}


# ---- shells -------------------------------------------------------------------

def default_popen(argv: list[str], cwd: str) -> int:
    log_dir = ACTION_LOG_DEFAULT.parent
    log_dir.mkdir(parents=True, exist_ok=True)
    fh = open(log_dir / f"studio-shell-{argv[2]}.log", "ab")  # noqa: SIM115 -- lives as long as the child
    return subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL, stdout=fh, stderr=subprocess.STDOUT, start_new_session=True).pid


def default_kill(pid: int) -> None:
    try:
        os.kill(pid, 15)
    except ProcessLookupError:
        pass


def default_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def default_which(name: str) -> str | None:
    from shutil import which
    return which(name)


def default_free_port(lo: int = 8900, hi: int = 8999) -> int:
    for port in range(lo, hi + 1):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise ActionRefused("NO_PORT", "no free port in 8900-8999")


class Shells:
    def __init__(self, registry_path: Path | None = None, *, popen=default_popen, kill=default_kill, alive=default_alive,
                 which=default_which, free_port=default_free_port, now=time.time) -> None:
        self.path = Path(registry_path) if registry_path else SHELLS_DEFAULT
        self._popen, self._kill, self._alive, self._which, self._free_port, self._now = popen, kill, alive, which, free_port, now

    def _read(self) -> dict[str, Any]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _write(self, rows: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(rows, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)

    def sweep(self) -> int:
        rows = self._read(); now = self._now(); gone = 0
        for key, row in list(rows.items()):
            expired = now >= float(row.get("expires_at", 0))
            if expired or not self._alive(int(row["pid"])):
                if expired and self._alive(int(row["pid"])):
                    self._kill(int(row["pid"]))
                rows.pop(key); gone += 1
        self._write(rows)
        return gone

    def list(self) -> list[dict[str, Any]]:
        self.sweep()
        return [dict(row, key=key) for key, row in sorted(self._read().items())]

    def open(self, venture: str, app: str, cwd: str) -> dict[str, Any]:
        v, a = _slug(venture, "venture"), _slug(app, "app")
        self.sweep()
        rows = self._read(); key = f"{v}/{a}"
        if key in rows:
            row = rows[key]
            return {"ok": True, "url": f"http://127.0.0.1:{row['port']}/", "port": row["port"], "expires_at": row["expires_at"], "live": len(rows)}
        if not self._which("ttyd"):
            raise ActionRefused("TTYD_MISSING", f"ttyd is not installed; run {INSTALL_TTYD}")
        if len(rows) >= SHELL_LIMIT:
            raise ActionRefused("SHELL_LIMIT", f"{SHELL_LIMIT} shells are already open; close one first")
        if not os.path.isdir(cwd):
            raise ActionRefused("NOT_DECLARED", f"repo path is not a directory: {cwd}")
        port = self._free_port()
        argv = ["ttyd", "-p", str(port), "-i", "127.0.0.1", "-W", "-t", "disableLeaveAlert=true", "fish"]
        pid = self._popen(argv, cwd)
        opened = self._now()
        rows[key] = {"venture": v, "app": a, "port": port, "pid": pid, "cwd": cwd, "opened_at": opened, "expires_at": opened + SHELL_TTL_S}
        self._write(rows)
        return {"ok": True, "url": f"http://127.0.0.1:{port}/", "port": port, "expires_at": rows[key]["expires_at"], "live": len(rows)}

    def close(self, venture: str, app: str) -> dict[str, Any]:
        key = f"{_slug(venture, 'venture')}/{_slug(app, 'app')}"
        rows = self._read(); closed = 0
        if key in rows:
            self._kill(int(rows[key]["pid"])); rows.pop(key); closed = 1
            self._write(rows)
        return {"ok": True, "closed": closed}
