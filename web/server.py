# plugins/claude-ventures/web/server.py
"""claude-ventures web server — thin satellite of claude_webui.WebuiKernel.

Read-only: no MutationCatalog, kernel enforces hard-405. Standard kernel
routes only (/, /api/list, /api/detail/<slug>, /api/stats, /api/feed,
/healthz, /static/*). No handler subclass needed.

Mode A standalone:   python web/server.py --port 8890
Mode B mount:        registered in claude-webui/scripts/webui_platform.py
                     via _FACTORIES["ventures"] -> build_kernel(port=0)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from claude_webui import WebuiKernel  # noqa: E402

from ventures_accessor import NAMESPACE, VenturesAccessor  # noqa: E402

STATIC_DIR: Path = HERE / "static"
DEFAULT_PORT = 8890


def build_kernel(
    port: int = DEFAULT_PORT,
    bind: str = "127.0.0.1",
    data_root: Path | None = None,
) -> WebuiKernel:
    """Construct (don't start) the ventures substrate kernel. Read-only."""
    accessor = VenturesAccessor(data_root=data_root)
    return WebuiKernel(
        accessor=accessor,
        port=port,
        bind=bind,
        static_dir=STATIC_DIR,
        signature_fn=accessor.signature,
        poll_interval_s=2.0,
        mutation_catalog=None,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="claude-ventures webui")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", DEFAULT_PORT)))
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--data-root", default=None,
                        help="Override ventures data root (default ~/.claude/local/ventures)")
    args = parser.parse_args(argv)
    data_root = Path(args.data_root).expanduser() if args.data_root else None
    kernel = build_kernel(port=args.port, bind=args.bind, data_root=data_root)
    s = kernel.accessor.stats()  # type: ignore[attr-defined]
    print(
        f"[ventures-web] namespace={NAMESPACE} "
        f"data_root={kernel.accessor.data_root} "  # type: ignore[attr-defined]
        f"active={s['key_metric']} overdue={s['overdue_total']}",
        file=sys.stderr,
    )
    return kernel.serve()


if __name__ == "__main__":
    raise SystemExit(main())
