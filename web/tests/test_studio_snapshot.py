from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import studio_snapshot as S


def test_write_is_atomic_and_readable(tmp_path: Path):
    p = tmp_path / "runtime" / "studio-snapshot.json"
    out = S.write_snapshot({"generated_at": "2026-08-29T17:00:00+00:00", "interval_s": 60, "apps": {}}, path=p)
    assert out == p and p.is_file()
    assert [q.name for q in p.parent.iterdir()] == [p.name]  # no temp file left behind
    assert json.loads(p.read_text())["interval_s"] == 60


def test_read_fresh_and_stale(tmp_path: Path):
    p = tmp_path / "s.json"
    gen = datetime(2026, 8, 29, 17, 0, tzinfo=timezone.utc)
    S.write_snapshot({"generated_at": gen.isoformat(), "interval_s": 60, "apps": {}}, path=p)
    fresh = S.read_snapshot(p, now=gen + timedelta(seconds=90))
    assert fresh["present"] is True and fresh["stale"] is False and abs(fresh["age_s"] - 90) < 1
    old = S.read_snapshot(p, now=gen + timedelta(seconds=181))
    assert old["stale"] is True


def test_read_missing_and_malformed(tmp_path: Path):
    missing = S.read_snapshot(tmp_path / "nope.json")
    assert missing == {"present": False, "data": None, "generated_at": None, "age_s": None, "stale": True, "interval_s": 60}
    bad = tmp_path / "bad.json"; bad.write_text("{not json")
    r = S.read_snapshot(bad)
    assert r["present"] is False and r["stale"] is True and "error" in r


def test_is_stale_rule():
    assert S.is_stale(None, 60) is True
    assert S.is_stale(180, 60) is False
    assert S.is_stale(180.1, 60) is True
