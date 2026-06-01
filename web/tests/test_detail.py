from __future__ import annotations
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import ventures_backlog  # noqa: E402
import ventures_projects  # noqa: E402


def _mk_backlog(tmp_path: Path) -> Path:
    d = tmp_path / "backlog"
    d.mkdir()
    (d / "task-1.md").write_text("---\nid: 1\ntitle: Critical thing\nstatus: To Do\npriority: critical\nventure: bcrg\ndue: 2026-07-01\n---\nbody\n")
    (d / "task-2.md").write_text("---\nid: 2\ntitle: Low thing\nstatus: To Do\npriority: low\nventure: bcrg\n---\nbody\n")
    (d / "task-3.md").write_text("---\nid: 3\ntitle: Other venture\nstatus: To Do\npriority: high\nventure: regen-ai\n---\nbody\n")
    (d / "task-4.md").write_text("---\nid: 4\ntitle: High via parent_id\nstatus: To Do\npriority: high\nparent_id: bcrg.proj.ms1\nparent_type: milestone\n---\nbody\n")
    return d


def test_tasks_for_venture_priority_sorted(tmp_path: Path):
    bl = _mk_backlog(tmp_path)
    tasks = ventures_backlog.tasks_for("bcrg", backlog_dir=bl)
    titles = [t["title"] for t in tasks]
    assert titles == ["Critical thing", "High via parent_id", "Low thing"]
    assert tasks[0]["id"] == "1"
    assert tasks[0]["priority"] == "critical"
    assert "regen-ai" not in [t.get("venture") for t in tasks]


def test_tasks_for_milestone_uses_parent_id(tmp_path: Path):
    bl = _mk_backlog(tmp_path)
    tasks = ventures_backlog.tasks_for("bcrg", milestone="ms1", backlog_dir=bl)
    assert [t["title"] for t in tasks] == ["High via parent_id"]


def _mk_projects(tmp_path: Path) -> Path:
    d = tmp_path / "ventures" / "project-mirror" / "projects"
    d.mkdir(parents=True)
    (d / "cognitive-engine.md").write_text(
        "# Project: Cognitive Engine\n"
        "**Venture:** Project Mirror\n"
        "**Objective:** Build the pipeline.\n\n"
        "## Milestones\n"
        "- [ ] **M1: Ingestion** — goal text\n"
        "- [x] **M2: Graph** — done\n"
    )
    return tmp_path / "ventures"


def test_projects_parse_and_list(tmp_path: Path):
    vroot = _mk_projects(tmp_path)
    p = ventures_projects.get("cognitive-engine", ventures_root=vroot)
    assert p["slug"] == "cognitive-engine"
    assert p["venture"] == "Project Mirror"
    assert p["objective"] == "Build the pipeline."
    assert len(p["milestones"]) == 2
    assert p["milestones"][0]["title"].startswith("M1")
    assert p["milestones"][1]["done"] is True
    lst = ventures_projects.list_for("Project Mirror", ventures_root=vroot)
    assert [x["slug"] for x in lst] == ["cognitive-engine"]
