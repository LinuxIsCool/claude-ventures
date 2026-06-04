#!/usr/bin/env bun
/**
 * migrate-fractal.ts — task-416 Phase 2 migration (thin-slice: BCRG first).
 *
 * Reshapes a flat venture (embedded `milestones:` in {slug}.md) into the fractal
 * V→P→M tree on disk, using the Phase 1 ProjectStore / MilestoneStore so the output
 * is byte-compatible with the MCP tools and webui. Backlog FK matches are PROPOSED
 * in the report but never auto-applied (the high-blast-radius step stays manual).
 *
 * Usage:
 *   bun run scripts/migrate-fractal.ts --venture bcrg            # dry-run (default)
 *   bun run scripts/migrate-fractal.ts --venture bcrg --apply    # write the tree
 *
 * Safety:
 *   - dry-run is the default; --apply is required to write SOURCE DATA (ventures/backlog).
 *     A dry-run still writes its review report under ventures/_migration/<date>/ — that
 *     report IS the review surface and never touches source data.
 *   - ProjectStore.create / MilestoneStore.create throw on pre-existing entities,
 *     so re-running --apply is safe (won't clobber).
 *   - Rollback for a venture tree: `rm -rf ~/.claude/local/ventures/<venture>/projects`
 *
 * The decomposition is DECLARATIVE (PLANS below) — the judgment lives here, in data,
 * reviewed by Shawn, not inferred by code. Add a venture's plan, dry-run, then apply.
 */

import { readFile, readdir, mkdir, writeFile } from "fs/promises";
import { existsSync } from "fs";
import { join } from "path";
import { homedir } from "os";
import matter from "gray-matter";

import { ProjectStore } from "../src/store/project";
import { MilestoneStore } from "../src/store/milestone";
import type { CreateProjectInput } from "../src/types/project";
import type { CreateMilestoneInput } from "../src/types/milestone-v2";

const VENTURES_ROOT = join(homedir(), ".claude/local/ventures");
const BACKLOG_ROOT = join(homedir(), ".claude/local/backlog");

type StageValue =
  | "active" | "exploring" | "dormant" | "seed" | "sustaining" | "harvesting";
type Priority = "critical" | "high" | "medium" | "low" | "none";

interface MilestonePlan {
  slug: string;
  name: string;
  stage: StageValue;
  priority: Priority;
  target: string;
  deadline?: string;
  exit_criteria?: string[];
  from?: string;                 // provenance: which embedded milestone id this came from
}
interface ProjectPlan {
  slug: string;
  name: string;
  stage: StageValue;
  priority: Priority;
  owner: string;
  stakeholders?: string[];
  deadline?: string;
  note?: string;                 // project.md body
  milestones: MilestonePlan[];
}
interface VenturePlan {
  venture: string;
  projects: ProjectPlan[];
}

