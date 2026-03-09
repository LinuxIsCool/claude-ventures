/**
 * Markdown Store
 *
 * Persists ventures as markdown files with YAML frontmatter.
 * Files organized by stage: active/, exploring/, seed/, etc.
 */

import { readdir, readFile, writeFile, unlink } from "fs/promises";
import { existsSync } from "fs";
import { join, basename } from "path";
import matter from "gray-matter";
import { nanoid } from "nanoid";

import type {
  Venture,
  CreateVentureInput,
  UpdateVentureInput,
  VentureQuery,
  VentureFilter,
  Milestone,
  Deliverable,
  Invoice,
  VentureStageValue,
  VentureStore,
} from "../types";
import {
  paths,
  ensureDirectories,
  getVentureDirectory,
  loadConfig,
} from "../config";
import { calculatePriority, createDefaultContext, sortByPriority } from "../priority/calculator";

// =============================================================================
// ID Generation
// =============================================================================

function generateVentureId(): string {
  return `ven-${nanoid(8)}`;
}

function generateMilestoneId(): string {
  return `ms-${nanoid(6)}`;
}

function generateDeliverableId(): string {
  return `del-${nanoid(6)}`;
}

function generateInvoiceId(): string {
  return `inv-${nanoid(6)}`;
}

// =============================================================================
// File Operations
// =============================================================================

function ventureToFilename(venture: Venture): string {
  const safeTitle = venture.title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 50);
  return `${safeTitle}.md`;
}

function parseVenture(content: string, filePath: string): Venture {
  const { data, content: notes } = matter(content);

  return {
    id: data.id || basename(filePath, ".md"),
    title: data.title || "Untitled Venture",
    description: data.description,
    type: data.type || "creative",
    stage: data.stage || "seed",
    priority: data.priority || "none",
    calculated_priority: data.calculated_priority,
    created_at: data.created_at || data.created || new Date().toISOString(),
    updated_at: data.updated_at || data.updated || new Date().toISOString(),
    started_at: data.started_at,
    deadlines: data.deadlines || [],
    milestones: data.milestones || [],
    co_venturers: data.co_venturers || [],
    financial: data.financial,
    tags: data.tags || [],
    links: data.links,
    related_ventures: data.related_ventures || data["related-ventures"] || [],
    data: data.data,
    integrations: data.integrations,
    notes: notes.trim() || undefined,
    file_path: filePath,
  };
}

function serializeVenture(venture: Venture): string {
  const { notes, file_path, ...frontmatter } = venture;

  const cleanFrontmatter = Object.fromEntries(
    Object.entries(frontmatter).filter(([, v]) => v !== undefined)
  );

  return matter.stringify(notes || "", cleanFrontmatter);
}

async function readVenturesFromDirectory(dirPath: string): Promise<Venture[]> {
  if (!existsSync(dirPath)) return [];

  const files = await readdir(dirPath);
  const mdFiles = files.filter((f) => f.endsWith(".md"));

  const ventures: Venture[] = [];

  for (const file of mdFiles) {
    try {
      const filePath = join(dirPath, file);
      const content = await readFile(filePath, "utf-8");
      const venture = parseVenture(content, filePath);
      ventures.push(venture);
    } catch (err) {
      console.error(`Failed to read venture ${file}:`, err);
    }
  }

  return ventures;
}

async function getAllVentures(): Promise<Venture[]> {
  ensureDirectories();

  const stages = ["seed", "exploring", "active", "sustaining", "dormant", "harvesting"];
  const results = await Promise.all(
    stages.map((stage) => readVenturesFromDirectory(getVentureDirectory(stage as VentureStageValue)))
  );

  return results.flat();
}

// =============================================================================
// Filter & Sort
// =============================================================================

function matchesFilter<T>(value: T, filter: T | T[] | undefined): boolean {
  if (filter === undefined) return true;
  if (Array.isArray(filter)) return filter.includes(value);
  return value === filter;
}

