/**
 * Milestone MCP tools — thin handlers over MilestoneStore.
 *
 * Mirror of project-tools.ts pattern. Factory injects the store so tests
 * can use a hermetic MilestoneStore. Production wiring in src/mcp/server.ts
 * (Task 13).
 */

import type { MilestoneStore } from "../../store/milestone";
import type {
  CreateMilestoneInput,
  UpdateMilestoneInput,
  MilestoneFilter,
  MilestoneV2,
} from "../../types/milestone-v2";

export interface MilestoneListArgs extends MilestoneFilter {
  sort_by?: "priority" | "deadline" | "created" | "updated" | "name";
  sort_order?: "asc" | "desc";
  limit?: number;
  offset?: number;
}

export interface MilestoneGetArgs {
  venture: string;
  project: string;
  slug: string;
}

export interface MilestoneUpdateArgs {
  venture: string;
  project: string;
  slug: string;
  patch: UpdateMilestoneInput;
}

export interface MilestoneCloseArgs {
  venture: string;
  project: string;
  slug: string;
  stage: "sustaining" | "dormant" | "harvesting";
  retro_md?: string;
}

export function makeMilestoneTools(store: MilestoneStore) {
  return {
    async milestone_create(input: CreateMilestoneInput): Promise<MilestoneV2> {
      return store.create(input);
    },

    async milestone_list(args: MilestoneListArgs): Promise<MilestoneV2[]> {
      const { sort_by, sort_order, limit, offset, ...filter } = args;
      return store.list({ filter, sort_by, sort_order, limit, offset });
    },

    async milestone_get(args: MilestoneGetArgs): Promise<MilestoneV2 | null> {
      return store.get(args.venture, args.project, args.slug);
    },

    async milestone_update(args: MilestoneUpdateArgs): Promise<MilestoneV2> {
      return store.update(args.venture, args.project, args.slug, args.patch);
    },

    async milestone_close(args: MilestoneCloseArgs): Promise<MilestoneV2> {
      const patch: UpdateMilestoneInput = { stage: args.stage };
      if (args.retro_md) patch.notes = args.retro_md;
      return store.update(args.venture, args.project, args.slug, patch);
    },
  };
}

export type MilestoneTools = ReturnType<typeof makeMilestoneTools>;
