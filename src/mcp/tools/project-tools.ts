/**
 * Project MCP tools — thin handlers over ProjectStore.
 *
 * Each tool takes plain JSON args (matching the MCP input schema in
 * src/mcp/tools/schemas.ts that Task 13 will add) and delegates to ProjectStore.
 *
 * Factory pattern (makeProjectTools) lets tests inject a hermetic ProjectStore.
 * Production wiring happens in src/mcp/server.ts (Task 13).
 */

import type { ProjectStore } from "../../store/project";
import type {
  CreateProjectInput,
  UpdateProjectInput,
  ProjectFilter,
  Project,
} from "../../types/project";

export interface ProjectListArgs extends ProjectFilter {
  sort_by?: "priority" | "deadline" | "created" | "updated" | "name";
  sort_order?: "asc" | "desc";
  limit?: number;
  offset?: number;
}

export interface ProjectGetArgs {
  venture: string;
  slug: string;
}

export interface ProjectUpdateArgs {
  venture: string;
  slug: string;
  patch: UpdateProjectInput;
}

export interface ProjectCloseArgs {
  venture: string;
  slug: string;
  stage: "sustaining" | "dormant" | "harvesting";
  retro_md?: string;
}

export function makeProjectTools(store: ProjectStore) {
  return {
    async project_create(input: CreateProjectInput): Promise<Project> {
      return store.create(input);
    },

    async project_list(args: ProjectListArgs): Promise<Project[]> {
      const { sort_by, sort_order, limit, offset, ...filter } = args;
      return store.list({ filter, sort_by, sort_order, limit, offset });
    },

    async project_get(args: ProjectGetArgs): Promise<Project | null> {
      return store.get(args.venture, args.slug);
    },

    async project_update(args: ProjectUpdateArgs): Promise<Project> {
      return store.update(args.venture, args.slug, args.patch);
    },

    async project_close(args: ProjectCloseArgs): Promise<Project> {
      const patch: UpdateProjectInput = { stage: args.stage };
      if (args.retro_md) patch.notes = args.retro_md;
      return store.update(args.venture, args.slug, patch);
    },
  };
}

export type ProjectTools = ReturnType<typeof makeProjectTools>;
