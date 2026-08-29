# web/tests/test_dependency_keys.py
from __future__ import annotations
from datetime import date
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import ventures_backlog
import ventures_tasks
from ventures_scope import PortfolioScope

TODAY = date(2026, 8, 28)


def _venture(tmp_path: Path) -> Path:
    vr = tmp_path / "ventures"
    for lc in ("exploring", "active", "sustaining", "dormant", "harvesting"):
        (vr / lc).mkdir(parents=True)
    (vr / "active" / "v.md").write_text("---\nid: v\ntitle: v\n---\n")
    return vr


def _task(bl: Path, ident: int, extra: str = "") -> None:
    (bl / f"task-{ident}.md").write_text(
        f"---\nid: {ident}\ntitle: t{ident}\nventure: v\nstatus: To Do\n{extra}---\n")


def test_schema_key_depends_on_is_read(tmp_path: Path):
    bl = tmp_path / "backlog"; bl.mkdir()
    _task(bl, 1, "depends_on: [task-7, 8]\nblocks: [9]\n")
    rows = ventures_backlog._all_tasks(bl)
    assert rows[0]["depends_on"] == ["7", "8"]
    assert rows[0]["blocks"] == ["9"]


def test_legacy_keys_still_count(tmp_path: Path):
    bl = tmp_path / "backlog"; bl.mkdir()
    _task(bl, 1, "blocked_by: [2]\ndependencies: [task-3]\n")
    rows = ventures_backlog._all_tasks(bl)
    assert rows[0]["depends_on"] == ["2", "3"]


def test_blocked_flag_follows_depends_on(tmp_path: Path):
    vr = _venture(tmp_path)
    bl = tmp_path / "backlog"; bl.mkdir()
    _task(bl, 1, "depends_on: [2]\n")
    _task(bl, 2)
    rows = {r["id"]: r for r in ventures_tasks.records(
        vr, bl, PortfolioScope(frozenset({"v"})), TODAY)}
    assert rows["1"]["blocked"] is True
    assert rows["2"]["blocked"] is False


def test_mutation_removing_edge_unblocks(tmp_path: Path):
    """Deleting the only depends_on edge must flip blocked to False.

    Guards against a reader that returns True for any task with any list key.
    """
    vr = _venture(tmp_path)
    bl = tmp_path / "backlog"; bl.mkdir()
    _task(bl, 1, "depends_on: [2]\n")
    scope = PortfolioScope(frozenset({"v"}))
    before = ventures_tasks.records(vr, bl, scope, TODAY)[0]["blocked"]
    _task(bl, 1, "depends_on: []\n")
    ventures_backlog._CACHE.clear()
    after = ventures_tasks.records(vr, bl, scope, TODAY)[0]["blocked"]
    assert (before, after) == (True, False)


def test_scalar_and_string_values_are_tolerated(tmp_path: Path):
    """A bare scalar (YAML int or plain string) must not raise, not be char-split."""
    bl = tmp_path / "backlog"; bl.mkdir()
    _task(bl, 1, "depends_on: 7\nblocks: task-9\n")
    rows = ventures_backlog._all_tasks(bl)
    assert rows[0]["depends_on"] == ["7"]
    assert rows[0]["blocks"] == ["9"]


def test_mapping_value_is_skipped_without_raising(tmp_path: Path):
    bl = tmp_path / "backlog"; bl.mkdir()
    _task(bl, 1, "depends_on: {a: 1}\n")
    rows = ventures_backlog._all_tasks(bl)
    assert rows[0]["depends_on"] == []
