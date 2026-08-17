from __future__ import annotations

from datetime import date
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import ventures_focus
import ventures_tasks
from ventures_scope import PortfolioScope


TODAY = date(2026, 8, 9)  # Sunday


def _stores(tmp_path: Path) -> tuple[Path, Path]:
    vr = tmp_path / "ventures"
    for lifecycle in ("exploring", "active", "sustaining", "dormant", "harvesting"):
        (vr / lifecycle).mkdir(parents=True)
    for lifecycle, slug in (("active", "starred"), ("dormant", "sleeping"), ("active", "other")):
        (vr / lifecycle / f"{slug}.md").write_text(f"---\nid: {slug}\ntitle: {slug}\n---\n")
    bl = tmp_path / "backlog"; bl.mkdir()
    rows = [
        (1, "oldest", "2026-08-01", "high", "To Do", ""),
        (2, "today", "2026-08-09", "medium", "To Do", ""),
        (3, "overflow today", "2026-08-08", "critical", "To Do", ""),
        (4, "soon one", "2026-08-10", "low", "To Do", ""),
        (5, "soon two", "2026-08-15", "medium", "To Do", ""),
        (6, "soon three", "2026-08-20", "high", "To Do", ""),
        (7, "soon overflow", "2026-08-21", "high", "To Do", ""),
        (8, "undated", "", "high", "To Do", ""),
        (9, "blocked", "2026-08-09", "critical", "blocked", "x"),
        (10, "closed", "2026-08-01", "high", "done", ""),
    ]
    for ident, title, due, priority, status, blocked in rows:
        (bl / f"task-{ident}.md").write_text(
            f"---\nid: {ident}\ntitle: {title}\nventure: starred\nstatus: {status}\npriority: {priority}\ndue: {due}\n"
            + (f"blocked_by: [{blocked}]\n" if blocked else "") + "---\n")
    (bl / "task-20.md").write_text("---\nid: 20\ntitle: other\nventure: other\nstatus: To Do\ndue: 2026-08-09\n---\n")
    return vr, bl


def test_empty_star_scope_is_intentionally_empty(tmp_path: Path):
    vr, bl = _stores(tmp_path)
    out = ventures_focus.buckets(vr, bl, TODAY, PortfolioScope(frozenset()))
    assert all(out[key] == [] for key in ("today", "this_week", "soon", "backlog"))
    assert out["scope"]["empty"] is True


def test_focus_caps_exact_grouping_and_task_links(tmp_path: Path):
    vr, bl = _stores(tmp_path)
    scope = PortfolioScope(frozenset({"starred"}))
    out = ventures_focus.buckets(vr, bl, TODAY, scope)
    assert [t["id"] for t in out["today"]] == ["1", "3"]
    assert out["this_week"] == []  # today is Sunday
    assert [t["id"] for t in out["soon"]] == ["4", "5", "6"]
    assert {t["id"] for t in out["backlog"]} == {"2", "7", "8", "9"}
    grouped = out["today"] + out["this_week"] + out["soon"] + out["backlog"]
    assert len({t["id"] for t in grouped}) == len(grouped)
    assert all(t["href"] == f"/backlog/tasks/{t['id']}" for t in grouped)


def test_widgets_share_scope_and_overdue_semantics(tmp_path: Path):
    vr, bl = _stores(tmp_path)
    scope = PortfolioScope(frozenset({"starred"}))
    active = ventures_tasks.widget(vr, bl, scope, TODAY, "active", True)
    overdue = ventures_tasks.widget(vr, bl, scope, TODAY, "overdue", True)
    assert active["count"] == 9
    assert {t["id"] for t in overdue["records"]} == {"1", "3"}


def test_lifecycle_filter_maps_display_groups(tmp_path: Path):
    vr, bl = _stores(tmp_path)
    assert PortfolioScope(frozenset({"sleeping"}), frozenset({"active"})).includes("sleeping", "dormant") is False
    assert PortfolioScope(frozenset({"starred"}), frozenset({"active"})).includes("starred", "active") is True


def test_card_metrics_reconcile_with_focus_and_keep_overdue_warning(tmp_path: Path):
    vr, bl = _stores(tmp_path)
    metrics = ventures_tasks.card_metrics(vr, bl, TODAY)["ventures"]["starred"]
    focus = ventures_focus.buckets(vr, bl, TODAY, PortfolioScope(frozenset({"starred"})))
    assert metrics == {
        "today": len(focus["today"]),
        "this_week": len(focus["this_week"]),
        "soon": len(focus["soon"]),
        "backlog": len(focus["backlog"]),
        "overdue": 2,
    }
