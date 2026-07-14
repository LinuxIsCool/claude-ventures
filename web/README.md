# claude-ventures webui

Read-only portfolio surface over `~/.claude/local/ventures/`.

- **Launch (Mode A):** `/ventures-web` or `python web/server.py --port 8890`
- **Mode B:** mounted at `http://localhost:8800/ventures/` by the claude-webui Platform.
- **Endpoints:** `/`, `/api/list`, `/api/detail/<slug>`, `/api/stats`, `/api/feed`, `/healthz`, `/static/*`
- **Read-only contract:** hard-405 on POST/PUT/DELETE/PATCH. No webui-owned DB — reads the markdown store directly (Data Sync Doctrine). Same tree claude-backlog FKs into.
- **Privacy:** binds 127.0.0.1 by default.
- **Frontend:** `static/index.html` (the kernel serves index from `static_dir`). All data values are HTML-escaped before insertion.
