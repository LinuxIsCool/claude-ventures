---
name: lifecycle
description: Stage transitions, dormancy patterns, and venture reactivation
---

# Lifecycle Management

## Venture Stages

| Stage | Description | Typical Duration |
|-------|-------------|-----------------|
| **seed** | Idea captured, not yet explored | Days to months |
| **exploring** | Active research and discovery | Weeks to months |
| **active** | Primary focus, work in progress | Weeks to years |
| **sustaining** | Maintenance mode, periodic attention | Months to years |
| **dormant** | Paused, waiting for conditions | Indefinite |
| **harvesting** | Wrapping up, extracting value | Days to weeks |

## Transition Patterns

**Forward progression**: seed → exploring → active → sustaining → harvesting
**Pause**: any → dormant (venture goes quiet, context will return)
**Reactivation**: dormant → active (conditions changed, context returned)
**Pivot**: exploring → seed (direction changed, back to ideation)
**Escalation**: sustaining → active (new deadline, renewed energy)

## Dormancy

Dormant ventures are NOT dead. They:
- Keep their manual priority score (no decay)
- Stay visible in portfolio when strategically connected
- Can be reactivated at any time
- Get surfaced when conversation context touches their domain

## Transition Command
```
venture_transition({
  id: "ven-abc123",
  stage: "dormant",
  notes: "Pausing until April grant cycle"
})
```

Always add transition notes — they provide future context for reactivation decisions.
