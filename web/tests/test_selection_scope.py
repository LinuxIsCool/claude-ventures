"""Selection is what scopes the rail, the counters and the task table.

These tests execute the page's own scopeQuery() in node rather than grepping
index.html, so they fail when the *behaviour* changes, not when a string moves.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parent.parent
INDEX = (WEB / "static" / "index.html").read_text()
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node is required to run page logic")


def _scope_query_source() -> str:
    m = re.search(r"\n(    function scopeQuery\(\) \{.*?\n    \})\n", INDEX, re.S)
    assert m, "scopeQuery() not found in index.html"
    return m.group(1)


def _run_scope(selected, stars, statuses=()) -> str:
    """Run the page's real scopeQuery() against a given selection/star state."""
    script = f"""
{_scope_query_source()}
const state = {{
  selected: new Set({json.dumps(list(selected))}),
  stars: new Set({json.dumps(list(stars))}),
  statuses: new Set({json.dumps(list(statuses))}),
}};
console.log(scopeQuery());
"""
    out = subprocess.run([NODE, "--input-type=module", "-e", script],
                         capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def _ventures(query: str) -> list[str]:
    from urllib.parse import parse_qs
    return [v for v in parse_qs(query).get("ventures", [""])[0].split(",") if v]


def test_highlighting_ventures_scopes_the_view_to_them():
    assert _ventures(_run_scope(selected=["legion", "bcrg"], stars=[])) == ["legion", "bcrg"]


def test_selection_wins_over_stars_when_both_are_set():
    got = _ventures(_run_scope(selected=["legion"], stars=["cie", "indigenomics-ai"]))
    assert got == ["legion"], "a highlighted venture must override the starred set"


def test_stars_are_the_fallback_when_nothing_is_highlighted():
    got = _ventures(_run_scope(selected=[], stars=["cie", "indigenomics-ai"]))
    assert got == ["cie", "indigenomics-ai"]


def test_empty_selection_and_no_stars_scopes_to_nothing():
    assert _ventures(_run_scope(selected=[], stars=[])) == []


def test_lifecycle_filter_still_rides_along_with_the_scope():
    assert "lifecycle=active" in _run_scope(selected=["legion"], stars=[], statuses=["active"])


def test_scoped_task_table_is_fetched_and_rendered_below_the_cards():
    assert 'api("api/tasks?" + scopeQuery())' in INDEX, "the page must call the tasks endpoint"
    assert 'id="scoped-tasks"' in INDEX, "the task table needs a host element below the grid"
    assert "function renderScopedTasks" in INDEX
