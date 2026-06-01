---
description: Launch the claude-ventures webui (Mode A standalone, port 8890) and open browser
---

Run the ventures webui standalone and open it:

```bash
python ~/.claude/plugins/local/legion-plugins/plugins/claude-ventures/web/server.py --port 8890 &
sleep 1 && xdg-open http://127.0.0.1:8890/
```

Read-only portfolio surface over `~/.claude/local/ventures/`. For the
multi-tenant Legion Hub, it is also mounted at
http://localhost:8800/ventures/ when the claude-webui Platform runs.
