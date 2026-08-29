# web/ventures_apps.py
"""Discover app manifests: <ventures_root>/<venture>/apps/<slug>/app.md.

Read-through, no DB, cached on an mtime signature of the manifest files so the
studio route pays one YAML parse per edit, not per request. Mirrors
ventures_projects.py; the manifest shape is backlog task-824 section 6.1.
"""
from __future__ import annotations
import sys
from pathlib import Path
from typing import Any

import yaml

import ventures_cache

_VROOT_DEFAULT = Path.home() / ".claude" / "local" / "ventures"
_CACHE: dict[str, Any] = {}


def _apps_dir(venture: str, ventures_root: Path | None) -> Path:
    root = Path(ventures_root) if ventures_root else _VROOT_DEFAULT
    return root / venture / "apps"


def _split(text: str) -> tuple[dict[str, Any] | None, str]:
    if not text.startswith("---"):
        return None, ""
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, ""
    try:
        fm = yaml.safe_load(parts[1])
    except Exception:  # noqa: BLE001 -- a malformed manifest is data, not a crash
        return None, ""
    if not isinstance(fm, dict):
        return None, ""
    return fm, parts[2].strip()


def _build(d: Path) -> dict[str, Any]:
    apps: list[dict[str, Any]] = []
    errors: list[str] = []
    for md in sorted(d.glob("*/app.md")):
        fm, notes = _split(md.read_text(encoding="utf-8"))
        if fm is None:
            errors.append(f"{md.parent.name}/app.md")
            print(f"[ventures-web] skip app manifest {md}", file=sys.stderr)
            continue
        app = dict(fm)
        app["slug"] = md.parent.name  # directory name is the manifest's identity
        app.setdefault("environments", [])
        app.setdefault("depends_on", [])
        app["notes"] = notes
        app["file_path"] = str(md)
        apps.append(app)
    apps.sort(key=lambda a: str(a.get("slug")))
    return {"apps": apps, "errors": errors}


def _cached(venture: str, ventures_root: Path | None) -> dict[str, Any]:
    d = _apps_dir(venture, ventures_root)
    if not d.is_dir():
        return {"apps": [], "errors": []}
    sig = ventures_cache.mtime_signature(d.glob("*/app.md"))
    return ventures_cache.cached(_CACHE, str(d.resolve()), sig, lambda: _build(d))


def list_for(venture: str, ventures_root: Path | None = None) -> list[dict[str, Any]]:
    return list(_cached(venture, ventures_root)["apps"])


def errors_for(venture: str, ventures_root: Path | None = None) -> list[str]:
    return list(_cached(venture, ventures_root)["errors"])


def get(venture: str, slug: str, ventures_root: Path | None = None) -> dict[str, Any] | None:
    for app in list_for(venture, ventures_root):
        if app.get("slug") == slug:
            return app
    return None
