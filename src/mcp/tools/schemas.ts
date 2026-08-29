/**
 * MCP Tool Schemas — JSON Schema definitions for all venture management tools.
 */

export const ventureCreateSchema = {
  type: "object" as const,
  properties: {
    title: {
      type: "string",
      description: "Venture title",
    },
    type: {
      type: "string",
      enum: ["creative", "research", "consulting", "infrastructure", "community"],
      description: "Venture type",
    },
    stage: {
      type: "string",
      enum: ["seed", "exploring", "active", "sustaining", "dormant", "harvesting"],
      description: "Venture stage",
      default: "seed",
    },
    priority: {
      type: "string",
      enum: ["critical", "high", "medium", "low", "none"],
      description: "Manual priority level",
      default: "none",
    },
    description: {
      type: "string",
      description: "Venture description",
    },
    tags: {
      type: "array",
      items: { type: "string" },
      description: "Tags for categorization",
    },
    co_venturers: {
      type: "array",
      items: {
        type: "object" as const,
        properties: {
          name: { type: "string" },
          role: { type: "string" },
          contact: { type: "string" },
        },
        required: ["name", "role"],
      },
      description: "People involved in this venture",
    },
    deadlines: {
      type: "array",
      items: {
        type: "object" as const,
        properties: {
          date: { type: "string", description: "YYYY-MM-DD" },
          label: { type: "string" },
          type: { type: "string", enum: ["external", "internal"], default: "internal" },
          time: { type: "string", description: "HH:MM" },
        },
        required: ["date", "type"],
      },
      description: "Deadlines (external = immovable, internal = flexible)",
    },
    links: {
      type: "object" as const,
      additionalProperties: { type: "string" },
      description: "Named links (repo, drive, etc.)",
    },
    related_ventures: {
      type: "array",
      items: { type: "string" },
      description: "IDs of related ventures",
    },
    data: {
      type: "object" as const,
      properties: {
        root: { type: "string", description: "Root path on data drive" },
        transcripts: { type: "string" },
        media: { type: "string" },
        datasets: { type: "string" },
      },
      description: "Data paths for heavy files (layer 3)",
    },
  },
  required: ["title", "type"],
};

export const ventureListSchema = {
  type: "object" as const,
  properties: {
    type: {
      type: "string",
      enum: ["creative", "research", "consulting", "infrastructure", "community"],
      description: "Filter by venture type",
    },
    stage: {
      type: "string",
      enum: ["seed", "exploring", "active", "sustaining", "dormant", "harvesting"],
      description: "Filter by stage",
    },
    priority: {
      type: "string",
      enum: ["critical", "high", "medium", "low", "none"],
      description: "Filter by manual priority",
    },
    tags: {
      type: "array",
      items: { type: "string" },
      description: "Filter by tags (match any)",
    },
    overdue: {
      type: "boolean",
      description: "Filter to only overdue ventures",
    },
    due_within_days: {
      type: "number",
      description: "Filter to ventures due within N days",
    },
    min_priority: {
      type: "number",
      description: "Filter by minimum calculated priority (0-100)",
    },
    sort_by: {
      type: "string",
      enum: ["priority", "deadline", "created", "updated", "stage", "title"],
      description: "Sort field (default: priority)",
      default: "priority",
    },
    sort_order: {
      type: "string",
      enum: ["asc", "desc"],
      description: "Sort order",
    },
    limit: {
      type: "number",
      description: "Maximum results to return",
    },
  },
};

export const ventureGetSchema = {
  type: "object" as const,
  properties: {
    id: {
      type: "string",
      description: "Venture ID",
    },
  },
  required: ["id"],
};

export const ventureUpdateSchema = {
  type: "object" as const,
  properties: {
    id: { type: "string", description: "Venture ID" },
    title: { type: "string", description: "New title" },
    type: {
      type: "string",
      enum: ["creative", "research", "consulting", "infrastructure", "community"],
    },
    stage: {
      type: "string",
      enum: ["seed", "exploring", "active", "sustaining", "dormant", "harvesting"],
    },
    priority: {
      type: "string",
      enum: ["critical", "high", "medium", "low", "none"],
    },
    description: { type: "string" },
    tags: { type: "array", items: { type: "string" } },
    notes: { type: "string", description: "Append notes (markdown)" },
    deadlines: {
      type: "array",
      items: {
        type: "object" as const,
        properties: {
          date: { type: "string" },
          label: { type: "string" },
          type: { type: "string", enum: ["external", "internal"] },
        },
        required: ["date", "type"],
      },
    },
    co_venturers: {
      type: "array",
      items: {
        type: "object" as const,
        properties: {
          name: { type: "string" },
          role: { type: "string" },
          contact: { type: "string" },
        },
        required: ["name", "role"],
      },
    },
    links: {
      type: "object" as const,
      additionalProperties: { type: "string" },
    },
    related_ventures: { type: "array", items: { type: "string" } },
    data: {
      type: "object" as const,
      properties: {
        root: { type: "string" },
        transcripts: { type: "string" },
        media: { type: "string" },
        datasets: { type: "string" },
      },
    },
  },
  required: ["id"],
};

