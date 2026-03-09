---
name: venture-master
description: Master skill for venture portfolio management (4 sub-skills). Covers portfolio analysis, lifecycle management, connections, and financials. Invoke for venture creation, priority review, stage transitions, or portfolio strategy.
allowed-tools: Read, Skill, Task, Glob, Grep
---

# Venture Master Skill

Venture portfolio management — tracking creative, research, and professional initiatives across their full lifecycle with priority ranking based on external deadlines, strategic alignment, and manual priority.

## Sub-Skills Index

| Sub-Skill | Use When | File |
|-----------|----------|------|
| **portfolio** | Analyzing the portfolio, attention allocation, strategic view | `subskills/portfolio.md` |
| **lifecycle** | Stage transitions, dormancy/reactivation patterns | `subskills/lifecycle.md` |
| **connections** | Co-venturer network, cross-venture links, related resources | `subskills/connections.md` |
| **financials** | Funding tracking, grants, investment of time/money/social capital | `subskills/financials.md` |

## Quick Reference

### Venture Types
- **creative**: Art, installations, performances
- **research**: Studies, investigations, experiments
- **consulting**: Client work, contracts
- **infrastructure**: Tools, systems, platforms
- **community**: Organizations, networks, events

### Venture Stages (non-linear)
```
seed → exploring → active → sustaining → dormant → harvesting
```

Ventures can move in any direction. Dormant ventures reactivate when context returns.

### Priority Weights
| Factor | Weight | Description |
|--------|--------|-------------|
| External deadline urgency | 45% | Cliff curve for immovable deadlines |
| Manual priority | 30% | User-set, no decay for dormant |
| Strategic alignment | 15% | Connections to other active ventures |
| Financial signal | 5% | Outstanding payments, funding status |
| Stage modifier | 5% | Active > Exploring > Seed |

### MCP Tools Available
- `venture_create`, `venture_list`, `venture_get`, `venture_update`, `venture_delete`, `venture_search`
- `venture_add_milestone`, `venture_add_deliverable`, `venture_complete_item`
- `venture_transition`
- `venture_add_invoice`, `venture_mark_paid`, `venture_financials`
- `venture_timeline`, `venture_portfolio`

## Usage Examples

**Create a creative venture:**
```
venture_create({
  title: "Salish Sea Dreaming",
  type: "creative",
  stage: "active",
  priority: "high",
  deadlines: [{ date: "2026-04-15", label: "Salt Spring Art Show", type: "external" }],
  co_venturers: [{ name: "Carol Anne Hilton", role: "Framework architect" }],
  data: { root: "/mnt/data-24tb/10-19_Projects/10_Active/salish-sea-dreaming" }
})
```

**Check portfolio health:**
```
venture_portfolio({})
```

**Transition a venture:**
```
venture_transition({ id: "ven-abc123", stage: "dormant", notes: "Pausing until grant comes through" })
```

## Data Storage

Ventures stored as markdown with YAML frontmatter in `~/.claude/local/ventures/<stage>/`.
Heavy data (media, transcripts) on the data drive, referenced via the `data` field.
