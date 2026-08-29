# web/ventures_git.py
"""Cheap, cached git state for an app's repo. Read-only; never fetches.

Every call is a handful of local git invocations with a 2 s timeout, memoised
on the mtime signature of the repo root and its .git bookkeeping files so a
page that lists ten apps costs ten stat() walks, not ten git runs.
"""
from __future__ import annotations
import os
import subprocess
from pathlib import Path
from typing import Any

import ventures_cache

_CACHE: dict[str, Any] = {}
_TIMEOUT = 2.0


def _git(path: Path, *args: str) -> str:
    # Read-only callers must not let `git status` opportunistically refresh
    # and rewrite .git/index (its "racily clean" stat-cache side effect):
    # that touch changes the index mtime even when nothing real changed, so
    # the cache signature could never match itself between calls.
    # GIT_OPTIONAL_LOCKS=0 is git's documented escape hatch for this.
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    out = subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True, timeout=_TIMEOUT, check=True, env=env)
    return out.stdout.strip()


def _linked_worktree_gitdir(path: Path, git_file: Path) -> Path | None:
    # A linked worktree's `.git` is a FILE containing `gitdir: <path>`,
    # pointing at the per-worktree gitdir (HEAD/index/logs-HEAD live there,
    # not under this `.git` file). Unreadable or malformed content is not
    # this function's problem to raise on; the caller just gets nothing to
    # add to the signature.
    try:
        first_line = git_file.read_text().splitlines()[0]
    except (OSError, IndexError):
        return None
    prefix = "gitdir:"
    if not first_line.startswith(prefix):
        return None
    raw = first_line[len(prefix):].strip()
    if not raw:
        return None
    gitdir = Path(raw)
    return gitdir if gitdir.is_absolute() else path / gitdir


def _signature(path: Path) -> tuple:
    git = path / ".git"
    candidates = [path, git]
    if git.is_dir():
        candidates += [git / "HEAD", git / "index", git / "logs" / "HEAD"]
    elif git.is_file():
        gitdir = _linked_worktree_gitdir(path, git)
        if gitdir is not None:
            candidates += [gitdir / "HEAD", gitdir / "index", gitdir / "logs" / "HEAD"]
    return ventures_cache.mtime_signature(candidates)


def _read(path: Path) -> dict[str, Any]:
    try:
        branch = _git(path, "rev-parse", "--abbrev-ref", "HEAD")
        head = _git(path, "rev-parse", "--short=7", "HEAD")
        porcelain = _git(path, "status", "--porcelain")
        worktrees = _git(path, "worktree", "list", "--porcelain")
        last = _git(path, "log", "-1", "--format=%cI")
    except subprocess.TimeoutExpired:
        return {"ok": False, "path": str(path), "reason": "git timeout"}
    except (subprocess.CalledProcessError, OSError):
        return {"ok": False, "path": str(path), "reason": "git error"}
    return {
        "ok": True,
        "path": str(path),
        "branch": branch,
        "head": head,
        "dirty": len([ln for ln in porcelain.splitlines() if ln.strip()]),
        "worktrees": sum(1 for ln in worktrees.splitlines() if ln.startswith("worktree ")),
        "last_commit": last,
        "vcs": "jj+git" if (path / ".jj").is_dir() else "git",
    }


def repo_state(raw_path: str) -> dict[str, Any]:
    path = Path(os.path.expanduser(str(raw_path)))
    if not path.is_dir():
        return {"ok": False, "path": str(path), "reason": "missing"}
    if not (path / ".git").exists():
        return {"ok": False, "path": str(path), "reason": "not a git repo"}
    return ventures_cache.cached(_CACHE, str(path), _signature(path), lambda: _read(path))
