# Claude Ventures Plugin

> **Vision:** claude-ventures keeps track of everything you're working on — your
> projects, who's involved, and what's due — with the goal of one day organizing
> your whole working life and running it forward on its own so you have to remember less.

Venture portfolio management for creative, research, and professional initiatives.

## Getting Started

Initialize with `venture_init({ default_currency: "CAD" })`, then use `venture_create` to add ventures.

## Architecture

| Layer | Purpose | Location |
|-------|---------|----------|
| Plugin code | How it works | This repo |
| Venture index | Metadata (YAML+markdown) | `~/.claude/local/ventures/` |
| Venture data | Heavy files | `/mnt/data-24tb/10-19_Projects/` |

## MCP Tools

All tools prefixed with `venture_`: create, list, get, update, delete, search, transition, add_milestone, add_deliverable, complete_item, add_invoice, mark_paid, financials, timeline, portfolio.

## Priority Model

External deadline urgency (45%) + Manual priority (30%) + Strategic alignment (15%) + Financial signal (5%) + Stage modifier (5%).

External deadlines use a cliff curve. Dormant ventures keep their priority indefinitely.

## Data Schema

### SQLite

`ventures.db` exists but is **0 bytes / unused**. All data lives in markdown files.

### File Layout

```
~/.claude/local/ventures/
  ventures.db                      # UNUSED (0 bytes)
  active/*.md                      # Active venture files (YAML frontmatter + markdown body)
  exploring/*.md                   # Exploring-stage ventures
  docs/{slug}/                     # Heavy files, cloned repos, source documents
    repos/                         # Git clones
    sources/                       # Ingested documents
```

### Venture Frontmatter Schema

```yaml
---
id: bcrg                           # Slug identifier
title: BCRG / Avalanche Foundation
description: "..."
type: contract                     # contract | legal-entity | product | research | community
stage: active                      # seed | exploring | active | sustaining | dormant | harvesting
priority: high                     # critical | high | medium | low

co_venturers:
  - name: Shawn Anderson
    role: Systems engineering
    contact: telegram:user:12345   # Optional
    notes: "..."                   # Optional

deadlines:                         # Optional
  - date: 2026-04-15
    description: "Phase 2 deliverable"

milestones:                        # Optional
  - title: "MVP launch"
    status: complete
    date: 2026-03-01

deliverables:                      # Optional
  - title: "Report v1"
    status: in_progress

financial:                         # Optional
  invoices: [...]
  revenue_to_date: 10000
  currency: CAD
---
```

### Canonical Counts

```bash
ls ~/.claude/local/ventures/active/*.md | wc -l
ls ~/.claude/local/ventures/exploring/*.md | wc -l
```

## Venture Stages

seed → exploring → active → sustaining → dormant → harvesting (non-linear, any direction)
