# web/tests/test_vendor_manifest.py
"""The vendor bytes are not in git; the manifest is. When the bytes are present
they must match the manifest, and the manifest must be well formed."""
from __future__ import annotations
import hashlib, json
from pathlib import Path

VENDOR = Path(__file__).resolve().parent.parent / "static" / "vendor"


def test_manifest_well_formed():
    m = json.loads((VENDOR / "MANIFEST.json").read_text())
    names = [f["name"] for f in m["files"]]
    assert names == ["cytoscape.min.js", "dagre.min.js", "cytoscape-dagre.js"]
    for f in m["files"]:
        assert f["url"].startswith("https://") and len(f["sha256"]) == 64 and f["bytes"] > 0


def test_present_bytes_match_manifest():
    m = json.loads((VENDOR / "MANIFEST.json").read_text())
    for f in m["files"]:
        p = VENDOR / f["name"]
        if p.exists():
            assert hashlib.sha256(p.read_bytes()).hexdigest() == f["sha256"], f["name"]
            assert p.stat().st_size == f["bytes"]