export const ventureDeleteSchema = {
  type: "object" as const,
  properties: {
    id: { type: "string", description: "Venture ID to delete" },
  },
  required: ["id"],
};

export const ventureSearchSchema = {
  type: "object" as const,
  properties: {
    query: {
      type: "string",
      description: "Search text (matches title, description, notes, tags, co-venturers)",
    },
  },
  required: ["query"],
};

export const ventureTransitionSchema = {
  type: "object" as const,
  properties: {
    id: { type: "string", description: "Venture ID" },
    stage: {
      type: "string",
      enum: ["seed", "exploring", "active", "sustaining", "dormant", "harvesting"],
      description: "New stage",
    },
    notes: { type: "string", description: "Optional transition notes" },
  },
  required: ["id", "stage"],
};

export const addMilestoneSchema = {
  type: "object" as const,
  properties: {
    venture_id: { type: "string", description: "Venture ID" },
    title: { type: "string", description: "Milestone title" },
    description: { type: "string" },
    deadline: {
      type: "object" as const,
      properties: {
        date: { type: "string" },
        type: { type: "string", enum: ["external", "internal"], default: "internal" },
      },
      required: ["date"],
    },
  },
  required: ["venture_id", "title"],
};

export const addDeliverableSchema = {
  type: "object" as const,
  properties: {
    venture_id: { type: "string", description: "Venture ID" },
    milestone_id: { type: "string", description: "Milestone ID" },
    title: { type: "string", description: "Deliverable title" },
    description: { type: "string" },
    deadline: {
      type: "object" as const,
      properties: {
        date: { type: "string" },
        type: { type: "string", enum: ["external", "internal"] },
      },
      required: ["date"],
    },
  },
  required: ["venture_id", "milestone_id", "title"],
};

export const completeItemSchema = {
  type: "object" as const,
  properties: {
    venture_id: { type: "string", description: "Venture ID" },
    milestone_id: { type: "string", description: "Milestone ID" },
    deliverable_id: { type: "string", description: "Deliverable ID (omit to complete milestone)" },
  },
  required: ["venture_id", "milestone_id"],
};

export const addInvoiceSchema = {
  type: "object" as const,
  properties: {
    venture_id: { type: "string", description: "Venture ID" },
    amount: { type: "number", description: "Invoice amount" },
    currency: { type: "string", description: "Currency code (default: CAD)", default: "CAD" },
    description: { type: "string" },
    date: { type: "string", description: "Invoice date (YYYY-MM-DD)" },
  },
  required: ["venture_id", "amount"],
};

export const markPaidSchema = {
  type: "object" as const,
  properties: {
    venture_id: { type: "string", description: "Venture ID" },
    invoice_id: { type: "string", description: "Invoice ID" },
  },
  required: ["venture_id", "invoice_id"],
};

export const ventureFinancialsSchema = {
  type: "object" as const,
  properties: {
    type: {
      type: "string",
      enum: ["creative", "research", "consulting", "infrastructure", "community"],
    },
    stage: {
      type: "string",
      enum: ["seed", "exploring", "active", "sustaining", "dormant", "harvesting"],
    },
  },
};

export const ventureTimelineSchema = {
  type: "object" as const,
  properties: {
    days_ahead: { type: "number", description: "Days to look ahead (default: 90)", default: 90 },
    include_overdue: { type: "boolean", description: "Include overdue ventures", default: true },
  },
};

export const venturePortfolioSchema = {
  type: "object" as const,
  properties: {},
  description: "Get a portfolio-level dashboard view of all ventures",
};

export const ventureInitSchema = {
  type: "object" as const,
  properties: {
    default_currency: {
      type: "string",
      description: "Default currency (default: CAD)",
      default: "CAD",
    },
    data_drive_path: {
      type: "string",
      description: "Path to data drive for heavy files",
    },
  },
};

