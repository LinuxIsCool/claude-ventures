from __future__ import annotations
import sys
from datetime import date
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import ventures_backlog  # noqa: E402
import ventures_projects  # noqa: E402
import ventures_detail  # noqa: E402


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


def _mk_full_store(tmp_path: Path) -> tuple[Path, Path]:
    vroot = tmp_path / "ventures"
    (vroot / "active").mkdir(parents=True)
    (vroot / "active" / "bcrg.md").write_text(
        "---\nid: bcrg\ntitle: BCRG\nstage: active\npriority: critical\n"
        "description: Validator research.\n"
        "co_venturers:\n  - name: Shawn\n    role: Lead\n"
        "milestones:\n  - id: ms1\n    title: Phase 2\n    status: complete\n    completed: true\n    deliverables: [x]\n"
        # Real schema. This fixture previously wrote `financial.revenue_to_date`,
        # a key NO venture file has ever contained, and asserted the payload
        # returned it. That is why the suite stayed green while the Financial
        # section rendered an em-dash for every venture in the store.
        "financial:\n  status: contracted\n"
        "  total_invoiced:\n    amount: 50000\n    currency: CAD\n"
        "  invoices:\n    - id: INV-001\n      amount: 50000\n      currency: CAD\n"
        "      description: Phase 2\n      status: paid\n      issued: 2026-01-05\n"
        "deadlines:\n  - date: 2026-12-01\n    label: Renewal\n    type: hard\n"
        "links:\n  github: https://github.com/x\n"
        "---\nbody\n"
    )
    bl = tmp_path / "backlog"
    bl.mkdir()
    (bl / "task-1.md").write_text("---\nid: 1\ntitle: Do thing\nstatus: To Do\npriority: high\nventure: bcrg\n---\n")
    return vroot, bl


def test_venture_detail_assembles(tmp_path: Path):
    vroot, bl = _mk_full_store(tmp_path)
    d = ventures_detail.venture("bcrg", ventures_root=vroot, backlog_dir=bl)
    assert d["title"] == "BCRG"
    assert d["milestones"][0]["id"] == "ms1"
    assert d["financial"]["total_invoiced"]["amount"] == 50000
    assert d["financial"]["invoices"][0]["id"] == "INV-001"
    assert d["links"]["github"] == "https://github.com/x"
    assert [t["title"] for t in d["tasks"]] == ["Do thing"]
    assert d["co_venturers"][0]["name"] == "Shawn"


def test_venture_detail_includes_deadlines(tmp_path: Path):
    """Regression: `deadlines` was parsed by the accessor and then dropped by
    the payload assembler, so the page could not render the field that matters
    most. It must survive the whole path."""
    vroot, bl = _mk_full_store(tmp_path)
    d = ventures_detail.venture("bcrg", ventures_root=vroot, backlog_dir=bl)
    assert d["deadlines"][0]["date"] == "2026-12-01"
    assert d["deadlines"][0]["label"] == "Renewal"


def test_structured_project_tree_is_discovered(tmp_path: Path):
    """Regression: projects were read from project-mirror/ only, so the real
    per-venture trees rendered as 'none'. Both formats must be found, and the
    structured one must parse as YAML rather than through the prose regexes."""
    vroot = tmp_path / "ventures"
    msdir = vroot / "acme" / "projects" / "build-it" / "milestones"
    msdir.mkdir(parents=True)
    (vroot / "acme" / "projects" / "build-it" / "project.md").write_text(
        "---\nslug: build-it\nname: Build It\nventure: acme\nstage: active\n"
        "priority: high\nowner: shawn\nmilestones:\n  - m1\n---\n", encoding="utf-8")
    (msdir / "m1.md").write_text(
        "---\nslug: m1\nname: First cut\nproject: build-it\nventure: acme\n"
        "stage: active\ndeadline: '2026-09-01'\n---\n", encoding="utf-8")

    lst = ventures_projects.list_for("acme", ventures_root=vroot)
    assert [p["slug"] for p in lst] == ["build-it"]
    assert lst[0]["name"] == "Build It"
    assert lst[0]["format"] == "structured"
    assert lst[0]["milestones"][0]["title"] == "First cut"
    assert lst[0]["milestones"][0]["deadline"] == "2026-09-01"


def test_projects_are_deduped_across_slug_and_title(tmp_path: Path):
    """venture() looks up by slug AND by title; a project matching both must
    appear once, not twice."""
    vroot = tmp_path / "ventures"
    (vroot / "active").mkdir(parents=True)
    (vroot / "active" / "acme.md").write_text(
        "---\nid: acme\ntitle: acme\nstage: active\npriority: low\n---\n", encoding="utf-8")
    pdir = vroot / "acme" / "projects" / "solo"
    pdir.mkdir(parents=True)
    (pdir / "project.md").write_text(
        "---\nslug: solo\nname: Solo\nventure: acme\n---\n", encoding="utf-8")
    d = ventures_detail.venture("acme", ventures_root=vroot, backlog_dir=tmp_path)
    assert [p["slug"] for p in d["projects"]] == ["solo"]


