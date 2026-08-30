from __future__ import annotations
import json
import threading
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).resolve().parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import studio_actions as A

MANIFEST = """---
slug: site
name: Site
venture: acme
kind: static
stage: active
repo:
  path: {repo}
environments:
  - name: dev
    url: http://dev.local
  - name: staging
    url: http://staging.local
    controllable: false
  - name: lab
    url: http://lab.local
    controllable: true
runtime:
  kind: compose
  file: {file}
  project: acme-site
depends_on: []
---
"""


def _root(tmp_path: Path, file: str | None = "deploy/compose.yml") -> Path:
    vroot = tmp_path / "ventures"
    repo = tmp_path / "repo"; (repo / "deploy").mkdir(parents=True)
    (repo / "deploy" / "compose.yml").write_text("name: acme-site\nservices: {}\n")
    d = vroot / "acme" / "apps" / "site"; d.mkdir(parents=True)
    (d / "app.md").write_text(MANIFEST.format(repo=str(repo), file=file or "deploy/compose.yml"))
    return vroot


NO_CONTROLLABLE_MANIFEST = """---
slug: site
name: Site
venture: acme
kind: static
stage: active
repo:
  path: {repo}
environments:
  - name: prod
    url: http://prod.local
    controllable: false
runtime:
  kind: compose
  file: deploy/compose.yml
  project: acme-site
depends_on: []
---
"""


def _root_no_controllable(tmp_path: Path) -> Path:
    """Like _root(), but every declared environment is controllable: false
    (a CIE-shaped manifest) so no shell is ever permitted for this app."""
    vroot = tmp_path / "ventures"
    repo = tmp_path / "repo"; (repo / "deploy").mkdir(parents=True)
    (repo / "deploy" / "compose.yml").write_text("name: acme-site\nservices: {}\n")
    d = vroot / "acme" / "apps" / "site"; d.mkdir(parents=True)
    (d / "app.md").write_text(NO_CONTROLLABLE_MANIFEST.format(repo=str(repo)))
    return vroot


def test_resolve_declared_and_controllable(tmp_path: Path):
    vroot = _root(tmp_path)
    r = A.resolve("acme", "site", "dev", ventures_root=vroot)
    assert r.project == "acme-site" and r.file.endswith("repo/deploy/compose.yml") and r.controllable is True
    assert r.cwd == str(tmp_path / "repo")
    assert A.resolve("acme", "site", "lab", ventures_root=vroot).controllable is True
    assert A.resolve("acme", "site", "staging", ventures_root=vroot).controllable is False


def test_resolve_refusals(tmp_path: Path):
    vroot = _root(tmp_path)
    with pytest.raises(A.ActionRefused) as e: A.resolve("acme", "nope", "dev", ventures_root=vroot)
    assert e.value.code == "NOT_DECLARED"
    with pytest.raises(A.ActionRefused) as e: A.resolve("acme", "site", "prod", ventures_root=vroot)
    assert e.value.code == "NOT_DECLARED"
    with pytest.raises(A.ActionRefused) as e: A.resolve("acme", "site", "dev; rm -rf /", ventures_root=vroot)
    assert e.value.code == "BAD_ARG"
    vroot2 = _root(tmp_path / "x", file="/nonexistent/compose.yml")
    with pytest.raises(A.ActionRefused) as e: A.resolve("acme", "site", "dev", ventures_root=vroot2)
    assert e.value.code == "NOT_DECLARED" and "compose file" in e.value.message


def test_resolve_repo_returns_repo_path_or_refuses(tmp_path: Path):
    vroot = _root(tmp_path)
    assert A.resolve_repo("acme", "site", ventures_root=vroot) == str(tmp_path / "repo")
    with pytest.raises(A.ActionRefused) as e: A.resolve_repo("acme", "nope", ventures_root=vroot)
    assert e.value.code == "NOT_DECLARED"


def test_resolve_repo_requires_a_controllable_environment(tmp_path: Path):
    vroot = _root_no_controllable(tmp_path)
    with pytest.raises(A.ActionRefused) as e: A.resolve_repo("acme", "site", ventures_root=vroot)
    assert e.value.code == "NOT_CONTROLLABLE"


def test_commands_are_exact(tmp_path: Path):
    r = A.resolve("acme", "site", "dev", ventures_root=_root(tmp_path))
    assert A.command("start", r) == ["docker", "compose", "-p", "acme-site", "-f", r.file, "start"]
    assert A.command("stop", r) == ["docker", "compose", "-p", "acme-site", "-f", r.file, "stop"]
    assert A.command("logs", r) == ["docker", "compose", "-p", "acme-site", "-f", r.file, "logs", "--tail", "200", "--no-color"]
    assert A.command("status", r) == ["docker", "compose", "-p", "acme-site", "-f", r.file, "ps", "--format", "json"]
    with pytest.raises(A.ActionRefused): A.command("down", r)