// NOTE: completed items map to `harvesting` — the 6-state vocab has no terminal
// "done" (Phase 0 §10.7, Shawn override). Flagged in the report as a revisit item.
const PLANS: Record<string, VenturePlan> = {
  "regen-ai": {
    venture: "regen-ai",
    projects: [
      { slug: "claims-engine", name: "Claims Engine", stage: "active", priority: "high", owner: "shawn", stakeholders: ["samu", "gregory-landua", "brandon"], note: "Regen claims engine.", milestones: [
        { slug: "claims-engine-v1", name: "Claims Engine V1", stage: "active", priority: "high", target: "V1 shipped", from: "ms-claims-engine" } ] },
      { slug: "registry-agent", name: "Registry Review Agent (RA)", stage: "active", priority: "high", owner: "shawn", stakeholders: ["brandon", "gregory-landua"], note: "Registry Review MCP / RA agent.", milestones: [
        { slug: "registry-mcp", name: "Registry Review MCP (RA Agent)", stage: "active", priority: "high", target: "MCP in marketplace", from: "ms-registry-agent" } ] },
      { slug: "methodology-agent", name: "Methodology Evaluation Agent", stage: "active", priority: "medium", owner: "shawn", stakeholders: ["gregory-landua"], note: "Methodology evaluation agent.", milestones: [
        { slug: "methodology-eval", name: "Methodology Evaluation Agent", stage: "active", priority: "medium", target: "Eval agent operational", from: "ms-methodology-agent" } ] },
      { slug: "protocol-politicians", name: "Protocol Politicians (9 Governance Agents)", stage: "active", priority: "medium", owner: "shawn", stakeholders: ["gregory-landua"], note: "9 governance agents. TACO/PACTO framework.", milestones: [
        { slug: "governance-agents", name: "Protocol Politicians — 9 governance agents", stage: "active", priority: "medium", target: "9 agents operational", from: "ms-protocol-politicians" } ] },
      { slug: "regen-app", name: "Regen App (Rolls) — Platform MVP", stage: "active", priority: "high", owner: "shawn", stakeholders: ["dave", "becca", "gregory-landua"], note: "Platform MVP (Rolls).", milestones: [
        { slug: "rolls-mvp", name: "Regen App (Rolls) Platform MVP", stage: "active", priority: "high", target: "MVP shipped", from: "ms-regen-app" } ] },
      { slug: "knowledge-commons", name: "Regen Knowledge Commons", stage: "exploring", priority: "low", owner: "shawn", stakeholders: ["becca", "gregory-landua"], note: "Knowledge commons — designed, not yet built.", milestones: [
        { slug: "commons-v1", name: "Regen Knowledge Commons v1", stage: "exploring", priority: "low", target: "Commons v1", from: "ms-knowledge-commons" } ] },
    ],
  },
  "indigenomics-ai": {
    venture: "indigenomics-ai",
    projects: [
      {
        slug: "telus-activation",
        name: "TELUS Activation — 6-month engagement",
        stage: "active", priority: "high", owner: "shawn",
        stakeholders: ["carol-anne-hilton", "tanya", "andrea", "roshan"],
        note: "Core 6-month TELUS contract delivery. Weekly activation sprint (Feb–Apr) + midpoint + renewal.",
        milestones: [
          { slug: "week1-handoff", name: "Week 1: K handoff + consolidation (Feb 26–Mar 4)", stage: "harvesting", priority: "high", target: "Handoff + consolidation complete", from: "ms-week1-handoff" },
          { slug: "week2-pipeline", name: "Week 2: Data pipeline + governance gate (Mar 5–11)", stage: "harvesting", priority: "high", target: "Pipeline + governance gate", from: "ms-week2-pipeline" },
          { slug: "week3-methodology", name: "Week 3: Methodology + data processing (Mar 12–18)", stage: "harvesting", priority: "high", target: "Methodology + processing", from: "ms-week3-methodology" },
          { slug: "week4-5-validation", name: "Weeks 4-5: Validation runs + iteration (Mar 19–Apr 1)", stage: "harvesting", priority: "high", target: "Validation runs + iteration", from: "ms-week4-5-validation" },
          { slug: "week6-review", name: "Week 6: Carol Anne quality review (Apr 2–8)", stage: "harvesting", priority: "high", target: "Carol Anne quality review", from: "ms-week6-review" },
          { slug: "week7-launch", name: "Week 7: Final prep + launch (Apr 9–12)", stage: "harvesting", priority: "high", target: "Final prep + launch", from: "ms-week7-launch" },
          { slug: "victoria-demo", name: "Phase 4.5 Victoria in-person demo (Apr 17)", stage: "harvesting", priority: "medium", target: "In-person demo delivered", from: "ms-victoria-demo" },
          { slug: "midpoint-touchbase", name: "TELUS Midpoint Touch Base (May 8)", stage: "harvesting", priority: "medium", target: "Midpoint touch base held", from: "ms-midpoint-touchbase" },
          { slug: "midpoint-report", name: "Joint midpoint report co-signed", stage: "active", priority: "high", target: "Indigenomics + TELUS mutual sign-off (OVERDUE, TELUS doc pending)", deadline: "2026-06-01", from: "ms-midpoint-report" },
          { slug: "engagement-renewal", name: "TELUS engagement continuation past 6-month window", stage: "active", priority: "high", target: "Renewal decision", deadline: "2026-08-20", from: "ms-engagement-renewal" },
        ],
      },
      {
        slug: "gateway",
        name: "Indigenomics AI Gateway + Reliability (Phase 5a)",
        stage: "active", priority: "high", owner: "shawn",
        note: "Gateway prototype + reliability engineering foundations. TELUS AI Factory, conversational models, sovereign-compute.",
        milestones: [
          { slug: "phase-5a-prototype", name: "Phase 5a Gateway prototype + reliability foundations", stage: "active", priority: "high", target: "Gateway v0 + reliability engineering substrate", from: "ms-phase-5a-prototype" },
        ],
      },
      {
        slug: "neu-capstone",
        name: "Northeastern University CS Capstone",
        stage: "active", priority: "medium", owner: "shawn",
        note: "Indigenomics Education Platform. Kickoff Jun 1, showcase Aug 10.",
        milestones: [
          { slug: "capstone", name: "NEU CS Capstone — Education Platform", stage: "active", priority: "medium", target: "Kickoff Jun 1 → showcase Aug 10", deadline: "2026-08-10", from: "ms-neu-capstone" },
        ],
      },
      {
        slug: "creator-jam",
        name: "Indigenomics Creator Tech Jam",
        stage: "harvesting", priority: "low", owner: "shawn",
        note: "Virtual + Vancouver + Victoria, May 21–26. Complete.",
        milestones: [
          { slug: "jam-complete", name: "Creator Tech Jam delivered (May 21–26)", stage: "harvesting", priority: "low", target: "Jam delivered across 3 venues", from: "ms-creator-jam" },
        ],
      },
      {
        slug: "impact-summit",
        name: "Indigenomics IMPACT Summit",
        stage: "active", priority: "medium", owner: "shawn",
        note: "IMPACT Summit, Sept 26.",
        milestones: [
          { slug: "summit-2026", name: "IMPACT Summit 2026 (Sept 26)", stage: "active", priority: "medium", target: "Summit delivered", deadline: "2026-09-26", from: "ms-impact-2026" },
        ],
      },
      {
        slug: "indian-act-survey",
        name: "National Indian Act Economic Survey",
        stage: "active", priority: "medium", owner: "shawn",
        note: "150 years of the Indian Act. Survey launch (was Apr 12 — overdue).",
        milestones: [
          { slug: "survey-launch", name: "National Indian Act Economic Survey launch", stage: "active", priority: "medium", target: "Survey launched", deadline: "2026-04-12" },
        ],
      },
    ],
  },
  bcrg: {
    venture: "bcrg",
    projects: [
      {
        slug: "avalanche-phase2",
        name: "Avalanche Phase 2 — PSUU Research ($100K)",
        stage: "active", priority: "high", owner: "shawn",
        stakeholders: ["hash-n", "eric-lu", "daniel-ortiz"],
        deadline: "2026-12-31",
        note: "The $100K Avalanche Foundation research contract (4 × $25K). PSUU for Avalanche staking.",
        milestones: [
          { slug: "m0-contract-signed", name: "Contract signed (DocuSign DA8F5A53)", stage: "harvesting", priority: "high", target: "Phase 2 agreement executed", deadline: "2026-04-15", from: "ms-phase2-agreement" },
          { slug: "m1-data-kickoff", name: "M0–M1: Data access + staking model spec", stage: "active", priority: "high", target: "Snowflake p-chain access, behavioral state-var model, calibrated response functions, preliminary validation", from: "ms-phase2-delivery" },
          { slug: "m2-simulation", name: "M2: 50K+ PSUU simulation trajectories", stage: "seed", priority: "high", target: "KPI computation, final validation, sensitivity analysis, workshop", from: "ms-phase2-delivery" },
          { slug: "m3-recommendations", name: "M3: Parameter recommendation report", stage: "seed", priority: "high", target: "Scenario playbook, open-source release, knowledge transfer", from: "ms-phase2-delivery" },
          { slug: "cycle1-acp-validation", name: "First cycle — ACP-275 + ACP-285 PSUU validation", stage: "active", priority: "high", target: "Reproduce Eric Lu's yield/APY-stability MRS; out-of-sample r_min probe; Pareto frontier", from: "ms-phase2-cycle1-acps" },
        ],
      },
      {
        slug: "cadcad-grant",
        name: "cadCAD Org Grant ($40K)",
        stage: "active", priority: "medium", owner: "shawn",
        stakeholders: ["octopus", "hash-n", "jeff-emmett"],
        note: "Separate workstream. PI: Octopus. ALife + cadCAD research program. Proposal v1.3 on main.",
        milestones: [
          { slug: "proposal-submission", name: "Proposal submission to cadCAD org wallet", stage: "active", priority: "medium", target: "Jeff submits v1.3 once Foundation funding-flow pipeline unblocked", from: "ms-cadcad-grant" },
        ],
      },
      {
        slug: "tbff",
        name: "Threshold-Based Flow Funding (TBFF)",
        stage: "active", priority: "medium", owner: "shawn",
        note: "TBFF workstream. Milestones TBD — migrated as a project shell.",
        milestones: [],
      },
      {
        slug: "tec-post-mortem",
        name: "TEC Post-Mortem Analysis",
        stage: "active", priority: "medium", owner: "shawn",
        note: "Token Engineering Commons post-mortem analysis. Milestones TBD — migrated as a project shell.",
        milestones: [],
      },
      {
        slug: "conding-library",
        name: "conding — bonding-curve Python library",
        stage: "harvesting", priority: "low", owner: "shawn",
        note: "Historical reference. nbdev-based Python bonding-curve analysis library with GitHub Pages docs. v1 shipped.",
        milestones: [
          { slug: "v1-shipped", name: "conding Library v1 shipped", stage: "harvesting", priority: "low", target: "Python bonding-curve library + GitHub Pages docs published (nbdev)", from: "ms-conding-library" },
        ],
      },
      {
        slug: "avalanche-phase1",
        name: "Avalanche Phase 1 (InfraBridge grant)",
        stage: "harvesting", priority: "low", owner: "shawn",
        note: "Historical reference. Initial Avalanche grant paid in AVAX via the InfraBridge program. Established track record; lost value to AVAX volatility.",
        milestones: [
          { slug: "phase1-delivered", name: "Phase 1 research deliverables paid", stage: "harvesting", priority: "low", target: "Avalanche Economic Model: A Systems Engineering Perspective — delivered + paid", from: "ms-phase1" },
        ],
      },
    ],
  },
};

