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
