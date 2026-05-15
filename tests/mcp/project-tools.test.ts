import { describe, expect, test, beforeEach, afterEach } from "bun:test";
import { mkdtempSync, rmSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import { makeProjectTools } from "../../src/mcp/tools/project-tools";
import { ProjectStore } from "../../src/store/project";

let tmpRoot: string;
let tools: ReturnType<typeof makeProjectTools>;

beforeEach(() => {
  tmpRoot = mkdtempSync(join(tmpdir(), "project-mcp-test-"));
  tools = makeProjectTools(new ProjectStore({ ventures_root: tmpRoot }));
});

afterEach(() => rmSync(tmpRoot, { recursive: true, force: true }));

describe("project_create", () => {
  test("creates a project and returns it", async () => {
    const result = await tools.project_create({
      slug: "tbff",
      name: "TBFF",
      venture: "bcrg",
      stage: "active",
      priority: "high",
      owner: "shawn",
      co_owners: [],
      stakeholders: [],
      milestones: [],
    });
    expect(result.slug).toBe("tbff");
  });

  test("returns error for duplicate", async () => {
    const input = {
      slug: "tbff",
      name: "TBFF",
      venture: "bcrg",
      stage: "active" as const,
      priority: "high" as const,
      owner: "shawn",
      co_owners: [],
      stakeholders: [],
      milestones: [],
    };
    await tools.project_create(input);
    await expect(tools.project_create(input)).rejects.toThrow();
  });
});

describe("project_list / project_get / project_update / project_close", () => {
  test("full lifecycle round-trips", async () => {
    await tools.project_create({
      slug: "tbff",
      name: "TBFF",
      venture: "bcrg",
      stage: "active",
      priority: "high",
      owner: "shawn",
      co_owners: [],
      stakeholders: [],
      milestones: [],
    });
    const list = await tools.project_list({ venture: "bcrg" });
    expect(list).toHaveLength(1);

    const got = await tools.project_get({ venture: "bcrg", slug: "tbff" });
    expect(got!.name).toBe("TBFF");

    const updated = await tools.project_update({
      venture: "bcrg",
      slug: "tbff",
      patch: { priority: "medium" },
    });
    expect(updated.priority).toBe("medium");

    const closed = await tools.project_close({
      venture: "bcrg",
      slug: "tbff",
      stage: "harvesting",
    });
    expect(closed.stage).toBe("harvesting");
  });
});
