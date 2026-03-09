---
name: connections
description: Co-venturer network, cross-venture links, and resource connections
---

# Connections

## Co-Venturers

People involved across ventures. Track:
- **Name**: Full name
- **Role**: Their function in the venture
- **Contact**: Email, phone, social (optional)

Cross-reference co-venturers across ventures to find collaboration patterns:
```
venture_search({ query: "Carol Anne" })
```

## Cross-Venture Links

Ventures can reference each other via `related_ventures`:
```
venture_update({
  id: "ven-abc123",
  related_ventures: ["ven-def456", "ven-ghi789"]
})
```

Related ventures boost each other's strategic alignment score when both are active.

## Resource Links

The `links` field stores named URLs:
```
venture_update({
  id: "ven-abc123",
  links: {
    repo: "https://github.com/org/project",
    drive: "https://drive.google.com/...",
    docs: "https://notion.so/..."
  }
})
```

## Data Paths

Layer 3 references to heavy storage:
```
venture_update({
  id: "ven-abc123",
  data: {
    root: "/mnt/data-24tb/10-19_Projects/10_Active/venture-name",
    transcripts: "transcripts/",
    media: "media/",
    datasets: "datasets/"
  }
})
```

## Network Analysis

When reviewing the portfolio, look for:
- **People bridges**: Co-venturers who appear in multiple ventures
- **Domain clusters**: Ventures with overlapping tags
- **Resource sharing**: Ventures that could share data/infrastructure
- **Strategic synergies**: Active ventures that strengthen each other
