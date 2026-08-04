# web/ventures_contract.py
"""The schema contract: what the store writes vs what the page reads.

This module exists because the venture detail page shipped for months rendering
a subset of the record while looking complete. Three fields were silently
dropped (`deadlines`), read from a key nothing writes (`financial.revenue_to_date`),
or joined from the wrong directory (`projects`). The test suite was green
throughout, because its fixtures were written to match the renderer rather than
the store.

So the contract is checked in BOTH directions:

  orphan writers  a key that exists in real venture files and that no band
                  declares a read for. Something is being written and never
                  shown. This is the `deadlines` failure.

  orphan readers  a path a band declares and that no venture file contains.
                  Something is being read that nothing writes. This is the
                  `financial.revenue_to_date` failure.

The declarations live in `venture_bands.json`, which is ALSO what the frontend
iterates to render. That is deliberate: a declaration the page does not use is
a comment, and comments rot. Bands whose renderer is `custom` are the exception
and are reported separately, because for those the declaration is not
load-bearing and the contract can only take their word for it.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import yaml

HERE = Path(__file__).resolve().parent
MANIFEST_PATH = HERE / "venture_bands.json"

_LIFECYCLES = ("seed", "exploring", "active", "sustaining", "dormant", "harvesting")
_MAX_DEPTH = 3


# --------------------------------------------------------------------------
# What the store actually writes
# --------------------------------------------------------------------------

def _flatten(value: Any, prefix: str, out: dict[str, int], depth: int = 1) -> None:
    """Flatten frontmatter into dotted paths.

    dict          -> prefix.key
    list of dicts -> prefix[].key
    list of others -> prefix[]
    Beyond _MAX_DEPTH the subtree is recorded as the prefix itself and not
    descended, so an arbitrarily nested blob cannot explode the contract.
    """
    if isinstance(value, dict):
        if depth > _MAX_DEPTH:
            out[prefix] = out.get(prefix, 0) + 1
            return
        for k, v in value.items():
            _flatten(v, f"{prefix}.{k}" if prefix else str(k), out, depth + 1)
        return
    if isinstance(value, list):
        if not value:
            out[prefix] = out.get(prefix, 0) + 1
            return
        if any(isinstance(x, dict) for x in value):
            if depth > _MAX_DEPTH:
                out[prefix] = out.get(prefix, 0) + 1
                return
            for item in value:
                if isinstance(item, dict):
                    for k, v in item.items():
                        _flatten(v, f"{prefix}[].{k}", out, depth + 1)
            return
        out[f"{prefix}[]"] = out.get(f"{prefix}[]", 0) + 1
        return
    out[prefix] = out.get(prefix, 0) + 1


def _frontmatter(md: Path) -> dict[str, Any] | None:
    try:
        text = md.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        data = yaml.safe_load(parts[1])
    except Exception:  # noqa: BLE001 -- a malformed file is data, not a crash
        return None
    return data if isinstance(data, dict) else None


def venture_files(ventures_root: Path) -> Iterable[Path]:
    for lifecycle in _LIFECYCLES:
        d = ventures_root / lifecycle
        if not d.is_dir():
            continue
        yield from sorted(d.glob("*.md"))


def observed_paths(ventures_root: Path) -> dict[str, int]:
    """Every dotted path present in any venture file, with a venture count."""
    counts: dict[str, int] = {}
    for md in venture_files(ventures_root):
        fm = _frontmatter(md)
        if not fm:
            continue
        per_file: dict[str, int] = {}
        _flatten(fm, "", per_file)
        for path in per_file:
            counts[path] = counts.get(path, 0) + 1
    return counts


def unparseable(ventures_root: Path) -> list[str]:
    """Venture files that exist but yield no frontmatter.

    These are the files the accessor silently skips to stderr. Surfacing them
    here means a malformed venture becomes visible instead of just vanishing
    from the portfolio.
    """
    bad = []
    for md in venture_files(ventures_root):
        if _frontmatter(md) is None:
            bad.append(md.name)
    return bad


# --------------------------------------------------------------------------
# What the page declares it reads
# --------------------------------------------------------------------------

def load_manifest(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or MANIFEST_PATH).read_text(encoding="utf-8"))


def declared_reads(manifest: dict[str, Any]) -> dict[str, str]:
    """path -> band key, for every read any band declares."""
    out: dict[str, str] = {}
    for band in manifest["bands"]:
        for path in band.get("reads", []):
            out[path] = band["key"]
    return out


def _tail_prefixes(manifest: dict[str, Any]) -> list[tuple[str, str]]:
    """(prefix, band key) for bands that render an open-ended remainder.

    A band declaring `"tail": "financial.*"` claims everything under
    `financial.` that it does not name explicitly. That is how a venture can
    invent `financial.cadcad_grant` without the contract going red and without
    the value being dropped.

    The bare `"*"` catch-all is excluded here on purpose; see `_catch_all`.
    """
    out = []
    for band in manifest["bands"]:
        tail = band.get("tail")
        if tail and tail.endswith("*") and tail != "*":
            out.append((tail[:-1], band["key"]))
    return out


def _catch_all(manifest: dict[str, Any]) -> str | None:
    """The band declaring `"tail": "*"`, if any.

    A catch-all guarantees no field is ever dropped from the page, which is the
    behaviour we want for the reader. But it would also make `orphan_writers`
    permanently empty, which would quietly disable the very check this module
    exists for. So paths that ONLY the catch-all claims are reported separately
    as `uncategorized`: visible, counted, and not a pass.
    """
    for band in manifest["bands"]:
        if band.get("tail") == "*":
            return band["key"]
    return None


def _container_covered(path: str, reads: dict[str, str]) -> bool:
    """True when `path` is a container whose CONTENTS are declared.

    `deadlines: []` flattens to the bare path `deadlines`, while a populated
    one flattens to `deadlines[].date` and friends. An empty list is a venture
    with none of that thing, not an unread field, so the container counts as
    covered whenever anything beneath it is read.
    """
    return any(
        r == f"{path}[]" or r.startswith(f"{path}[].") or r.startswith(f"{path}.")
        for r in reads
    )


def _ignored(manifest: dict[str, Any]) -> dict[str, str]:
    return dict(manifest.get("ignored", {}))


# --------------------------------------------------------------------------
# The two directions
# --------------------------------------------------------------------------

def classify(ventures_root: Path, manifest: dict[str, Any]) -> dict[str, dict[str, int]]:
    """Split every observed store path into covered / uncategorized / orphaned.

    covered        a band names it, a scoped tail claims it, its contents are
                   declared, or it is explicitly ignored with a reason
    uncategorized  only the `"*"` catch-all claims it: it renders, but nobody
                   has decided where it belongs
    orphaned       nothing claims it at all -- written and never shown
    """
    reads = declared_reads(manifest)
    tails = _tail_prefixes(manifest)
    ignored = _ignored(manifest)
    has_catch_all = _catch_all(manifest) is not None

    covered: dict[str, int] = {}
    uncategorized: dict[str, int] = {}
    orphaned: dict[str, int] = {}
    for path, count in sorted(observed_paths(ventures_root).items()):
        if (
            path in reads
            or path in ignored
            or any(path.startswith(prefix) for prefix, _ in tails)
            or _container_covered(path, reads)
        ):
            covered[path] = count
        elif has_catch_all:
            uncategorized[path] = count
        else:
            orphaned[path] = count
    return {"covered": covered, "uncategorized": uncategorized, "orphaned": orphaned}


def orphan_writers(ventures_root: Path, manifest: dict[str, Any]) -> dict[str, int]:
    """Store paths nothing claims. A non-empty result is a contract failure."""
    return classify(ventures_root, manifest)["orphaned"]


def orphan_readers(ventures_root: Path, manifest: dict[str, Any]) -> dict[str, str]:
    """Declared reads that appear in zero venture files.

    A path present in no venture is either a typo, a field that was renamed, or
    a renderer written against an imagined schema. All three are defects.
    """
    observed = observed_paths(ventures_root)
    out: dict[str, str] = {}
    for path, band in sorted(declared_reads(manifest).items()):
        if observed.get(path, 0) == 0:
            out[path] = band
    return out


def non_load_bearing(manifest: dict[str, Any]) -> list[str]:
    """Bands whose renderer is custom, so their declarations are unverified.

    Reported, never silently tolerated: this is the honest accounting of how
    much of the contract is actually enforced by rendering.
    """
    return [b["key"] for b in manifest["bands"] if b.get("renderer") == "custom"]


def report(ventures_root: Path, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    """One structured verdict, used by the tests and by /healthz."""
    m = manifest or load_manifest()
    split = classify(ventures_root, m)
    readers = orphan_readers(ventures_root, m)
    bad = unparseable(ventures_root)
    return {
        "ventures_scanned": sum(1 for _ in venture_files(ventures_root)),
        "paths_observed": sum(len(v) for v in split.values()),
        "covered": len(split["covered"]),
        "orphan_writers": split["orphaned"],
        "uncategorized": split["uncategorized"],
        "orphan_readers": readers,
        "unparseable": bad,
        "non_load_bearing_bands": non_load_bearing(m),
        "ok": not split["orphaned"] and not readers and not bad,
    }