// ── Fractal V/P/M schemas (task-416 Phase 1) ──────────────────────────

const SLUG_SEGMENT = { type: "string", pattern: "^[a-z0-9][a-z0-9-]*$" };
const STAGE = {
  type: "string",
  enum: ["seed", "exploring", "active", "sustaining", "dormant", "harvesting"],
};
const PRIORITY = {
  type: "string",
  enum: ["critical", "high", "medium", "low", "none"],
};
const CLOSE_STAGE = {
  type: "string",
  enum: ["sustaining", "dormant", "harvesting"],
};

export const PROJECT_CREATE_SCHEMA = {
  type: "object" as const,
  properties: {
    slug: SLUG_SEGMENT,
    name: { type: "string" },
    description: { type: "string" },
    venture: SLUG_SEGMENT,
    stage: STAGE,
    priority: PRIORITY,
    owner: { type: "string" },
    co_owners: { type: "array", items: { type: "string" } },
    stakeholders: { type: "array", items: { type: "string" } },
    deadline: { type: "string", format: "date" },
    milestones: { type: "array", items: SLUG_SEGMENT },
    notes: { type: "string" },
  },
  required: ["slug", "name", "venture", "stage", "priority", "owner", "co_owners", "stakeholders", "milestones"],
};

export const PROJECT_LIST_SCHEMA = {
  type: "object" as const,
  properties: {
    venture: SLUG_SEGMENT,
    stage: { oneOf: [STAGE, { type: "array", items: STAGE }] },
    priority: { oneOf: [PRIORITY, { type: "array", items: PRIORITY }] },
    owner: { type: "string" },
    due_within_days: { type: "number" },
    overdue: { type: "boolean" },
    sort_by: { type: "string", enum: ["priority", "deadline", "created", "updated", "name"] },
    sort_order: { type: "string", enum: ["asc", "desc"] },
    limit: { type: "number" },
    offset: { type: "number" },
  },
};

export const PROJECT_GET_SCHEMA = {
  type: "object" as const,
  properties: { venture: SLUG_SEGMENT, slug: SLUG_SEGMENT },
  required: ["venture", "slug"],
};

export const PROJECT_UPDATE_SCHEMA = {
  type: "object" as const,
  properties: {
    venture: SLUG_SEGMENT,
    slug: SLUG_SEGMENT,
    patch: { type: "object" },
  },
  required: ["venture", "slug", "patch"],
};

export const PROJECT_CLOSE_SCHEMA = {
  type: "object" as const,
  properties: {
    venture: SLUG_SEGMENT,
    slug: SLUG_SEGMENT,
    stage: CLOSE_STAGE,
    retro_md: { type: "string" },
  },
  required: ["venture", "slug", "stage"],
};

const APP_KIND = { type: "string", enum: ["web", "api", "static", "pipeline", "library"] };
const APP_STAGE = { type: "string", enum: ["planned", "active", "paused", "retired"] };
const APP_ENVIRONMENT = {
  type: "object",
  properties: {
    name: { type: "string" },
    url: { type: "string" },
    host: { type: "string" },
    healthz: { type: "string", description: "path appended to url" },
    deploy: { type: "string", enum: ["compose", "vercel", "pages", "nginx", "manual"] },
    status: { type: "string", enum: ["live", "unprovisioned", "paused"] },
    controllable: { type: "boolean", description: "Studio may start/stop; default true only for dev" },
  },
  required: ["name"],
};
const APP_RUNTIME = {
  type: "object",
  properties: {
    kind: { type: "string", enum: ["compose", "process", "none"] },
    file: { type: "string" },
    project: { type: "string" },
    network: { type: "string" },
    hostname: { type: "string" },
  },
  required: ["kind"],
};
const APP_REPO = {
  type: "object",
  properties: {
    path: { type: "string" },
    remote: { type: "string" },
    default_branch: { type: "string" },
    vcs: { type: "string", enum: ["git", "jj+git"] },
  },
  required: ["path"],
};

