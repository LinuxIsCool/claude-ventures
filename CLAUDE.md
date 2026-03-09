# Claude Ventures Plugin

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

## Venture Stages

seed → exploring → active → sustaining → dormant → harvesting (non-linear, any direction)
