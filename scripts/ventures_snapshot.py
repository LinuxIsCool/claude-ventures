#!/usr/bin/env python3
# plugins/claude-ventures/scripts/ventures_snapshot.py
"""CLI: compute today's ventures metrics snapshot (append-only JSONL).

Wraps web/ventures_snapshot.ensure_today() — idempotent per-date. Prints the
resulting row as JSON to stdout.

Usage:
    python scripts/ventures_snapshot.py [--data-root P] [--backlog-dir P] [--out P]

--out defaults to the module's default snapshot path
(~/.claude/local/ventures/metrics/snapshots.jsonl).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

# Add the sibling web/ dir to sys.path so we can import ventures_snapshot
# (and its own siblings: ventures_accessor, ventures_backlog).
WEB_DIR = Path(__file__).resolve().parent.parent / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

import ventures_snapshot  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="claude-ventures daily metrics snapshot")
    parser.add_argument(
        "--data-root",
        default=None,
        help="Ventures data root (default ~/.claude/local/ventures)",
    )
    parser.add_argument(
        "--backlog-dir",
        default=None,
        help="Backlog tasks directory (default ~/.claude/local/backlog)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Snapshot JSONL path (default ~/.claude/local/ventures/metrics/snapshots.jsonl)",
    )
    args = parser.parse_args(argv)

    out = (
        Path(args.out).expanduser()
        if args.out
        else ventures_snapshot._SNAPSHOT_PATH_DEFAULT
    )
    data_root = (
        Path(args.data_root).expanduser()
        if args.data_root
        else Path.home() / ".claude" / "local" / "ventures"
    )
    backlog_dir = (
        Path(args.backlog_dir).expanduser()
        if args.backlog_dir
        else Path.home() / ".claude" / "local" / "backlog"
    )

    row = ventures_snapshot.ensure_today(out, data_root, backlog_dir, today=date.today())
    print(json.dumps(row))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
