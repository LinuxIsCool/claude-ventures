/** App MCP tools: thin handlers over AppStore (same shape as project-tools.ts). */

import type { AppStore } from "../../store/app";
import type { CreateAppInput, UpdateAppInput, AppFilter, App, AppStage } from "../../types/app";

export interface AppListArgs extends AppFilter {
  sort_by?: "name" | "created" | "updated";
  sort_order?: "asc" | "desc";
  limit?: number;
  offset?: number;
}
export interface AppGetArgs { venture: string; slug: string }
export interface AppUpdateArgs { venture: string; slug: string; patch: UpdateAppInput }
export interface AppCloseArgs { venture: string; slug: string; stage: Extract<AppStage, "paused" | "retired">; retro_md?: string }

export function makeAppTools(store: AppStore) {
  return {
    async app_create(input: CreateAppInput): Promise<App> {
      return store.create(input);
    },
    async app_list(args: AppListArgs = {}): Promise<App[]> {
      const { sort_by, sort_order, limit, offset, ...filter } = args;
      return store.list({ filter, sort_by, sort_order, limit, offset });
    },
    async app_get(args: AppGetArgs): Promise<App | null> {
      return store.get(args.venture, args.slug);
    },
    async app_update(args: AppUpdateArgs): Promise<App> {
      return store.update(args.venture, args.slug, args.patch);
    },
    async app_close(args: AppCloseArgs): Promise<App> {
      const patch: UpdateAppInput = { stage: args.stage };
      if (args.retro_md) patch.notes = args.retro_md;
      return store.update(args.venture, args.slug, patch);
    },
  };
}

export type AppTools = ReturnType<typeof makeAppTools>;
