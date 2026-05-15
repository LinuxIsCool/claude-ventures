import { describe, expect, test, beforeEach, afterEach } from "bun:test";
import { mkdtempSync, rmSync, existsSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import { ProjectStore } from "../../src/store/project";
import type { CreateProjectInput } from "../../src/types/project";

let tmpRoot: string;
let store: ProjectStore;

beforeEach(() => {
  tmpRoot = mkdtempSync(join(tmpdir(), "ventures-fractal-test-"));
  store = new ProjectStore({ ventures_root: tmpRoot });
});

afterEach(() => {
  rmSync(tmpRoot, { recursive: true, force: true });
});

describe("ProjectStore.create", () => {
  test("creates project.md at canonical path", async () => {
    const input: CreateProjectInput = {
      slug: "tbff",
      name: "Threshold-Based Flow Funding",
      venture: "bcrg",
      stage: "active",
      priority: "high",
      owner: "shawn",
      co_owners: [],
      stakeholders: ["hash-n"],
      milestones: [],
      deadline: "2026-09-30",
    };
    const p = await store.create(input);
    const expectedPath = join(tmpRoot, "bcrg", "projects", "tbff", "project.md");
    expect(existsSync(expectedPath)).toBe(true);
    expect(p.slug).toBe("tbff");
    expect(p.venture).toBe("bcrg");
    expect(p.created_at).toBeTruthy();
    expect(p.file_path).toBe(expectedPath);
  });

  test("rejects duplicate slug within same venture", async () => {
    const input: CreateProjectInput = {
      slug: "tbff",
      name: "TBFF",
      venture: "bcrg",
      stage: "active",
      priority: "high",
      owner: "shawn",
      co_owners: [],
      stakeholders: [],
      milestones: [],
    };
    await store.create(input);
    await expect(store.create(input)).rejects.toThrow(/already exists/);
  });

  test("rejects invalid slug segment", async () => {
    const input: CreateProjectInput = {
      slug: "TBFF Caps",
      name: "TBFF",
      venture: "bcrg",
      stage: "active",
      priority: "high",
      owner: "shawn",
      co_owners: [],
      stakeholders: [],
      milestones: [],
    };
    await expect(store.create(input)).rejects.toThrow(/invalid slug/);
  });
});

describe("ProjectStore.get", () => {
  test("returns null for missing project", async () => {
    expect(await store.get("bcrg", "missing")).toBeNull();
  });

  test("round-trips a created project", async () => {
    const input: CreateProjectInput = {
      slug: "tbff",
      name: "TBFF",
      venture: "bcrg",
      stage: "active",
      priority: "high",
      owner: "shawn",
      co_owners: ["hash-n"],
      stakeholders: ["jeff-emmett"],
      milestones: ["m1-spec"],
      deadline: "2026-09-30",
      notes: "# Project Brief\nThe spec lives here.",
    };
    await store.create(input);
    const got = await store.get("bcrg", "tbff");
    expect(got).not.toBeNull();
    expect(got!.name).toBe("TBFF");
    expect(got!.co_owners).toEqual(["hash-n"]);
    expect(got!.notes?.trim()).toContain("# Project Brief");
  });
});

describe("ProjectStore.list", () => {
  test("lists projects under a venture", async () => {
    const base: CreateProjectInput = {
      slug: "tbff",
      name: "TBFF",
      venture: "bcrg",
      stage: "active",
      priority: "high",
      owner: "shawn",
      co_owners: [],
      stakeholders: [],
      milestones: [],
    };
    await store.create({ ...base, slug: "tbff" });
    await store.create({ ...base, slug: "octopus-cadcad", name: "Octopus cadCAD" });
    await store.create({ ...base, slug: "alife", name: "ALife", stage: "exploring" });
    const list = await store.list({ filter: { venture: "bcrg" } });
    expect(list).toHaveLength(3);
  });

  test("filters by stage", async () => {
    const base: CreateProjectInput = {
      slug: "x",
      name: "x",
      venture: "bcrg",
      stage: "active",
      priority: "high",
      owner: "shawn",
      co_owners: [],
      stakeholders: [],
      milestones: [],
    };
    await store.create({ ...base, slug: "tbff" });
    await store.create({ ...base, slug: "alife", stage: "exploring" });
    const list = await store.list({ filter: { venture: "bcrg", stage: "exploring" } });
    expect(list).toHaveLength(1);
    expect(list[0].slug).toBe("alife");
  });
});

describe("ProjectStore.update", () => {
  test("merges patch into existing project", async () => {
    const input: CreateProjectInput = {
      slug: "tbff",
      name: "TBFF",
      venture: "bcrg",
      stage: "active",
      priority: "high",
      owner: "shawn",
      co_owners: [],
      stakeholders: [],
      milestones: [],
    };
    await store.create(input);
    const updated = await store.update("bcrg", "tbff", { stage: "sustaining" });
    expect(updated.stage).toBe("sustaining");
    expect(updated.priority).toBe("high");
    const reloaded = await store.get("bcrg", "tbff");
    expect(reloaded!.stage).toBe("sustaining");
  });
});
