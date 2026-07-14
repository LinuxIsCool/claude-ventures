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

  test("sort_by priority desc surfaces highest priority first (not lowest)", async () => {
    const base: CreateProjectInput = {
      slug: "x",
      name: "x",
      venture: "bcrg",
      stage: "active",
      owner: "shawn",
      co_owners: [],
      stakeholders: [],
      milestones: [],
      priority: "none",
    };
    await store.create({ ...base, slug: "crit", priority: "critical" });
    await store.create({ ...base, slug: "none", priority: "none" });
    await store.create({ ...base, slug: "low", priority: "low" });

    const desc = await store.list({
      filter: { venture: "bcrg" },
      sort_by: "priority",
      sort_order: "desc",
    });
    // Regression: desc used to sort by a 0=critical..4=none rank ascending,
    // which put "none" first. It must put "critical" first.
    expect(desc.map((p) => p.slug)).toEqual(["crit", "low", "none"]);

    const asc = await store.list({
      filter: { venture: "bcrg" },
      sort_by: "priority",
      sort_order: "asc",
    });
    expect(asc.map((p) => p.slug)).toEqual(["none", "low", "crit"]);
  });

  test("calculated_priority weighs overdue deadline above a merely high-tagged item", async () => {
    const base: CreateProjectInput = {
      slug: "x",
      name: "x",
      venture: "bcrg",
      stage: "active",
      owner: "shawn",
      co_owners: [],
      stakeholders: [],
      milestones: [],
      priority: "none",
    };
    const yesterday = new Date(Date.now() - 86_400_000).toISOString().slice(0, 10);
    await store.create({ ...base, slug: "overdue-low", priority: "low", deadline: yesterday });
    await store.create({ ...base, slug: "high-no-deadline", priority: "high" });

    const list = await store.list({
      filter: { venture: "bcrg" },
      sort_by: "priority",
      sort_order: "desc",
    });

    expect(list.map((p) => p.slug)).toEqual(["overdue-low", "high-no-deadline"]);
    // overdue urgency (100 * 0.6) + low tag (25 * 0.4) = 70
    expect(list[0].calculated_priority).toBe(70);
    // no deadline (0 * 0.6) + high tag (75 * 0.4) = 30
    expect(list[1].calculated_priority).toBe(30);
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
