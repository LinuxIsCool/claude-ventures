import { describe, expect, test, beforeEach, afterEach } from "bun:test";
import { mkdtempSync, rmSync, existsSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import { MilestoneStore } from "../../src/store/milestone";
import type { CreateMilestoneInput } from "../../src/types/milestone-v2";

let tmpRoot: string;
let store: MilestoneStore;

beforeEach(() => {
  tmpRoot = mkdtempSync(join(tmpdir(), "milestones-test-"));
  store = new MilestoneStore({ ventures_root: tmpRoot });
});

afterEach(() => {
  rmSync(tmpRoot, { recursive: true, force: true });
});

const baseInput = (overrides: Partial<CreateMilestoneInput> = {}): CreateMilestoneInput => ({
  slug: "m1-spec",
  name: "Spec v1",
  project: "tbff",
  venture: "bcrg",
  stage: "active",
  priority: "high",
  target: "Spec doc published",
  exit_criteria: ["committed", "reviewed"],
  tasks: [],
  ...overrides,
});

describe("MilestoneStore.create", () => {
  test("creates {slug}.md at canonical path", async () => {
    const m = await store.create(baseInput());
    const expected = join(tmpRoot, "bcrg", "projects", "tbff", "milestones", "m1-spec.md");
    expect(existsSync(expected)).toBe(true);
    expect(m.slug).toBe("m1-spec");
    expect(m.venture).toBe("bcrg");
    expect(m.project).toBe("tbff");
  });

  test("rejects duplicate", async () => {
    await store.create(baseInput());
    await expect(store.create(baseInput())).rejects.toThrow(/already exists/);
  });

  test("rejects invalid slug", async () => {
    await expect(store.create(baseInput({ slug: "bad slug" }))).rejects.toThrow(/invalid slug/);
  });
});

describe("MilestoneStore.get", () => {
  test("returns null for missing", async () => {
    expect(await store.get("bcrg", "tbff", "missing")).toBeNull();
  });

  test("round-trips", async () => {
    await store.create(baseInput({ deadline: "2026-06-15", notes: "# Plan\nDo the thing." }));
    const got = await store.get("bcrg", "tbff", "m1-spec");
    expect(got!.deadline).toBe("2026-06-15");
    expect(got!.notes?.trim()).toContain("# Plan");
    expect(got!.exit_criteria).toEqual(["committed", "reviewed"]);
  });
});

describe("MilestoneStore.list", () => {
  test("lists milestones under a project", async () => {
    await store.create(baseInput({ slug: "m1-spec" }));
    await store.create(baseInput({ slug: "m2-prototype", name: "Prototype" }));
    const list = await store.list({ filter: { venture: "bcrg", project: "tbff" } });
    expect(list).toHaveLength(2);
  });

  test("filters by due_within_days", async () => {
    const soon = new Date(Date.now() + 5 * 86_400_000).toISOString().slice(0, 10);
    const later = new Date(Date.now() + 60 * 86_400_000).toISOString().slice(0, 10);
    await store.create(baseInput({ slug: "soon", deadline: soon }));
    await store.create(baseInput({ slug: "later", deadline: later }));
    const list = await store.list({
      filter: { venture: "bcrg", project: "tbff", due_within_days: 14 },
    });
    expect(list).toHaveLength(1);
    expect(list[0].slug).toBe("soon");
  });
});

describe("MilestoneStore.update", () => {
  test("merges patch", async () => {
    await store.create(baseInput());
    const updated = await store.update("bcrg", "tbff", "m1-spec", {
      stage: "sustaining",
      priority: "medium",
    });
    expect(updated.stage).toBe("sustaining");
    expect(updated.priority).toBe("medium");
  });
});