function applyFilters(ventures: Venture[], filter?: VentureFilter): Venture[] {
  if (!filter) return ventures;

  return ventures.filter((venture) => {
    if (!matchesFilter(venture.type, filter.type)) return false;
    if (!matchesFilter(venture.stage, filter.stage)) return false;
    if (!matchesFilter(venture.priority, filter.priority)) return false;

    if (filter.tags && filter.tags.length > 0) {
      const hasMatchingTag = filter.tags.some((tag) =>
        venture.tags.includes(tag)
      );
      if (!hasMatchingTag) return false;
    }

    if (filter.has_deadline !== undefined) {
      const hasDeadline = venture.deadlines.length > 0;
      if (hasDeadline !== filter.has_deadline) return false;
    }

    if (filter.overdue !== undefined) {
      const isOverdue =
        venture.deadlines.some((d) => new Date(d.date) < new Date()) &&
        venture.stage !== "harvesting";
      if (!!isOverdue !== filter.overdue) return false;
    }

    if (filter.due_within_days !== undefined && venture.deadlines.length > 0) {
      const nearestDate = venture.deadlines
        .map((d) => new Date(d.date).getTime())
        .sort((a, b) => a - b)[0];
      const daysUntil = (nearestDate - Date.now()) / (1000 * 60 * 60 * 24);
      if (daysUntil > filter.due_within_days) return false;
    }

    if (filter.min_priority !== undefined) {
      const score = calculatePriority(venture, createDefaultContext());
      if (score.total < filter.min_priority) return false;
    }

    return true;
  });
}

function applySorting(
  ventures: Venture[],
  sortBy?: string,
  sortOrder?: "asc" | "desc"
): Venture[] {
  if (!sortBy || sortBy === "priority") {
    return sortByPriority(ventures);
  }

  const sorted = [...ventures].sort((a, b) => {
    switch (sortBy) {
      case "deadline": {
        const aDeadline = a.deadlines[0]?.date || "9999-12-31";
        const bDeadline = b.deadlines[0]?.date || "9999-12-31";
        return aDeadline.localeCompare(bDeadline);
      }
      case "created":
        return a.created_at.localeCompare(b.created_at);
      case "updated":
        return a.updated_at.localeCompare(b.updated_at);
      case "stage": {
        const stageOrder = ["seed", "exploring", "active", "sustaining", "dormant", "harvesting"];
        return stageOrder.indexOf(a.stage) - stageOrder.indexOf(b.stage);
      }
      case "title":
        return a.title.localeCompare(b.title);
      default:
        return 0;
    }
  });

  return sortOrder === "desc" ? sorted.reverse() : sorted;
}

// =============================================================================
// Store Implementation
// =============================================================================

