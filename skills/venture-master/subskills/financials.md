---
name: financials
description: Funding tracking, grants, invoicing, and investment tracking
---

# Financial Tracking

## Funding Status

Each venture has a funding status:
- **unfunded**: No money involved (most creative/community ventures)
- **seeking**: Actively looking for funding (grants, investors)
- **partial**: Some funding secured
- **funded**: Fully funded

## Funding Opportunities

Track grant applications, investor conversations:
```
venture_update({
  id: "ven-abc123",
  financial: {
    status: "seeking",
    opportunities: [
      { name: "BC Arts Council Grant", stage: "application", deadline: "2026-06-15" },
      { name: "Canada Council", stage: "lead" }
    ]
  }
})
```

## Invoicing (Consulting Ventures)

For paid work:
```
venture_add_invoice({ venture_id: "ven-abc123", amount: 5000, currency: "CAD", description: "Phase 1" })
venture_mark_paid({ venture_id: "ven-abc123", invoice_id: "inv-xyz" })
venture_financials({})
```

## Investment Types

Not all investment is monetary. Track:
- **Time**: Hours spent (via milestones and notes)
- **Money**: Direct funding, expenses
- **Social capital**: Relationship building, community standing
- **Infrastructure**: Tools, compute, equipment

## Financial Summary

Cross-venture financial overview:
```
venture_financials({ type: "consulting" })
```

Shows total invoiced, received, and outstanding across all matching ventures.
