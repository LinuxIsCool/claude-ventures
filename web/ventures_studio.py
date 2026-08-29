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
import studio_snapshot

_LATER = {"meetings": "done", "network": "done", "live": "snapshot"}


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
                "cert": None,
            })
    out.sort(key=lambda d: (d["host"], str(d["env"])))
    return out


def studio(slug: str, ventures_root: Path | None = None, backlog_dir: Path | None = None,
           snapshot_path: Path | None = None, now=None) -> dict[str, Any]:
    v = ventures_detail.venture_record(slug, ventures_root)
    if v is None:
        return {"error": "not found", "slug": slug}
    snap = studio_snapshot.read_snapshot(snapshot_path, now=now)
    live_apps = (snap["data"] or {}).get("apps", {})
    live_certs = (snap["data"] or {}).get("certs", {})
    apps = []
    for app in ventures_apps.list_for(slug, ventures_root=ventures_root):
        app = dict(app)
        app["environments"] = [dict(e, controllable=_controllable(e)) for e in (app.get("environments") or []) if isinstance(e, dict)]
        repo = app.get("repo") if isinstance(app.get("repo"), dict) else {}
        app["git"] = ventures_git.repo_state(repo["path"]) if repo.get("path") else None
        live = live_apps.get(f"{slug}/{app['slug']}")
        app["live"] = {"git": live.get("git"), "containers": live.get("containers", []), "containers_error": live.get("containers_error")} if live else None
        for env in app["environments"]:
            env["live"] = (live or {}).get("environments", {}).get(str(env.get("name"))) if live else None
        apps.append(app)
    domains = _domains(apps)
    for d in domains:
        d["cert"] = live_certs.get(d["host"])
    return {
        "venture": {"slug": v["slug"], "title": v.get("title"), "lifecycle": v.get("lifecycle"), "priority": v.get("priority")},
        "apps": apps,
        "domains": domains,
        "errors": ventures_apps.errors_for(slug, ventures_root=ventures_root),
        "counts": {"apps": len(apps), "domains": len(domains), "controllable": sum(1 for d in domains if d["controllable"])},
        "phase": dict(_LATER),
        "snapshot": {k: snap[k] for k in ("present", "generated_at", "age_s", "stale", "interval_s")},
    }
