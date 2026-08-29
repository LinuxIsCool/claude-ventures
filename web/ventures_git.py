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
    out = subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True, timeout=_TIMEOUT, check=True)
    return out.stdout.strip()


def _signature(path: Path) -> tuple:
    git = path / ".git"
    candidates = [path, git]
    if git.is_dir():
        candidates += [git / "HEAD", git / "index", git / "logs" / "HEAD"]
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
    key = str(path)
    entry = _CACHE.get(key)
    if entry is not None and entry["sig"] == _signature(path):
        return entry["value"]
    # `git status` (inside _read) rewrites .git/index's mtime as a side
    # effect of its racily-clean stat-cache refresh, even when nothing
    # changed. Re-signature after the read, not before, so that self-
    # inflicted touch is captured in what we cache against rather than
    # invalidating the entry on every subsequent call.
    value = _read(path)
    _CACHE[key] = {"sig": _signature(path), "value": value}
    return value
