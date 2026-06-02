# plugins/claude-ventures/web/tests/test_focus.py
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # web/
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import ventures_focus  # noqa: E402
from ventures_accessor import VenturesAccessor  # noqa: E402

TODAY = date(2026, 6, 1)


def _d(offset: int) -> str:
    return (TODAY + timedelta(days=offset)).isoformat()


def _mk_store(tmp_path: Path) -> tuple[Path, Path]:
    """One active venture with five deadlines at offsets -5, 0, +3, +20, +90.
    Each carries a parseable date and no done/reached exclusion, so the
    -5 deadline is the ONLY overdue one (parity with stats overdue_total=1)."""
    vroot = tmp_path / "ventures"
    (vroot / "active").mkdir(parents=True)
    (vroot / "active" / "alpha.md").write_text(
        "---\n"
        "id: alpha\n"
        "title: Alpha Venture\n"
        "stage: active\n"
        "priority: high\n"
        "deadlines:\n"
        f'  - date: "{_d(-5)}"\n    label: Past obligation\n    type: hard\n'
        f'  - date: "{_d(0)}"\n    label: Due today\n    type: hard\n'
        f'  - date: "{_d(3)}"\n    label: This week\n    type: hard\n'
        f'  - date: "{_d(20)}"\n    label: Soon thing\n    type: hard\n'
        f'  - date: "{_d(90)}"\n    label: Far future\n    type: hard\n'
        "---\nbody\n"
    )
    bl = tmp_path / "backlog"
    bl.mkdir()
    return vroot, bl


def test_deadline_bucketing_by_days(tmp_path: Path):
    vroot, bl = _mk_store(tmp_path)
    out = ventures_focus.buckets(vroot, bl, TODAY)
    labels = lambda key: [i["title"] for i in out[key] if i["kind"] == "deadline"]
    assert labels("attention") == ["Past obligation"]
    assert labels("today") == ["Due today"]
    assert labels("this_week") == ["This week"]
    assert labels("soon") == ["Soon thing"]
    # +90 is > 30 days out -> dropped from every bucket
    all_titles = [i["title"] for key in out for i in out[key]]
    assert "Far future" not in all_titles


def test_deadline_days_field(tmp_path: Path):
    vroot, bl = _mk_store(tmp_path)
    out = ventures_focus.buckets(vroot, bl, TODAY)
    by_title = {i["title"]: i for key in out for i in out[key]}
    assert by_title["Past obligation"]["days"] == -5
    assert by_title["Due today"]["days"] == 0
    assert by_title["This week"]["days"] == 3
    assert by_title["Soon thing"]["days"] == 20


def test_deadline_ref_shape(tmp_path: Path):
    vroot, bl = _mk_store(tmp_path)
    out = ventures_focus.buckets(vroot, bl, TODAY)
    dl = out["today"][0]
    assert dl["kind"] == "deadline"
    assert dl["venture"] == "alpha"
    assert dl["ref"] == {"v": "alpha"}
    assert dl["date"] == _d(0)
    assert dl["priority"] == "high"


def test_attention_parity_with_overdue_total(tmp_path: Path):
    vroot, bl = _mk_store(tmp_path)
    out = ventures_focus.buckets(vroot, bl, TODAY)
    deadline_attention = [i for i in out["attention"] if i["kind"] == "deadline"]
    overdue_total = VenturesAccessor(data_root=vroot, today=TODAY).stats()["overdue_total"]
    assert len(deadline_attention) == overdue_total == 1


def test_overdue_exclusions_and_harvesting(tmp_path: Path):
    vroot = tmp_path / "ventures"
    (vroot / "active").mkdir(parents=True)
    (vroot / "harvesting").mkdir(parents=True)
    (vroot / "active" / "gamma.md").write_text(
        "---\nid: gamma\ntitle: Gamma\nstage: active\npriority: high\n"
        "deadlines:\n"
        f'  - date: "{_d(-10)}"\n    label: Real overdue\n    type: hard\n'
        f'  - date: "{_d(-9)}"\n    label: Reached thing\n    type: milestone-reached\n'
        f'  - date: "{_d(-8)}"\n    label: Done thing\n    status: complete\n'
        "---\n"
    )
    # harvesting venture: its overdue deadline contributes NO attention item
    (vroot / "harvesting" / "omega.md").write_text(
        "---\nid: omega\ntitle: Omega\nstage: harvesting\npriority: high\n"
        "deadlines:\n"
        f'  - date: "{_d(-3)}"\n    label: Harvest overdue\n    type: hard\n'
        "---\n"
    )
    bl = tmp_path / "backlog"
    bl.mkdir()
    out = ventures_focus.buckets(vroot, bl, TODAY)
    att = [i["title"] for i in out["attention"] if i["kind"] == "deadline"]
    assert att == ["Real overdue"]
    overdue_total = VenturesAccessor(data_root=vroot, today=TODAY).stats()["overdue_total"]
    assert len(att) == overdue_total == 1


