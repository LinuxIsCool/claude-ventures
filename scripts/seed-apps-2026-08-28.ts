// scripts/seed-apps-2026-08-28.ts
// One-shot: author the four known client app manifests (task-824 Phase 0).
// Re-running is safe: existing apps are skipped, not overwritten.
import { AppStore } from "../src/store/app";
import type { CreateAppInput } from "../src/types/app";
import { paths } from "../src/config";

const apps: CreateAppInput[] = [
  {
    slug: "living-library",
    name: "Indigenomics Living Library Model",
    venture: "indigenomics-ai",
    project: "gateway",
    kind: "web",
    stage: "active",
    repo: { path: "~/Workspace/IndigenomicsAI", remote: "indigenomicsxyz/IndigenomicsAI", default_branch: "main", vcs: "jj+git" },
    run: "pnpm -C v2 dev",
    test: "pnpm -C v2 test",
    status_doc: "v2/STATUS.md",
    environments: [
      { name: "dev", url: "https://dev.indigenomics.xyz", host: "legion2", healthz: "/healthz", deploy: "compose", status: "live", controllable: true },
      { name: "staging", url: "https://staging.indigenomics.xyz", host: "legion2", healthz: "/healthz", deploy: "compose", status: "live", controllable: false },
      { name: "prod", url: "https://indigenomics.xyz", status: "unprovisioned", controllable: false },
    ],
    depends_on: ["neo4j", "postgres"],
    secrets: "~/.claude/local/secrets/indigenomics.env",
    runtime: { kind: "compose", file: "deploy/compose/dev.yml", project: "indigenomics-dev", network: "legion", hostname: "living-library.dev.legion" },
    notes: "Next.js apps (api, web, ws) over Neo4j and Postgres; the Indigenomics Living Library Model platform. Dev and staging both run on legion2 behind an nginx gate.",
  },
  {
    slug: "data-platform",
    name: "Indigenomics Data Platform",
    venture: "indigenomics-ai",
    project: "neu-capstone",
    kind: "web",
    stage: "planned",
    repo: { path: "~/Workspace/indigenomics-data-platform", remote: "Indigenomics/indigenomics-data-platform", default_branch: "main", vcs: "git" },
    status_doc: "ROADMAP.md",
    environments: [],
    depends_on: [],
    notes: "NEU capstone (Cohort 2) scaffold unifying indigenomics-rap and indigenomics-legal-cases. No runnable code yet; stack direction is AWS (Bedrock + DynamoDB).",
  },
  {
    slug: "fast-site",
    name: "Indigenomics fast site",
    venture: "indigenomics-ai",
    kind: "static",
    stage: "active",
    repo: { path: "~/Workspace/indigenomics-site", remote: "Indigenomics/site", default_branch: "main", vcs: "git" },
    run: "python3 -m http.server -d public 8081",
    test: "scripts/smoke-routes.sh",
    status_doc: "RECOVERY.md",
    environments: [
      { name: "prod", url: "https://indigenomics.com", deploy: "nginx", status: "live", controllable: false },
    ],
    depends_on: [],
    notes: "Static replica of indigenomics.com (389 routes). Canonical checkout is ~/Workspace/indigenomics-site; ~/Workspace/indigenomics-fast-site-recovered is a duplicate clone at the same commit and can be removed.",
  },
  {
    slug: "listening",
    name: "CIE Listening App",
    venture: "civic-intelligence-engine",
    kind: "web",
    stage: "paused",
    repo: { path: "~/Workspace/civic-intelligence-engine", remote: "OpenCivics-Labs/civic-intelligence-engine", default_branch: "main", vcs: "git" },
    run: "npm --prefix apps/listening run dev",
    test: "scripts/test-all.sh",
    status_doc: "PAUSE.md",
    environments: [
      { name: "dev", url: "https://civicintelligence.xyz/dev/", host: "netcup", healthz: "/healthz", deploy: "nginx", status: "paused", controllable: false },
      { name: "staging", url: "https://civicintelligence.xyz/staging/", host: "netcup", healthz: "/healthz", deploy: "nginx", status: "paused", controllable: false },
      { name: "demo", url: "https://civicintelligence.xyz/demo/", host: "netcup", healthz: "/healthz", deploy: "nginx", status: "paused", controllable: false },
    ],
    depends_on: [],
    secrets: "~/.claude/local/secrets/cie-demo.env",
    notes: "React 19 + Vite listening app, OCL018. Paused 2026-08-20 per PAUSE.md; hosted on a shared VPS whose ingress we do not own, so no environment is controllable from the Studio.",
  },
];

const store = new AppStore({ ventures_root: paths.base });
for (const a of apps) {
  if (await store.get(a.venture, a.slug)) { console.log(`skip ${a.venture}.${a.slug} (exists)`); continue; }
  const created = await store.create(a);
  console.log(`created ${created.file_path}`);
}