// Hand-curated backlog FK mapping (judgment, reviewed by Shawn). Key = task id
// (as it appears in frontmatter `id:`), value = composite parent slug.
// parent_type is derived from dot-depth: 0=venture, 1=project, 2=milestone.
const BACKLOG_FK: Record<string, Record<string, string>> = {
  "regen-ai": {
    "task-086": "regen-ai",
    "432": "regen-ai.registry-agent.registry-mcp",
    "448": "regen-ai.claims-engine.claims-engine-v1",
  },
  "indigenomics-ai": {
    "task-012": "indigenomics-ai.telus-activation",
    "task-026": "indigenomics-ai",
    "task-028": "indigenomics-ai",
    "task-171": "indigenomics-ai",
    "443": "indigenomics-ai.gateway.phase-5a-prototype",
    "485": "indigenomics-ai.gateway",
    "539": "indigenomics-ai.gateway",
    "540": "indigenomics-ai.telus-activation",
    "547": "indigenomics-ai.neu-capstone.capstone",
    "558": "indigenomics-ai.gateway.phase-5a-prototype",
  },
  bcrg: {
    "429": "bcrg.avalanche-phase2.m1-data-kickoff",
    "task-025": "bcrg",
    "408": "bcrg.cadcad-grant",
    "411": "bcrg.cadcad-grant",
    "419": "bcrg.cadcad-grant.proposal-submission",
    "467": "bcrg.cadcad-grant.proposal-submission",
    "533": "bcrg.avalanche-phase2",
    "535": "bcrg.avalanche-phase2",
    "536": "bcrg.avalanche-phase2",
    "537": "bcrg.cadcad-grant",
  },
};

