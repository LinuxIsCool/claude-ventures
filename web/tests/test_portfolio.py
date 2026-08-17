from __future__ import annotations

from datetime import date
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import ventures_portfolio


def _store(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "ventures"
    (root / "active").mkdir(parents=True)
    (root / "exploring").mkdir()
    (root / "active" / "legion.md").write_text(
        "---\nid: legion\ntitle: Legion\ntype: infrastructure\npriority: critical\n"
        "links:\n  repo: https://example.test/legion\ntags: [agents, prompts]\n---\n"
    )
    (root / "exploring" / "idea.md").write_text(
        "---\nid: idea\ntitle: New Idea\npriority: low\n---\n"
    )
    backlog = tmp_path / "backlog"; backlog.mkdir()
    (backlog / "task-1.md").write_text(
        "---\nid: 1\ntitle: Ship it\nventure: legion\nstatus: pending\npriority: high\ndue: 2026-08-09\n---\n"
    )
    return root, backlog


def test_data_view_exposes_schema_all_properties_and_metrics(tmp_path: Path):
    root, backlog = _store(tmp_path)
    out = ventures_portfolio.data_view(root, backlog, date(2026, 8, 9), {},
                                       {"legion": {"emoji": "⚔️", "colour": "#88aaff"}})
    legion = next(row for row in out["records"] if row["slug"] == "legion")
    assert legion["links.repo"] == "https://example.test/legion"
    assert legion["tags.__count"] == 2
    assert legion["task.today"] == 1
    assert legion["emoji"] == "⚔️"
    assert "links.repo" in out["schema"]["presets"]["all"]
    assert legion["status"] == "active"
    assert legion["storage_lifecycle"] == "active"
    assert next(c for c in out["schema"]["columns"] if c["key"] == "status")["label"] == "Status"


def test_data_view_filters_selection_lifecycle_text_and_sorts(tmp_path: Path):
    root, backlog = _store(tmp_path)
    query = {"ventures": ["legion"], "selected_only": ["true"],
             "lifecycle": ["active"], "q": ["infrastructure"], "sort": ["title:desc"]}
    out = ventures_portfolio.data_view(root, backlog, date(2026, 8, 9), query)
    assert [row["slug"] for row in out["records"]] == ["legion"]
    assert out["query"]["sort"] == [{"key": "title", "direction": "desc"}]


def test_data_view_searches_linked_task_context(tmp_path: Path):
    root, backlog = _store(tmp_path)
    out = ventures_portfolio.data_view(root, backlog, date(2026, 8, 9), {"q": ["ship it"]})
    assert [row["slug"] for row in out["records"]] == ["legion"]


def test_data_view_can_filter_to_ventures_with_work(tmp_path: Path):
    root, backlog = _store(tmp_path)
    out = ventures_portfolio.data_view(root, backlog, date(2026, 8, 9), {"work_only": ["true"]})
    assert [row["slug"] for row in out["records"]] == ["legion"]


def test_data_view_can_show_only_starred_ventures(tmp_path: Path):
    root, backlog = _store(tmp_path)
    query = {"stars": ["idea"], "stars_only": ["true"]}
    out = ventures_portfolio.data_view(root, backlog, date(2026, 8, 9), query)
    assert [row["slug"] for row in out["records"]] == ["idea"]
    assert out["query"]["scope"] == "starred"


def test_data_view_new_query_contract_and_facets(tmp_path: Path):
    root, backlog = _store(tmp_path)
    query = {"scope": ["all"], "status": ["active"], "work": ["has"]}
    out = ventures_portfolio.data_view(root, backlog, date(2026, 8, 9), query)
    assert [row["slug"] for row in out["records"]] == ["legion"]
    assert out["query"] | {"status": ["active"], "scope": "all", "work": "has"} == out["query"]
    assert out["facets"]["status"] == {"exploring": 0, "active": 1, "complete": 0}
