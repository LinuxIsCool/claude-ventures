# web/tests/test_studio_page.py
"""The Studio tab is opt-in markup in index.html plus its own module file.
There is no JS runner here, so assert the served bytes carry every hook the
page needs. Each assertion names a real failure mode seen in this hub:
a missing script tag, a tab not in the whitelist, a class purged from Tailwind."""
from __future__ import annotations
from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "static"


def test_index_wires_studio_tab():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert '<script src="static/studio.js"></script>' in html
    assert '["studio","Studio"]' in html
    assert '"studio"' in html.split("const module =", 1)[1].split("\n", 1)[0]
    assert 'VenturesStudio.mount(' in html
    assert '.studio-grid' in html and '.studio-table' in html
    assert '.studio-network' in html


def test_studio_module_defines_mount_and_sections():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "window.VenturesStudio" in js
    assert "mount(" in js
    for needle in ("Library", "Domains", "studio-grid", "studio-table", "/studio"):
        assert needle in js
    assert "safeHref(" in js
    assert "safeHref(e.url)" in js and "safeHref(d.url)" in js
    for needle in ("Network", "/network", "loadVendor(", "cytoscape(", "critical_path", "studio-network", "renderFallbackList("):
        assert needle in js
    assert "—" not in js  # no em-dashes in copy
