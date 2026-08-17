from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # web/
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import ventures_snapshot  # noqa: E402
import ventures_trends  # noqa: E402


def _mk_store(tmp_path: Path) -> tuple[Path, Path]:
    """Ventures store with 3 completed milestones on 3 distinct dates,
    revenue, and a couple of future deadlines."""
    vroot = tmp_path / "ventures"
    (vroot / "active").mkdir(parents=True)
    (vroot / "exploring").mkdir(parents=True)

    (vroot / "active" / "alpha.md").write_text(
        "---\n"
        "id: alpha\n"
        "title: Alpha Venture\n"
        "stage: active\n"
        "priority: critical\n"
        "deadlines:\n"
        "  - date: \"2026-06-10\"\n"
        "    label: Near deadline\n"
        "    type: hard\n"
        "  - date: \"2026-07-01\"\n"
        "    label: Later deadline\n"
        "    type: soft\n"
        "milestones:\n"
        "  - id: ms1\n"
        "    title: Phase 1\n"
        "    status: complete\n"
        "    completed: true\n"
        "    date: \"2026-03-01\"\n"
        "  - id: ms2\n"
        "    title: Phase 2\n"
        "    status: complete\n"
        "    date: \"2026-04-01\"\n"
        "financial:\n"
        "  revenue_to_date: 50000\n"
        "  currency: CAD\n"
        "---\n\nBody.\n"
    )
    (vroot / "exploring" / "beta.md").write_text(
        "---\n"
        "id: beta\n"
        "title: Beta Venture\n"
        "stage: exploring\n"
        "priority: medium\n"
        "milestones:\n"
        "  - id: bm1\n"
        "    title: Discovery\n"
        "    status: done\n"
        "    completed: true\n"
        "    date: \"2026-05-01\"\n"
        "  - id: bm2\n"
        "    title: Undated complete\n"
        "    status: complete\n"
        "financial:\n"
        "  revenue_to_date: 1500\n"
        "---\n\nBody.\n"
    )

    bl = tmp_path / "backlog"
    bl.mkdir()
    (bl / "task-1.md").write_text(
        "---\nid: 1\ntitle: Open task\nstatus: To Do\npriority: high\nventure: alpha\n---\nbody\n"
    )
    return vroot, bl


def test_milestones_reached_cumulative_monotonic(tmp_path: Path):
    vroot, bl = _mk_store(tmp_path)
    snap = tmp_path / "metrics" / "snapshots.jsonl"
    out = ventures_trends.trends(vroot, bl, today=date(2026, 6, 2), snapshot_path=snap)
    series = out["series"]["milestones_reached_cumulative"]
    # 3 completed milestones with parseable dates -> 3 distinct dates
    assert len(series) == 3
    values = [p["value"] for p in series]
    # monotonic non-decreasing
    assert all(values[i] <= values[i + 1] for i in range(len(values) - 1))
    # ends at 3
    assert values[-1] == 3
    # dates sorted ascending
    dates = [p["date"] for p in series]
    assert dates == sorted(dates)


def test_name_lists_present_and_correct(tmp_path: Path):
    vroot, bl = _mk_store(tmp_path)
    snap = tmp_path / "metrics" / "snapshots.jsonl"
    out = ventures_trends.trends(vroot, bl, today=date(2026, 6, 2), snapshot_path=snap)
    assert out["derivable"] == [
        "milestones_reached_cumulative",
        "deadline_pressure",
    ]
    assert out["snapshot_based"] == [
        "tasks_open",
        "deadlines_overdue",
        "milestones_complete",
        "ventures_by_stage",
    ]
    # every named series is present in the series dict
    for name in out["derivable"] + out["snapshot_based"]:
        assert name in out["series"]


def test_unavailable_revenue_series_is_not_invented(tmp_path: Path):
    vroot, bl = _mk_store(tmp_path)
    snap = tmp_path / "metrics" / "snapshots.jsonl"
    out = ventures_trends.trends(vroot, bl, today=date(2026, 6, 2), snapshot_path=snap)
    assert "revenue_cumulative" not in out["series"]


def test_deadline_pressure_12_weeks(tmp_path: Path):
    vroot, bl = _mk_store(tmp_path)
    snap = tmp_path / "metrics" / "snapshots.jsonl"
    out = ventures_trends.trends(vroot, bl, today=date(2026, 6, 2), snapshot_path=snap)
    dp = out["series"]["deadline_pressure"]
    assert len(dp) == 12
    # total counted deadlines within the 12-week horizon: both 06-10 and 07-01 are future
    assert sum(p["value"] for p in dp) == 2


def test_snapshot_based_two_dates_monotonic(tmp_path: Path):
    vroot, bl = _mk_store(tmp_path)
    snap = tmp_path / "metrics" / "snapshots.jsonl"
    # seed two prior rows on two dates
    ventures_snapshot.append(snap, ventures_snapshot.compute(vroot, bl, date(2026, 5, 30)))
    ventures_snapshot.append(snap, ventures_snapshot.compute(vroot, bl, date(2026, 5, 31)))
    out = ventures_trends.trends(vroot, bl, today=date(2026, 6, 2), snapshot_path=snap)
    to = out["series"]["tasks_open"]
    # 2 seeded + today's lazy row = 3
    assert len(to) >= 2
    dates = [p["date"] for p in to]
    assert dates == sorted(dates)


def test_lazy_write_creates_file(tmp_path: Path):
    vroot, bl = _mk_store(tmp_path)
    snap = tmp_path / "metrics" / "fresh.jsonl"
    assert not snap.exists()
    ventures_trends.trends(vroot, bl, today=date(2026, 6, 2), snapshot_path=snap)
    assert snap.exists()
    rows = ventures_snapshot.load(snap)
    assert any(r.get("date") == "2026-06-02" for r in rows)
