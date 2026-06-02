from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # web/
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import ventures_timeline  # noqa: E402


def _mk_store(tmp_path: Path) -> tuple[Path, Path]:
    vroot = tmp_path / "ventures"
    (vroot / "active").mkdir(parents=True)
    # Venture A: dated milestone + dated deadline + (later) a dated linked task
    (vroot / "active" / "alpha.md").write_text(
        "---\n"
        "id: alpha\n"
        "title: Alpha Venture\n"
        "stage: active\n"
        "priority: high\n"
        "milestones:\n"
        "  - id: ms1\n"
        "    title: MVP launch\n"
        "    status: in_progress\n"
        "    date: \"2026-05-01\"\n"
        "deadlines:\n"
        "  - date: \"2026-07-01\"\n"
        "    label: Phase 2 deliverable\n"
        "    type: hard\n"
        "---\nbody\n"
    )
    # Venture B: no dated items at all
    (vroot / "active" / "beta.md").write_text(
        "---\n"
        "id: beta\n"
        "title: Beta Venture\n"
        "stage: active\n"
        "priority: medium\n"
        "milestones:\n"
        "  - id: ms9\n"
        "    title: Undated milestone\n"
        "    status: planned\n"
        "deadlines:\n"
        "  - label: No date deadline\n"
        "    type: soft\n"
        "---\nbody\n"
    )
    bl = tmp_path / "backlog"
    bl.mkdir()
    # dated, venture-linked task -> goes into alpha's lane
    (bl / "task-1.md").write_text(
        "---\nid: 1\ntitle: Do the thing\nstatus: To Do\npriority: critical\nventure: alpha\ndue: 2026-06-15\n---\nbody\n"
    )
    # undated venture-linked task -> ignored
    (bl / "task-2.md").write_text(
        "---\nid: 2\ntitle: Undated task\nstatus: To Do\npriority: low\nventure: alpha\n---\nbody\n"
    )
    # dated task linked to a venture with NO own dated items still creates no lane
    # because beta has no dated items? No — a dated task is itself a dated item.
    # Keep beta truly empty: no dated tasks for beta.
    return vroot, bl


def test_timeline_one_lane_three_items_sorted(tmp_path: Path):
    vroot, bl = _mk_store(tmp_path)
    tl = ventures_timeline.timeline(vroot, bl, today=date(2026, 6, 1))
    lanes = tl["lanes"]
    # Exactly one lane (alpha); beta omitted (no dated items)
    assert len(lanes) == 1
    lane = lanes[0]
    assert lane["venture"] == "alpha"
    assert lane["title"] == "Alpha Venture"
    items = lane["items"]
    assert len(items) == 3
    # sorted by date ascending: milestone 05-01, task 06-15, deadline 07-01
    assert [i["date"] for i in items] == ["2026-05-01", "2026-06-15", "2026-07-01"]
    assert [i["type"] for i in items] == ["milestone", "task", "deadline"]
    # range across all items
    assert tl["range"] == {"min": "2026-05-01", "max": "2026-07-01"}


def test_timeline_item_fields(tmp_path: Path):
    vroot, bl = _mk_store(tmp_path)
    tl = ventures_timeline.timeline(vroot, bl, today=date(2026, 6, 1))
    items = tl["lanes"][0]["items"]
    by_type = {i["type"]: i for i in items}
    ms = by_type["milestone"]
    assert ms["id"] == "ms1"
    assert ms["title"] == "MVP launch"
    assert ms["status"] == "in_progress"
    dl = by_type["deadline"]
    assert dl["title"] == "Phase 2 deliverable"
    tk = by_type["task"]
    assert tk["id"] == "1"
    assert tk["title"] == "Do the thing"
    assert tk["priority"] == "critical"


def test_timeline_empty_store(tmp_path: Path):
    vroot = tmp_path / "ventures"
    (vroot / "active").mkdir(parents=True)
    bl = tmp_path / "backlog"
    bl.mkdir()
    tl = ventures_timeline.timeline(vroot, bl, today=date(2026, 6, 1))
    assert tl["lanes"] == []
    assert tl["range"] == {"min": None, "max": None}
