/**
 * FKValidator — verify a (parent_id, parent_type) tuple resolves to an entity on disk.
 *
 * parent_type ∈ {venture, project, milestone}
 * parent_id is a composite slug; its level must match parent_type.
 *
 * Used by claude-backlog (Python mirror in scripts/fractal_fk.py) and by
 * migration tools to check FK integrity before write.
 */

import { existsSync } from "fs";
import { join } from "path";
import { parseCompositeSlug } from "../utils/composite-slug";

export type ParentType = "venture" | "project" | "milestone";

export interface FKValidatorOptions {
  ventures_root: string;
}

export interface FKResolveResult {
  ok: boolean;
  error?: string;
  resolved_path?: string;
}

const VALID_TYPES: ParentType[] = ["venture", "project", "milestone"];
const STAGE_DIRS = ["active", "exploring", "seed", "sustaining", "dormant", "harvesting"];

export class FKValidator {
  constructor(private opts: FKValidatorOptions) {}

  async resolve(parentId: string, parentType: ParentType): Promise<FKResolveResult> {
    if (!VALID_TYPES.includes(parentType)) {
      return { ok: false, error: `invalid parent_type "${parentType}"` };
    }
    let parsed;
    try {
      parsed = parseCompositeSlug(parentId);
    } catch (e) {
      return { ok: false, error: (e as Error).message };
    }

    if (parsed.level !== parentType) {
      return {
        ok: false,
        error: `level mismatch: parent_id "${parentId}" is ${parsed.level}, but parent_type is ${parentType}`,
      };
    }

    if (parentType === "venture") {
      for (const stage of STAGE_DIRS) {
        const path = join(this.opts.ventures_root, stage, `${parsed.venture}.md`);
        if (existsSync(path)) return { ok: true, resolved_path: path };
      }
      return { ok: false, error: `venture "${parsed.venture}" not found in any stage dir` };
    }

    if (parentType === "project") {
      const path = join(
        this.opts.ventures_root,
        parsed.venture,
        "projects",
        parsed.project!,
        "project.md"
      );
      if (existsSync(path)) return { ok: true, resolved_path: path };
      return { ok: false, error: `project "${parsed.venture}.${parsed.project}" not found` };
    }

    // milestone
    const path = join(
      this.opts.ventures_root,
      parsed.venture,
      "projects",
      parsed.project!,
      "milestones",
      `${parsed.milestone}.md`
    );
    if (existsSync(path)) return { ok: true, resolved_path: path };
    return {
      ok: false,
      error: `milestone "${parsed.venture}.${parsed.project}.${parsed.milestone}" not found`,
    };
  }
}