export function createMarkdownStore(): VentureStore {
  return {
    async create(input: CreateVentureInput): Promise<Venture> {
      ensureDirectories();

      const now = new Date().toISOString();
      const venture: Venture = {
        ...input,
        id: generateVentureId(),
        created_at: now,
        updated_at: now,
        deadlines: input.deadlines || [],
        milestones: input.milestones || [],
        co_venturers: input.co_venturers || [],
        tags: input.tags || [],
        related_ventures: input.related_ventures || [],
      };

      venture.calculated_priority = calculatePriority(
        venture,
        createDefaultContext()
      ).total;

      const dir = getVentureDirectory(venture.stage);
      const filename = ventureToFilename(venture);
      const filePath = join(dir, filename);

      venture.file_path = filePath;

      const content = serializeVenture(venture);
      await writeFile(filePath, content, "utf-8");

      return venture;
    },

    async get(id: string): Promise<Venture | null> {
      const ventures = await getAllVentures();
      return ventures.find((v) => v.id === id) || null;
    },

    async update(id: string, input: UpdateVentureInput): Promise<Venture> {
      const venture = await this.get(id);
      if (!venture) {
        throw new Error(`Venture not found: ${id}`);
      }

      const updated: Venture = {
        ...venture,
        ...input,
        id: venture.id,
        created_at: venture.created_at,
        updated_at: new Date().toISOString(),
      };

      updated.calculated_priority = calculatePriority(
        updated,
        createDefaultContext()
      ).total;

      const newDir = getVentureDirectory(updated.stage);
      const filename = ventureToFilename(updated);
      const newPath = join(newDir, filename);

      if (venture.file_path && venture.file_path !== newPath) {
        try {
          await unlink(venture.file_path);
        } catch {
          // Ignore if file doesn't exist
        }
      }

      updated.file_path = newPath;

      const content = serializeVenture(updated);
      await writeFile(newPath, content, "utf-8");

      return updated;
    },

    async delete(id: string): Promise<void> {
      const venture = await this.get(id);
      if (!venture) {
        throw new Error(`Venture not found: ${id}`);
      }

      if (venture.file_path) {
        await unlink(venture.file_path);
      }
    },

    async list(query?: VentureQuery): Promise<Venture[]> {
      let ventures = await getAllVentures();

      ventures = applyFilters(ventures, query?.filter);
      ventures = applySorting(ventures, query?.sort_by, query?.sort_order);

      if (query?.offset) {
        ventures = ventures.slice(query.offset);
      }
      if (query?.limit) {
        ventures = ventures.slice(0, query.limit);
      }

      return ventures;
    },

    async search(text: string): Promise<Venture[]> {
      const ventures = await getAllVentures();
      const searchLower = text.toLowerCase();

      const results = ventures.filter((venture) => {
        return (
          venture.title.toLowerCase().includes(searchLower) ||
          venture.description?.toLowerCase().includes(searchLower) ||
          venture.notes?.toLowerCase().includes(searchLower) ||
          venture.tags.some((tag) => tag.toLowerCase().includes(searchLower)) ||
          venture.co_venturers.some((cv) => cv.name.toLowerCase().includes(searchLower))
        );
      });

      return sortByPriority(results);
    },

    async addMilestone(
      ventureId: string,
      milestone: Omit<Milestone, "id">
    ): Promise<Milestone> {
      const venture = await this.get(ventureId);
      if (!venture) {
        throw new Error(`Venture not found: ${ventureId}`);
      }

      const newMilestone: Milestone = {
        ...milestone,
        id: generateMilestoneId(),
        deliverables: milestone.deliverables || [],
        completed: milestone.completed || false,
        status: milestone.status || "pending",
      };

      venture.milestones.push(newMilestone);
      await this.update(ventureId, { milestones: venture.milestones });

      return newMilestone;
    },

    async updateMilestone(
      ventureId: string,
      milestoneId: string,
      updates: Partial<Milestone>
    ): Promise<Milestone> {
      const venture = await this.get(ventureId);
      if (!venture) {
        throw new Error(`Venture not found: ${ventureId}`);
      }

      const milestoneIndex = venture.milestones.findIndex(
        (m) => m.id === milestoneId
      );
      if (milestoneIndex === -1) {
        throw new Error(`Milestone not found: ${milestoneId}`);
      }

      const updated = {
        ...venture.milestones[milestoneIndex],
        ...updates,
        id: milestoneId,
      };
      venture.milestones[milestoneIndex] = updated;

      await this.update(ventureId, { milestones: venture.milestones });

      return updated;
    },

    async completeMilestone(ventureId: string, milestoneId: string): Promise<void> {
      await this.updateMilestone(ventureId, milestoneId, {
        completed: true,
        status: "completed",
        completed_at: new Date().toISOString(),
      });
    },

    async addDeliverable(
      ventureId: string,
      milestoneId: string,
      deliverable: Omit<Deliverable, "id">
    ): Promise<Deliverable> {
      const venture = await this.get(ventureId);
      if (!venture) {
        throw new Error(`Venture not found: ${ventureId}`);
      }

      const milestone = venture.milestones.find((m) => m.id === milestoneId);
      if (!milestone) {
        throw new Error(`Milestone not found: ${milestoneId}`);
      }

      const newDeliverable: Deliverable = {
        ...deliverable,
        id: generateDeliverableId(),
        completed: deliverable.completed || false,
      };

      milestone.deliverables.push(newDeliverable);
      await this.update(ventureId, { milestones: venture.milestones });

      return newDeliverable;
    },

    async completeDeliverable(
      ventureId: string,
      milestoneId: string,
      deliverableId: string
    ): Promise<void> {
      const venture = await this.get(ventureId);
      if (!venture) {
        throw new Error(`Venture not found: ${ventureId}`);
      }

      const milestone = venture.milestones.find((m) => m.id === milestoneId);
      if (!milestone) {
        throw new Error(`Milestone not found: ${milestoneId}`);
      }

      const deliverable = milestone.deliverables.find(
        (d) => d.id === deliverableId
      );
      if (!deliverable) {
        throw new Error(`Deliverable not found: ${deliverableId}`);
      }

      deliverable.completed = true;
      deliverable.completed_at = new Date().toISOString();

      await this.update(ventureId, { milestones: venture.milestones });
    },

    async transitionStage(
      ventureId: string,
      newStage: VentureStageValue,
      notes?: string
    ): Promise<Venture> {
      const venture = await this.get(ventureId);
      if (!venture) {
        throw new Error(`Venture not found: ${ventureId}`);
      }

      const updates: UpdateVentureInput = {
        stage: newStage,
      };

      if (newStage === "active" && !venture.started_at) {
        updates.started_at = new Date().toISOString();
      }

      if (notes) {
        const existingNotes = venture.notes || "";
        const timestamp = new Date().toISOString().split("T")[0];
        updates.notes = `${existingNotes}\n\n## ${timestamp}: Stage → ${newStage}\n\n${notes}`.trim();
      }

      return this.update(ventureId, updates);
    },

    async addInvoice(
      ventureId: string,
      invoice: Omit<Invoice, "id">
    ): Promise<Invoice> {
      const venture = await this.get(ventureId);
      if (!venture) {
        throw new Error(`Venture not found: ${ventureId}`);
      }

      const newInvoice: Invoice = {
        ...invoice,
        id: generateInvoiceId(),
        paid: invoice.paid || false,
      };

      if (!venture.financial) {
        const config = loadConfig();
        venture.financial = {
          status: "unfunded",
          invoices: [],
          total_invoiced: { amount: 0, currency: config.default_currency },
          total_received: { amount: 0, currency: config.default_currency },
          outstanding: { amount: 0, currency: config.default_currency },
        };
      }

      const projectCurrency = venture.financial.total_invoiced.currency;
      if (newInvoice.amount.currency !== projectCurrency) {
        throw new Error(
          `Invoice currency (${newInvoice.amount.currency}) does not match venture currency (${projectCurrency}).`
        );
      }

      venture.financial.invoices.push(newInvoice);

      venture.financial.total_invoiced.amount = venture.financial.invoices.reduce(
        (sum, inv) => sum + inv.amount.amount,
        0
      );
      venture.financial.total_received.amount = venture.financial.invoices
        .filter((inv) => inv.paid)
        .reduce((sum, inv) => sum + inv.amount.amount, 0);
      venture.financial.outstanding.amount =
        venture.financial.total_invoiced.amount -
        venture.financial.total_received.amount;

      await this.update(ventureId, { financial: venture.financial });

      return newInvoice;
    },

    async markInvoicePaid(ventureId: string, invoiceId: string): Promise<void> {
      const venture = await this.get(ventureId);
      if (!venture || !venture.financial) {
        throw new Error(`Venture not found: ${ventureId}`);
      }

      const invoice = venture.financial.invoices.find((i) => i.id === invoiceId);
      if (!invoice) {
        throw new Error(`Invoice not found: ${invoiceId}`);
      }

      invoice.paid = true;
      invoice.paid_date = new Date().toISOString();

      venture.financial.total_received.amount = venture.financial.invoices
        .filter((inv) => inv.paid)
        .reduce((sum, inv) => sum + inv.amount.amount, 0);
      venture.financial.outstanding.amount =
        venture.financial.total_invoiced.amount -
        venture.financial.total_received.amount;

      await this.update(ventureId, { financial: venture.financial });
    },
  };
}

export const store = createMarkdownStore();
