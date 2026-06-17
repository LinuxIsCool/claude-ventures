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
from datetime import date, datetime
from pathlib import Path
import yaml

VENTURES_BASE = Path.home() / ".claude" / "local" / "ventures"
METRICS_LATEST = VENTURES_BASE / "metrics" / "latest.json"
DEADLINE_WINDOW_DAYS = 45
# Overdue items older than this, with no reconciliation flag, are treated as
# "likely passed/completed but un-reconciled" — aggregated into one muted line
# rather than screamed individually. (task-4151: freshness gate / no broken alarms)
STALE_OVERDUE_DAYS = 14
# Cached vision-metrics snapshot older than this is marked stale, not presented as current.
METRICS_TTL_HOURS = 24

# A deadline carrying any of these is considered reconciled and is never surfaced.
_RECONCILED_STATUSES = {
    "complete", "completed", "done", "cancelled", "canceled",
    "moot", "skipped", "achieved", "shipped", "closed",
}


def _is_reconciled(dl: dict) -> bool:
    """True if a deadline is explicitly marked done/moot/etc. — so it is never
    surfaced as overdue. Deadlines have no status field today; this lets the data
    model express truth going forward without a code change."""
    if dl.get("reconciled") is True or dl.get("done") is True:
        return True
    return str(dl.get("status", "")).strip().lower() in _RECONCILED_STATUSES


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

    line = (
        f"FK {fmt('fk_bind_rate')} · overdue {fmt('overdue_ratio')} · "
        f"coverage {fmt('portfolio_coverage')} · fresh {fmt('data_freshness')} · "
        f"autonomy {fmt('human_touch_dependency')} (human-touch)"
    )

    # Freshness gate: don't present a stale snapshot as current.
    try:
        computed = datetime.fromisoformat(snap.get("computed_at"))
        age_h = (datetime.now(computed.tzinfo) - computed).total_seconds() / 3600
        if age_h > METRICS_TTL_HOURS:
            line += f" — ⚠ snapshot {age_h:.0f}h old, may be stale (run /ventures-metrics)"
    except Exception:
        pass
    return line


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
                    if _is_reconciled(dl):
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
        # Freshness gate: recently-overdue (≤ STALE_OVERDUE_DAYS) are live fires worth
        # naming; older un-reconciled ones are likely already passed/done and get
        # aggregated into one muted line instead of a wall of false alarms.
        stale_overdue = [u for u in urgent if u["days"] < -STALE_OVERDUE_DAYS]
        for u in urgent:
            if u["days"] < -STALE_OVERDUE_DAYS:
                continue  # rolled into the muted aggregate below
            if u["days"] < 0:
                sys_parts.append(f"{u['venture']} ({abs(u['days'])}d OVERDUE)")
                ctx_parts.append(f"OVERDUE: {u['venture']} — {u['label']} ({abs(u['days'])}d overdue)")
            elif u["days"] == 0:
                sys_parts.append(f"{u['venture']} (DUE TODAY)")
                ctx_parts.append(f"DUE TODAY: {u['venture']} — {u['label']}")
            else:
                sys_parts.append(f"{u['venture']} ({u['days']}d)")
                ctx_parts.append(f"Deadline approaching: {u['venture']} — {u['label']} ({u['days']}d)")

        if stale_overdue:
            sys_parts.append(f"{len(stale_overdue)} stale-overdue (unreconciled)")
            ctx_parts.append(
                f"{len(stale_overdue)} venture deadline(s) >{STALE_OVERDUE_DAYS}d overdue and "
                f"un-reconciled — likely already passed or completed; NOT shown individually to "
                f"avoid false alarms. Reconcile (mark status: complete / reconciled: true) or "
                f"review via /ventures."
            )

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
