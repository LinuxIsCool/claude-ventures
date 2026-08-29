#!/usr/bin/env bash
# scripts/fetch-vendor.sh: materialise web/static/vendor/*.js from MANIFEST.json,
# verifying sha256. Idempotent; skips files that already match.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../web/static/vendor"
python3 - <<'EOF'
import hashlib, json, pathlib, sys, urllib.request
m = json.loads(pathlib.Path("MANIFEST.json").read_text())
for f in m["files"]:
    p = pathlib.Path(f["name"])
    if p.exists() and hashlib.sha256(p.read_bytes()).hexdigest() == f["sha256"]:
        print(f"ok      {p}"); continue
    data = urllib.request.urlopen(f["url"], timeout=30).read()
    got = hashlib.sha256(data).hexdigest()
    if got != f["sha256"]:
        sys.exit(f"sha256 mismatch for {p}: {got} != {f['sha256']}")
    p.write_bytes(data); print(f"fetched {p} ({len(data)} bytes)")
EOF
