#!/usr/bin/env python
"""Generate web/static/venture-identity.json = {slug: {emoji, colour}}.

Reads the universal emoji + colour languages (claude-emoji / claude-colours) directly via sqlite
(read-only) at their claude-paths-resolved locations — no cross-plugin Python imports needed.
The ventures webui fetches this to paint each card with its emoji + identity colour.

Run: python scripts/gen_identity.py
"""
import json
import sqlite3
import sys
from pathlib import Path

try:
    from claude_paths import data_dir
    EMOJI_DB = data_dir("emoji") / "emoji.db"
    COLOURS_DB = data_dir("colours") / "colours.db"
except Exception:  # fallback to the locked XDG state paths
    base = Path("~/.local/state/legion").expanduser()
    EMOJI_DB, COLOURS_DB = base / "emoji/emoji.db", base / "colours/colours.db"


def _ro(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def main():
    emojis = dict(_ro(EMOJI_DB).execute(
        "SELECT entity_key, emoji FROM emoji_mappings WHERE entity_key LIKE 'venture:%'"))
    colours = dict(_ro(COLOURS_DB).execute(
        "SELECT entity_key, hex FROM colours WHERE entity_key LIKE 'venture:%'"))
    out = {}
    for key in sorted(set(emojis) | set(colours)):
        slug = key.split(":", 1)[1]
        out[slug] = {"emoji": emojis.get(key), "colour": colours.get(key)}
    dest = Path(__file__).resolve().parent.parent / "web" / "static" / "venture-identity.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"wrote {dest} — {len(out)} ventures ({sum(1 for v in out.values() if v['emoji'])} emoji, "
          f"{sum(1 for v in out.values() if v['colour'])} colour)")


if __name__ == "__main__":
    main()