def test_perform_runs_logs_and_returns(tmp_path: Path):
    vroot = _root(tmp_path); log = tmp_path / "actions.log"
    calls = []
    def run(argv, timeout, cwd):
        calls.append((argv, timeout, cwd)); return (0, "Container acme-site-web-1 Started\n")
    t = iter([0.0, 0.25]); clock = lambda: next(t)
    out = A.perform("start", "acme", "site", "dev", run=run, log_path=log, ventures_root=vroot, clock=clock)
    assert out["ok"] is True and out["exit"] == 0 and abs(out["elapsed_ms"] - 250) < 0.01
    assert "Started" in out["output_tail"]
    assert calls[0][1] == 60 and calls[0][2] == str(tmp_path / "repo")
    row = json.loads(log.read_text().splitlines()[-1])
    assert row["action"] == "start" and row["exit"] == 0 and row["argv"][0] == "docker" and row["ok"] is True


def test_perform_refuses_non_controllable_and_logs_refusal(tmp_path: Path):
    vroot = _root(tmp_path); log = tmp_path / "actions.log"
    ran = []
    with pytest.raises(A.ActionRefused) as e:
        A.perform("stop", "acme", "site", "staging", run=lambda *a: ran.append(a) or (0, ""), log_path=log, ventures_root=vroot)
    assert e.value.code == "NOT_CONTROLLABLE" and ran == []
    row = json.loads(log.read_text().splitlines()[-1])
    assert row["refused"] == "NOT_CONTROLLABLE" and row["exit"] is None


def test_perform_status_parses_compose_ps(tmp_path: Path):
    vroot = _root(tmp_path)
    run = lambda argv, timeout, cwd: (0, '{"Name":"acme-site-web-1","State":"running","Health":"healthy"}\n{"Name":"acme-site-db-1","State":"exited","Health":""}\n')
    out = A.perform("status", "acme", "site", "dev", run=run, log_path=tmp_path / "l", ventures_root=vroot)
    assert out["containers"] == [{"name": "acme-site-web-1", "state": "running", "health": "healthy"}, {"name": "acme-site-db-1", "state": "exited", "health": ""}]


def test_perform_logs_returns_lines_and_nonzero_exit_is_not_ok(tmp_path: Path):
    vroot = _root(tmp_path)
    run = lambda argv, timeout, cwd: (1, "no such project\n")
    out = A.perform("logs", "acme", "site", "dev", run=run, log_path=tmp_path / "l", ventures_root=vroot)
    assert out["ok"] is False and out["lines"] == ["no such project"]


def test_perform_runner_exception_is_reported(tmp_path: Path):
    vroot = _root(tmp_path)
    def run(argv, timeout, cwd): raise TimeoutError("docker hung")
    out = A.perform("start", "acme", "site", "dev", run=run, log_path=tmp_path / "l", ventures_root=vroot)
    assert out["ok"] is False and out["exit"] is None and "docker hung" in out["error"]


class _Fake:
    def __init__(self):
        self.pids = iter([101, 102, 103]); self.alive_pids = set(); self.killed = []; self.spawned = []; self.t = 1000.0
    def popen(self, argv, cwd): pid = next(self.pids); self.alive_pids.add(pid); self.spawned.append((argv, cwd)); return pid
    def kill(self, pid): self.killed.append(pid); self.alive_pids.discard(pid)
    def alive(self, pid): return pid in self.alive_pids
    def which(self, name): return "/usr/bin/ttyd"
    def free_port(self): return 8901
    def now(self): return self.t


def _shells(tmp_path, fake, log_path=None):
    return A.Shells(tmp_path / "shells.json", popen=fake.popen, kill=fake.kill, alive=fake.alive, which=fake.which,
                     free_port=fake.free_port, now=fake.now, log_path=log_path or (tmp_path / "actions.log"))


def test_shell_open_registers_and_limits(tmp_path: Path):
    f = _Fake(); s = _shells(tmp_path, f)
    out = s.open("acme", "site", str(tmp_path))
    assert out["ok"] is True and out["url"] == "http://127.0.0.1:8901/" and out["port"] == 8901 and out["live"] == 1
    assert f.spawned[0][0][:6] == ["ttyd", "-p", "8901", "-i", "127.0.0.1", "-W"] and f.spawned[0][0][-1] == "fish" and f.spawned[0][1] == str(tmp_path)
    assert s.open("acme", "site", str(tmp_path))["port"] == 8901  # idempotent: same app returns the live shell
    s.open("acme", "other", str(tmp_path))
    with pytest.raises(A.ActionRefused) as e: s.open("acme", "third", str(tmp_path))
    assert e.value.code == "SHELL_LIMIT"
    assert json.loads((tmp_path / "shells.json").read_text())["acme/site"]["pid"] == 101


def test_shell_sweep_expired_and_dead(tmp_path: Path):
    f = _Fake(); s = _shells(tmp_path, f)
    s.open("acme", "site", str(tmp_path)); s.open("acme", "other", str(tmp_path))
    f.alive_pids.discard(102)             # other died on its own
    f.t += A.SHELL_TTL_S + 1              # site expired
    assert s.sweep() == 2 and s.list() == [] and f.killed == [101]


