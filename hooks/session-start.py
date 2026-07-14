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
METRICS_LATEST = VENTURES_BASE / "metrics" / "latest.json"
DEADLINE_WINDOW_DAYS = 45


def metrics_brief_line():
    """Read the CACHED vision-metrics snapshot (no compute) and build a compact
    4-axis line. Returns None if no snapshot exists yet. Fast + defensive — this
    runs inside a 5s session-start hook."""
    try:
        snap = json.loads(METRICS_LATEST.read_text())
    except Exception:
        return None
    by = {m.get("metric"): m for m in snap.get("metrics", [])}

    def fmt(name):
        m = by.get(name)
        if not m or m.get("value") is None:
            return "?"
        v, unit = m["value"], m.get("unit", "")
        if unit.startswith("ratio") or unit == "composite_0_1":
            return f"{v:.0%}"
        if unit == "days_and_ratio":
            return f"{v:.0f}d"
        if unit == "spearman_-1_1":
            return f"{v:.2f}"
        return str(v)

    return (
        f"FK {fmt('fk_bind_rate')} · overdue {fmt('overdue_ratio')} · "
        f"coverage {fmt('portfolio_coverage')} · fresh {fmt('data_freshness')} · "
        f"autonomy {fmt('human_touch_dependency')} (human-touch)"
    )


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
                    # Terminal statuses silence the deadline; anything open
                    # (active/pending/blocked-*/missed-needs-redate/absent)
                    # still surfaces. Without this, evidence-annotated
                    # completions scream OVERDUE forever (2026-07-13 sweep).
                    if str(dl.get("status", "")).lower() in (
                        "complete", "completed", "met", "done",
                        "past", "superseded", "cancelled",
                    ):
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

    metrics_line = metrics_brief_line()
    if metrics_line:
        sys_parts.append("metrics: " + metrics_line)
        ctx_parts.append("Vision metrics (4-axis, cached snapshot): " + metrics_line
                         + ". Full dashboard: /ventures-metrics or "
                         "~/.claude/local/ventures/metrics/dashboard.html")

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