def test_milestones_dated_open_only(tmp_path: Path):
    vroot = tmp_path / "ventures"
    (vroot / "active").mkdir(parents=True)
    (vroot / "active" / "alpha.md").write_text(
        "---\nid: alpha\ntitle: Alpha\nstage: active\npriority: medium\n"
        "milestones:\n"
        f'  - id: ms1\n    title: Open milestone\n    status: in_progress\n    date: "{_d(2)}"\n'
        f'  - id: ms2\n    title: Done milestone\n    status: done\n    date: "{_d(4)}"\n'
        f'  - id: ms3\n    title: Completed flag\n    completed: true\n    date: "{_d(5)}"\n'
        "  - id: ms4\n    title: Undated\n    status: planned\n"
        "---\n"
    )
    bl = tmp_path / "backlog"
    bl.mkdir()
    out = ventures_focus.buckets(vroot, bl, TODAY)
    ms = [i for i in out["this_week"] if i["kind"] == "milestone"]
    assert [i["title"] for i in ms] == ["Open milestone"]
    assert ms[0]["ref"] == {"v": "alpha", "m": "ms1"}
    assert ms[0]["days"] == 2


def test_tasks_open_dated_venture_linked(tmp_path: Path):
    vroot = tmp_path / "ventures"
    (vroot / "active").mkdir(parents=True)
    (vroot / "active" / "alpha.md").write_text(
        "---\nid: alpha\ntitle: Alpha\nstage: active\npriority: medium\n---\n"
    )
    bl = tmp_path / "backlog"
    bl.mkdir()
    # open + dated + venture-linked -> this_week
    (bl / "task-1.md").write_text(
        f'---\nid: 1\ntitle: Open task\nstatus: To Do\npriority: high\nventure: alpha\ndue: {_d(5)}\n---\n'
    )
    # closed -> excluded
    (bl / "task-2.md").write_text(
        f'---\nid: 2\ntitle: Done task\nstatus: done\npriority: high\nventure: alpha\ndue: {_d(5)}\n---\n'
    )
    # undated -> excluded
    (bl / "task-3.md").write_text(
        "---\nid: 3\ntitle: Undated task\nstatus: To Do\npriority: high\nventure: alpha\n---\n"
    )
    out = ventures_focus.buckets(vroot, bl, TODAY)
    tasks = [i for i in out["this_week"] if i["kind"] == "task"]
    assert [i["title"] for i in tasks] == ["Open task"]
    t = tasks[0]
    assert t["ref"] == {"task": "1", "v": "alpha"}
    assert t["priority"] == "high"
    assert t["days"] == 5


def test_sort_within_buckets(tmp_path: Path):
    vroot = tmp_path / "ventures"
    (vroot / "active").mkdir(parents=True)
    (vroot / "active" / "alpha.md").write_text(
        "---\nid: alpha\ntitle: Alpha\nstage: active\npriority: high\n"
        "deadlines:\n"
        f'  - date: "{_d(-2)}"\n    label: Less overdue\n    type: hard\n'
        f'  - date: "{_d(-9)}"\n    label: Most overdue\n    type: hard\n'
        f'  - date: "{_d(6)}"\n    label: Later week\n    type: hard\n'
        f'  - date: "{_d(2)}"\n    label: Earlier week\n    type: hard\n'
        "---\n"
    )
    bl = tmp_path / "backlog"
    bl.mkdir()
    out = ventures_focus.buckets(vroot, bl, TODAY)
    # attention: most-overdue first (most negative days first)
    assert [i["title"] for i in out["attention"]] == ["Most overdue", "Less overdue"]
    # this_week: date ascending
    assert [i["title"] for i in out["this_week"]] == ["Earlier week", "Later week"]


def test_empty_store(tmp_path: Path):
    vroot = tmp_path / "ventures"
    (vroot / "active").mkdir(parents=True)
    bl = tmp_path / "backlog"
    bl.mkdir()
    out = ventures_focus.buckets(vroot, bl, TODAY)
    assert out == {"today": [], "this_week": [], "soon": [], "attention": []}
