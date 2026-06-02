# plugins/claude-ventures/web/ventures_accessor.py
"""VenturesAccessor — read-through to ~/.claude/local/ventures/.

Frontmatter contract (mirrors claude-ventures/src/store/):
  top-level: id, title, description, persona, type, stage, priority
  co_venturers: [{name, role}]
  deadlines:   [{date 'YYYY-MM-DD', label, type}]  <- overdue source
Lifecycle = parent dir (active|exploring|dormant|harvesting).
Overdue = deadline.date < today (no per-deadline done flag; matches
daily-brief OVERDUE semantics). No webapp DB. PyYAML parse; one malformed
file is skipped (logged to stderr), the rest still serve.
"""
from __future__ import annotations

import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

from claude_webui.healthz import healthz_response

NAMESPACE = "legion.claude-venture"

_HOME = Path.home()
_DATA_ROOT_DEFAULT = _HOME / ".claude" / "local" / "ventures"
_LIFECYCLES = ("seed", "exploring", "active", "sustaining", "dormant", "harvesting")


def _split_frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    data = yaml.safe_load(parts[1])
    return data if isinstance(data, dict) else {}


class VenturesAccessor:
    """Reads the ventures markdown store. Implements the Accessor protocol."""

    def __init__(self, data_root: Path | None = None, today: date | None = None):
        self.data_root = Path(data_root) if data_root else _DATA_ROOT_DEFAULT
        self._today = today or date.today()

    def _iter_files(self):
        for lifecycle in _LIFECYCLES:
            d = self.data_root / lifecycle
            if not d.is_dir():
                continue
            for md in sorted(d.glob("*.md")):
                yield lifecycle, md

    def _parse(self, lifecycle: str, md: Path) -> dict[str, Any] | None:
        try:
            fm = _split_frontmatter(md.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"[ventures-web] skip malformed {md}: {exc}", file=sys.stderr)
            return None
        if not fm:
            return None
        slug = str(fm.get("id") or md.stem)
        deadlines = fm.get("deadlines") or []
        if not isinstance(deadlines, list):
            deadlines = []
        deadlines = [d for d in deadlines if isinstance(d, dict)]
        # Normalize deadline label: the documented schema uses `description`,
        # while several live files use `label`. Carry a single `label` key so
        # detail() + stats() render consistently regardless of which the
        # author used.
        for d in deadlines:
            if not d.get("label"):
                d["label"] = d.get("description", "")
        overdue = (
            [] if lifecycle == "harvesting"
            else [d for d in deadlines if self._is_overdue(d)]
        )
        return {
            "slug": slug,
            "title": fm.get("title", slug),
            "description": fm.get("description", ""),
            "stage": fm.get("stage", lifecycle),
            "priority": fm.get("priority", "medium"),
            "lifecycle": lifecycle,
            "co_venturers": fm.get("co_venturers") or [],
            "deadlines": deadlines,
            "overdue_count": len(overdue),
            "_overdue": overdue,
            "milestones": (fm.get("milestones") if isinstance(fm.get("milestones"), list) else []),
            "financial": fm.get("financial") or {},
            "links": fm.get("links") or {},
            "related_ventures": fm.get("related_ventures") or [],
        }

    def _is_overdue(self, deadline: dict[str, Any]) -> bool:
        status = str(deadline.get("status", "")).strip().lower()
        if status in {"complete", "completed", "done"}:
            return False
        if "reached" in str(deadline.get("type", "")).strip().lower():
            return False
        raw = str(deadline.get("date", "")).strip()
        try:
            d = datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            return False
        return d < self._today

    def list(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        out = []
        for lifecycle, md in self._iter_files():
            v = self._parse(lifecycle, md)
            if v is None:
                continue
            out.append({k: v[k] for k in (
                "slug", "title", "stage", "priority", "lifecycle", "overdue_count"
            )})
        return out

    def detail(self, item_id: str) -> dict[str, Any]:
        for lifecycle, md in self._iter_files():
            v = self._parse(lifecycle, md)
            if v and v["slug"] == item_id:
                return {k: val for k, val in v.items() if not k.startswith("_")}
        return {"error": "not found", "slug": item_id}

    def stats(self) -> dict[str, Any]:
        by_lifecycle = {lc: 0 for lc in _LIFECYCLES}
        overdue: list[dict[str, Any]] = []
        for lifecycle, md in self._iter_files():
            v = self._parse(lifecycle, md)
            if v is None:
                continue
            by_lifecycle[lifecycle] += 1
            for d in v["_overdue"]:
                dt = datetime.strptime(str(d["date"]).strip(), "%Y-%m-%d").date()
                overdue.append({
                    "venture": v["slug"],
                    "label": d.get("label", ""),
                    "date": str(d["date"]).strip(),
                    "days_overdue": (self._today - dt).days,
                })
        overdue.sort(key=lambda x: x["days_overdue"], reverse=True)
        return {
            "key_metric": by_lifecycle["active"],
            "key_metric_label": "active ventures",
            "by_lifecycle": by_lifecycle,
            "overdue_total": len(overdue),
            "overdue_milestones": overdue,
        }

    def feed(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        items = self.list(params)
        items.sort(key=lambda x: x["overdue_count"], reverse=True)
        return items

    def healthz(self) -> dict[str, Any]:
        t0 = time.perf_counter()
        s = self.stats()
        resp = healthz_response(
            namespace=NAMESPACE,
            database=str(self.data_root),
            elapsed_ms=(time.perf_counter() - t0) * 1000.0,
            ok=True,
        )
        resp["stats"] = {"key_metric": s["key_metric"], "key_metric_label": s["key_metric_label"]}
        return resp

    def signature(self) -> tuple:
        sig = []
        for _lifecycle, md in self._iter_files():
            sig.append((str(md), md.stat().st_mtime_ns))
        return tuple(sig)
