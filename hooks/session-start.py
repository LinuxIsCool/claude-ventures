#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml"]
# ///
"""
Session-start hook for claude-ventures.
Reads active ventures and injects context about approaching deadlines.
"""

import json
import sys
from datetime import date
from pathlib import Path
import yaml

VENTURES_BASE = Path.home() / ".claude" / "local" / "ventures"
DEADLINE_WINDOW_DAYS = 45


def parse_frontmatter(content: str) -> dict:
    """Extract YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        return {}
    end = content.find("---", 3)
    if end == -1:
        return {}
    return yaml.safe_load(content[3:end]) or {}


def main():
    try:
        json.loads(sys.stdin.read() or "{}")
    except Exception:
        pass

    today = date.today()

    ventures = []
    urgent = []

    for stage_dir_name in ["active", "exploring"]:
        stage_dir = VENTURES_BASE / stage_dir_name
        if not stage_dir.exists():
            continue
        for f in stage_dir.glob("*.md"):
            try:
                content = f.read_text()
                data = parse_frontmatter(content)
                title = data.get("title", f.stem)
                ventures.append(title)

                for dl in data.get("deadlines", []):
                    if not isinstance(dl, dict) or "date" not in dl:
                        continue
                    dl_date = dl["date"]
                    if isinstance(dl_date, str):
                        dl_date = date.fromisoformat(dl_date)
                    days_until = (dl_date - today).days
                    if days_until <= DEADLINE_WINDOW_DAYS:
                        label = dl.get("label", str(dl.get("date", "")))
                        urgent.append({
                            "venture": title,
                            "label": label,
                            "days": days_until,
                        })
            except Exception:
                continue

    if not ventures:
        return

    # Compact systemMessage for user banner
    sys_parts = [f"[ventures] {len(ventures)} active"]
    # Detailed additionalContext for Claude
    ctx_parts = [f"Active ventures: {len(ventures)}."]

    if urgent:
        urgent.sort(key=lambda x: x["days"])
        for u in urgent:
            if u["days"] < 0:
                sys_parts.append(f"{u['venture']} ({abs(u['days'])}d OVERDUE)")
                ctx_parts.append(f"OVERDUE: {u['venture']} — {u['label']} ({abs(u['days'])}d overdue)")
            elif u["days"] == 0:
                sys_parts.append(f"{u['venture']} (DUE TODAY)")
                ctx_parts.append(f"DUE TODAY: {u['venture']} — {u['label']}")
            else:
                sys_parts.append(f"{u['venture']} ({u['days']}d)")
                ctx_parts.append(f"Deadline approaching: {u['venture']} — {u['label']} ({u['days']}d)")

    sys_msg = " · ".join(sys_parts)
    ctx_msg = " ".join(ctx_parts)

    print(json.dumps({
        "systemMessage": sys_msg,
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": ctx_msg,
        },
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
