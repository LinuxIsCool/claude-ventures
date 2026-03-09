#!/usr/bin/env bun
/**
 * Claude Ventures MCP Server
 *
 * Venture portfolio management via Model Context Protocol.
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  ListToolsRequestSchema,
  CallToolRequestSchema,
  type Tool,
} from "@modelcontextprotocol/sdk/types.js";

import { store } from "../store/markdown";
import { ensureDirectories, isInitialized, paths, loadConfig, saveConfig } from "../config";
import { calculatePriority, createDefaultContext, getUrgentVentures } from "../priority/calculator";
import type { CreateVentureInput, UpdateVentureInput, VentureQuery, VentureFilter } from "../types";

import {
  ventureCreateSchema,
  ventureListSchema,
  ventureGetSchema,
  ventureUpdateSchema,
  ventureDeleteSchema,
  ventureSearchSchema,
  ventureTransitionSchema,
  addMilestoneSchema,
  addDeliverableSchema,
  completeItemSchema,
  addInvoiceSchema,
  markPaidSchema,
  ventureFinancialsSchema,
  ventureTimelineSchema,
  venturePortfolioSchema,
  ventureInitSchema,
} from "./tools/schemas";

// =============================================================================
// Response Helpers
// =============================================================================

function textResponse(text: string) {
  return { content: [{ type: "text" as const, text }] };
}

function errorResponse(message: string) {
  return { content: [{ type: "text" as const, text: `Error: ${message}` }], isError: true };
}

function jsonResponse(data: unknown) {
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

// =============================================================================
// Main Server
// =============================================================================

async function main() {
  const server = new Server(
    { name: "claude-ventures", version: "0.1.0" },
    { capabilities: { tools: {} } }
  );

  const initialized = isInitialized();

  server.setRequestHandler(ListToolsRequestSchema, async () => {
    const tools: Tool[] = [];

    if (!initialized) {
      tools.push({
        name: "venture_init",
        description: "Initialize the ventures directory. Required before using other venture tools.",
        inputSchema: ventureInitSchema,
      });
    }

    tools.push(
      {
        name: "venture_create",
        description: "Create a new venture. Specify type (creative/research/consulting/infrastructure/community), stage, deadlines, co-venturers.",
        inputSchema: ventureCreateSchema,
      },
      {
        name: "venture_list",
        description: "List ventures with optional filtering by type, stage, priority, tags. Sorted by calculated priority by default.",
        inputSchema: ventureListSchema,
      },
      {
        name: "venture_get",
        description: "Get detailed information about a specific venture including milestones, co-venturers, and financials.",
        inputSchema: ventureGetSchema,
      },
      {
        name: "venture_update",
        description: "Update venture fields. Can change title, type, stage, priority, deadlines, co-venturers, tags, links, or add notes.",
        inputSchema: ventureUpdateSchema,
      },
      {
        name: "venture_delete",
        description: "Delete a venture permanently.",
        inputSchema: ventureDeleteSchema,
      },
      {
        name: "venture_search",
        description: "Search ventures by text. Matches title, description, notes, tags, and co-venturer names.",
        inputSchema: ventureSearchSchema,
      },
      {
        name: "venture_transition",
        description: "Transition a venture to a new stage (seed/exploring/active/sustaining/dormant/harvesting). Ventures can move in any direction.",
        inputSchema: ventureTransitionSchema,
      },
      {
        name: "venture_add_milestone",
        description: "Add a milestone to a venture.",
        inputSchema: addMilestoneSchema,
      },
      {
        name: "venture_add_deliverable",
        description: "Add a deliverable to a milestone within a venture.",
        inputSchema: addDeliverableSchema,
      },
      {
        name: "venture_complete_item",
        description: "Mark a milestone or deliverable as completed. Omit deliverable_id to complete the milestone.",
        inputSchema: completeItemSchema,
      },
      {
        name: "venture_add_invoice",
        description: "Add an invoice to a venture for financial tracking.",
        inputSchema: addInvoiceSchema,
      },
      {
        name: "venture_mark_paid",
        description: "Mark an invoice as paid.",
        inputSchema: markPaidSchema,
      },
      {
        name: "venture_financials",
        description: "Get a financial summary across all ventures.",
        inputSchema: ventureFinancialsSchema,
      },
      {
        name: "venture_timeline",
        description: "Get a timeline view of ventures grouped by deadline proximity.",
        inputSchema: ventureTimelineSchema,
      },
      {
        name: "venture_portfolio",
        description: "Get a portfolio-level dashboard: active ventures, approaching deadlines, dormant ventures with strategic connections, portfolio health.",
        inputSchema: venturePortfolioSchema,
      }
    );

    return { tools };
  });

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;

    try {
      if (name === "venture_init") {
        ensureDirectories();
        const config = loadConfig();
        const typedArgs = args as { default_currency?: string; data_drive_path?: string };
        if (typedArgs?.default_currency) {
          config.default_currency = typedArgs.default_currency;
        }
        if (typedArgs?.data_drive_path) {
          config.data_drive_path = typedArgs.data_drive_path;
        }
        saveConfig(config);
        return textResponse(
          `Ventures directory initialized at ${paths.base}\n\nStage directories created: seed, exploring, active, sustaining, dormant, harvesting\n\nYou can now create ventures using venture_create.`
        );
      }

      if (!initialized && !isInitialized()) {
        return errorResponse("Ventures not initialized. Run venture_init first.");
      }

      switch (name) {
        case "venture_create": {
          const input = args as {
            title: string;
            type: string;
            stage?: string;
            priority?: string;
            description?: string;
            tags?: string[];
            co_venturers?: Array<{ name: string; role: string; contact?: string }>;
            deadlines?: Array<{ date: string; label?: string; type?: string; time?: string }>;
            links?: Record<string, string>;
            related_ventures?: string[];
            data?: { root?: string; transcripts?: string; media?: string; datasets?: string };
          };

          const createInput: CreateVentureInput = {
            title: input.title,
            type: input.type as CreateVentureInput["type"],
            stage: (input.stage as CreateVentureInput["stage"]) || "seed",
            priority: (input.priority as CreateVentureInput["priority"]) || "none",
            description: input.description,
            tags: input.tags || [],
            co_venturers: input.co_venturers || [],
            deadlines: (input.deadlines || []).map((d) => ({
              date: d.date,
              label: d.label,
              type: (d.type as "external" | "internal") || "internal",
              time: d.time,
            })),
            milestones: [],
            related_ventures: input.related_ventures || [],
            links: input.links,
            data: input.data as CreateVentureInput["data"],
          };

          const venture = await store.create(createInput);
          const score = calculatePriority(venture, createDefaultContext());

          return textResponse(
            `Created venture: ${venture.title}\n\nID: ${venture.id}\nType: ${venture.type}\nStage: ${venture.stage}\nPriority Score: ${score.total}/100\nFile: ${venture.file_path}`
          );
        }

        case "venture_list": {
          const input = args as {
            type?: string;
            stage?: string;
            priority?: string;
            tags?: string[];
            overdue?: boolean;
            due_within_days?: number;
            min_priority?: number;
            sort_by?: string;
            sort_order?: "asc" | "desc";
            limit?: number;
          };

          const query: VentureQuery = {
            filter: {
              type: input.type as VentureFilter["type"],
              stage: input.stage as VentureFilter["stage"],
              priority: input.priority as VentureFilter["priority"],
              tags: input.tags,
              overdue: input.overdue,
              due_within_days: input.due_within_days,
              min_priority: input.min_priority,
            },
            sort_by: (input.sort_by as VentureQuery["sort_by"]) || "priority",
            sort_order: input.sort_order,
            limit: input.limit,
          };

          const ventures = await store.list(query);

          if (ventures.length === 0) {
            return textResponse("No ventures found matching the criteria.");
          }

          const lines = ventures.map((v, i) => {
            const deadline = v.deadlines[0] ? ` (due: ${v.deadlines[0].date})` : "";
            const coVenturers = v.co_venturers.length > 0
              ? ` [${v.co_venturers.map((cv) => cv.name).join(", ")}]`
              : "";
            return `${i + 1}. [${v.calculated_priority}] ${v.title}${coVenturers}${deadline}\n   ID: ${v.id} | Stage: ${v.stage} | Type: ${v.type}`;
          });

          return textResponse(
            `Found ${ventures.length} venture(s):\n\n${lines.join("\n\n")}`
          );
        }

        case "venture_get": {
          const { id } = args as { id: string };
          const venture = await store.get(id);

          if (!venture) {
            return errorResponse(`Venture not found: ${id}`);
          }

          const score = calculatePriority(venture, createDefaultContext());

          return jsonResponse({
            ...venture,
            priority_score: score,
          });
        }

        case "venture_update": {
          const { id, ...updates } = args as { id: string } & UpdateVentureInput;
          const venture = await store.update(id, updates);
          const score = calculatePriority(venture, createDefaultContext());

          return textResponse(
            `Updated venture: ${venture.title}\n\nNew priority score: ${score.total}/100`
          );
        }

        case "venture_delete": {
          const { id } = args as { id: string };
          const venture = await store.get(id);

          if (!venture) {
            return errorResponse(`Venture not found: ${id}`);
          }

          await store.delete(id);
          return textResponse(`Deleted venture: ${venture.title}`);
        }

        case "venture_search": {
          const { query } = args as { query: string };
          const ventures = await store.search(query);

          if (ventures.length === 0) {
            return textResponse(`No ventures found matching: "${query}"`);
          }

          const lines = ventures.map((v) => {
            return `- [${v.calculated_priority}] ${v.title} (${v.stage})\n  ID: ${v.id}`;
          });

          return textResponse(
            `Found ${ventures.length} venture(s) matching "${query}":\n\n${lines.join("\n\n")}`
          );
        }

        case "venture_transition": {
          const input = args as { id: string; stage: string; notes?: string };

          const venture = await store.transitionStage(
            input.id,
            input.stage as "seed" | "exploring" | "active" | "sustaining" | "dormant" | "harvesting",
            input.notes
          );

          return textResponse(
            `Transitioned "${venture.title}" to ${input.stage}\n\nPriority: ${venture.calculated_priority}/100`
          );
        }

        case "venture_add_milestone": {
          const input = args as {
            venture_id: string;
            title: string;
            description?: string;
            deadline?: { date: string; type?: string };
          };

          const milestone = await store.addMilestone(input.venture_id, {
            title: input.title,
            description: input.description,
            status: "pending",
            deadline: input.deadline
              ? { date: input.deadline.date, type: (input.deadline.type as "external" | "internal") || "internal" }
              : undefined,
            deliverables: [],
            completed: false,
          });

          return textResponse(
            `Added milestone: ${milestone.title}\n\nID: ${milestone.id}${milestone.deadline ? `\nDeadline: ${milestone.deadline.date}` : ""}`
          );
        }

        case "venture_add_deliverable": {
          const input = args as {
            venture_id: string;
            milestone_id: string;
            title: string;
            description?: string;
            deadline?: { date: string; type?: string };
          };

          const deliverable = await store.addDeliverable(
            input.venture_id,
            input.milestone_id,
            {
              title: input.title,
              description: input.description,
              deadline: input.deadline
                ? { date: input.deadline.date, type: (input.deadline.type as "external" | "internal") || "internal" }
                : undefined,
              completed: false,
            }
          );

          return textResponse(`Added deliverable: ${deliverable.title}\n\nID: ${deliverable.id}`);
        }

        case "venture_complete_item": {
          const input = args as {
            venture_id: string;
            milestone_id: string;
            deliverable_id?: string;
          };

          if (input.deliverable_id) {
            await store.completeDeliverable(
              input.venture_id,
              input.milestone_id,
              input.deliverable_id
            );
            return textResponse(`Marked deliverable ${input.deliverable_id} as completed.`);
          } else {
            await store.completeMilestone(input.venture_id, input.milestone_id);
            return textResponse(`Marked milestone ${input.milestone_id} as completed.`);
          }
        }

        case "venture_add_invoice": {
          const input = args as {
            venture_id: string;
            amount: number;
            currency?: string;
            description?: string;
            date?: string;
          };

          const invoice = await store.addInvoice(input.venture_id, {
            date: input.date || new Date().toISOString().split("T")[0],
            amount: {
              amount: input.amount,
              currency: input.currency || "CAD",
            },
            description: input.description,
            paid: false,
          });

          return textResponse(
            `Added invoice: ${invoice.amount.currency} ${invoice.amount.amount}\n\nID: ${invoice.id}\nDate: ${invoice.date}`
          );
        }

        case "venture_mark_paid": {
          const { venture_id, invoice_id } = args as {
            venture_id: string;
            invoice_id: string;
          };

          await store.markInvoicePaid(venture_id, invoice_id);
          return textResponse(`Marked invoice ${invoice_id} as paid.`);
        }

        case "venture_financials": {
          const input = args as { type?: string; stage?: string };

          const ventures = await store.list({
            filter: {
              type: input.type as VentureFilter["type"],
              stage: input.stage as VentureFilter["stage"],
            },
          });

          const byCurrency: Record<string, { invoiced: number; received: number; outstanding: number }> = {};

          for (const venture of ventures) {
            if (venture.financial) {
              const currency = venture.financial.total_invoiced.currency;
              if (!byCurrency[currency]) {
                byCurrency[currency] = { invoiced: 0, received: 0, outstanding: 0 };
              }
              byCurrency[currency].invoiced += venture.financial.total_invoiced.amount;
              byCurrency[currency].received += venture.financial.total_received.amount;
              byCurrency[currency].outstanding += venture.financial.outstanding.amount;
            }
          }

          const lines = Object.entries(byCurrency).map(([currency, totals]) => {
            return `${currency}:\n  Invoiced: ${totals.invoiced.toFixed(2)}\n  Received: ${totals.received.toFixed(2)}\n  Outstanding: ${totals.outstanding.toFixed(2)}`;
          });

          if (lines.length === 0) {
            return textResponse("No financial data found for the selected ventures.");
          }

          return textResponse(
            `Financial Summary (${ventures.length} ventures):\n\n${lines.join("\n\n")}`
          );
        }

        case "venture_timeline": {
          const input = args as { days_ahead?: number; include_overdue?: boolean };
          const daysAhead = input.days_ahead ?? 90;
          const includeOverdue = input.include_overdue ?? true;

          const allVentures = await store.list({});

          const overdue: typeof allVentures = [];
          const thisWeek: typeof allVentures = [];
          const thisMonth: typeof allVentures = [];
          const thisQuarter: typeof allVentures = [];
          const noDeadline: typeof allVentures = [];

          const now = new Date();

          for (const venture of allVentures) {
            if (venture.stage === "harvesting") continue;

            if (venture.deadlines.length === 0) {
              noDeadline.push(venture);
              continue;
            }

            const nearestDate = new Date(
              venture.deadlines
                .map((d) => new Date(d.date).getTime())
                .sort((a, b) => a - b)[0]
            );
            const daysUntil = (nearestDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24);

            if (daysUntil < 0) {
              if (includeOverdue) overdue.push(venture);
            } else if (daysUntil <= 7) {
              thisWeek.push(venture);
            } else if (daysUntil <= 30) {
              thisMonth.push(venture);
            } else if (daysUntil <= daysAhead) {
              thisQuarter.push(venture);
            }
          }

          const sections: string[] = [];

          if (overdue.length > 0) {
            sections.push(`## OVERDUE (${overdue.length})\n${overdue.map((v) => `- [${v.calculated_priority}] ${v.title} (due: ${v.deadlines[0]?.date})`).join("\n")}`);
          }
          if (thisWeek.length > 0) {
            sections.push(`## This Week (${thisWeek.length})\n${thisWeek.map((v) => `- [${v.calculated_priority}] ${v.title} (due: ${v.deadlines[0]?.date})`).join("\n")}`);
          }
          if (thisMonth.length > 0) {
            sections.push(`## This Month (${thisMonth.length})\n${thisMonth.map((v) => `- [${v.calculated_priority}] ${v.title} (due: ${v.deadlines[0]?.date})`).join("\n")}`);
          }
          if (thisQuarter.length > 0) {
            sections.push(`## Next ${daysAhead} Days (${thisQuarter.length})\n${thisQuarter.map((v) => `- [${v.calculated_priority}] ${v.title} (due: ${v.deadlines[0]?.date})`).join("\n")}`);
          }
          if (noDeadline.length > 0) {
            sections.push(`## No Deadline (${noDeadline.length})\n${noDeadline.map((v) => `- [${v.calculated_priority}] ${v.title}`).join("\n")}`);
          }

          return textResponse(
            sections.length > 0
              ? `# Venture Timeline\n\n${sections.join("\n\n")}`
              : "No active ventures found."
          );
        }

        case "venture_portfolio": {
          const allVentures = await store.list({});

          const byStage: Record<string, typeof allVentures> = {};
          for (const v of allVentures) {
            if (!byStage[v.stage]) byStage[v.stage] = [];
            byStage[v.stage].push(v);
          }

          const urgent = getUrgentVentures(allVentures, 14);

          const sections: string[] = [];

          sections.push(`# Venture Portfolio\n\nTotal: ${allVentures.length} ventures`);

          // Stage breakdown
          const stageOrder = ["active", "exploring", "seed", "sustaining", "dormant", "harvesting"];
          const stageSummary = stageOrder
            .filter((s) => byStage[s]?.length > 0)
            .map((s) => `- **${s}**: ${byStage[s].length}`)
            .join("\n");
          sections.push(`## By Stage\n${stageSummary}`);

          // Urgent deadlines
          if (urgent.length > 0) {
            const urgentLines = urgent.map((v) => {
              const deadline = v.deadlines[0];
              const daysUntil = deadline
                ? Math.round((new Date(deadline.date).getTime() - Date.now()) / (1000 * 60 * 60 * 24))
                : null;
              const urgency = daysUntil !== null
                ? daysUntil < 0 ? "OVERDUE" : `${daysUntil}d`
                : "";
              return `- [${v.calculated_priority}] **${v.title}** — ${deadline?.label || deadline?.date} (${urgency})`;
            });
            sections.push(`## Approaching Deadlines\n${urgentLines.join("\n")}`);
          }

          // Active ventures detail
          if (byStage["active"]?.length > 0) {
            const activeLines = byStage["active"].map((v) => {
              const coVenturers = v.co_venturers.length > 0
                ? ` with ${v.co_venturers.map((cv) => cv.name).join(", ")}`
                : "";
              return `- [${v.calculated_priority}] **${v.title}**${coVenturers}`;
            });
            sections.push(`## Active Ventures\n${activeLines.join("\n")}`);
          }

          // Dormant ventures with connections
          if (byStage["dormant"]?.length > 0) {
            const dormantWithConnections = byStage["dormant"].filter(
              (v) => v.related_ventures.length > 0
            );
            if (dormantWithConnections.length > 0) {
              const dormantLines = dormantWithConnections.map((v) => {
                return `- ${v.title} (connected to: ${v.related_ventures.join(", ")})`;
              });
              sections.push(`## Dormant with Active Connections\n${dormantLines.join("\n")}`);
            }
          }

          return textResponse(sections.join("\n\n"));
        }

        default:
          return errorResponse(`Unknown tool: ${name}`);
      }
    } catch (err) {
      return errorResponse(err instanceof Error ? err.message : String(err));
    }
  });

  const transport = new StdioServerTransport();
  await server.connect(transport);

  console.error("Claude Ventures MCP server started");
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
