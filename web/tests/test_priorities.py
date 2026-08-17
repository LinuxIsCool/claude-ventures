# plugins/claude-ventures/web/tests/test_priorities.py
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # web/
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import ventures_priorities  # noqa: E402


def _mk_store(tmp_path: Path) -> tuple[Path, Path]:
    """ACTIVE venture with revenue + overdue critical task;
    DORMANT venture with no revenue + a low-priority task due +20 days."""
    vroot = tmp_path / "ventures"
    (vroot / "active").mkdir(parents=True)
    (vroot / "dormant").mkdir(parents=True)
    (vroot / "active" / "alpha.md").write_text(
        "---\nid: alpha\ntitle: Alpha\nstage: active\npriority: critical\n"
        "financial:\n  revenue_to_date: 50000\n  currency: CAD\n"
        "---\nbody\n"
    )
    (vroot / "dormant" / "zeta.md").write_text(
        "---\nid: zeta\ntitle: Zeta\nstage: dormant\npriority: low\n"
        "financial:\n  revenue_to_date: 0\n"
        "---\nbody\n"
    )
    bl = tmp_path / "backlog"
    bl.mkdir()
    # overdue critical task in the active venture
    (bl / "task-1.md").write_text(
        "---\nid: 1\ntitle: Overdue critical\nstatus: To Do\npriority: critical\n"
        "venture: alpha\ndue: 2026-05-01\n---\nbody\n"
    )
    # low-priority task due +20 days in the dormant venture
    (bl / "task-2.md").write_text(
        "---\nid: 2\ntitle: Far low\nstatus: To Do\npriority: low\n"
        "venture: zeta\ndue: 2026-06-21\n---\nbody\n"
    )
    return vroot, bl


def test_score_parts_sum_to_score(tmp_path: Path):
    vroot, bl = _mk_store(tmp_path)
    out = ventures_priorities.ranked(vroot, bl, date(2026, 6, 1))
    assert out["items"], "expected ranked items"
    for it in out["items"]:
        parts = it["score_parts"]
        assert (
            parts["urgency"] + parts["manual"] + parts["stage"]
            == it["score"]
        ), it


def test_overdue_critical_active_revenue_outranks_far_low_dormant(tmp_path: Path):
    vroot, bl = _mk_store(tmp_path)
    out = ventures_priorities.ranked(vroot, bl, date(2026, 6, 1))
    titles = [it["title"] for it in out["items"]]
    assert "Overdue critical" in titles
    assert "Far low" in titles
    assert titles.index("Overdue critical") < titles.index("Far low")
    # explicit score sanity: overdue critical active = 50+30+10
    crit = next(it for it in out["items"] if it["title"] == "Overdue critical")
    assert crit["score"] == 90
    far = next(it for it in out["items"] if it["title"] == "Far low")
    # +20 days urgency = round(45*(1-20/30)) = 15; low=4; dormant=2; no rev=0
    assert far["score_parts"] == {"urgency": 15, "manual": 4, "stage": 2}
    assert far["score"] == 21
    assert out["signals_available"]["financial"] is False


def test_completed_tasks_excluded(tmp_path: Path):
    vroot, bl = _mk_store(tmp_path)
    (bl / "task-3.md").write_text(
        "---\nid: 3\ntitle: Done one\nstatus: done\npriority: critical\n"
        "venture: alpha\ndue: 2026-05-01\n---\n"
    )
    out = ventures_priorities.ranked(vroot, bl, date(2026, 6, 1))
    assert "Done one" not in [it["title"] for it in out["items"]]


def test_deadlines_become_items_and_respect_overdue_exclusions(tmp_path: Path):
    vroot = tmp_path / "ventures"
    (vroot / "active").mkdir(parents=True)
    (vroot / "active" / "gamma.md").write_text(
        "---\nid: gamma\ntitle: Gamma\nstage: active\npriority: high\n"
        "deadlines:\n"
        "  - date: \"2026-04-01\"\n    label: Real obligation\n    type: hard\n"
        "  - date: \"2026-04-02\"\n    label: Reached thing\n    type: milestone-reached\n"
        "  - date: \"2026-04-03\"\n    label: Done thing\n    status: complete\n"
        "---\n"
    )
    bl = tmp_path / "backlog"
    bl.mkdir()
    out = ventures_priorities.ranked(vroot, bl, date(2026, 6, 1))
    dl = [it for it in out["items"] if it["kind"] == "deadline"]
    labels = [it["title"] for it in dl]
    assert labels == ["Real obligation"]  # reached + complete excluded
    assert dl[0]["ref"] == {"v": "gamma"}


def test_tie_break_by_earlier_due(tmp_path: Path):
    """Two items with identical scores; earlier due date sorts first."""
    vroot = tmp_path / "ventures"
    (vroot / "active").mkdir(parents=True)
    (vroot / "active" / "a.md").write_text(
        "---\nid: a\ntitle: A\nstage: active\npriority: medium\n---\n"
    )
    bl = tmp_path / "backlog"
    bl.mkdir()
    # both medium, same venture (active, no revenue), both >30 days out so
    # urgency==0 for both => identical scores; they differ only by due date.
    (bl / "task-1.md").write_text(
        "---\nid: 1\ntitle: Later\nstatus: To Do\npriority: medium\nventure: a\ndue: 2026-09-20\n---\n"
    )
    (bl / "task-2.md").write_text(
        "---\nid: 2\ntitle: Earlier\nstatus: To Do\npriority: medium\nventure: a\ndue: 2026-09-10\n---\n"
    )
    out = ventures_priorities.ranked(vroot, bl, date(2026, 6, 1))
    tasks = [it for it in out["items"] if it["kind"] == "task"]
    assert [t["title"] for t in tasks] == ["Earlier", "Later"]
    assert tasks[0]["score"] == tasks[1]["score"]


def test_empty_due_sorts_last_in_tie(tmp_path: Path):
    vroot = tmp_path / "ventures"
    (vroot / "active").mkdir(parents=True)
    (vroot / "active" / "a.md").write_text(
        "---\nid: a\ntitle: A\nstage: dormant\npriority: medium\n---\n"
    )
    # put venture in dormant dir so urgency 0 even though a no-due task
    (vroot / "dormant").mkdir(parents=True)
    (vroot / "dormant" / "b.md").write_text(
        "---\nid: b\ntitle: B\nstage: dormant\npriority: low\n---\n"
    )
    bl = tmp_path / "backlog"
    bl.mkdir()
    # both low priority, dormant, no revenue => same score; one has due, one doesn't
    (bl / "task-1.md").write_text(
        "---\nid: 1\ntitle: NoDue\nstatus: To Do\npriority: low\nventure: b\n---\n"
    )
    (bl / "task-2.md").write_text(
        "---\nid: 2\ntitle: HasDue\nstatus: To Do\npriority: low\nventure: b\ndue: 2026-09-01\n---\n"
    )
    out = ventures_priorities.ranked(vroot, bl, date(2026, 6, 1))
    tasks = [it["title"] for it in out["items"] if it["kind"] == "task" and it["venture"] == "b"]
    # HasDue (due far out, urgency 0) and NoDue (urgency 0) share score; "" due sorts last
    assert tasks == ["HasDue", "NoDue"]
