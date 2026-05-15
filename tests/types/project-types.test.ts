import { describe, expect, test } from "bun:test";
import type {
  Project,
  CreateProjectInput,
  UpdateProjectInput,
  ProjectFilter,
} from "../../src/types/project";
import { PROJECT_STAGES_ORDERED } from "../../src/types/project";

describe("Project type shape", () => {
  test("PROJECT_STAGES_ORDERED has 6 states", () => {
    expect(PROJECT_STAGES_ORDERED).toEqual([
      "seed",
      "exploring",
      "active",
      "sustaining",
      "dormant",
      "harvesting",
    ]);
  });

  test("Project type compiles with required fields", () => {
    const p: Project = {
      slug: "tbff",
      name: "Threshold-Based Flow Funding",
      venture: "bcrg",
      stage: "active",
      priority: "high",
      owner: "shawn",
      co_owners: [],
      stakeholders: ["hash-n", "jeff-emmett"],
      deadline: "2026-09-30",
      milestones: ["m1-spec", "m2-prototype"],
      docs_dir: "~/.claude/local/ventures/bcrg/projects/tbff/docs/",
      created_at: "2026-05-14T00:00:00Z",
      updated_at: "2026-05-14T00:00:00Z",
      file_path: "/tmp/p.md",
    };
    expect(p.slug).toBe("tbff");
    expect(p.venture).toBe("bcrg");
  });

  test("CreateProjectInput omits id/timestamps", () => {
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
    expect(input.slug).toBe("tbff");
  });

  test("ProjectFilter accepts venture+stage+owner", () => {
    const f: ProjectFilter = { venture: "bcrg", stage: "active", owner: "shawn" };
    expect(f.venture).toBe("bcrg");
  });
});
