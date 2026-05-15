/**
 * Tree + co-link MCP tools.
 *
 * - venture_tree: nested V→P→M JSON via VentureTreeBuilder
 * - venture_co_links: peer/parent/child venture references from a single venture file
 */

import { existsSync } from "fs";
import { readFile } from "fs/promises";
import { join } from "path";
import matter from "gray-matter";
import { VentureTreeBuilder, type VentureTreeNode } from "../../store/tree";

export interface TreeToolsOptions {
  ventures_root: string;
}

export interface VentureTreeArgs {
  slug: string;
}

export interface VentureCoLinksArgs {
  slug: string;
}

export interface VentureCoLinks {
  slug: string;
  co_ventures: string[];
  parent_ventures: string[];
  child_ventures: string[];
}

const STAGE_DIRS = ["active", "exploring", "seed", "sustaining", "dormant", "harvesting"];

export function makeTreeTools(opts: TreeToolsOptions) {
  const builder = new VentureTreeBuilder(opts);

  return {
    async venture_tree(args: VentureTreeArgs): Promise<VentureTreeNode | null> {
      return builder.build(args.slug);
    },

    async venture_co_links(args: VentureCoLinksArgs): Promise<VentureCoLinks | null> {
      for (const stage of STAGE_DIRS) {
        const path = join(opts.ventures_root, stage, `${args.slug}.md`);
        if (!existsSync(path)) continue;
        const raw = await readFile(path, "utf-8");
        const { data } = matter(raw);
        return {
          slug: args.slug,
          co_ventures: data.co_ventures ?? [],
          parent_ventures: data.parent_ventures ?? [],
          child_ventures: data.child_ventures ?? [],
        };
      }
      return null;
    },
  };
}

export type TreeTools = ReturnType<typeof makeTreeTools>;
