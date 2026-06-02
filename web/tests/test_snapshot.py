# plugins/claude-ventures/web/tests/test_snapshot.py
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # web/
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import ventures_snapshot  # noqa: E402


def _make_store(tmp_path: Path) -> tuple[Path, Path]:
    """Build a tiny ventures store + backlog dir and return (ventures_root, backlog_dir)."""
    vroot = tmp_path / "ventures"
    (vroot / "active").mkdir(parents=True)
    (vroot / "exploring").mkdir(parents=True)

    # alpha: active, one overdue (past) deadline, 2 milestones (1 complete),
    #        revenue 50000
    (vroot / "active" / "alpha.md").write_text(
        "---\n"
        "id: alpha\n"
        "title: Alpha Venture\n"
        "stage: active\n"
        "priority: critical\n"
        "deadlines:\n"
        "  - date: \"2026-04-01\"\n"
        "    label: Overdue thing\n"
        "    type: hard\n"
        "milestones:\n"
        "  - id: ms1\n"
        "    title: Phase 1\n"
        "    status: complete\n"
        "    completed: true\n"
        "  - id: ms2\n"
        "    title: Phase 2\n"
        "    status: in-progress\n"
        "financial:\n"
        "  revenue_to_date: 50000\n"
        "  currency: CAD\n"
        "---\n\nBody.\n"
    )
    # beta: exploring, no overdue, 1 milestone (not complete), revenue 1500
    (vroot / "exploring" / "beta.md").write_text(
        "---\n"
        "id: beta\n"
        "title: Beta Venture\n"
        "stage: exploring\n"
        "priority: medium\n"
        "milestones:\n"
        "  - id: bm1\n"
        "    title: Discovery\n"
        "    status: planned\n"
        "financial:\n"
        "  revenue_to_date: 1500\n"
        "---\n\nBody.\n"
    )

    bl = tmp_path / "backlog"
    bl.mkdir()
    # open task linked to alpha
    (bl / "task-1.md").write_text(
        "---\nid: 1\ntitle: Open task\nstatus: To Do\npriority: high\nventure: alpha\n---\nbody\n"
    )
    # done task linked to alpha
    (bl / "task-2.md").write_text(
        "---\nid: 2\ntitle: Done task\nstatus: done\npriority: low\nventure: alpha\n---\nbody\n"
    )
    # task linked via parent_id (open)
    (bl / "task-3.md").write_text(
        "---\nid: 3\ntitle: Parent linked\nstatus: In Progress\npriority: medium\n"
        "parent_id: beta.proj.bm1\nparent_type: milestone\n---\nbody\n"
    )
    # unlinked task — must be ignored
    (bl / "task-4.md").write_text(
        "---\nid: 4\ntitle: Unlinked\nstatus: To Do\npriority: low\n---\nbody\n"
    )
    return vroot, bl


def test_compute_keys_and_counts(tmp_path: Path):
    vroot, bl = _make_store(tmp_path)
    today = date(2026, 6, 1)
    row = ventures_snapshot.compute(vroot, bl, today)

    assert set(row.keys()) == {
        "date",
        "ventures_total",
        "by_stage",
        "deadlines_overdue",
        "tasks_open",
        "tasks_completed_total",
        "milestones_total",
        "milestones_complete",
        "revenue_total",
    }
    assert row["date"] == "2026-06-01"
    assert row["ventures_total"] == 2
    # by_stage from accessor stats: active=1, exploring=1
    assert row["by_stage"]["active"] == 1
    assert row["by_stage"]["exploring"] == 1
    assert row["deadlines_overdue"] == 1
    # venture-linked tasks: task-1 (open), task-2 (done), task-3 (open via parent)
    assert row["tasks_open"] == 2
    assert row["tasks_completed_total"] == 1
    # milestones: alpha 2 + beta 1 = 3, one complete (ms1)
    assert row["milestones_total"] == 3
    assert row["milestones_complete"] == 1
    # revenue: 50000 + 1500
    assert row["revenue_total"] == 51500.0


def test_ensure_today_idempotent(tmp_path: Path):
    vroot, bl = _make_store(tmp_path)
    today = date(2026, 6, 1)
    path = tmp_path / "metrics" / "snapshots.jsonl"

    r1 = ventures_snapshot.ensure_today(path, vroot, bl, today)
    assert path.exists()
    assert r1["date"] == "2026-06-01"
    assert len(ventures_snapshot.load(path)) == 1

    # re-run same day -> still exactly one row
    ventures_snapshot.ensure_today(path, vroot, bl, today)
    rows = ventures_snapshot.load(path)
    assert len(rows) == 1
    assert rows[0]["date"] == "2026-06-01"


def test_ensure_today_two_dates(tmp_path: Path):
    vroot, bl = _make_store(tmp_path)
    path = tmp_path / "metrics" / "snapshots.jsonl"

    ventures_snapshot.ensure_today(path, vroot, bl, date(2026, 6, 1))
    ventures_snapshot.ensure_today(path, vroot, bl, date(2026, 6, 2))
    rows = ventures_snapshot.load(path)
    assert len(rows) == 2
    assert sorted(r["date"] for r in rows) == ["2026-06-01", "2026-06-02"]


def test_load_missing_path(tmp_path: Path):
    assert ventures_snapshot.load(tmp_path / "nope" / "snapshots.jsonl") == []


def test_append_creates_parents(tmp_path: Path):
    path = tmp_path / "a" / "b" / "snapshots.jsonl"
    ventures_snapshot.append(path, {"date": "2026-06-01", "ventures_total": 1})
    rows = ventures_snapshot.load(path)
    assert rows == [{"date": "2026-06-01", "ventures_total": 1}]
    # second append adds a line
    ventures_snapshot.append(path, {"date": "2026-06-02", "ventures_total": 2})
    assert len(ventures_snapshot.load(path)) == 2
    # confirm raw JSONL is one object per line
    lines = path.read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["date"] == "2026-06-01"
