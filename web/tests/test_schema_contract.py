"""The schema contract, checked in both directions.

Why both: the detail page shipped for months dropping `deadlines` (written,
never read) while reading `financial.revenue_to_date` (read, never written).
A one-directional check catches exactly one of those.

Why against the real store: the suite that was green throughout the bug used a
fixture asserting `financial.revenue_to_date == 50000`. A hand-written fixture
is only as truthful as its author. So the hermetic tests below cover the
LOGIC, and the real-store tests cover REALITY, and neither substitutes for the
other.

Skips here are loud on purpose. A test that quietly skips when its data source
moves reports success forever, which is the failure mode this whole module
exists to prevent.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import ventures_contract as contract  # noqa: E402

REAL_STORE = Path.home() / ".claude" / "local" / "ventures"


def _real_store_or_skip() -> Path:
    if not (REAL_STORE / "active").is_dir():
        pytest.skip(
            f"LOUD SKIP: real venture store not found at {REAL_STORE}. "
            "The contract is unverified against reality on this machine. "
            "This is not a pass."
        )
    return REAL_STORE


# ---------------------------------------------------------------- hermetic --

def _mini_store(tmp_path: Path) -> Path:
    root = tmp_path / "ventures"
    (root / "active").mkdir(parents=True)
    (root / "active" / "alpha.md").write_text(
        "---\n"
        "id: alpha\ntitle: Alpha\nstage: active\npriority: high\n"
        "deadlines:\n  - date: 2026-01-01\n    label: Ship\n"
        "financial:\n  status: contracted\n  invented_key: 7\n"
        "---\nbody\n",
        encoding="utf-8",
    )
    return root


def _mini_manifest(**over) -> dict:
    m = {
        "ignored": {"id": "routing slug"},
        "bands": [
            {"key": "identity", "renderer": "kv", "reads": ["title", "stage", "priority"]},
            {"key": "deadlines", "renderer": "table",
             "reads": ["deadlines[].date", "deadlines[].label"]},
            {"key": "financial", "renderer": "kv", "tail": "financial.*",
             "reads": ["financial.status"]},
        ],
    }
    m.update(over)
    return m


def test_flatten_shapes(tmp_path: Path):
    obs = contract.observed_paths(_mini_store(tmp_path))
    assert obs["title"] == 1
    assert obs["deadlines[].date"] == 1
    assert obs["financial.status"] == 1
    assert obs["financial.invented_key"] == 1


def test_scoped_tail_covers_unnamed_keys(tmp_path: Path):
    root = _mini_store(tmp_path)
    split = contract.classify(root, _mini_manifest())
    # financial.* claims invented_key without it being named
    assert "financial.invented_key" in split["covered"]
    assert not split["orphaned"]


def test_orphan_writer_is_detected(tmp_path: Path):
    root = _mini_store(tmp_path)
    m = _mini_manifest()
    m["bands"] = [b for b in m["bands"] if b["key"] != "deadlines"]
    orphans = contract.orphan_writers(root, m)
    assert "deadlines[].date" in orphans, "a written-but-unread field must be caught"


def test_orphan_reader_is_detected(tmp_path: Path):
    root = _mini_store(tmp_path)
    m = _mini_manifest()
    m["bands"][0]["reads"].append("financial.revenue_to_date")
    readers = contract.orphan_readers(root, m)
    assert "financial.revenue_to_date" in readers, (
        "a read-but-never-written field must be caught: this is the exact "
        "defect that shipped"
    )


def test_container_with_empty_list_is_not_an_orphan(tmp_path: Path):
    root = tmp_path / "ventures"
    (root / "active").mkdir(parents=True)
    (root / "active" / "b.md").write_text(
        "---\nid: b\ntitle: B\nstage: active\npriority: low\ndeadlines: []\n---\n",
        encoding="utf-8",
    )
    split = contract.classify(root, _mini_manifest())
    assert "deadlines" in split["covered"], "an empty list is 'none of these', not 'unread'"


def test_catch_all_reports_uncategorized_rather_than_covered(tmp_path: Path):
    root = _mini_store(tmp_path)
    m = _mini_manifest()
    m["bands"] = [b for b in m["bands"] if b["key"] != "deadlines"]
    m["bands"].append({"key": "other", "renderer": "kv", "tail": "*", "reads": []})
    split = contract.classify(root, m)
    assert not split["orphaned"], "a catch-all means nothing is dropped"
    assert "deadlines[].date" in split["uncategorized"], (
        "but a catch-all must NOT silently mark drift as covered"
    )


def test_unparseable_files_are_surfaced(tmp_path: Path):
    root = _mini_store(tmp_path)
    (root / "active" / "broken.md").write_text("---\n: : not yaml :\n---\n", encoding="utf-8")
    assert "broken.md" in contract.unparseable(root)


# ------------------------------------------------------------- the real store --

def test_manifest_is_valid_json_and_well_formed():
    m = contract.load_manifest()
    assert m["bands"], "manifest must declare bands"
    keys = [b["key"] for b in m["bands"]]
    assert len(keys) == len(set(keys)), f"duplicate band keys: {keys}"
    for b in m["bands"]:
        assert "renderer" in b, f"band {b['key']} must declare a renderer"
        assert isinstance(b.get("reads", []), list)
    catch_alls = [b["key"] for b in m["bands"] if b.get("tail") == "*"]
    assert len(catch_alls) <= 1, f"at most one catch-all band, got {catch_alls}"


def test_no_orphan_writers_in_real_store():
    """Every field any venture writes is claimed by some band."""
    root = _real_store_or_skip()
    orphans = contract.orphan_writers(root, contract.load_manifest())
    assert not orphans, (
        "fields are written to the store and read by nothing:\n  "
        + "\n  ".join(f"{p} (in {n} ventures)" for p, n in orphans.items())
    )


def test_no_orphan_readers_in_real_store():
    """Every path the page declares exists in at least one venture."""
    root = _real_store_or_skip()
    readers = contract.orphan_readers(root, contract.load_manifest())
    assert not readers, (
        "the page declares reads for fields no venture has:\n  "
        + "\n  ".join(f"{p} (band {b})" for p, b in readers.items())
    )


def test_no_unparseable_ventures_in_real_store():
    root = _real_store_or_skip()
    bad = contract.unparseable(root)
    assert not bad, f"venture files that parse to nothing and vanish silently: {bad}"


def _custom_band_names(index_html: str) -> set[str]:
    """Names registered in the frontend's CUSTOM_BANDS object literal.

    Matches both shorthand methods (`identity(v) {`) and property assignment
    (`identity: fn`), scanning only the balanced body of the literal so an
    unrelated function elsewhere in the file cannot satisfy the contract.
    """
    start = index_html.find("const CUSTOM_BANDS")
    if start == -1:
        return set()
    brace = index_html.find("{", start)
    depth, i = 0, brace
    while i < len(index_html):
        if index_html[i] == "{":
            depth += 1
        elif index_html[i] == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    body = index_html[brace + 1:i]
    top_level, names, depth = [], set(), 0
    for line in body.splitlines():
        stripped = line.strip()
        if depth == 0:
            m = re.match(r"^(\w+)\s*[(:]", stripped)
            if m:
                names.add(m.group(1))
        depth += line.count("{") - line.count("}")
        top_level.append(depth)
    return names


def test_frontend_implements_every_declared_band():
    """The manifest must be load-bearing, not decorative.

    A band declared in venture_bands.json and not implemented by the frontend
    is a promise the page does not keep -- which is the whole defect class this
    contract exists to end. `custom` bands must have a named renderer function;
    generic bands must have their renderer kind implemented.
    """
    index = (HERE / "static" / "index.html").read_text(encoding="utf-8")
    m = contract.load_manifest()

    missing_generic = sorted(
        {b["renderer"] for b in m["bands"] if b["renderer"] != "custom"}
        - {kind for kind in ("kv", "table", "chips") if f'case "{kind}"' in index}
    )
    assert not missing_generic, (
        f"manifest uses generic renderers the frontend does not implement: {missing_generic}"
    )

    registered = _custom_band_names(index)
    missing_custom = [
        b["key"] for b in m["bands"]
        if b["renderer"] == "custom" and b["key"] not in registered
    ]
    assert not missing_custom, (
        f"bands declared with a custom renderer but not registered in "
        f"CUSTOM_BANDS: {missing_custom}"
    )

    assert "VENTURE_BANDS" in index or "venture_bands.json" in index, (
        "the frontend must consume the manifest; if it does not, the "
        "declarations are comments and this contract is theatre"
    )


def test_report_is_serialisable_for_healthz():
    root = _real_store_or_skip()
    rep = contract.report(root)
    json.dumps(rep)  # must survive the wire
    assert rep["ventures_scanned"] > 0
    assert "ok" in rep
