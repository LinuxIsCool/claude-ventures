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
