/**
 * Project — the middle level of the fractal V/P/M hierarchy.
 * Lives at ~/.claude/local/ventures/{venture}/projects/{slug}/project.md.
 */

import type { PriorityLevelValue, VentureStageValue } from "./index";

/**
 * Project lifecycle states. Currently identical to VentureStageValue per
 * Phase 0 spec (Shawn override of false-fractal warning, 2026-05-14).
 * If projects ever diverge to a different state set, change this alias to a
 * project-local literal union without touching consumer code.
 */
export type ProjectStageValue = VentureStageValue;

export { VENTURE_STAGES_ORDERED as PROJECT_STAGES_ORDERED } from "./index";

export interface Project {
  slug: string;                    // local slug ("tbff"), unique within venture
  name: string;
  description?: string;
  venture: string;                 // FK — venture slug
  stage: ProjectStageValue;        // 6-state, same as venture
  priority: PriorityLevelValue;
  owner: string;                   // single primary owner (FK to people)
  co_owners: string[];             // additional owners
  stakeholders: string[];          // FK to people
  deadline?: string;               // ISO date
  milestones: string[];            // list of local milestone slugs
  calculated_priority?: number;    // 0-100, computed at list-time — see priority/item-priority.ts
  docs_dir?: string;
  notes?: string;                  // markdown body
  created_at: string;
  updated_at: string;
  file_path?: string;              // resolved at read time
}

export type CreateProjectInput = Omit<
  Project,
  "created_at" | "updated_at" | "file_path"
>;

export type UpdateProjectInput = Partial<
  Omit<Project, "slug" | "venture" | "created_at" | "file_path">
>;

export interface ProjectFilter {
  venture?: string;                // single venture or undefined for all
  stage?: ProjectStageValue | ProjectStageValue[];
  priority?: PriorityLevelValue | PriorityLevelValue[];
  owner?: string;
  due_within_days?: number;
  overdue?: boolean;
}

export interface ProjectQuery {
  filter?: ProjectFilter;
  sort_by?: "priority" | "deadline" | "created" | "updated" | "name";
  sort_order?: "asc" | "desc";
  limit?: number;
  offset?: number;
}