function parentTypeOf(parentId: string): "venture" | "project" | "milestone" {
  const depth = parentId.split(".").length;
  if (depth === 1) return "venture";
  if (depth === 2) return "project";
  if (depth === 3) return "milestone";
  throw new Error(`invalid composite parent_id "${parentId}" — expected 1–3 dot-segments`);
}

function fkTargetExists(parentId: string): boolean {
  const parts = parentId.split(".");
  if (parts.length === 1) {
    return ["active", "exploring", "sustaining", "dormant", "seed", "harvesting"]
      .some((st) => existsSync(join(VENTURES_ROOT, st, `${parts[0]}.md`)));
  }
  if (parts.length === 2) {
    return existsSync(join(VENTURES_ROOT, parts[0], "projects", parts[1], "project.md"));
  }
  return existsSync(join(VENTURES_ROOT, parts[0], "projects", parts[1], "milestones", `${parts[2]}.md`));
}

/** Surgically insert parent_id + parent_type after the `id:` line, scoped STRICTLY
 *  to the YAML frontmatter block (between the first two `---` fences) so a body line
 *  starting with `id:`/`parent_id:` can never trigger a false match or body corruption. */
function insertFk(content: string, parentId: string, parentType: string): { content: string; status: string } {
  const lines = content.split("\n");
  if (lines[0]?.trim() !== "---") return { content, status: "NO frontmatter fence — skipped" };
  const closeIdx = lines.findIndex((l, i) => i > 0 && l.trim() === "---");
  if (closeIdx === -1) return { content, status: "unterminated frontmatter — skipped" };
  const fm = lines.slice(1, closeIdx);                       // frontmatter body only
  if (fm.some((l) => /^parent_id:/.test(l))) return { content, status: "already-has-fk (skipped)" };
  const relIdIdx = fm.findIndex((l) => /^id:/.test(l));
  if (relIdIdx === -1) return { content, status: "NO id: in frontmatter — skipped" };
  lines.splice(1 + relIdIdx + 1, 0, `parent_id: ${parentId}`, `parent_type: ${parentType}`);
  return { content: lines.join("\n"), status: "inserted" };
}

