/**
 * MilestoneStore — read/write MilestoneV2 entities as {slug}.md files.
 *
 * Path: {ventures_root}/{venture}/projects/{project}/milestones/{slug}.md
 *
 * Constructor takes an explicit `ventures_root` (NOT singleton paths) so
 * tests can use a temp directory.
 */

import { mkdir, readFile, readdir, writeFile } from "fs/promises";
import { existsSync } from "fs";
import { join, dirname, basename } from "path";
import matter from "gray-matter";

import type {
  MilestoneV2,
  CreateMilestoneInput,
  UpdateMilestoneInput,
  MilestoneQuery,
  MilestoneFilter,
} from "../types/milestone-v2";
import { isValidSlugSegment } from "../utils/composite-slug";

export interface MilestoneStoreOptions {
  ventures_root: string;
}

export class MilestoneStore {
  constructor(private opts: MilestoneStoreOptions) {}

  private getMilestonesDir(venture: string, project: string): string {
    return join(this.opts.ventures_root, venture, "projects", project, "milestones");
  }

  private getMilestoneFile(venture: string, project: string, slug: string): string {
    return join(this.getMilestonesDir(venture, project), `${slug}.md`);
  }

  async create(input: CreateMilestoneInput): Promise<MilestoneV2> {
    if (!isValidSlugSegment(input.slug)) {
      throw new Error(`invalid slug "${input.slug}"`);
    }
    const filePath = this.getMilestoneFile(input.venture, input.project, input.slug);
    if (existsSync(filePath)) {
      throw new Error(
        `milestone ${input.venture}.${input.project}.${input.slug} already exists at ${filePath}`
      );
    }

    const now = new Date().toISOString();
    const milestoneDocsDir = join(
      this.getMilestonesDir(input.venture, input.project),
      input.slug,
      "docs"
    );
    const m: MilestoneV2 = {
      ...input,
      docs_dir: input.docs_dir ?? milestoneDocsDir,
      created_at: now,
      updated_at: now,
      file_path: filePath,
    };
    await this.write(m);
    return m;
  }

  async get(venture: string, project: string, slug: string): Promise<MilestoneV2 | null> {
    const filePath = this.getMilestoneFile(venture, project, slug);
    if (!existsSync(filePath)) return null;
    const content = await readFile(filePath, "utf-8");
    return this.parse(content, filePath);
  }

  async update(
    venture: string,
    project: string,
    slug: string,
    patch: UpdateMilestoneInput
  ): Promise<MilestoneV2> {
    const existing = await this.get(venture, project, slug);
    if (!existing) {
      throw new Error(`milestone ${venture}.${project}.${slug} not found`);
    }
    const merged: MilestoneV2 = {
      ...existing,
      ...patch,
      slug: existing.slug,
      project: existing.project,
      venture: existing.venture,
      created_at: existing.created_at,
      updated_at: new Date().toISOString(),
    };
    await this.write(merged);
    return merged;
  }

  async list(query: MilestoneQuery = {}): Promise<MilestoneV2[]> {
    const filter = query.filter ?? {};
    const ventureSlugs = filter.venture ? [filter.venture] : await this.discoverVentures();
    const milestones: MilestoneV2[] = [];

    for (const v of ventureSlugs) {
      const projectsDir = join(this.opts.ventures_root, v, "projects");
      if (!existsSync(projectsDir)) continue;
      const projectSlugs = filter.project
        ? [filter.project]
        : await this.discoverProjects(v);

      for (const p of projectSlugs) {
        const msDir = this.getMilestonesDir(v, p);
        if (!existsSync(msDir)) continue;
        const entries = await readdir(msDir, { withFileTypes: true });
        const slugs = entries
          .filter((e) => e.isFile() && e.name.endsWith(".md"))
          .map((e) => e.name.slice(0, -3))
          .filter((slug) => isValidSlugSegment(slug));
        const loaded = await Promise.all(slugs.map((slug) => this.get(v, p, slug)));
        for (const m of loaded) {
          if (m && this.matches(m, filter)) milestones.push(m);
        }
      }
    }

    if (query.sort_by) {
      const dir = query.sort_order === "desc" ? -1 : 1;
      milestones.sort((a, b) => this.compareBy(a, b, query.sort_by!) * dir);
    }
    const offset = query.offset ?? 0;
    const limit = query.limit ?? milestones.length;
    return milestones.slice(offset, offset + limit);
  }

