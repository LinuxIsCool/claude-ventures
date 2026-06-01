---
name: ventures-metrics
description: Show the claude-ventures vision-progress dashboard — 10 metrics across four axes (breadth, structure, autonomy, artifact) with trend arrows vs the last snapshot
---

# /ventures-metrics Command

Render the vision-progress dashboard for claude-ventures. Each metric is tagged to one
of four axes derived from the plugin's vision (*keep track of everything · organize it ·
run it forward · remember less*) and shows its trend versus the previous snapshot.

## Instructions

1. Run the read-only instrument and show the human-readable table:

   ```bash
   uv run ~/.claude/local/scripts/ventures-metrics.py --pretty
   ```

2. To refresh the persisted snapshot + HTML dashboard (writes to
   `~/.claude/local/ventures/metrics/`):

   ```bash
   uv run ~/.claude/local/scripts/ventures-metrics.py --write
   ```

   Then the dashboard is at `~/.claude/local/ventures/metrics/dashboard.html`.

3. For the one-line 4-axis rollup (used by the session-start hook / briefs):

   ```bash
   uv run ~/.claude/local/scripts/ventures-metrics.py --brief-line
   ```

## What the metrics mean

| Axis | Metrics |
|------|---------|
| **Breadth** (track everything) | portfolio coverage, record completeness, data freshness, network density, financial visibility |
| **Structure** (organize it) | FK bind rate ⚠gate, overdue ratio, priority–activity alignment |
| **Autonomy** (run it forward) | human-touch dependency ⚠gate |
| **Artifact** (the tool itself) | engineering maturity |

The two **gates** (FK bind rate, human-touch dependency) read their blocked value until
the fractal migration (task-416 Phase 2) and an autonomous venture-writer exist. Every
future autonomy/rate metric is downstream of these two moving.

Background, design, and the full baseline live in backlog **task-548**.
