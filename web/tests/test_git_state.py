# web/tests/test_git_state.py
from __future__ import annotations
import subprocess
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import ventures_git


def _repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x", "HOME": str(tmp_path)}
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=r, check=True, env=env)
    (r / "a.txt").write_text("a\n")
    subprocess.run(["git", "add", "a.txt"], cwd=r, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", "first"], cwd=r, check=True, env=env)
    return r


def test_clean_repo_state(tmp_path: Path):
    r = _repo(tmp_path)
    s = ventures_git.repo_state(str(r))
    assert s["ok"] is True
    assert s["branch"] == "main"
    assert len(s["head"]) == 7
    assert s["dirty"] == 0
    assert s["worktrees"] == 1
    assert s["last_commit"][:4].isdigit()
    assert s["vcs"] == "git"


def test_dirty_count_and_jj_marker(tmp_path: Path):
    r = _repo(tmp_path)
    (r / "b.txt").write_text("b\n")
    (r / ".jj").mkdir()
    ventures_git._CACHE.clear()
    s = ventures_git.repo_state(str(r))
    assert s["dirty"] == 1
    assert s["vcs"] == "jj+git"


def test_missing_and_non_repo(tmp_path: Path):
    assert ventures_git.repo_state(str(tmp_path / "nope")) == {"ok": False, "path": str(tmp_path / "nope"), "reason": "missing"}
    plain = tmp_path / "plain"; plain.mkdir()
    assert ventures_git.repo_state(str(plain))["reason"] == "not a git repo"


def test_tilde_is_expanded(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    r = _repo(tmp_path)
    s = ventures_git.repo_state("~/repo")
    assert s["ok"] is True and s["path"] == str(r)


def test_cache_hits_until_signature_changes(tmp_path: Path, monkeypatch):
    r = _repo(tmp_path)
    ventures_git._CACHE.clear()
    calls = {"n": 0}
    real = ventures_git._read
    def counting(path):
        calls["n"] += 1
        return real(path)
    monkeypatch.setattr(ventures_git, "_read", counting)
    ventures_git.repo_state(str(r)); ventures_git.repo_state(str(r))
    assert calls["n"] == 1
    (r / "c.txt").write_text("c\n")  # changes the root dir mtime
    ventures_git.repo_state(str(r))
    assert calls["n"] == 2


def test_linked_worktree_signature_invalidates_on_commit(tmp_path: Path):
    # A linked worktree's `.git` is a FILE (`gitdir: <path>`), not a
    # directory, so the plain `git.is_dir()` branch in _signature() never
    # picks up its HEAD/index/logs-HEAD. Neither the worktree root nor the
    # `.git` file itself changes mtime on commit, so a cache built once for
    # a worktree path would never invalidate.
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x", "HOME": str(tmp_path)}
    r = _repo(tmp_path)
    wt = tmp_path / "wt"
    subprocess.run(["git", "worktree", "add", str(wt), "-b", "wt-branch"], cwd=r, check=True, env=env)
    ventures_git._CACHE.clear()

    s1 = ventures_git.repo_state(str(wt))
    assert s1["ok"] is True
    assert s1["branch"] == "wt-branch"

    (wt / "a.txt").write_text("changed\n")
    # Pin the commit date away from "now" (rather than relying on real-clock
    # separation from the first commit, which can land in the same second
    # and make last_commit compare equal by coincidence, not by bug).
    second_env = {**env, "GIT_AUTHOR_DATE": "2020-01-01T00:00:01+00:00", "GIT_COMMITTER_DATE": "2020-01-01T00:00:01+00:00"}
    subprocess.run(["git", "-C", str(wt), "commit", "-am", "second"], check=True, env=second_env)

    # No _CACHE.clear() here: the cache must invalidate on its own.
    s2 = ventures_git.repo_state(str(wt))
    assert s2["head"] != s1["head"]
    assert s2["last_commit"] != s1["last_commit"]