function parseArgs() {
  const args = process.argv.slice(2);
  const ventureIdx = args.indexOf("--venture");
  return {
    venture: ventureIdx >= 0 ? args[ventureIdx + 1] : null,
    apply: args.includes("--apply"),
    backlog: args.includes("--backlog"),
  };
}

async function runBacklogFk(venture: string, apply: boolean) {
  const map = BACKLOG_FK[venture];
  if (!map) { console.error(`no BACKLOG_FK mapping for ${venture}`); process.exit(1); }
  const files = (await readdir(BACKLOG_ROOT)).filter((f) => f.startsWith("task-") && f.endsWith(".md"));
  const byId: Record<string, string> = {};
  for (const f of files) {
    const data = matter(await readFile(join(BACKLOG_ROOT, f), "utf-8")).data as any;
    if (data?.id != null) byId[String(data.id)] = f;
  }
  const lines: string[] = [];
  const log = (s = "") => { lines.push(s); console.log(s); };
  log(`# BCRG backlog FK backfill — ${apply ? "APPLY" : "DRY-RUN"}`);
  log(`${Object.keys(map).length} tasks mapped\n`);
  let ok = 0, bad = 0;
  for (const [taskId, parentId] of Object.entries(map)) {
    const ptype = parentTypeOf(parentId);
    if (!fkTargetExists(parentId)) { log(`  ✗ task ${taskId}: FK target ${parentId} does NOT resolve — SKIP`); bad++; continue; }
    const file = byId[taskId];
    if (!file) { log(`  ✗ task ${taskId}: backlog file not found — SKIP`); bad++; continue; }
    const path = join(BACKLOG_ROOT, file);
    const before = await readFile(path, "utf-8");
    const { content, status } = insertFk(before, parentId, ptype);
    log(`  ${status === "inserted" ? "✓" : "·"} task ${taskId} → ${parentId} (${ptype}) [${status}]`);
    if (apply && status === "inserted") await writeFile(path, content, "utf-8");
    if (status === "inserted") ok++;
  }
  log(`\n${ok} ${apply ? "written" : "to-insert"} · ${bad} unresolved`);
  const date = new Date().toISOString().slice(0, 10);
  const dir = join(VENTURES_ROOT, "_migration", date);
  await mkdir(dir, { recursive: true });
  await writeFile(join(dir, `${venture}-backlog-fk-${apply ? "apply" : "dryrun"}.md`), lines.join("\n"));
}

