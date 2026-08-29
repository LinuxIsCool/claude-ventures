/**
 * AppStore: read/write App entities as app.md files.
 * Path: {ventures_root}/{venture}/apps/{slug}/app.md
 * Mirrors ProjectStore (src/store/project.ts) so the two stay learnable together.
 */

import { mkdir, readFile, readdir, writeFile } from "fs/promises";
import { existsSync } from "fs";
import { join, dirname, basename } from "path";
import matter from "gray-matter";

import type { App, CreateAppInput, UpdateAppInput, AppQuery, AppFilter } from "../types/app";
import { isValidSlugSegment } from "../utils/composite-slug";

export interface AppStoreOptions {
  ventures_root: string;
}

export class AppStore {
  constructor(private opts: AppStoreOptions) {}

  private dir(venture: string, slug: string): string {
    return join(this.opts.ventures_root, venture, "apps", slug);
  }

  private file(venture: string, slug: string): string {
    return join(this.dir(venture, slug), "app.md");
  }

  async create(input: CreateAppInput): Promise<App> {
    if (!isValidSlugSegment(input.slug)) throw new Error(`invalid slug "${input.slug}"`);
    if (!isValidSlugSegment(input.venture)) throw new Error(`invalid venture slug "${input.venture}"`);
    const filePath = this.file(input.venture, input.slug);
    if (existsSync(filePath)) {
      throw new Error(`app ${input.venture}.${input.slug} already exists at ${filePath}`);
    }
    const now = new Date().toISOString();
    const app: App = { ...input, created_at: now, updated_at: now, file_path: filePath };
    await this.write(app);
    return app;
  }

  async get(venture: string, slug: string): Promise<App | null> {
    const filePath = this.file(venture, slug);
    if (!existsSync(filePath)) return null;
    return this.parse(await readFile(filePath, "utf-8"), filePath);
  }

  async update(venture: string, slug: string, patch: UpdateAppInput): Promise<App> {
    const existing = await this.get(venture, slug);
    if (!existing) throw new Error(`app ${venture}.${slug} not found`);
    const merged: App = {
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

  async list(query: AppQuery = {}): Promise<App[]> {
    const filter = query.filter ?? {};
    const ventures = filter.venture ? [filter.venture] : await this.discoverVentureSlugs();
    const apps: App[] = [];
    for (const v of ventures) {
      const appsDir = join(this.opts.ventures_root, v, "apps");
      if (!existsSync(appsDir)) continue;
      const entries = await readdir(appsDir, { withFileTypes: true });
      const slugs = entries.filter((e) => e.isDirectory() && isValidSlugSegment(e.name)).map((e) => e.name);
      for (const a of await Promise.all(slugs.map((s) => this.get(v, s)))) {
        if (a && this.matches(a, filter)) apps.push(a);
      }
    }
    if (query.sort_by) {
      const dir = query.sort_order === "desc" ? -1 : 1;
      apps.sort((a, b) => this.compareBy(a, b, query.sort_by!) * dir);
    }
    const offset = query.offset ?? 0;
    const limit = query.limit ?? apps.length;
    return apps.slice(offset, offset + limit);
  }

  private async discoverVentureSlugs(): Promise<string[]> {
    if (!existsSync(this.opts.ventures_root)) return [];
    const entries = await readdir(this.opts.ventures_root, { withFileTypes: true });
    return entries.filter((e) => e.isDirectory() && isValidSlugSegment(e.name)).map((e) => e.name);
  }

  private matches(a: App, f: AppFilter): boolean {
    if (f.venture && a.venture !== f.venture) return false;
    if (f.project && a.project !== f.project) return false;
    if (f.stage) {
      const stages = Array.isArray(f.stage) ? f.stage : [f.stage];
      if (!stages.includes(a.stage)) return false;
    }
    if (f.kind) {
      const kinds = Array.isArray(f.kind) ? f.kind : [f.kind];
      if (!kinds.includes(a.kind)) return false;
    }
    return true;
  }

  private compareBy(a: App, b: App, field: string): number {
    switch (field) {
      case "created": return a.created_at.localeCompare(b.created_at);
      case "updated": return a.updated_at.localeCompare(b.updated_at);
      case "name":
      default: return a.name.localeCompare(b.name);
    }
  }

  private parse(content: string, filePath: string): App {
    const { data, content: notes } = matter(content);
    const venture = data.venture ?? basename(dirname(dirname(dirname(filePath))));
    const slug = data.slug ?? basename(dirname(filePath));
    return {
      slug,
      name: data.name ?? slug,
      venture,
      project: data.project,
      kind: data.kind ?? "web",
      stage: data.stage ?? "active",
      repo: data.repo ?? { path: "" },
      run: data.run,
      test: data.test,
      status_doc: data.status_doc,
      environments: data.environments ?? [],
      depends_on: data.depends_on ?? [],
      secrets: data.secrets,
      runtime: data.runtime,
      notes: notes.trim() || undefined,
      created_at: data.created_at ?? new Date().toISOString(),
      updated_at: data.updated_at ?? new Date().toISOString(),
      file_path: filePath,
    };
  }

  private async write(a: App): Promise<void> {
    const filePath = a.file_path ?? this.file(a.venture, a.slug);
    await mkdir(dirname(filePath), { recursive: true });
    const { notes, file_path, ...frontmatter } = a;
    const clean = Object.fromEntries(Object.entries(frontmatter).filter(([, v]) => v !== undefined));
    await writeFile(filePath, matter.stringify(notes ?? "", clean), "utf-8");
  }
}
