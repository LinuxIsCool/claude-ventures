# web/actions_server.py
"""studio-actions: the write-capable sibling of the read-only ventures satellite.

One mount, one write endpoint (POST /api/mutate), seven tools, all routed
through studio_actions.perform / Shells under the declared-only rule.
Spec: backlog task-824 sections 6.5 and 6.6.
"""
from __future__ import annotations
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from claude_webui import WebuiKernel
from claude_webui.dispatcher import MutationCatalog, MutationError
from claude_webui.healthz import healthz_response

import studio_actions as A

STATIC_DIR = HERE / "static-actions"
AUDIT_DIR_DEFAULT = Path.home() / ".claude" / "local" / "ventures" / "runtime" / "studio-actions-audit"
NAMESPACE = "legion.studio-actions"


class ActionsAccessor:
    def __init__(self, log_path: Path, shells: A.Shells) -> None:
        self.log_path, self.shells = log_path, shells

    def _rows(self, limit: int = 50) -> list[dict[str, Any]]:
        try:
            lines = self.log_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        out = []
        for ln in reversed(lines[-limit:]):
            try:
                out.append(json.loads(ln))
            except ValueError:
                continue
        return out

    def list(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        return self._rows()

    def detail(self, item_id: str) -> dict[str, Any]:
        return {}

    def stats(self) -> dict[str, Any]:
        today = datetime.now(timezone.utc).date().isoformat()
        return {"key_metric": sum(1 for r in self._rows(500) if str(r.get("ts", "")).startswith(today)),
                "key_metric_label": "actions today", "shells": len(self.shells.list())}

    def feed(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        return self._rows()

    def signature(self) -> tuple:
        try:
            return (self.log_path.stat().st_mtime_ns,)
        except OSError:
            return (0,)

    def healthz(self) -> dict[str, Any]:
        t0 = time.perf_counter()
        stats = self.stats()
        resp = healthz_response(NAMESPACE, str(self.log_path), round((time.perf_counter() - t0) * 1000, 3), ok=True)
        resp["stats"] = stats
        return resp


def _wrap(fn):
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return fn(args or {})
        except A.ActionRefused as exc:
            raise MutationError(exc.code, exc.message) from exc
    return handler


def build_kernel(port: int = 8891, bind: str = "127.0.0.1", ventures_root: Path | None = None, log_path: Path | None = None,
                 shells_path: Path | None = None, run=None, shells: A.Shells | None = None, audit_dir: Path | None = None) -> WebuiKernel:
    log = Path(log_path) if log_path else A.ACTION_LOG_DEFAULT
    runner = run or A.default_run
    sh = shells or A.Shells(shells_path)
    catalog = MutationCatalog(audit_dir=audit_dir or AUDIT_DIR_DEFAULT, timeout_s=90, paradigm="channel-rpc")

    def act(action):
        return _wrap(lambda a: A.perform(action, a.get("venture"), a.get("app"), a.get("env"), run=runner, log_path=log, ventures_root=ventures_root))

    def shell_open(a):
        r = A.resolve_repo(a.get("venture"), a.get("app"), ventures_root=ventures_root)
        return sh.open(a.get("venture"), a.get("app"), r)

    for name, action in (("studio_status", "status"), ("studio_start", "start"), ("studio_stop", "stop"), ("studio_logs", "logs")):
        catalog.register(name, act(action), args_schema={"type": "object", "required": ["venture", "app", "env"]})
    catalog.register("studio_shell_open", _wrap(shell_open), args_schema={"type": "object", "required": ["venture", "app"]})
    catalog.register("studio_shell_close", _wrap(lambda a: sh.close(a.get("venture"), a.get("app"))), args_schema={"type": "object", "required": ["venture", "app"]})
    catalog.register("studio_shells", _wrap(lambda a: {"shells": sh.list()}), args_schema={"type": "object"})
    accessor = ActionsAccessor(log, sh)
    return WebuiKernel(accessor=accessor, port=port, bind=bind, static_dir=STATIC_DIR, signature_fn=accessor.signature,
                       poll_interval_s=5.0, mutation_catalog=catalog)


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--port", type=int, default=8891); ap.add_argument("--bind", default="127.0.0.1")
    args = ap.parse_args(argv)
    build_kernel(port=args.port, bind=args.bind).serve()
    return 0


if __name__ == "__main__":
    sys.exit(main())