def test_shell_close_and_missing_ttyd(tmp_path: Path):
    f = _Fake(); s = _shells(tmp_path, f)
    s.open("acme", "site", str(tmp_path))
    assert s.close("acme", "site") == {"ok": True, "closed": 1} and f.killed == [101]
    assert s.close("acme", "site") == {"ok": True, "closed": 0}
    f.which = lambda name: None
    s2 = _shells(tmp_path, f)
    with pytest.raises(A.ActionRefused) as e: s2.open("acme", "site", str(tmp_path))
    assert e.value.code == "TTYD_MISSING" and "install-ttyd.sh" in e.value.message


def test_shell_open_is_serialised(tmp_path: Path):
    f = _Fake()
    real_popen = f.popen

    def slow_popen(argv, cwd):
        import time as _time
        _time.sleep(0.05)
        return real_popen(argv, cwd)

    f.popen = slow_popen
    s = _shells(tmp_path, f)

    results: list[dict] = []
    errors: list[A.ActionRefused] = []

    def worker(i: int) -> None:
        try:
            results.append(s.open("acme", f"app{i}", str(tmp_path)))
        except A.ActionRefused as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
    for t in threads: t.start()
    for t in threads: t.join()

    assert len(results) == A.SHELL_LIMIT
    assert len(f.spawned) == A.SHELL_LIMIT
    assert len(errors) == 6 - A.SHELL_LIMIT
    assert all(e.code == "SHELL_LIMIT" for e in errors)
    rows = json.loads((tmp_path / "shells.json").read_text())
    assert len(rows) == A.SHELL_LIMIT


# ---- finding 1: shell open/close reach the action log -----------------------

def test_shell_open_and_close_log_to_action_log(tmp_path: Path):
    f = _Fake(); log = tmp_path / "actions.log"
    s = _shells(tmp_path, f, log_path=log)
    out = s.open("acme", "site", str(tmp_path))
    last = json.loads(log.read_text().splitlines()[-1])
    assert last["action"] == "shell_open" and last["ok"] is True and last["port"] == out["port"] and last["pid"] == 101
    assert out["token"] and out["token"] not in log.read_text()
    s.close("acme", "site")
    last = json.loads(log.read_text().splitlines()[-1])
    assert last["action"] == "shell_close" and last["closed"] == 1


def test_shell_open_refusal_logs_refused_code(tmp_path: Path):
    f = _Fake(); f.which = lambda name: None
    log = tmp_path / "actions.log"
    s = _shells(tmp_path, f, log_path=log)
    with pytest.raises(A.ActionRefused) as e:
        s.open("acme", "site", str(tmp_path))
    row = json.loads(log.read_text().splitlines()[-1])
    assert row["action"] == "shell_open" and row["ok"] is False and row["refused"] == e.value.code == "TTYD_MISSING"


# ---- finding 2: the registry lock is held across processes ------------------

def test_registry_lock_file_is_held_during_open(tmp_path: Path, monkeypatch):
    f = _Fake(); s = _shells(tmp_path, f)
    ops: list[int] = []
    real_flock = A.fcntl.flock

    def recording_flock(fd, op):
        ops.append(op)
        return real_flock(fd, op)

    monkeypatch.setattr(A.fcntl, "flock", recording_flock)
    s.open("acme", "site", str(tmp_path))
    assert A.fcntl.LOCK_EX in ops and A.fcntl.LOCK_UN in ops
    assert ops.index(A.fcntl.LOCK_EX) < ops.index(A.fcntl.LOCK_UN)
    assert (tmp_path / "shells.json.lock").exists()


# ---- finding 3: _log() is safe under concurrent writers ---------------------

def test_log_is_thread_safe(tmp_path: Path):
    log = tmp_path / "actions.log"

    def worker():
        for i in range(20):
            A._log(log, {"ts": "x", "action": "noop", "i": i})

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads: t.start()
    for t in threads: t.join()
    lines = log.read_text().splitlines()
    assert len(lines) == 160
    for ln in lines:
        json.loads(ln)


# ---- ruling: per-shell credential ---------------------------------------

def test_shell_open_issues_a_random_token_credential(tmp_path: Path):
    f = _Fake(); s = _shells(tmp_path, f)
    out = s.open("acme", "site", str(tmp_path))
    argv = f.spawned[0][0]
    assert "-c" in argv and argv.index("-c") < argv.index("fish")
    cred = argv[argv.index("-c") + 1]
    assert cred.startswith("studio:") and len(cred) >= 20
    assert out["token"] == cred.split("studio:", 1)[1]
    assert out["user"] == "studio"
    registry_raw = (tmp_path / "shells.json").read_text()
    assert out["token"] not in registry_raw
    assert json.loads(registry_raw)["acme/site"]["auth"] == "token"


def test_shell_open_reuse_returns_no_token_and_a_note(tmp_path: Path):
    f = _Fake(); s = _shells(tmp_path, f)
    first = s.open("acme", "site", str(tmp_path))
    second = s.open("acme", "site", str(tmp_path))
    assert first["token"] and second["token"] is None
    assert "reuse" in second["note"]
