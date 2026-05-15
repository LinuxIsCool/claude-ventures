import { describe, expect, test, beforeEach, afterEach } from "bun:test";
import { mkdtempSync, rmSync, mkdirSync, writeFileSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import { FKValidator } from "../../src/validation/fk";

let tmpRoot: string;
let v: FKValidator;

beforeEach(() => {
  tmpRoot = mkdtempSync(join(tmpdir(), "fk-test-"));
  v = new FKValidator({ ventures_root: tmpRoot });
});

afterEach(() => rmSync(tmpRoot, { recursive: true, force: true }));

function seedVenture(slug: string) {
  mkdirSync(join(tmpRoot, "active"), { recursive: true });
  writeFileSync(join(tmpRoot, "active", `${slug}.md`), `---\nslug: ${slug}\n---\n`);
}

function seedProject(venture: string, slug: string) {
  mkdirSync(join(tmpRoot, venture, "projects", slug), { recursive: true });
  writeFileSync(
    join(tmpRoot, venture, "projects", slug, "project.md"),
    `---\nslug: ${slug}\nventure: ${venture}\n---\n`
  );
}

function seedMilestone(venture: string, project: string, slug: string) {
  mkdirSync(join(tmpRoot, venture, "projects", project, "milestones"), { recursive: true });
  writeFileSync(
    join(tmpRoot, venture, "projects", project, "milestones", `${slug}.md`),
    `---\nslug: ${slug}\nproject: ${project}\nventure: ${venture}\n---\n`
  );
}

describe("FKValidator.resolve", () => {
  test("resolves a valid venture FK", async () => {
    seedVenture("bcrg");
    const r = await v.resolve("bcrg", "venture");
    expect(r.ok).toBe(true);
  });

  test("resolves a valid project FK", async () => {
    seedVenture("bcrg");
    seedProject("bcrg", "tbff");
    const r = await v.resolve("bcrg.tbff", "project");
    expect(r.ok).toBe(true);
  });

  test("resolves a valid milestone FK", async () => {
    seedVenture("bcrg");
    seedProject("bcrg", "tbff");
    seedMilestone("bcrg", "tbff", "m1-spec");
    const r = await v.resolve("bcrg.tbff.m1-spec", "milestone");
    expect(r.ok).toBe(true);
  });

  test("rejects missing venture", async () => {
    const r = await v.resolve("missing", "venture");
    expect(r.ok).toBe(false);
    expect(r.error).toMatch(/not found/);
  });

  test("rejects missing project", async () => {
    seedVenture("bcrg");
    const r = await v.resolve("bcrg.missing", "project");
    expect(r.ok).toBe(false);
  });

  test("rejects missing milestone", async () => {
    seedVenture("bcrg");
    seedProject("bcrg", "tbff");
    const r = await v.resolve("bcrg.tbff.missing", "milestone");
    expect(r.ok).toBe(false);
  });

  test("rejects parent_type mismatch (slug vs declared type)", async () => {
    seedVenture("bcrg");
    seedProject("bcrg", "tbff");
    const r = await v.resolve("bcrg.tbff", "milestone");
    expect(r.ok).toBe(false);
    expect(r.error).toMatch(/level mismatch/);
  });

  test("rejects unknown parent_type value", async () => {
    const r = await v.resolve("bcrg", "task" as any);
    expect(r.ok).toBe(false);
    expect(r.error).toMatch(/invalid parent_type/);
  });
});