export const APP_CREATE_SCHEMA = {
  type: "object" as const,
  properties: {
    slug: SLUG_SEGMENT,
    name: { type: "string" },
    venture: SLUG_SEGMENT,
    project: SLUG_SEGMENT,
    kind: APP_KIND,
    stage: APP_STAGE,
    repo: APP_REPO,
    run: { type: "string" },
    test: { type: "string" },
    status_doc: { type: "string" },
    environments: { type: "array", items: APP_ENVIRONMENT },
    depends_on: { type: "array", items: { type: "string" } },
    secrets: { type: "string", description: "path to an env file; never values" },
    runtime: APP_RUNTIME,
    notes: { type: "string" },
  },
  required: ["slug", "name", "venture", "kind", "stage", "repo", "environments", "depends_on"],
};

export const APP_LIST_SCHEMA = {
  type: "object" as const,
  properties: {
    venture: SLUG_SEGMENT,
    project: SLUG_SEGMENT,
    stage: { oneOf: [APP_STAGE, { type: "array", items: APP_STAGE }] },
    kind: { oneOf: [APP_KIND, { type: "array", items: APP_KIND }] },
    sort_by: { type: "string", enum: ["name", "created", "updated"] },
    sort_order: { type: "string", enum: ["asc", "desc"] },
    limit: { type: "number" },
    offset: { type: "number" },
  },
};

export const APP_GET_SCHEMA = {
  type: "object" as const,
  properties: { venture: SLUG_SEGMENT, slug: SLUG_SEGMENT },
  required: ["venture", "slug"],
};

export const APP_UPDATE_SCHEMA = {
  type: "object" as const,
  properties: { venture: SLUG_SEGMENT, slug: SLUG_SEGMENT, patch: { type: "object" } },
  required: ["venture", "slug", "patch"],
};

export const APP_CLOSE_SCHEMA = {
  type: "object" as const,
  properties: {
    venture: SLUG_SEGMENT,
    slug: SLUG_SEGMENT,
    stage: { type: "string", enum: ["paused", "retired"] },
    retro_md: { type: "string" },
  },
  required: ["venture", "slug", "stage"],
};

export const MILESTONE_CREATE_SCHEMA = {
  type: "object" as const,
  properties: {
    slug: SLUG_SEGMENT,
    name: { type: "string" },
    description: { type: "string" },
    project: SLUG_SEGMENT,
    venture: SLUG_SEGMENT,
    stage: STAGE,
    priority: PRIORITY,
    target: { type: "string" },
    deadline: { type: "string", format: "date" },
    exit_criteria: { type: "array", items: { type: "string" } },
    tasks: { type: "array", items: { type: "number" } },
    notes: { type: "string" },
  },
  required: ["slug", "name", "project", "venture", "stage", "priority", "target", "exit_criteria", "tasks"],
};

export const MILESTONE_LIST_SCHEMA = {
  type: "object" as const,
  properties: {
    venture: SLUG_SEGMENT,
    project: SLUG_SEGMENT,
    stage: { oneOf: [STAGE, { type: "array", items: STAGE }] },
    priority: { oneOf: [PRIORITY, { type: "array", items: PRIORITY }] },
    due_within_days: { type: "number" },
    overdue: { type: "boolean" },
    sort_by: { type: "string", enum: ["priority", "deadline", "created", "updated", "name"] },
    sort_order: { type: "string", enum: ["asc", "desc"] },
    limit: { type: "number" },
    offset: { type: "number" },
  },
};

export const MILESTONE_GET_SCHEMA = {
  type: "object" as const,
  properties: { venture: SLUG_SEGMENT, project: SLUG_SEGMENT, slug: SLUG_SEGMENT },
  required: ["venture", "project", "slug"],
};

export const MILESTONE_UPDATE_SCHEMA = {
  type: "object" as const,
  properties: {
    venture: SLUG_SEGMENT, project: SLUG_SEGMENT, slug: SLUG_SEGMENT,
    patch: { type: "object" },
  },
  required: ["venture", "project", "slug", "patch"],
};

export const MILESTONE_CLOSE_SCHEMA = {
  type: "object" as const,
  properties: {
    venture: SLUG_SEGMENT, project: SLUG_SEGMENT, slug: SLUG_SEGMENT,
    stage: CLOSE_STAGE,
    retro_md: { type: "string" },
  },
  required: ["venture", "project", "slug", "stage"],
};

export const VENTURE_TREE_SCHEMA = {
  type: "object" as const,
  properties: { slug: SLUG_SEGMENT },
  required: ["slug"],
};

export const VENTURE_CO_LINKS_SCHEMA = {
  type: "object" as const,
  properties: { slug: SLUG_SEGMENT },
  required: ["slug"],
};
