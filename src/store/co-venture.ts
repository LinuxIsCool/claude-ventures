/**
 * CoVentureMirror — auto-derives child_ventures back-refs and validates
 * peer co_venture symmetry across all ventures.
 *
 * - rebuildChildVentures: scan all venture .md files, compute child_ventures
 *   from parent_ventures back-refs, write updates only when changed.
 * - validateCoVentures: report asymmetric peer relationships (A names B as
 *   peer but B doesn't name A back, or B doesn't exist).
 */

import { readdir, readFile, writeFile } from "fs/promises";
import { existsSync } from "fs";
import { join, basename } from "path";
import matter from "gray-matter";

const STAGE_DIRS = ["active", "exploring", "seed", "sustaining", "dormant", "harvesting"];

export interface CoVentureMirrorOptions {
  ventures_root: string;
}

interface VentureFile {
  slug: string;
  path: string;
  data: Record<string, any>;
  body: string;
}

export interface RebuildResult {
  updated: string[];                         // venture slugs whose files changed
}

export interface ValidateResult {
  asymmetries: Array<{ from: string; to: string; missing_back_ref: boolean }>;
}

export class CoVentureMirror {
  constructor(private opts: CoVentureMirrorOptions) {}

  async rebuildChildVentures(): Promise<RebuildResult> {
    const all = await this.loadAll();
    const childMap = new Map<string, string[]>();
    for (const v of all) {
      const parents: string[] = v.data.parent_ventures ?? [];
      for (const p of parents) {
        if (!childMap.has(p)) childMap.set(p, []);
        childMap.get(p)!.push(v.slug);
      }
    }

    const updated: string[] = [];
    for (const v of all) {
      const newChildren = (childMap.get(v.slug) ?? []).slice().sort();
      const oldChildren: string[] = (v.data.child_ventures ?? []).slice().sort();
      if (!arraysEqual(newChildren, oldChildren)) {
        v.data.child_ventures = newChildren;
        await writeFile(v.path, matter.stringify(v.body, v.data), "utf-8");
        updated.push(v.slug);
      }
    }
    return { updated };
  }

  async validateCoVentures(): Promise<ValidateResult> {
    const all = await this.loadAll();
    const slugSet = new Set(all.map((v) => v.slug));
    const asymmetries: ValidateResult["asymmetries"] = [];
    const coMap = new Map<string, Set<string>>();
    for (const v of all) {
      coMap.set(v.slug, new Set(v.data.co_ventures ?? []));
    }
    for (const [from, peers] of coMap) {
      for (const to of peers) {
        if (!slugSet.has(to)) {
          asymmetries.push({ from, to, missing_back_ref: true });
          continue;
        }
        const back = coMap.get(to) ?? new Set();
        if (!back.has(from)) asymmetries.push({ from, to, missing_back_ref: true });
      }
    }
    return { asymmetries };
  }

  private async loadAll(): Promise<VentureFile[]> {
    const result: VentureFile[] = [];
    for (const stage of STAGE_DIRS) {
      const dir = join(this.opts.ventures_root, stage);
      if (!existsSync(dir)) continue;
      const entries = await readdir(dir, { withFileTypes: true });
      for (const entry of entries) {
        if (!entry.isFile() || !entry.name.endsWith(".md")) continue;
        const path = join(dir, entry.name);
        const raw = await readFile(path, "utf-8");
        const parsed = matter(raw);
        const slug = parsed.data.slug ?? basename(entry.name, ".md");
        result.push({ slug, path, data: parsed.data, body: parsed.content });
      }
    }
    return result;
  }
}

function arraysEqual(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false;
  return a.every((x, i) => x === b[i]);
}
