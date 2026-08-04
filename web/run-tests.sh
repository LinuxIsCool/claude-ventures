#!/usr/bin/env bash
# Run the ventures webui test suite on any machine.
#
# The suite needs an interpreter that can import BOTH `yaml` and `claude_webui`.
# `claude_webui` is not on PyPI; it is a sibling plugin resolved via the venv the
# Legion webui hub runs from. So we cannot just `uv run --with pytest python`:
# we have to find an interpreter that already sees claude_webui, then layer
# pytest on top of it.
#
# Resolution order (first interpreter that can import both wins):
#   1. $VENTURES_TEST_PYTHON      explicit override
#   2. the legion-webui venv      the hub's own interpreter
#   3. python3                    for environments that installed the deps
#
# Usage:  ./run-tests.sh              # whole suite, quiet
#         ./run-tests.sh -k contract  # any pytest args pass through
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

_can_import() {
  "$1" -c 'import yaml, claude_webui' >/dev/null 2>&1
}

PY=""
for candidate in \
  "${VENTURES_TEST_PYTHON:-}" \
  "$HOME/.local/opt/legion-webui-venv/bin/python" \
  "$(command -v python3 || true)"
do
  [ -n "$candidate" ] && [ -x "$candidate" ] || continue
  if _can_import "$candidate"; then PY="$candidate"; break; fi
done

if [ -z "$PY" ]; then
  echo "run-tests.sh: no interpreter can import both 'yaml' and 'claude_webui'." >&2
  echo "  Set VENTURES_TEST_PYTHON to one that can, e.g.:" >&2
  echo "  VENTURES_TEST_PYTHON=/path/to/venv/bin/python ./run-tests.sh" >&2
  exit 2
fi

# pytest may not be present in that interpreter's environment. Prefer it if it
# is (no network, no temp env); otherwise let uv layer it on without mutating
# the hub's venv.
if "$PY" -c 'import pytest' >/dev/null 2>&1; then
  exec "$PY" -m pytest "${@:--q}"
elif command -v uv >/dev/null 2>&1; then
  exec uv run --python "$PY" --with pytest python -m pytest "${@:--q}"
else
  echo "run-tests.sh: found $PY but it has no pytest, and uv is not installed." >&2
  echo "  Install uv, or: $PY -m pip install pytest" >&2
  exit 2
fi
