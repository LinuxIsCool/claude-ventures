import { describe, expect, test, beforeEach, afterEach } from "bun:test";
import { mkdtempSync, rmSync, mkdirSync, writeFileSync, readFileSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import matter from "gray-matter";
import { CoVentureMirror } from "../../src/store/co-venture";

let tmpRoot: string;
let mirror: CoVentureMirror;

function writeVenture(stage: string, slug: string, frontmatter: Record<string, any>) {
  const dir = join(tmpRoot, stage);
  mkdirSync(dir, { recursive: true });
  writeFileSync(
    join(dir, `${slug}.md`),
    matter.stringify("# body", { slug, name: slug, stage, priority: "high", ...frontmatter })
  );
}

beforeEach(() => {
  tmpRoot = mkdtempSync(join(tmpdir(), "covent-test-"));
  mirror = new CoVentureMirror({ ventures_root: tmpRoot });
});

afterEach(() => rmSync(tmpRoot, { recursive: true, force: true }));

describe("CoVentureMirror.rebuildChildVentures", () => {
  test("auto-derives child_ventures from parent_ventures back-refs", async () => {
    writeVenture("active", "symbiocene-labs", { parent_ventures: [] });
    writeVenture("active", "regen-network", { parent_ventures: [] });
    writeVenture("active", "regen-ai", {
      parent_ventures: ["symbiocene-labs", "regen-network"],
    });

    const result = await mirror.rebuildChildVentures();

    expect(result.updated).toEqual(
      expect.arrayContaining(["symbiocene-labs", "regen-network"])
    );

    const symb = matter(readFileSync(join(tmpRoot, "active", "symbiocene-labs.md"), "utf-8"));
    expect(symb.data.child_ventures).toEqual(["regen-ai"]);

    const regen = matter(readFileSync(join(tmpRoot, "active", "regen-network.md"), "utf-8"));
    expect(regen.data.child_ventures).toEqual(["regen-ai"]);
  });

  test("clears stale child_ventures entries", async () => {
    writeVenture("active", "symbiocene-labs", {
      parent_ventures: [],
      child_ventures: ["regen-ai", "ghost-venture"],
    });
    writeVenture("active", "regen-ai", { parent_ventures: ["symbiocene-labs"] });

    await mirror.rebuildChildVentures();

    const symb = matter(readFileSync(join(tmpRoot, "active", "symbiocene-labs.md"), "utf-8"));
    expect(symb.data.child_ventures).toEqual(["regen-ai"]);
  });

  test("validates peer-symmetric co_ventures (warns on asymmetry)", async () => {
    writeVenture("active", "cascadia-systems", {
      co_ventures: ["longtail-financial"],
      parent_ventures: [],
    });
    writeVenture("active", "longtail-financial", { co_ventures: [], parent_ventures: [] });

    const result = await mirror.validateCoVentures();
    expect(result.asymmetries).toHaveLength(1);
    expect(result.asymmetries[0]).toEqual({
      from: "cascadia-systems",
      to: "longtail-financial",
      missing_back_ref: true,
    });
  });
});
