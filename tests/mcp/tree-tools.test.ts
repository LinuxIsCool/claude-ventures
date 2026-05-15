import { describe, expect, test, beforeEach, afterEach } from "bun:test";
import { mkdtempSync, rmSync, mkdirSync, writeFileSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import matter from "gray-matter";
import { makeTreeTools } from "../../src/mcp/tools/tree-tools";

let tmpRoot: string;
let tools: ReturnType<typeof makeTreeTools>;

beforeEach(() => {
  tmpRoot = mkdtempSync(join(tmpdir(), "tree-mcp-test-"));
  tools = makeTreeTools({ ventures_root: tmpRoot });
});

afterEach(() => rmSync(tmpRoot, { recursive: true, force: true }));

function writeVenture(slug: string, frontmatter: Record<string, any> = {}) {
  mkdirSync(join(tmpRoot, "active"), { recursive: true });
  writeFileSync(
    join(tmpRoot, "active", `${slug}.md`),
    matter.stringify("", { slug, name: slug, stage: "active", priority: "high", ...frontmatter })
  );
}

describe("venture_tree", () => {
  test("returns nested venture for existing slug", async () => {
    writeVenture("bcrg");
    const tree = await tools.venture_tree({ slug: "bcrg" });
    expect(tree).not.toBeNull();
    expect(tree!.venture.slug).toBe("bcrg");
    expect(tree!.projects).toEqual([]);
  });

  test("returns null for missing", async () => {
    expect(await tools.venture_tree({ slug: "missing" })).toBeNull();
  });
});

describe("venture_co_links", () => {
  test("returns peer + parent + child references", async () => {
    writeVenture("symbiocene-labs", { child_ventures: ["regen-ai"] });
    writeVenture("regen-network", { child_ventures: ["regen-ai"] });
    writeVenture("regen-ai", {
      parent_ventures: ["symbiocene-labs", "regen-network"],
      co_ventures: [],
    });
    writeVenture("cascadia-systems", { co_ventures: ["longtail-financial"] });
    writeVenture("longtail-financial", { co_ventures: ["cascadia-systems"] });

    const links = await tools.venture_co_links({ slug: "regen-ai" });
    expect(links!.parent_ventures).toEqual(["symbiocene-labs", "regen-network"]);
    expect(links!.co_ventures).toEqual([]);
    expect(links!.child_ventures).toEqual([]);

    const cas = await tools.venture_co_links({ slug: "cascadia-systems" });
    expect(cas!.co_ventures).toEqual(["longtail-financial"]);
  });
});
