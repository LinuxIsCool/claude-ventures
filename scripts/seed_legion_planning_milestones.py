#!/usr/bin/env python3
"""Add deterministic planning buckets to every Legion plugin project.

The existing ``unscheduled`` milestone remains an explicit inbox.  These
additional buckets let Backlog classify already-understood plugin work without
inventing release names: ``now``, ``next``, ``later``, ``maintenance``, and
``completed``.  Dry-run is the default; ``--apply`` backs up changed project
records and publishes every write atomically.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


MILESTONES: dict[str, tuple[str, str, str]] = {
    "now": (
        "Now",
        "Work actively in progress or blocked inside the current execution window.",
        "All committed work is completed, moved, or explicitly blocked with an owner.",
    ),
    "next": (
        "Next",
        "Critical, due, or explicitly sequenced work intended to follow Now.",
        "Every task is either promoted to Now or deliberately resequenced.",
    ),
    "later": (
        "Later",
        "Valid project work that has context but no near-term delivery commitment.",
        "Work is promoted, retired, or retained with current rationale.",
    ),
    "maintenance": (
        "Maintenance",
        "Reliability, repair, regression, and upkeep work for the plugin.",
        "The maintenance objective is verified and its regression coverage is recorded.",
    ),
    "completed": (
        "Completed",
        "Historical work already complete, retained for project rollups and provenance.",
        "Tasks remain immutable historical evidence unless formally reopened.",
    ),
}


def split_markdown(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) != 3:
        raise ValueError(f"invalid frontmatter: {path}")
    metadata = yaml.safe_load(parts[1]) or {}
    if not isinstance(metadata, dict):
        raise ValueError(f"frontmatter is not a mapping: {path}")
    return metadata, parts[2].lstrip("\n")


def markdown(metadata: dict[str, Any], body: str) -> str:
    frontmatter = yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True).rstrip()
    return f"---\n{frontmatter}\n---\n\n{body.lstrip()}"


def atomic_write(path: Path, text: str) -> None:
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        temp_path = None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def plan(ventures_root: Path) -> list[dict[str, Any]]:
    project_files = sorted((ventures_root / "legion" / "projects").glob("*/project.md"))
    result: list[dict[str, Any]] = []
    for project_file in project_files:
        metadata, _body = split_markdown(project_file)
        current = metadata.get("milestones") or []
        if not isinstance(current, list):
            current = [current]
        missing = [slug for slug in MILESTONES if slug not in current]
        missing_files = [
            slug for slug in MILESTONES
            if not (project_file.parent / "milestones" / f"{slug}.md").is_file()
        ]
        result.append({
            "project": project_file.parent.name,
            "project_file": str(project_file),
            "missing_project_links": missing,
            "missing_milestone_files": missing_files,
        })
    return result


def apply(ventures_root: Path, rows: list[dict[str, Any]]) -> tuple[Path, list[str]]:
    now = datetime.now(timezone.utc).isoformat()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = ventures_root / ".planning-milestone-backups" / stamp
    changed: list[str] = []
    for row in rows:
        project_file = Path(row["project_file"])
        if row["missing_project_links"]:
            backup = backup_root / project_file.relative_to(ventures_root)
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(project_file, backup)
            metadata, body = split_markdown(project_file)
            current = metadata.get("milestones") or []
            if not isinstance(current, list):
                current = [current]
            metadata["milestones"] = list(dict.fromkeys([*current, *MILESTONES]))
            metadata["updated_at"] = now
            atomic_write(project_file, markdown(metadata, body))
            changed.append(str(project_file))
        milestones_dir = project_file.parent / "milestones"
        milestones_dir.mkdir(parents=True, exist_ok=True)
        for milestone_slug in row["missing_milestone_files"]:
            name, description, target = MILESTONES[milestone_slug]
            milestone_file = milestones_dir / f"{milestone_slug}.md"
            metadata = {
                "slug": milestone_slug,
                "name": name,
                "description": description,
                "project": row["project"],
                "venture": "legion",
                "stage": "active",
                "priority": "none",
                "target": target,
                "exit_criteria": [],
                "tasks": [],
                "created_at": now,
                "updated_at": now,
            }
            atomic_write(
                milestone_file,
                markdown(metadata, f"# {name}\n\n{description}\n"),
            )
            changed.append(str(milestone_file))
    if changed:
        atomic_write(ventures_root / ".portfolio_revision", f"{now}\n")
    return backup_root, changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ventures-root", type=Path, default=Path.home() / ".claude/local/ventures")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    ventures_root = args.ventures_root.expanduser().resolve()
    rows = plan(ventures_root)
    result: dict[str, Any] = {
        "mode": "apply" if args.apply else "dry-run",
        "projects": len(rows),
        "projects_needing_links": sum(bool(row["missing_project_links"]) for row in rows),
        "missing_milestone_files": sum(len(row["missing_milestone_files"]) for row in rows),
    }
    if args.apply:
        backup_root, changed = apply(ventures_root, rows)
        result.update({"backup_root": str(backup_root), "changed": changed})
    else:
        result["plan"] = rows
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
