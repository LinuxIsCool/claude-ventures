#!/usr/bin/env python3
"""
Session-start hook for claude-ventures.
Reads active ventures and injects context about approaching deadlines.

Run with: uv run --python 3.12 hooks/session-start.py
"""

import os
import sys
import json
from datetime import datetime, date
from pathlib import Path

VENTURES_BASE = Path.home() / ".claude" / "local" / "ventures"
DEADLINE_WINDOW_DAYS = 14


def parse_frontmatter(content: str) -> dict:
    """Extract YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        return {}
    end = content.find("---", 3)
    if end == -1:
        return {}
    yaml_str = content[3:end].strip()
    # Simple YAML parsing for key fields (avoid heavy deps)
    result = {}
    current_key = None
    current_list = None
    for line in yaml_str.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and current_list is not None:
            item_str = stripped[2:].strip()
            # Handle inline object
            if ":" in item_str and not item_str.startswith('"'):
                current_list.append(item_str)
            else:
                current_list.append(item_str.strip("'\""))
            continue
        if ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()
            current_list = None
            if not val:
                # Could be a list or nested object
                current_key = key
                current_list = []
                result[key] = current_list
            else:
                result[key] = val.strip("'\"")
    return result


def find_deadlines(venture_data: dict) -> list[dict]:
    """Extract deadline info from venture frontmatter."""
    deadlines = []
    raw = venture_data.get("deadlines", [])
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str) and "date:" in item:
                # Parse inline format: "date: 2026-04-15"
                parts = {}
                for part in item.split(","):
                    k, _, v = part.strip().partition(":")
                    parts[k.strip()] = v.strip().strip("'\"")
                if "date" in parts:
                    deadlines.append(parts)
    return deadlines


def main():
    today = date.today()
    active_dir = VENTURES_BASE / "active"
    exploring_dir = VENTURES_BASE / "exploring"

    ventures = []
    urgent = []

    for stage_dir in [active_dir, exploring_dir]:
        if not stage_dir.exists():
            continue
        for f in stage_dir.glob("*.md"):
            try:
                content = f.read_text()
                data = parse_frontmatter(content)
                title = data.get("title", f.stem)
                stage = data.get("stage", stage_dir.name)
                ventures.append({"title": title, "stage": stage, "file": str(f)})

                # Check deadlines
                deadlines = find_deadlines(data)
                for dl in deadlines:
                    dl_date = date.fromisoformat(dl.get("date", "9999-12-31"))
                    days_until = (dl_date - today).days
                    if days_until <= DEADLINE_WINDOW_DAYS:
                        label = dl.get("label", dl.get("date", ""))
                        urgent.append({
                            "venture": title,
                            "deadline": dl.get("date"),
                            "label": label,
                            "days": days_until,
                        })
            except Exception:
                continue

    if not ventures:
        return

    parts = [f"Active ventures: {len(ventures)}."]

    if urgent:
        urgent.sort(key=lambda x: x["days"])
        for u in urgent:
            if u["days"] < 0:
                parts.append(f"OVERDUE: {u['venture']} — {u['label']} ({abs(u['days'])}d overdue)")
            elif u["days"] == 0:
                parts.append(f"DUE TODAY: {u['venture']} — {u['label']}")
            else:
                parts.append(f"Deadline approaching: {u['venture']} — {u['label']} ({u['days']}d)")

    print(" ".join(parts))


if __name__ == "__main__":
    main()
