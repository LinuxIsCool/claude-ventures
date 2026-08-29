# web/ventures_network.py
"""A venture's backlog as a dependency graph, in claude-home topology shape.

Edges point from the dependency to the dependent task. Cross-venture and
missing references become ghost nodes so an edge never dangles. Ranks are
longest-path depth; the critical path is the longest chain through
non-done own-venture tasks. Cycles are broken on the back-edges Kahn's
algorithm cannot consume and are counted, never hidden.
Spec: backlog task-824 sections 6.2 and 6.4.
"""
from __future__ import annotations
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import ventures_backlog

_TERMINAL = {"done", "complete", "completed", "closed", "cancelled", "canceled"}


def _done(task: dict[str, Any]) -> bool:
    return str(task.get("status") or "").strip().lower() in _TERMINAL


def _node(task: dict[str, Any], external: bool) -> dict[str, Any]:
    return {
        "id": task["id"],
        "title": task.get("title") or f"task-{task['id']}",
        "status": task.get("status") or "",
        "priority": str(task.get("priority") or "medium").lower(),
        "due": str(task.get("due") or ""),
        "project": "" if external else (task.get("project") or "unassigned"),
        "milestone": "" if external else (task.get("milestone") or "unscheduled"),
        "venture": task.get("venture") or "",
        "external": external,
        "done": _done(task),
        "href": f"/backlog/tasks/{task['id']}",
    }


def _ghost(ident: str) -> dict[str, Any]:
    return {"id": ident, "title": f"task-{ident} (missing)", "status": "", "priority": "medium",
            "due": "", "project": "", "milestone": "", "venture": "", "external": True,
            "done": False, "href": f"/backlog/tasks/{ident}"}


def _break_cycles(ids: list[str], edges: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Kahn's algorithm; edges left unconsumed are back-edges and are dropped.

    A pure cycle has no zero-indegree node at all, so Kahn's queue empties
    with every edge still unconsumed and none of it drained. When that
    happens, force a source: pick the remaining node with the smallest id
    (numeric ids compare numerically), drop only the edges INTO it (each
    counted as a cycle edge), and resume the algorithm from there.
    """
    indeg = {i: 0 for i in ids}
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in edges:
        out[e["source"]].append(e)
        indeg[e["target"]] += 1
    q = deque(i for i in ids if indeg[i] == 0)
    kept: list[dict[str, Any]] = []
    dropped = 0
    remaining = set(ids)
    while remaining:
        while q:
            n = q.popleft()
            if n not in remaining:
                continue
            remaining.discard(n)
            for e in out[n]:
                if e["target"] not in remaining:
                    continue
                kept.append(e)
                indeg[e["target"]] -= 1
                if indeg[e["target"]] == 0:
                    q.append(e["target"])
        if not remaining:
            break
        # Pure cycle: no zero-indegree node left. Force the smallest-id node
        # as a source. indeg[forced] at this point is exactly the count of
        # still-live edges INTO it (edges from already-processed nodes were
        # already subtracted); those are the cycle edges being dropped.
        forced = min(remaining, key=lambda i: (0, int(i)) if i.isdigit() else (1, i))
        dropped += indeg[forced]
        indeg[forced] = 0
        q.append(forced)
    return kept, dropped


def _ranks(ids: list[str], edges: list[dict[str, Any]]) -> dict[str, int]:
    rank = {i: 0 for i in ids}
    out: dict[str, list[str]] = defaultdict(list)
    indeg = {i: 0 for i in ids}
    for e in edges:
        out[e["source"]].append(e["target"])
        indeg[e["target"]] += 1
    q = deque(i for i in ids if indeg[i] == 0)
    while q:
        n = q.popleft()
        for t in out[n]:
            rank[t] = max(rank[t], rank[n] + 1)
            indeg[t] -= 1
            if indeg[t] == 0:
                q.append(t)
    return rank


def _critical_path(nodes: dict[str, dict[str, Any]], edges: list[dict[str, Any]]) -> list[str]:
    eligible = {i for i, n in nodes.items() if not n["external"] and not n["done"]}
    sub = [e for e in edges if e["source"] in eligible and e["target"] in eligible]
    if not sub:
        return []
    ids = sorted(eligible)
    rank = _ranks(ids, sub)
    best_len = {i: 1 for i in ids}
    prev: dict[str, str | None] = {i: None for i in ids}
    for i in sorted(ids, key=lambda x: rank[x]):
        for e in sub:
            if e["target"] == i and best_len[e["source"]] + 1 > best_len[i]:
                best_len[i] = best_len[e["source"]] + 1
                prev[i] = e["source"]
    end = max(ids, key=lambda x: (best_len[x], -int(x) if x.isdigit() else 0))
    path = []
    cur: str | None = end
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    return list(reversed(path))


def network(slug: str, backlog_dir: Path | None = None, include_done: bool = False) -> dict[str, Any]:
    d = Path(backlog_dir) if backlog_dir else ventures_backlog._BACKLOG_DEFAULT
    every = ventures_backlog._cached_tasks(d) if d.is_dir() else []
    by_id = {t["id"]: t for t in every}
    own = [t for t in every if str(t.get("venture") or "") == slug and (include_done or not _done(t))]
    nodes: dict[str, dict[str, Any]] = {t["id"]: _node(t, external=False) for t in own}
    raw_edges: list[dict[str, Any]] = []
    for t in own:
        for dep in t.get("depends_on") or []:
            raw_edges.append({"source": dep, "target": t["id"], "kind": "depends_on", "evidence": f"task-{t['id']}.depends_on"})
        for blocked in t.get("blocks") or []:
            raw_edges.append({"source": t["id"], "target": blocked, "kind": "depends_on", "evidence": f"task-{t['id']}.blocks"})
    for e in raw_edges:
        for end in (e["source"], e["target"]):
            if end not in nodes:
                nodes[end] = _node(by_id[end], external=True) if end in by_id else _ghost(end)
    seen: set[tuple[str, str]] = set()
    edges: list[dict[str, Any]] = []
    for e in raw_edges:
        key = (e["source"], e["target"])
        if key in seen or e["source"] == e["target"]:
            continue
        seen.add(key)
        edges.append(e)
    ids = sorted(nodes)
    edges, cycles = _break_cycles(ids, edges)
    ranks = _ranks(ids, edges)
    projects: dict[str, int] = defaultdict(int)
    milestones: dict[str, int] = defaultdict(int)
    for n in nodes.values():
        if not n["external"]:
            projects[n["project"]] += 1
            milestones[n["milestone"]] += 1
    group = lambda c: [{"key": k, "count": v} for k, v in sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))]
    return {
        "nodes": [nodes[i] for i in ids],
        "edges": edges,
        "groups": {"projects": group(projects), "milestones": group(milestones)},
        "critical_path": _critical_path(nodes, edges),
        "ranks": ranks,
        "counts": {"nodes": len(nodes), "external": sum(1 for n in nodes.values() if n["external"]),
                   "edges": len(edges), "cycles": cycles},
    }
