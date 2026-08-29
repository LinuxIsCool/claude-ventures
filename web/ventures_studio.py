# web/ventures_studio.py
"""Compose the per-venture Studio document: app library plus domains.

One JSON document per venture, built from declared data (app manifests) and
cheap cached git reads. No network calls; live health arrives in a later
phase as a poller snapshot. Spec: backlog task-824 sections 6.2 and 6.6.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import ventures_apps
import ventures_detail
import ventures_git

_LATER = {"meetings": "later", "network": "later", "live": "later"}


def _controllable(env: dict[str, Any]) -> bool:
    flag = env.get("controllable")
    if isinstance(flag, bool):
        return flag
    return str(env.get("name", "")) == "dev"


def _domains(apps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for app in apps:
        for env in app.get("environments") or []:
            url = str(env.get("url") or "")
            host = urlparse(url).hostname if url else None
            if not host:
                continue
            out.append({
                "host": host,
                "app": app.get("slug"),
                "env": env.get("name"),
                "url": url,
                "status": env.get("status") or "declared",
                "controllable": env["controllable"],
            })
    out.sort(key=lambda d: (d["host"], str(d["env"])))
    return out


def studio(slug: str, ventures_root: Path | None = None, backlog_dir: Path | None = None) -> dict[str, Any]:
    v = ventures_detail.venture_record(slug, ventures_root)
    if v is None:
        return {"error": "not found", "slug": slug}
    apps = []
    for app in ventures_apps.list_for(slug, ventures_root=ventures_root):
        app = dict(app)
        app["environments"] = [dict(e, controllable=_controllable(e)) for e in (app.get("environments") or []) if isinstance(e, dict)]
        repo = app.get("repo") if isinstance(app.get("repo"), dict) else {}
        app["git"] = ventures_git.repo_state(repo["path"]) if repo.get("path") else None
        apps.append(app)
    domains = _domains(apps)
    return {
        "venture": {"slug": v["slug"], "title": v.get("title"), "lifecycle": v.get("lifecycle"), "priority": v.get("priority")},
        "apps": apps,
        "domains": domains,
        "errors": ventures_apps.errors_for(slug, ventures_root=ventures_root),
        "counts": {"apps": len(apps), "domains": len(domains), "controllable": sum(1 for d in domains if d["controllable"])},
        "phase": dict(_LATER),
    }
