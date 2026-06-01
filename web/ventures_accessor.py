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

NAMESPACE = "legion.claude-venture"

_HOME = Path.home()
_DATA_ROOT_DEFAULT = _HOME / ".claude" / "local" / "ventures"
_LIFECYCLES = ("active", "exploring", "dormant", "harvesting")


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
        overdue = [d for d in deadlines if self._is_overdue(d)]
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
        }

    def _is_overdue(self, deadline: dict[str, Any]) -> bool:
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
