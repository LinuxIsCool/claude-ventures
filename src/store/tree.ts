/**
 * VentureTreeBuilder — assembles V→P→M nested JSON.
 *
 * Reads the venture stub from any of the 6 stage dirs (active/, exploring/, …),
 * then walks projects + milestones via ProjectStore + MilestoneStore. Used by
 * the venture_tree MCP tool and downstream webui consumers.
 */

import { existsSync } from "fs";
import { readFile } from "fs/promises";
import { join } from "path";
import matter from "gray-matter";

import { ProjectStore } from "./project";
import { MilestoneStore } from "./milestone";
import type { Project } from "../types/project";
import type { MilestoneV2 } from "../types/milestone-v2";

export interface VentureTreeOptions {
  ventures_root: string;
}

export interface VentureTreeNode {
  venture: {
    slug: string;
    name: string;
    stage: string;
    priority: string;
    description?: string;
  };
  projects: Array<{
    project: Project;
    milestones: MilestoneV2[];
  }>;
}

const STAGE_DIRS = ["active", "exploring", "seed", "sustaining", "dormant", "harvesting"];

export class VentureTreeBuilder {
  private projects: ProjectStore;
  private milestones: MilestoneStore;

  constructor(private opts: VentureTreeOptions) {
    this.projects = new ProjectStore(opts);
    this.milestones = new MilestoneStore(opts);
  }

  async build(ventureSlug: string): Promise<VentureTreeNode | null> {
    const ventureMeta = await this.findVentureMeta(ventureSlug);
    if (!ventureMeta) return null;

    const projects = await this.projects.list({ filter: { venture: ventureSlug } });
    const projectNodes = await Promise.all(
      projects.map(async (p) => ({
        project: p,
        milestones: await this.milestones.list({
          filter: { venture: ventureSlug, project: p.slug },
        }),
      }))
    );

    return { venture: ventureMeta, projects: projectNodes };
  }

  private async findVentureMeta(
    slug: string
  ): Promise<VentureTreeNode["venture"] | null> {
    for (const stage of STAGE_DIRS) {
      const path = join(this.opts.ventures_root, stage, `${slug}.md`);
      if (!existsSync(path)) continue;
      const content = await readFile(path, "utf-8");
      const { data } = matter(content);
      return {
        slug,
        name: data.name ?? slug,
        stage: data.stage ?? stage,
        priority: data.priority ?? "none",
        description: data.description,
      };
    }
    return null;
  }
}
