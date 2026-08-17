"""Compatibility entry point for the task-only portfolio focus contract."""
from datetime import date

import ventures_tasks
from ventures_scope import PortfolioScope


def buckets(ventures_root, backlog_dir, today: date,
            scope: PortfolioScope | None = None) -> dict:
    return ventures_tasks.focus(
        ventures_root, backlog_dir,
        scope or PortfolioScope(frozenset()), today,
    )
