import { describe, expect, test } from "bun:test";
import {
  getVentureTreeRoot,
  getProjectDirectory,
  getProjectFilePath,
  getMilestoneDirectory,
  getMilestoneFilePath,
} from "../src/config";

describe("fractal path helpers", () => {
  test("getVentureTreeRoot returns ~/ventures/{slug}", () => {
    const p = getVentureTreeRoot("bcrg");
    expect(p).toMatch(/\/ventures\/bcrg$/);
  });

  test("getProjectDirectory returns .../projects/{slug}", () => {
    const p = getProjectDirectory("bcrg", "tbff");
    expect(p).toMatch(/\/ventures\/bcrg\/projects\/tbff$/);
  });

  test("getProjectFilePath returns .../projects/{slug}/project.md", () => {
    const p = getProjectFilePath("bcrg", "tbff");
    expect(p).toMatch(/\/ventures\/bcrg\/projects\/tbff\/project\.md$/);
  });

  test("getMilestoneDirectory returns .../milestones/{slug}", () => {
    const p = getMilestoneDirectory("bcrg", "tbff", "m1-spec");
    expect(p).toMatch(/\/ventures\/bcrg\/projects\/tbff\/milestones\/m1-spec$/);
  });

  test("getMilestoneFilePath returns .../milestones/{slug}.md", () => {
    const p = getMilestoneFilePath("bcrg", "tbff", "m1-spec");
    expect(p).toMatch(/\/ventures\/bcrg\/projects\/tbff\/milestones\/m1-spec\.md$/);
  });
});
