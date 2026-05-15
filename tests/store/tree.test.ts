import { describe, expect, test, beforeEach, afterEach } from "bun:test";
import { mkdtempSync, rmSync, mkdirSync, writeFileSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import { VentureTreeBuilder } from "../../src/store/tree";
import { ProjectStore } from "../../src/store/project";
import { MilestoneStore } from "../../src/store/milestone";

let tmpRoot: string;
let builder: VentureTreeBuilder;

beforeEach(async () => {
  tmpRoot = mkdtempSync(join(tmpdir(), "tree-test-"));
  // Create a venture .md file at active/bcrg.md
  mkdirSync(join(tmpRoot, "active"), { recursive: true });
  writeFileSync(
    join(tmpRoot, "active", "bcrg.md"),
    `---\nslug: bcrg\nname: BCRG\nstage: active\npriority: high\n---\n# BCRG\n`
  );
  const ps = new ProjectStore({ ventures_root: tmpRoot });
  const ms = new MilestoneStore({ ventures_root: tmpRoot });
  await ps.create({
    slug: "tbff",
    name: "TBFF",
    venture: "bcrg",
    stage: "active",
    priority: "high",
    owner: "shawn",
    co_owners: [],
    stakeholders: [],
    milestones: ["m1-spec"],
  });
  await ms.create({
    slug: "m1-spec",
    name: "Spec",
    project: "tbff",
    venture: "bcrg",
    stage: "active",
    priority: "high",
    target: "ship spec",
    exit_criteria: [],
    tasks: [],
  });
  builder = new VentureTreeBuilder({ ventures_root: tmpRoot });
});

afterEach(() => rmSync(tmpRoot, { recursive: true, force: true }));

describe("VentureTreeBuilder.build", () => {
  test("returns nested V→P→M structure", async () => {
    const tree = await builder.build("bcrg");
    expect(tree).not.toBeNull();
    expect(tree!.venture.slug).toBe("bcrg");
    expect(tree!.projects).toHaveLength(1);
    expect(tree!.projects[0].project.slug).toBe("tbff");
    expect(tree!.projects[0].milestones).toHaveLength(1);
    expect(tree!.projects[0].milestones[0].slug).toBe("m1-spec");
  });

  test("returns null for missing venture", async () => {
    expect(await builder.build("missing")).toBeNull();
  });
});
