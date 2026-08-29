# web/tests/test_network.py
from __future__ import annotations
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import ventures_backlog
import ventures_network


def _task(bl: Path, ident: int, venture: str = "v", **fm) -> None:
    lines = [f"id: {ident}", f"title: t{ident}", f"venture: {venture}", f"status: {fm.pop('status', 'To Do')}"]
    for k, val in fm.items():
        lines.append(f"{k}: {val}")
    (bl / f"task-{ident}.md").write_text("---\n" + "\n".join(lines) + "\n---\n")


def _bl(tmp_path: Path) -> Path:
    bl = tmp_path / "backlog"; bl.mkdir()
    ventures_backlog._CACHE.clear()
    return bl


def test_edges_direction_dedupe_and_evidence(tmp_path: Path):
    bl = _bl(tmp_path)
    _task(bl, 1, project="p1", milestone="m1")
    _task(bl, 2, project="p1", depends_on="[1]")
    _task(bl, 3, project="p2", depends_on="[task-2, 1]", blocks="[4]")
    _task(bl, 4, project="p2", depends_on="[3]")   # duplicate of 3 blocks 4
    net = ventures_network.network("v", backlog_dir=bl)
    edges = {(e["source"], e["target"]) for e in net["edges"]}
    assert edges == {("1", "2"), ("2", "3"), ("1", "3"), ("3", "4")}
    assert net["counts"]["edges"] == 4
    ev = {(e["source"], e["target"]): e["evidence"] for e in net["edges"]}
    assert ev[("1", "2")] == "task-2.depends_on"
    assert ev[("3", "4")] in {"task-4.depends_on", "task-3.blocks"}
    assert all(e["kind"] == "depends_on" for e in net["edges"])


def test_ghost_nodes_for_external_and_missing(tmp_path: Path):
    bl = _bl(tmp_path)
    _task(bl, 1, depends_on="[7, 99]")
    _task(bl, 7, venture="other")
    net = ventures_network.network("v", backlog_dir=bl)
    by = {n["id"]: n for n in net["nodes"]}
    assert by["7"]["external"] is True and by["7"]["venture"] == "other" and by["7"]["title"] == "t7"
    assert by["99"]["external"] is True and by["99"]["title"] == "task-99 (missing)"
    assert by["1"]["external"] is False
    assert net["counts"] == {"nodes": 3, "external": 2, "edges": 2, "cycles": 0}


def test_done_tasks_hidden_unless_included(tmp_path: Path):
    bl = _bl(tmp_path)
    _task(bl, 1, status="done")
    _task(bl, 2, depends_on="[1]")
    net = ventures_network.network("v", backlog_dir=bl)
    ids = {n["id"] for n in net["nodes"]}
    assert ids == {"1", "2"}  # 1 stays as a ghost so the edge survives
    assert {n["id"]: n["external"] for n in net["nodes"]}["1"] is True
    net2 = ventures_network.network("v", backlog_dir=bl, include_done=True)
    assert {n["id"]: n["external"] for n in net2["nodes"]}["1"] is False
    assert {n["id"]: n["done"] for n in net2["nodes"]}["1"] is True


def test_groups_and_ranks(tmp_path: Path):
    bl = _bl(tmp_path)
    _task(bl, 1, project="gateway", milestone="ms1")
    _task(bl, 2, project="gateway", depends_on="[1]")
    _task(bl, 3, depends_on="[2]")
    net = ventures_network.network("v", backlog_dir=bl)
    assert net["groups"]["projects"][0] == {"key": "gateway", "count": 2}
    assert {g["key"] for g in net["groups"]["projects"]} == {"gateway", "unassigned"}
    assert net["groups"]["milestones"][0]["key"] in {"unscheduled", "ms1"}
    assert net["ranks"] == {"1": 0, "2": 1, "3": 2}


def test_critical_path_is_longest_chain(tmp_path: Path):
    bl = _bl(tmp_path)
    _task(bl, 1); _task(bl, 2, depends_on="[1]"); _task(bl, 3, depends_on="[2]")
    _task(bl, 4); _task(bl, 5, depends_on="[4]")
    net = ventures_network.network("v", backlog_dir=bl)
    assert net["critical_path"] == ["1", "2", "3"]


def test_cycle_is_broken_and_counted(tmp_path: Path):
    bl = _bl(tmp_path)
    _task(bl, 1, depends_on="[2]"); _task(bl, 2, depends_on="[1]")
    net = ventures_network.network("v", backlog_dir=bl)
    assert net["counts"]["cycles"] == 1
    assert len(net["critical_path"]) == 2
    assert set(net["ranks"].values()) == {0, 1}


def test_mutation_removing_edge_changes_counts(tmp_path: Path):
    bl = _bl(tmp_path)
    _task(bl, 1); _task(bl, 2, depends_on="[1]")
    before = ventures_network.network("v", backlog_dir=bl)["counts"]["edges"]
    _task(bl, 2)
    ventures_backlog._CACHE.clear()
    after = ventures_network.network("v", backlog_dir=bl)["counts"]["edges"]
    assert (before, after) == (1, 0)
