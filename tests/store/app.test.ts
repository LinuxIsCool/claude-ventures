import { describe, expect, test, beforeEach, afterEach } from "bun:test";
import { mkdtempSync, rmSync, existsSync, readFileSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import { AppStore } from "../../src/store/app";
import { isControllable } from "../../src/types/app";
import type { CreateAppInput } from "../../src/types/app";

let tmpRoot: string;
let store: AppStore;

const base: CreateAppInput = {
  slug: "living-library",
  name: "Indigenomics Living Library Model",
  venture: "indigenomics-ai",
  project: "gateway",
  kind: "web",
  stage: "active",
  repo: { path: "~/Workspace/IndigenomicsAI", remote: "indigenomicsxyz/IndigenomicsAI", default_branch: "main", vcs: "jj+git" },
  run: "pnpm -C v2 dev",
  environments: [
    { name: "dev", url: "https://dev.indigenomics.xyz", host: "legion2", healthz: "/healthz" },
    { name: "staging", url: "https://staging.indigenomics.xyz", host: "legion2", healthz: "/healthz" },
  ],
  depends_on: ["neo4j", "postgres"],
};

beforeEach(() => {
  tmpRoot = mkdtempSync(join(tmpdir(), "ventures-app-test-"));
  store = new AppStore({ ventures_root: tmpRoot });
});
afterEach(() => rmSync(tmpRoot, { recursive: true, force: true }));

describe("AppStore.create", () => {
  test("writes app.md at the canonical path", async () => {
    const app = await store.create(base);
    const p = join(tmpRoot, "indigenomics-ai", "apps", "living-library", "app.md");
    expect(existsSync(p)).toBe(true);
    expect(app.file_path).toBe(p);
    expect(readFileSync(p, "utf-8")).toContain("slug: living-library");
  });

  test("rejects a duplicate slug within the venture", async () => {
    await store.create(base);
    await expect(store.create(base)).rejects.toThrow(/already exists/);
  });

  test("rejects an invalid slug", async () => {
    await expect(store.create({ ...base, slug: "Bad Slug" })).rejects.toThrow(/invalid slug/);
  });
});

describe("AppStore.get / update / list", () => {
  test("round-trips nested repo, environments and runtime", async () => {
    await store.create({ ...base, runtime: { kind: "compose", file: "deploy/compose/dev.yml", project: "indigenomics-dev" } });
    const got = await store.get("indigenomics-ai", "living-library");
    expect(got?.repo.remote).toBe("indigenomicsxyz/IndigenomicsAI");
    expect(got?.environments.map((e) => e.name)).toEqual(["dev", "staging"]);
    expect(got?.runtime?.project).toBe("indigenomics-dev");
  });

  test("get returns null for a missing app", async () => {
    expect(await store.get("indigenomics-ai", "nope")).toBeNull();
  });

  test("update merges and bumps updated_at, keeps slug and venture", async () => {
    const a = await store.create(base);
    await new Promise((r) => setTimeout(r, 2));
    const b = await store.update("indigenomics-ai", "living-library", { stage: "paused", slug: "x", venture: "y" } as any);
    expect(b.stage).toBe("paused");
    expect(b.slug).toBe("living-library");
    expect(b.venture).toBe("indigenomics-ai");
    expect(b.updated_at > a.updated_at).toBe(true);
  });

  test("list filters by venture, project, stage and kind", async () => {
    await store.create(base);
    await store.create({ ...base, slug: "fast-site", project: undefined, kind: "static", stage: "active" });
    await store.create({ ...base, venture: "civic-intelligence-engine", slug: "listening", project: undefined, stage: "paused" });
    expect((await store.list()).length).toBe(3);
    expect((await store.list({ filter: { venture: "indigenomics-ai" } })).length).toBe(2);
    expect((await store.list({ filter: { project: "gateway" } })).map((a) => a.slug)).toEqual(["living-library"]);
    expect((await store.list({ filter: { kind: "static" } })).map((a) => a.slug)).toEqual(["fast-site"]);
    expect((await store.list({ filter: { stage: "paused" } })).map((a) => a.slug)).toEqual(["listening"]);
  });

  test("list sorts by name desc and paginates", async () => {
    await store.create({ ...base, slug: "a-app" });
    await store.create({ ...base, slug: "b-app" });
    const out = await store.list({ sort_by: "name", sort_order: "desc", limit: 1 });
    expect(out.map((a) => a.slug)).toEqual(["b-app"]);
  });
});

describe("isControllable", () => {
  test("defaults true for dev only, explicit flag wins", () => {
    expect(isControllable({ name: "dev" })).toBe(true);
    expect(isControllable({ name: "staging" })).toBe(false);
    expect(isControllable({ name: "staging", controllable: true })).toBe(true);
    expect(isControllable({ name: "dev", controllable: false })).toBe(false);
  });
});
