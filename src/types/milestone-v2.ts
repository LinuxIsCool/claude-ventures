/**
 * Milestone (v2) — the leaf entity in the fractal V/P/M hierarchy.
 * Lives at ~/.claude/local/ventures/{venture}/projects/{project}/milestones/{slug}.md.
 *
 * Tasks live in claude-backlog and FK back to milestones via parent_id + parent_type.
 *
 * Named MilestoneV2 to avoid clash with the legacy embedded Milestone interface
 * in src/types/index.ts (which Task 13 will rename to LegacyEmbeddedMilestone).
 */

import type { PriorityLevelValue, VentureStageValue } from "./index";

/**
 * Milestone lifecycle states. Currently identical to VentureStageValue per
 * Phase 0 spec (Shawn override of false-fractal warning, 2026-05-14).
 * If milestones ever diverge to a different state set, change this alias to a
 * milestone-local literal union without touching consumer code.
 */
export type MilestoneStageValue = VentureStageValue;

export interface MilestoneV2 {
  slug: string;                    // local slug ("m1-spec"), unique within project
  name: string;
  description?: string;
  project: string;                 // FK — project slug (local within venture)
  venture: string;                 // denormalized FK for query speed
  stage: MilestoneStageValue;      // 6-state, same as venture (alias above)
  priority: PriorityLevelValue;
  target: string;                  // human-readable target description
  deadline?: string;               // ISO date
  exit_criteria: string[];         // checklist items for completion
  calculated_priority?: number;    // 0-100, computed at list-time — see priority/item-priority.ts
  docs_dir?: string;
  tasks: number[];                 // claude-backlog task IDs (auto-derived from FK back-refs)
  notes?: string;                  // markdown body
  created_at: string;
  updated_at: string;
  file_path?: string;
}

export type CreateMilestoneInput = Omit<
  MilestoneV2,
  "created_at" | "updated_at" | "file_path"
>;

export type UpdateMilestoneInput = Partial<
  Omit<MilestoneV2, "slug" | "project" | "venture" | "created_at" | "file_path">
>;

export interface MilestoneFilter {
  venture?: string;
  project?: string;
  stage?: MilestoneStageValue | MilestoneStageValue[];
  priority?: PriorityLevelValue | PriorityLevelValue[];
  due_within_days?: number;
  overdue?: boolean;
}

export interface MilestoneQuery {
  filter?: MilestoneFilter;
  sort_by?: "priority" | "deadline" | "created" | "updated" | "name";
  sort_order?: "asc" | "desc";
  limit?: number;
  offset?: number;
}
