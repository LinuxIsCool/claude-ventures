/**
 * Project — the middle level of the fractal V/P/M hierarchy.
 * Lives at ~/.claude/local/ventures/{venture}/projects/{slug}/project.md.
 */

import type { PriorityLevelValue, VentureStageValue } from "./index";

export const PROJECT_STAGES_ORDERED: VentureStageValue[] = [
  "seed",
  "exploring",
  "active",
  "sustaining",
  "dormant",
  "harvesting",
];

export interface Project {
  slug: string;                    // local slug ("tbff"), unique within venture
  name: string;
  description?: string;
  venture: string;                 // FK — venture slug
  stage: VentureStageValue;        // 6-state, same as venture
  priority: PriorityLevelValue;
  owner: string;                   // single primary owner (FK to people)
  co_owners: string[];             // additional owners
  stakeholders: string[];          // FK to people
  deadline?: string;               // ISO date
  milestones: string[];            // list of local milestone slugs
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
  stage?: VentureStageValue | VentureStageValue[];
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
