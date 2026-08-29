# web/tests/test_apps.py
from __future__ import annotations
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import ventures_apps


def _app(vroot: Path, venture: str, slug: str, body: str) -> Path:
    d = vroot / venture / "apps" / slug
    d.mkdir(parents=True)
    p = d / "app.md"
    p.write_text(body)
    return p


GOOD = """---
slug: living-library
name: Living Library
venture: indigenomics-ai
kind: web
stage: active
repo:
  path: ~/Workspace/IndigenomicsAI
  remote: indigenomicsxyz/IndigenomicsAI
environments:
  - name: dev
    url: https://dev.indigenomics.xyz
    healthz: /healthz
  - name: staging
    url: https://staging.indigenomics.xyz
    controllable: false
depends_on: [neo4j]
---
Body notes here.
"""


def test_list_for_reads_manifests_sorted(tmp_path: Path):
    vroot = tmp_path / "ventures"
    _app(vroot, "indigenomics-ai", "zeta", GOOD.replace("living-library", "zeta"))
    _app(vroot, "indigenomics-ai", "living-library", GOOD)
    apps = ventures_apps.list_for("indigenomics-ai", ventures_root=vroot)
    assert [a["slug"] for a in apps] == ["living-library", "zeta"]
    assert apps[0]["repo"]["remote"] == "indigenomicsxyz/IndigenomicsAI"
    assert apps[0]["environments"][1]["controllable"] is False
    assert apps[0]["notes"] == "Body notes here."
    assert apps[0]["file_path"].endswith("apps/living-library/app.md")


def test_list_for_missing_venture_is_empty(tmp_path: Path):
    assert ventures_apps.list_for("nope", ventures_root=tmp_path / "ventures") == []


def test_get_returns_one_or_none(tmp_path: Path):
    vroot = tmp_path / "ventures"
    _app(vroot, "v", "a", GOOD)
    assert ventures_apps.get("v", "a", ventures_root=vroot)["name"] == "Living Library"
    assert ventures_apps.get("v", "b", ventures_root=vroot) is None


def test_malformed_manifest_is_skipped_and_reported(tmp_path: Path):
    vroot = tmp_path / "ventures"
    _app(vroot, "v", "good", GOOD)
    _app(vroot, "v", "bad", "---\nslug: [unclosed\n---\n")
    apps = ventures_apps.list_for("v", ventures_root=vroot)
    assert [a["slug"] for a in apps] == ["good"]
    assert ventures_apps.errors_for("v", ventures_root=vroot) == ["bad/app.md"]


def test_cache_invalidates_on_edit(tmp_path: Path):
    vroot = tmp_path / "ventures"
    p = _app(vroot, "v", "a", GOOD)
    assert ventures_apps.list_for("v", ventures_root=vroot)[0]["stage"] == "active"
    p.write_text(GOOD.replace("stage: active", "stage: paused"))
    import os
    os.utime(p, None)
    assert ventures_apps.list_for("v", ventures_root=vroot)[0]["stage"] == "paused"
