#!/usr/bin/env python3
"""Create the Legion venture's one-project-per-plugin hierarchy.

The script is additive and idempotent: existing project or milestone records
are never overwritten.  Dry-run is the default; pass ``--apply`` to create
missing records.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import yaml


def discover_plugins(root: Path) -> list[Path]:
    return sorted(
        path for path in root.iterdir()
        if path.is_dir() and not path.name.startswith((".", "_"))
        and ((path / "plugin.json").is_file() or (path / ".claude-plugin" / "plugin.json").is_file())
    )


def manifest(path: Path) -> dict:
    candidate = path / "plugin.json"
    if not candidate.is_file():
        candidate = path / ".claude-plugin" / "plugin.json"
    try:
        return json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def markdown(data: dict, body: str) -> str:
    return f"---\n{yaml.safe_dump(data, sort_keys=False, allow_unicode=True).rstrip()}\n---\n\n{body.rstrip()}\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugins-root", type=Path, default=Path.home() / "Workspace/legion-plugins/plugins")
    parser.add_argument("--ventures-root", type=Path, default=Path.home() / ".claude/local/ventures")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    now = datetime.now(timezone.utc).isoformat()
    planned: list[dict] = []
    created: list[str] = []
    existing: list[str] = []
    for plugin in discover_plugins(args.plugins_root):
        info = manifest(plugin)
        slug = plugin.name
        name = str(info.get("name") or slug)
        description = str(info.get("description") or f"Legion plugin project for {slug}.")
        project_path = args.ventures_root / "legion" / "projects" / slug / "project.md"
        milestone_path = project_path.parent / "milestones" / "unscheduled.md"
        entry = {
            "plugin": slug,
            "project": str(project_path),
            "milestone": str(milestone_path),
            "project_missing": not project_path.exists(),
            "milestone_missing": not milestone_path.exists(),
        }
        planned.append(entry)
        if not args.apply:
            continue
        if not project_path.exists():
            project_path.parent.mkdir(parents=True, exist_ok=True)
            project_path.write_text(markdown({
                "slug": slug,
                "name": name,
                "description": description,
                "venture": "legion",
                "stage": "active",
                "priority": "none",
                "owner": "shawn",
                "co_owners": [],
                "stakeholders": [],
                "milestones": ["unscheduled"],
                "docs_dir": str(project_path.parent / "docs"),
                "source_plugin": str(plugin),
                "created_at": now,
                "updated_at": now,
            }, f"# {name}\n\n{description}"), encoding="utf-8")
            created.append(str(project_path))
        else:
            existing.append(str(project_path))
        if not milestone_path.exists():
            milestone_path.parent.mkdir(parents=True, exist_ok=True)
            milestone_path.write_text(markdown({
                "slug": "unscheduled",
                "name": "Unscheduled",
                "description": f"Tasks for {slug} not yet assigned to a delivery milestone.",
                "project": slug,
                "venture": "legion",
                "stage": "active",
                "priority": "none",
                "target": "Triage tasks into a named delivery milestone.",
                "exit_criteria": [],
                "tasks": [],
                "created_at": now,
                "updated_at": now,
            }, "# Unscheduled\n\nThis is an explicit inbox, not a delivery commitment."), encoding="utf-8")
            created.append(str(milestone_path))
        else:
            existing.append(str(milestone_path))

    revision_path = args.ventures_root / ".portfolio_revision"
    revision_updated = False
    if args.apply and (created or not revision_path.exists()):
        revision_path.parent.mkdir(parents=True, exist_ok=True)
        temp_revision = revision_path.with_name(f".{revision_path.name}.{os.getpid()}.tmp")
        temp_revision.write_text(f"{now}\n", encoding="utf-8")
        os.replace(temp_revision, revision_path)
        revision_updated = True

    result = {
        "mode": "apply" if args.apply else "dry-run",
        "plugins": len(planned),
        "missing_projects": sum(row["project_missing"] for row in planned),
        "missing_milestones": sum(row["milestone_missing"] for row in planned),
        "created": created,
        "existing": existing,
        "revision": str(revision_path),
        "revision_updated": revision_updated,
        "plan": planned,
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
