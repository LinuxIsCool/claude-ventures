import { describe, expect, test } from "bun:test";
import type {
  MilestoneV2,
  CreateMilestoneInput,
  UpdateMilestoneInput,
  MilestoneFilter,
} from "../../src/types/milestone-v2";

describe("MilestoneV2 type shape", () => {
  test("required fields compile", () => {
    const m: MilestoneV2 = {
      slug: "m1-spec",
      name: "TBFF Spec v1 published",
      project: "tbff",
      venture: "bcrg",
      stage: "active",
      priority: "high",
      target: "Spec doc published, reviewed by 3 stakeholders",
      deadline: "2026-06-15",
      exit_criteria: ["Spec.md committed", "3 reviews complete"],
      docs_dir: "~/.claude/local/ventures/bcrg/projects/tbff/milestones/m1-spec/docs/",
      tasks: [101, 102, 105],
      created_at: "2026-05-14T00:00:00Z",
      updated_at: "2026-05-14T00:00:00Z",
      file_path: "/tmp/m.md",
    };
    expect(m.slug).toBe("m1-spec");
    expect(m.tasks).toHaveLength(3);
  });

  test("CreateMilestoneInput omits timestamps", () => {
    const input: CreateMilestoneInput = {
      slug: "m1-spec",
      name: "Spec",
      project: "tbff",
      venture: "bcrg",
      stage: "active",
      priority: "high",
      target: "ship",
      exit_criteria: [],
      tasks: [],
    };
    expect(input.slug).toBe("m1-spec");
  });

  test("MilestoneFilter accepts project+venture+due_within", () => {
    const f: MilestoneFilter = {
      venture: "bcrg",
      project: "tbff",
      due_within_days: 30,
    };
    expect(f.due_within_days).toBe(30);
  });
});
