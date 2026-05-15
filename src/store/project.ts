/**
 * ProjectStore — read/write Project entities as project.md files.
 *
 * Path: {ventures_root}/{venture}/projects/{project}/project.md
 *
 * Constructor takes an explicit `ventures_root` (NOT singleton paths) so
 * tests can use a temp directory and the store is testable in isolation.
 */

import { mkdir, readFile, readdir, writeFile } from "fs/promises";
import { existsSync } from "fs";
import { join, dirname, basename } from "path";
import matter from "gray-matter";

import type {
  Project,
  CreateProjectInput,
  UpdateProjectInput,
  ProjectQuery,
  ProjectFilter,
} from "../types/project";
import { isValidSlugSegment } from "../utils/composite-slug";

export interface ProjectStoreOptions {
  ventures_root: string;             // override for tests; production callers use paths.base
}

export class ProjectStore {
  constructor(private opts: ProjectStoreOptions) {}

  private getProjectDir(venture: string, project: string): string {
    return join(this.opts.ventures_root, venture, "projects", project);
  }

  private getProjectFile(venture: string, project: string): string {
    return join(this.getProjectDir(venture, project), "project.md");
  }

  async create(input: CreateProjectInput): Promise<Project> {
    if (!isValidSlugSegment(input.slug)) {
      throw new Error(`invalid slug "${input.slug}"`);
    }
    if (!isValidSlugSegment(input.venture)) {
      throw new Error(`invalid venture slug "${input.venture}"`);
    }
    const filePath = this.getProjectFile(input.venture, input.slug);
    if (existsSync(filePath)) {
      throw new Error(
        `project ${input.venture}.${input.slug} already exists at ${filePath}`
      );
    }

    const now = new Date().toISOString();
    const project: Project = {
      ...input,
      docs_dir: input.docs_dir ?? join(this.getProjectDir(input.venture, input.slug), "docs"),
      created_at: now,
      updated_at: now,
      file_path: filePath,
    };

    await this.write(project);
    return project;
  }

  async get(venture: string, slug: string): Promise<Project | null> {
    const filePath = this.getProjectFile(venture, slug);
    if (!existsSync(filePath)) return null;
    const content = await readFile(filePath, "utf-8");
    return this.parse(content, filePath);
  }

  async update(
    venture: string,
    slug: string,
    patch: UpdateProjectInput
  ): Promise<Project> {
    const existing = await this.get(venture, slug);
    if (!existing) {
      throw new Error(`project ${venture}.${slug} not found`);
    }
    const merged: Project = {
      ...existing,
      ...patch,
      slug: existing.slug,
      venture: existing.venture,
      created_at: existing.created_at,
      updated_at: new Date().toISOString(),
    };
    await this.write(merged);
    return merged;
  }

  async list(query: ProjectQuery = {}): Promise<Project[]> {
    const filter = query.filter ?? {};
    const ventureSlugs = filter.venture
      ? [filter.venture]
      : await this.discoverVentureSlugs();

    const projects: Project[] = [];
    for (const v of ventureSlugs) {
      const projectsDir = join(this.opts.ventures_root, v, "projects");
      if (!existsSync(projectsDir)) continue;
      const entries = await readdir(projectsDir, { withFileTypes: true });
      const slugs = entries
        .filter((e) => e.isDirectory() && isValidSlugSegment(e.name))
        .map((e) => e.name);
      const loaded = await Promise.all(slugs.map((slug) => this.get(v, slug)));
      for (const p of loaded) {
        if (p && this.matches(p, filter)) projects.push(p);
      }
    }

    if (query.sort_by) {
      const dir = query.sort_order === "desc" ? -1 : 1;
      projects.sort((a, b) => this.compareBy(a, b, query.sort_by!) * dir);
    }
    const offset = query.offset ?? 0;
    const limit = query.limit ?? projects.length;
    return projects.slice(offset, offset + limit);
  }

  // ── internals ──────────────────────────────────────────────────────

  private async discoverVentureSlugs(): Promise<string[]> {
    if (!existsSync(this.opts.ventures_root)) return [];
    const entries = await readdir(this.opts.ventures_root, { withFileTypes: true });
    return entries
      .filter((e) => e.isDirectory() && isValidSlugSegment(e.name))
      .map((e) => e.name);
  }

  private matches(p: Project, f: ProjectFilter): boolean {
    if (f.venture && p.venture !== f.venture) return false;
    if (f.owner && p.owner !== f.owner) return false;
    if (f.stage) {
      const stages = Array.isArray(f.stage) ? f.stage : [f.stage];
      if (!stages.includes(p.stage)) return false;
    }
    if (f.priority) {
      const prios = Array.isArray(f.priority) ? f.priority : [f.priority];
      if (!prios.includes(p.priority)) return false;
    }
    if (f.due_within_days != null) {
      if (!p.deadline) return false;
      const days = (new Date(p.deadline).getTime() - Date.now()) / 86_400_000;
      if (days < 0 || days > f.due_within_days) return false;
    }
    if (f.overdue) {
      if (!p.deadline) return false;
      if (new Date(p.deadline).getTime() > Date.now()) return false;
    }
    return true;
  }

  private compareBy(a: Project, b: Project, field: string): number {
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

  private parse(content: string, filePath: string): Project {
    const { data, content: notes } = matter(content);
    const venture = data.venture ?? basename(dirname(dirname(dirname(filePath))));
    const slug = data.slug ?? basename(dirname(filePath));
    return {
      slug,
      name: data.name ?? slug,
      description: data.description,
      venture,
      stage: data.stage ?? "active",
      priority: data.priority ?? "none",
      owner: data.owner ?? "",
      co_owners: data.co_owners ?? [],
      stakeholders: data.stakeholders ?? [],
      deadline: data.deadline,
      milestones: data.milestones ?? [],
      docs_dir: data.docs_dir,
      notes: notes.trim() || undefined,
      created_at: data.created_at ?? new Date().toISOString(),
      updated_at: data.updated_at ?? new Date().toISOString(),
      file_path: filePath,
    };
  }

  private async write(p: Project): Promise<void> {
    const filePath = p.file_path ?? this.getProjectFile(p.venture, p.slug);
    await mkdir(dirname(filePath), { recursive: true });

    const { notes, file_path, ...frontmatter } = p;
    const cleanFrontmatter = Object.fromEntries(
      Object.entries(frontmatter).filter(([, v]) => v !== undefined)
    );
    const body = notes ?? "";
    const content = matter.stringify(body, cleanFrontmatter);
    await writeFile(filePath, content, "utf-8");
  }
}
