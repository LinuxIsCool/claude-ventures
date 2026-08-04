# claude-ventures webui

Read-only portfolio surface over `~/.claude/local/ventures/`.

- **Launch (Mode A):** `/ventures-web` or `python web/server.py --port 8890`
- **Mode B:** mounted at `http://localhost:8800/ventures/` by the claude-webui Platform.
- **Endpoints:** `/`, `/api/list`, `/api/detail/<slug>`, `/api/stats`, `/api/feed`, `/healthz`, `/static/*`
- **Detail + overview:** `/api/venture/<slug>`, `/api/project/<slug>`, `/api/milestone/<v>/<id>`, `/api/focus`, `/api/timeline`, `/api/priorities`, `/api/trends`
- **Contract:** `/api/bands` (the render manifest), `/api/contract` (store-vs-page verdict)
- **Tests:** `./run-tests.sh` (resolves an interpreter that can import `yaml` + `claude_webui`, layers pytest via `uv` if needed). Override with `VENTURES_TEST_PYTHON`.

### The schema contract

`venture_bands.json` declares every band on the detail page and the exact paths
it reads. The frontend iterates it to render, and `ventures_contract.py` checks
it against the real store in **both** directions:

- **orphan writers** — a field in venture files that no band reads. This is how
  `deadlines` was parsed and then dropped by the payload assembler.
- **orphan readers** — a path the page declares that no venture has. This is how
  `financial.revenue_to_date` was rendered for months against a key that has
  never existed, with a green test suite, because the fixture invented it too.

Because the manifest is what renders the page, a declaration cannot rot into a
comment. Bands with `"renderer": "custom"` are the exception and are reported as
non-load-bearing so the real amount of enforcement stays visible. A band with
`"tail": "prefix.*"` claims unnamed keys under that prefix so venture-specific
fields render instead of vanishing; the single `"tail": "*"` catch-all renders
everything else but reports it as `uncategorized` rather than covered, so it
cannot silently disable the check.

Empty sections state **why** they are empty, from `record_fields` (what the file
had) rather than from the payload (which defaults `deadlines` to `[]`). "no
`financial` in this venture's record" and "`financial` is in this record but
empty" are different facts and must not look the same.
- **Read-only contract:** hard-405 on POST/PUT/DELETE/PATCH. No webui-owned DB — reads the markdown store directly (Data Sync Doctrine). Same tree claude-backlog FKs into.
- **Privacy:** binds 127.0.0.1 by default.
- **Frontend:** `static/index.html` (the kernel serves index from `static_dir`). All data values are HTML-escaped before insertion.