def test_venture_detail_not_found(tmp_path: Path):
    vroot, bl = _mk_full_store(tmp_path)
    assert ventures_detail.venture("nope", ventures_root=vroot, backlog_dir=bl) == {"error": "not found", "slug": "nope"}


def test_milestone_detail(tmp_path: Path):
    vroot, bl = _mk_full_store(tmp_path)
    d = ventures_detail.milestone("bcrg", "ms1", ventures_root=vroot, backlog_dir=bl)
    assert d["title"] == "Phase 2"
    assert d["venture"] == "bcrg"
    assert "tasks" in d


import http.client, threading, json as _json


def test_detail_routes_served(tmp_path: Path):
    vroot, bl = _mk_full_store(tmp_path)
    import server
    kernel = server.build_kernel(port=0, data_root=vroot)
    srv = kernel.build_server()
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    conn = http.client.HTTPConnection("127.0.0.1", port)
    conn.request("GET", "/api/venture/bcrg")
    r = conn.getresponse(); assert r.status == 200
    body = _json.loads(r.read()); assert body["title"] == "BCRG"
    conn.request("GET", "/api/milestone/bcrg/ms1")
    assert conn.getresponse().status == 200
    conn.request("POST", "/api/venture/bcrg")
    assert conn.getresponse().status == 405


def test_real_venture_detail_task_parity():
    import subprocess
    vroot = Path.home()/".claude"/"local"/"ventures"
    if not (vroot/"active").is_dir():
        import pytest; pytest.skip("no real store")
    d = ventures_detail.venture("bcrg", ventures_root=vroot)
    if d.get("error"):
        import pytest; pytest.skip("bcrg absent")
    bl = Path.home()/".claude"/"local"/"backlog"
    grep = subprocess.run(["bash","-c", f"grep -lE '^venture: bcrg$' {bl}/*.md 2>/dev/null | wc -l"], capture_output=True, text=True)
    venture_field_count = int(grep.stdout.strip() or 0)
    assert len(d["tasks"]) >= venture_field_count


def test_project_get_rejects_traversal(tmp_path: Path):
    vroot = _mk_projects(tmp_path)  # creates vroot/project-mirror/projects/cognitive-engine.md
    # write a sensitive file 2 levels above projects dir (i.e. at vroot level) — this is
    # exactly where "../../SECRET" resolves from inside the projects/ dir
    (vroot / "SECRET.md").write_text("---\ntop: secret\n---\nleak me\n")
    for evil in ["../../SECRET", "../../../../etc/hostname", "..%2f..%2fSECRET", "/etc/passwd", "foo/bar"]:
        assert ventures_projects.get(evil, ventures_root=vroot) is None, f"traversal not blocked: {evil}"
    # legit slug still works
    assert ventures_projects.get("cognitive-engine", ventures_root=vroot) is not None


def test_milestone_join_requires_matching_venture(tmp_path: Path):
    d = tmp_path / "backlog"; d.mkdir()
    (d / "a.md").write_text("---\nid: 10\ntitle: Mine\nstatus: To Do\npriority: high\nparent_id: bcrg.proj.ms1\nparent_type: milestone\n---\n")
    (d / "b.md").write_text("---\nid: 11\ntitle: Theirs\nstatus: To Do\npriority: high\nparent_id: regenai.proj.ms1\nparent_type: milestone\n---\n")
    tasks = ventures_backlog.tasks_for("bcrg", milestone="ms1", backlog_dir=d)
    assert [t["title"] for t in tasks] == ["Mine"]  # NOT "Theirs"


def test_backlog_cache_invalidates_on_change(tmp_path: Path):
    d = tmp_path / "backlog"; d.mkdir()
    (d / "t1.md").write_text("---\nid: 1\ntitle: A\nstatus: To Do\npriority: high\nventure: bcrg\n---\n")
    r1 = ventures_backlog.tasks_for("bcrg", backlog_dir=d)
    assert [t["title"] for t in r1] == ["A"]
    # add a file -> cache must invalidate and pick it up
    (d / "t2.md").write_text("---\nid: 2\ntitle: B\nstatus: To Do\npriority: critical\nventure: bcrg\n---\n")
    r2 = ventures_backlog.tasks_for("bcrg", backlog_dir=d)
    assert [t["title"] for t in r2] == ["B", "A"]  # critical sorts first


