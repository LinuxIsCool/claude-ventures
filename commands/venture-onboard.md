---
name: venture-onboard
description: Guided venture onboarding — gather details, connect resources, create a complete venture record
argument-hint: Venture name or brief description
allowed-tools: [
  "Read", "Write", "Edit", "Glob", "Grep", "Bash",
  "TodoWrite", "AskUserQuestion", "Task",
  "mcp__*"
]
---

# Venture Onboarding

You are helping a user set up a new venture with all its connections and context.

## Phase 1: Identity

Initial request: $ARGUMENTS

Ask the user:
- **Type**: creative / research / consulting / infrastructure / community?
- **Stage**: seed / exploring / active / sustaining?
- **Description**: Brief scope of the venture?

## Phase 2: People

- Who are the co-venturers? (name, role, contact)
- Any collaborators to add later?

## Phase 3: Timeline

- Any external deadlines? (exhibitions, grants, client deliveries — immovable)
- Any internal milestones? (self-imposed targets — flexible)
- For each: date, label, type (external/internal)

## Phase 4: Data & Resources

- Is there a data directory on the 24TB drive? Path?
  - Default: `/mnt/data-24tb/10-19_Projects/10_Active/<venture-slug>/`
  - Subdirs: transcripts/, media/, datasets/
- Links: repo URL, Google Drive, ArcGIS, reference URLs?
- Related ventures? (by ID)

## Phase 5: Financial (optional)

Skip if not applicable.
- Funding status: unfunded / seeking / partial / funded?
- Any funding opportunities to track?
- Billing type and rate (if consulting)?

## Phase 6: Tags & Categorization

- Suggested tags based on the description
- Ask user to confirm or modify

## Phase 7: Create

Present complete summary. On confirmation:
1. Call `venture_create` with all gathered data
2. Add milestones via `venture_add_milestone`
3. Create data directories if they don't exist (suggest bash command)
4. Report success with venture ID and file location

## Phase 8: Next Steps

- "Add your first deliverable"
- "Link to related ventures"
- "View portfolio: /ventures"