async function loadVentureFm(venture: string): Promise<any | null> {
  for (const stage of ["active", "exploring", "sustaining", "dormant", "seed", "harvesting"]) {
    const f = join(VENTURES_ROOT, stage, `${venture}.md`);
    if (existsSync(f)) return matter(await readFile(f, "utf-8")).data;
  }
  return null;
}

/** Propose backlog FK matches (word-boundary on venture slug). Never applied here. */
async function proposeBacklogFks(venture: string): Promise<{ id: string; title: string }[]> {
  const out: { id: string; title: string }[] = [];
  const re = new RegExp(`(?<![\\w-])${venture.replace(/-/g, "[ -]")}(?![\\w-])`, "i");
  if (!existsSync(BACKLOG_ROOT)) return out;
  for (const f of await readdir(BACKLOG_ROOT)) {
    if (!f.startsWith("task-") || !f.endsWith(".md")) continue;
    const data = matter(await readFile(join(BACKLOG_ROOT, f), "utf-8")).data as any;
    const vfield = String(data.venture ?? "").toLowerCase();
    const title = String(data.title ?? "");
    if (vfield === venture || re.test(title)) {
      out.push({ id: String(data.id ?? f), title: title.slice(0, 80) });
    }
  }
  return out;
}

async function main() {
  const { venture, apply, backlog } = parseArgs();
  if (backlog) {
    if (!venture) { console.error("usage: --venture <slug> --backlog [--apply]"); process.exit(1); }
    await runBacklogFk(venture, apply);
    return;
  }
  if (!venture || !PLANS[venture]) {
    console.error(`usage: bun run scripts/migrate-fractal.ts --venture <slug> [--apply|--backlog]`);
    console.error(`known plans: ${Object.keys(PLANS).join(", ")}`);
    process.exit(1);
  }
  const plan = PLANS[venture];
  const fm = await loadVentureFm(venture);
  if (!fm) { console.error(`venture ${venture} not found under ${VENTURES_ROOT}`); process.exit(1); }

  const projectStore = new ProjectStore({ ventures_root: VENTURES_ROOT });
  const milestoneStore = new MilestoneStore({ ventures_root: VENTURES_ROOT });

  const mode = apply ? "APPLY" : "DRY-RUN";
  const lines: string[] = [];
  const log = (s = "") => { lines.push(s); console.log(s); };

  log(`# BCRG fractal migration — ${mode}`);
  log(`venture: ${venture}  ·  ${plan.projects.length} projects  ·  ` +
      `${plan.projects.reduce((n, p) => n + p.milestones.length, 0)} milestones`);
  log("");
  log("> NOTE: completed items use stage `harvesting` — the 6-state vocab has no");
  log("> terminal `done` state (Phase 0 §10.7). Flagged for revisit.");
  log("");

  const embeddedIds = (fm.milestones ?? []).map((m: any) => m.id).filter(Boolean);
  const mappedFrom = new Set(plan.projects.flatMap(p => p.milestones.map(m => m.from).filter(Boolean)));
  const unmapped = embeddedIds.filter((id: string) => !mappedFrom.has(id));

  for (const p of plan.projects) {
    log(`## project: ${venture}.${p.slug}  (${p.stage}, ${p.priority})`);
    log(`   ${p.name}`);
    for (const m of p.milestones) {
      log(`   └─ ${venture}.${p.slug}.${m.slug}  (${m.stage})  ${m.from ? `← ${m.from}` : "[new]"}`);
    }
    if (p.milestones.length === 0) log(`   └─ (shell — milestones TBD)`);
    log("");

    if (apply) {
      const proj: CreateProjectInput = {
        slug: p.slug, name: p.name, venture, stage: p.stage, priority: p.priority,
        owner: p.owner, co_owners: [], stakeholders: p.stakeholders ?? [],
        deadline: p.deadline, milestones: p.milestones.map(m => m.slug), notes: p.note,
      };
      try {
        await projectStore.create(proj);
        log(`   ✓ created project ${venture}.${p.slug}`);
      } catch (e: any) {
        log(`   ! project ${venture}.${p.slug}: ${e.message}`);
      }
      for (const m of p.milestones) {
        const ms: CreateMilestoneInput = {
          slug: m.slug, name: m.name, project: p.slug, venture, stage: m.stage,
          priority: m.priority, target: m.target, deadline: m.deadline,
          exit_criteria: m.exit_criteria ?? [], tasks: [],
        };
        try {
          await milestoneStore.create(ms);
          log(`   ✓ created milestone ${venture}.${p.slug}.${m.slug}`);
        } catch (e: any) {
          log(`   ! milestone ${venture}.${p.slug}.${m.slug}: ${e.message}`);
        }
      }
      log("");
    }
  }

  log("## embedded-milestone coverage");
  log(`   embedded in ${venture}.md: ${embeddedIds.length}  [${embeddedIds.join(", ")}]`);
  log(`   mapped: ${embeddedIds.length - unmapped.length}  ·  unmapped: ${unmapped.length}` +
      (unmapped.length ? `  [${unmapped.join(", ")}]` : ""));
  log("");

  const fks = await proposeBacklogFks(venture);
  log(`## proposed backlog FK matches (NOT applied — review before backfill)`);
  log(`   ${fks.length} tasks word-match "${venture}"`);
  for (const t of fks.slice(0, 40)) log(`   - task-${t.id}: ${t.title}`);
  if (fks.length > 40) log(`   … +${fks.length - 40} more`);
  log("");
  log(`Next: assign each to a milestone parent_id (e.g. ${venture}.avalanche-phase2.cycle1-acp-validation),`);
  log(`then a separate --backlog pass sets parent_id/parent_type. Not done in this thin-slice.`);

  // Write report
  const date = new Date().toISOString().slice(0, 10);
  const reportDir = join(VENTURES_ROOT, "_migration", date);
  await mkdir(reportDir, { recursive: true });
  await writeFile(join(reportDir, `${venture}-${mode.toLowerCase()}.md`), lines.join("\n"));
  console.log(`\n[report written: ${join(reportDir, `${venture}-${mode.toLowerCase()}.md`)}]`);
}

main().catch((e) => { console.error(e); process.exit(1); });
