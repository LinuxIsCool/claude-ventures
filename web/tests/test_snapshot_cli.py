from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent.parent  # plugin dir
CLI_PATH = HERE / "scripts" / "ventures_snapshot.py"


def _load_cli():
    spec = importlib.util.spec_from_file_location("ventures_snapshot_cli", CLI_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_store(tmp_path: Path) -> tuple[Path, Path]:
    """Build a tiny ventures store + backlog dir, return (ventures_root, backlog_dir)."""
    vroot = tmp_path / "ventures"
    (vroot / "active").mkdir(parents=True)
    (vroot / "exploring").mkdir(parents=True)

    (vroot / "active" / "alpha.md").write_text(
        "---\n"
        "id: alpha\n"
        "title: Alpha Venture\n"
        "stage: active\n"
        "priority: critical\n"
        "milestones:\n"
        "  - id: ms1\n"
        "    title: Phase 1\n"
        "    status: complete\n"
        "    completed: true\n"
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


def test_cli_main_writes_one_row_and_prints_json(tmp_path: Path, capsys):
    vroot, bl = _make_store(tmp_path)
    out = tmp_path / "metrics" / "snapshots.jsonl"

    mod = _load_cli()
    rc = mod.main(
        ["--data-root", str(vroot), "--backlog-dir", str(bl), "--out", str(out)]
    )
    assert rc == 0

    # exactly one JSONL row on disk
    assert out.exists()
    lines = [ln for ln in out.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1

    # stdout parses as JSON with a date key
    captured = capsys.readouterr()
    parsed = json.loads(captured.out.strip())
    assert "date" in parsed
    assert parsed == json.loads(lines[0])