  // ── internals ──────────────────────────────────────────────────────

  private async discoverVentures(): Promise<string[]> {
    if (!existsSync(this.opts.ventures_root)) return [];
    const entries = await readdir(this.opts.ventures_root, { withFileTypes: true });
    return entries
      .filter((e) => e.isDirectory() && isValidSlugSegment(e.name))
      .map((e) => e.name);
  }

  private async discoverProjects(venture: string): Promise<string[]> {
    const projectsDir = join(this.opts.ventures_root, venture, "projects");
    if (!existsSync(projectsDir)) return [];
    const entries = await readdir(projectsDir, { withFileTypes: true });
    return entries
      .filter((e) => e.isDirectory() && isValidSlugSegment(e.name))
      .map((e) => e.name);
  }

  private matches(m: MilestoneV2, f: MilestoneFilter): boolean {
    if (f.venture && m.venture !== f.venture) return false;
    if (f.project && m.project !== f.project) return false;
    if (f.stage) {
      const stages = Array.isArray(f.stage) ? f.stage : [f.stage];
      if (!stages.includes(m.stage)) return false;
    }
    if (f.priority) {
      const prios = Array.isArray(f.priority) ? f.priority : [f.priority];
      if (!prios.includes(m.priority)) return false;
    }
    if (f.due_within_days != null) {
      if (!m.deadline) return false;
      const days = (new Date(m.deadline).getTime() - Date.now()) / 86_400_000;
      if (days < 0 || days > f.due_within_days) return false;
    }
    if (f.overdue) {
      if (!m.deadline) return false;
      if (new Date(m.deadline).getTime() > Date.now()) return false;
    }
    return true;
  }

  private compareBy(a: MilestoneV2, b: MilestoneV2, field: string): number {
    switch (field) {
      case "name":
        return a.name.localeCompare(b.name);
      case "created":
        return a.created_at.localeCompare(b.created_at);
      case "updated":
        return a.updated_at.localeCompare(b.updated_at);
      case "deadline":
        return (a.deadline ?? "9999").localeCompare(b.deadline ?? "9999");
      case "priority":
      default:
        return this.priorityRank(a.priority) - this.priorityRank(b.priority);
    }
  }

  private priorityRank(p: string): number {
    return ({ critical: 0, high: 1, medium: 2, low: 3, none: 4 } as Record<string, number>)[p] ?? 4;
  }

  private parse(content: string, filePath: string): MilestoneV2 {
    const { data, content: notes } = matter(content);
    const slug = data.slug ?? basename(filePath, ".md");
    const project = data.project ?? basename(dirname(dirname(filePath)));
    const venture = data.venture ?? basename(dirname(dirname(dirname(dirname(filePath)))));
    return {
      slug,
      name: data.name ?? slug,
      description: data.description,
      project,
      venture,
      stage: data.stage ?? "active",
      priority: data.priority ?? "none",
      target: data.target ?? "",
      deadline: data.deadline,
      exit_criteria: data.exit_criteria ?? [],
      docs_dir: data.docs_dir,
      tasks: data.tasks ?? [],
      notes: notes.trim() || undefined,
      created_at: data.created_at ?? new Date().toISOString(),
      updated_at: data.updated_at ?? new Date().toISOString(),
      file_path: filePath,
    };
  }

  private async write(m: MilestoneV2): Promise<void> {
    const filePath = m.file_path ?? this.getMilestoneFile(m.venture, m.project, m.slug);
    await mkdir(dirname(filePath), { recursive: true });
    const { notes, file_path, ...rest } = m;
    // Filter undefined to avoid YAMLException in gray-matter (matches markdown.ts pattern)
    const frontmatter = Object.fromEntries(
      Object.entries(rest).filter(([, v]) => v !== undefined)
    );
    const body = notes ?? "";
    const content = matter.stringify(body, frontmatter);
    await writeFile(filePath, content, "utf-8");
  }
}
