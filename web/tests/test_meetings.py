# web/tests/test_meetings.py
from __future__ import annotations
import sqlite3
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import ventures_meetings

_SCHEMA = """
CREATE TABLE meetings (id TEXT PRIMARY KEY, uuid TEXT NOT NULL UNIQUE, title TEXT NOT NULL, date TEXT NOT NULL, start_time TEXT, duration_seconds INTEGER, source TEXT NOT NULL DEFAULT 'unknown', status TEXT NOT NULL DEFAULT 'pending', transcript_id TEXT, venture_slugs TEXT DEFAULT '[]', agenda TEXT, summary TEXT, tags TEXT DEFAULT '[]');
CREATE TABLE meeting_decisions (id TEXT PRIMARY KEY, meeting_id TEXT NOT NULL, text TEXT NOT NULL, decision_type TEXT DEFAULT 'explicit', reversibility TEXT DEFAULT 'unknown', evidence_quote TEXT NOT NULL, venture_slug TEXT);
CREATE TABLE meeting_risks (id TEXT PRIMARY KEY, meeting_id TEXT NOT NULL, text TEXT NOT NULL, severity TEXT DEFAULT 'medium', likelihood TEXT DEFAULT 'unknown', mitigation TEXT, evidence_quote TEXT NOT NULL, venture_slug TEXT);
CREATE TABLE meeting_action_items (id TEXT PRIMARY KEY, meeting_id TEXT NOT NULL, text TEXT NOT NULL, assignee TEXT, deadline TEXT, priority TEXT DEFAULT 'medium', status TEXT DEFAULT 'open', evidence_quote TEXT NOT NULL, backlog_task_id TEXT);
CREATE VIRTUAL TABLE meetings_fts USING fts5(title, summary, agenda, content=meetings, content_rowid=rowid);
CREATE TRIGGER meetings_fts_insert AFTER INSERT ON meetings BEGIN INSERT INTO meetings_fts(rowid, title, summary, agenda) VALUES (new.rowid, new.title, new.summary, new.agenda); END;
"""


def _db(tmp_path: Path) -> Path:
    p = tmp_path / "meetings.db"
    c = sqlite3.connect(p)
    c.executescript(_SCHEMA)
    rows = [
        ("m1", "u1", "Capstone check-in", "2026-08-20", "14:00", 3600, "obs", "processed", "tx_a", '["indigenomics-ai"]', "agenda a", "We agreed on the poster.", '["capstone"]'),
        ("m2", "u2", "TELUS sync", "2026-08-05", "10:00", 1800, "google_meet", "processed", "", '["indigenomics-ai","regen-ai"]', None, "Grafana handoff.", "[]"),
        ("m3", "u3", "Avalanche M2", "2026-08-14", None, None, "obs", "pending", None, '["bcrg-avalanche"]', None, None, "[]"),
        ("m4", "u4", "Untagged call", "2026-08-01", None, None, "unknown", "pending", None, "[]", None, None, "[]"),
    ]
    c.executemany("INSERT INTO meetings(id,uuid,title,date,start_time,duration_seconds,source,status,transcript_id,venture_slugs,agenda,summary,tags) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    c.execute("INSERT INTO meeting_decisions VALUES ('d1','m1','Ship the poster','explicit','easy','we ship it','indigenomics-ai')")
    c.execute("INSERT INTO meeting_risks VALUES ('r1','m1','Deadline slip','high','likely','start early','might slip','indigenomics-ai')")
    c.execute("INSERT INTO meeting_action_items VALUES ('a1','m1','Print poster','shawn','2026-08-25','high','open','print it',NULL)")
    c.execute("INSERT INTO meeting_action_items VALUES ('a2','m1','Book room','jack',NULL,'medium','done','book it','412')")
    c.commit(); c.close()
    return p


def test_slug_matches():
    m = ventures_meetings.slug_matches
    assert m("indigenomics-ai", "indigenomics-ai") is True
    assert m("bcrg-avalanche", "bcrg-avalanche-foundation") is True
    assert m("bcrg-avalanche-foundation", "bcrg-avalanche") is False
    assert m("indigenomics-a", "indigenomics-ai") is False


def test_catalogue_matches_venture_newest_first(tmp_path: Path):
    doc = ventures_meetings.catalogue("indigenomics-ai", db_path=_db(tmp_path))
    assert doc["available"] is True and doc["fts"] is True
    assert [m["id"] for m in doc["items"]] == ["m1", "m2"]
    assert doc["count"] == 2 and doc["untagged"] == 1
    m1 = doc["items"][0]
    assert m1["transcript_href"] == "/transcripts/?view=transcript&tx=tx_a"
    assert doc["items"][1]["transcript_href"] is None
    assert m1["duration_min"] == 60 and m1["tags"] == ["capstone"]
    assert m1["counts"] == {"decisions": 1, "risks": 1, "actions_open": 1, "actions_total": 2}
    assert m1["decisions"][0]["text"] == "Ship the poster" and m1["decisions"][0]["quote"] == "we ship it"
    assert m1["risks"][0]["severity"] == "high"
    assert {a["id"]: a["status"] for a in m1["actions"]} == {"a1": "open", "a2": "done"}
    assert m1["actions"][1]["backlog_task_id"] == "412"
    assert doc["aggregates"] == {"meetings": 2, "decisions": 1, "risks": 1, "actions_open": 1}


def test_dash_prefix_alias(tmp_path: Path):
    doc = ventures_meetings.catalogue("bcrg-avalanche-foundation", db_path=_db(tmp_path))
    assert [m["id"] for m in doc["items"]] == ["m3"]


def test_fts_query_and_sanitising(tmp_path: Path):
    p = _db(tmp_path)
    doc = ventures_meetings.catalogue("indigenomics-ai", db_path=p, q="grafana")
    assert [m["id"] for m in doc["items"]] == ["m2"] and doc["fts"] is True
    doc = ventures_meetings.catalogue("indigenomics-ai", db_path=p, q='"poster')
    assert [m["id"] for m in doc["items"]] == ["m1"]
    doc = ventures_meetings.catalogue("indigenomics-ai", db_path=p, q="nothing-here-xyz")
    assert doc["items"] == [] and doc["count"] == 0
    doc = ventures_meetings.catalogue("indigenomics-ai", db_path=p, q="poster grafana")
    assert doc["items"] == []
    doc = ventures_meetings.catalogue("indigenomics-ai", db_path=p, q="capstone poster")
    assert [m["id"] for m in doc["items"]] == ["m1"]


def test_like_fallback_when_fts_missing(tmp_path: Path):
    p = _db(tmp_path)
    c = sqlite3.connect(p); c.execute("DROP TABLE meetings_fts"); c.commit(); c.close()
    doc = ventures_meetings.catalogue("indigenomics-ai", db_path=p, q="grafana")
    assert doc["fts"] is False and [m["id"] for m in doc["items"]] == ["m2"]


def test_missing_db_is_unavailable(tmp_path: Path):
    doc = ventures_meetings.catalogue("indigenomics-ai", db_path=tmp_path / "nope.db")
    assert doc == {"available": False, "reason": "meetings.db not found", "items": [], "count": 0, "query": "", "fts": False,
                   "aggregates": {"meetings": 0, "decisions": 0, "risks": 0, "actions_open": 0}, "untagged": 0}


def test_limit_and_count(tmp_path: Path):
    doc = ventures_meetings.catalogue("indigenomics-ai", db_path=_db(tmp_path), limit=1)
    assert len(doc["items"]) == 1 and doc["count"] == 2 and doc["aggregates"]["meetings"] == 2