def test_backlog_cache_no_parent_id_leak(tmp_path: Path):
    # cached entries must NOT expose internal _parent_id in returned summaries
    d = tmp_path / "backlog"; d.mkdir()
    (d / "t.md").write_text("---\nid: 9\ntitle: X\nstatus: To Do\npriority: low\nparent_id: bcrg.p.m\nparent_type: milestone\n---\n")
    out = ventures_backlog.tasks_for("bcrg", backlog_dir=d)
    assert out and all(not k.startswith("_") for k in out[0].keys())


# --- VenturesAccessor parse-cache regression tests (perf bug fix) ----------
import ventures_accessor  # noqa: E402


def _mk_ventures(tmp_path: Path) -> Path:
    vroot = tmp_path / "ventures"
    (vroot / "active").mkdir(parents=True)
    (vroot / "exploring").mkdir(parents=True)
    (vroot / "active" / "alpha.md").write_text(
        "---\nid: alpha\ntitle: Alpha\nstage: active\npriority: high\n"
        "deadlines:\n  - date: \"2026-01-01\"\n    label: old\n    type: hard\n---\nbody\n"
    )
    (vroot / "exploring" / "beta.md").write_text(
        "---\nid: beta\ntitle: Beta\nstage: exploring\npriority: low\n---\nbody\n"
    )
    return vroot


def test_detail_does_not_reparse_on_repeated_calls(tmp_path: Path, monkeypatch):
    """After the first parse pass, repeated list()/detail() calls trigger NO
    further _parse calls while the mtime-signature is unchanged."""
    vroot = _mk_ventures(tmp_path)
    acc = ventures_accessor.VenturesAccessor(data_root=vroot, today=date(2026, 6, 1))

    parse_calls = {"n": 0}
    orig_parse = acc._parse

    def counting_parse(lifecycle, md):
        parse_calls["n"] += 1
        return orig_parse(lifecycle, md)

    monkeypatch.setattr(acc, "_parse", counting_parse)

    # first call parses each file exactly once (2 files)
    acc.list({})
    assert parse_calls["n"] == 2

    # subsequent calls must NOT re-parse (signature unchanged)
    for _ in range(10):
        acc.detail("alpha")
        acc.detail("beta")
        acc.list({})
        acc.stats()
    assert parse_calls["n"] == 2  # still only the original pass


def test_detail_returns_correct_record_from_cache(tmp_path: Path):
    vroot = _mk_ventures(tmp_path)
    acc = ventures_accessor.VenturesAccessor(data_root=vroot, today=date(2026, 6, 1))
    acc.list({})  # warm cache
    d = acc.detail("alpha")
    assert d["title"] == "Alpha"
    assert d["lifecycle"] == "active"
    assert d["overdue_count"] == 1
    # internal _-prefixed keys stripped at the boundary
    assert all(not k.startswith("_") for k in d.keys())
    assert acc.detail("nope") == {"error": "not found", "slug": "nope"}


def test_accessor_cache_invalidates_on_mtime_change(tmp_path: Path, monkeypatch):
    """Touching a fixture file changes the signature -> next call re-parses."""
    vroot = _mk_ventures(tmp_path)
    acc = ventures_accessor.VenturesAccessor(data_root=vroot, today=date(2026, 6, 1))

    parse_calls = {"n": 0}
    orig_parse = acc._parse

    def counting_parse(lifecycle, md):
        parse_calls["n"] += 1
        return orig_parse(lifecycle, md)

    monkeypatch.setattr(acc, "_parse", counting_parse)

    acc.list({})
    assert parse_calls["n"] == 2

    # mutate a file's content + bump mtime
    import os
    f = vroot / "exploring" / "beta.md"
    f.write_text(
        "---\nid: beta\ntitle: Beta RENAMED\nstage: exploring\npriority: low\n---\nbody\n"
    )
    os.utime(f, ns=(2_000_000_000_000_000_000, 2_000_000_000_000_000_000))

    # next call re-parses (signature changed) and reflects the new content
    out = acc.detail("beta")
    assert out["title"] == "Beta RENAMED"
    assert parse_calls["n"] == 4  # full re-parse pass of both files


def test_inline_project_resolves_through_project_detail_route(tmp_path: Path):
    vroot = tmp_path / "ventures"
    (vroot / "active").mkdir(parents=True)
    (vroot / "active" / "legion.md").write_text(
        "---\nid: legion\ntitle: Legion\nprojects:\n"
        "  - id: legion-platform\n    title: Legion Platform\n    objective: Build the substrate.\n---\n"
    )
    backlog = tmp_path / "backlog"; backlog.mkdir()
    out = ventures_detail.project("legion-platform", ventures_root=vroot, backlog_dir=backlog)
    assert out["venture"] == "legion"
    assert out["title"] == "Legion Platform"
    assert out["tasks"] == []
