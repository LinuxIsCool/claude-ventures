"""One explicit portfolio-scope contract shared by every Ventures widget."""
from __future__ import annotations

from dataclasses import dataclass

_DISPLAY = {
    "exploring": {"seed", "exploring"},
    "active": {"active", "sustaining"},
    "complete": {"harvesting"},
}


@dataclass(frozen=True)
class PortfolioScope:
    venture_ids: frozenset[str]
    lifecycle_filters: frozenset[str] = frozenset({"all"})

    @classmethod
    def from_query(cls, query: dict[str, list[str]]) -> "PortfolioScope":
        def values(name: str) -> set[str]:
            return {part.strip().lower() for raw in query.get(name, [])
                    for part in raw.split(",") if part.strip()}
        ventures = values("ventures")
        filters = values("lifecycle") or {"all"}
        if "all" in filters:
            filters = {"all"}
        return cls(frozenset(ventures), frozenset(filters))

    def includes(self, venture_id: str, lifecycle: str) -> bool:
        if venture_id not in self.venture_ids:
            return False
        if "all" in self.lifecycle_filters:
            return True
        return any(lifecycle in _DISPLAY.get(name, set())
                   for name in self.lifecycle_filters)

    def as_dict(self) -> dict:
        return {
            "venture_ids": sorted(self.venture_ids),
            "lifecycle_filters": sorted(self.lifecycle_filters),
            "empty": not self.venture_ids,
        }
