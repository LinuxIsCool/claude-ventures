import { describe, expect, test, beforeEach, afterEach } from "bun:test";
import { mkdtempSync, rmSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import { makeMilestoneTools } from "../../src/mcp/tools/milestone-tools";
import { MilestoneStore } from "../../src/store/milestone";

let tmpRoot: string;
let tools: ReturnType<typeof makeMilestoneTools>;

beforeEach(() => {
  tmpRoot = mkdtempSync(join(tmpdir(), "milestone-mcp-test-"));
  tools = makeMilestoneTools(new MilestoneStore({ ventures_root: tmpRoot }));
});

afterEach(() => rmSync(tmpRoot, { recursive: true, force: true }));

const baseInput = (overrides: Partial<Record<string, any>> = {}) => ({
  slug: "m1-spec",
  name: "Spec",
  project: "tbff",
  venture: "bcrg",
  stage: "active" as const,
  priority: "high" as const,
  target: "ship",
  exit_criteria: [],
  tasks: [],
  ...overrides,
});

describe("milestone tools", () => {
  test("create + list + get + update + close round-trip", async () => {
    await tools.milestone_create(baseInput());
    const list = await tools.milestone_list({ venture: "bcrg", project: "tbff" });
    expect(list).toHaveLength(1);

    const got = await tools.milestone_get({
      venture: "bcrg",
      project: "tbff",
      slug: "m1-spec",
    });
    expect(got!.name).toBe("Spec");

    const updated = await tools.milestone_update({
      venture: "bcrg",
      project: "tbff",
      slug: "m1-spec",
      patch: { priority: "medium" },
    });
    expect(updated.priority).toBe("medium");

    const closed = await tools.milestone_close({
      venture: "bcrg",
      project: "tbff",
      slug: "m1-spec",
      stage: "harvesting",
    });
    expect(closed.stage).toBe("harvesting");
  });

  test("create rejects duplicate", async () => {
    await tools.milestone_create(baseInput());
    await expect(tools.milestone_create(baseInput())).rejects.toThrow();
  });
});
