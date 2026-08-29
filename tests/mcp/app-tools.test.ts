import { describe, expect, test, beforeEach, afterEach } from "bun:test";
import { mkdtempSync, rmSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import { makeAppTools } from "../../src/mcp/tools/app-tools";
import { AppStore } from "../../src/store/app";

let tmpRoot: string;
let tools: ReturnType<typeof makeAppTools>;

const input = {
  slug: "listening",
  name: "CIE Listening App",
  venture: "civic-intelligence-engine",
  kind: "web" as const,
  stage: "paused" as const,
  repo: { path: "~/Workspace/civic-intelligence-engine", remote: "OpenCivics-Labs/civic-intelligence-engine" },
  environments: [{ name: "dev", url: "https://civicintelligence.xyz/dev/", healthz: "/healthz" }],
  depends_on: [],
};

beforeEach(() => {
  tmpRoot = mkdtempSync(join(tmpdir(), "app-mcp-test-"));
  tools = makeAppTools(new AppStore({ ventures_root: tmpRoot }));
});
afterEach(() => rmSync(tmpRoot, { recursive: true, force: true }));

describe("app tools", () => {
  test("create then get", async () => {
    await tools.app_create(input);
    const got = await tools.app_get({ venture: "civic-intelligence-engine", slug: "listening" });
    expect(got?.name).toBe("CIE Listening App");
  });

  test("list with venture filter and sort", async () => {
    await tools.app_create(input);
    await tools.app_create({ ...input, slug: "api", name: "CIE API" });
    const out = await tools.app_list({ venture: "civic-intelligence-engine", sort_by: "name" });
    expect(out.map((a) => a.slug)).toEqual(["api", "listening"]);
  });

  test("list filters by stage array", async () => {
    await tools.app_create({ ...input, slug: "active-app", stage: "active" });
    await tools.app_create({ ...input, slug: "paused-app", stage: "paused" });
    await tools.app_create({ ...input, slug: "retired-app", stage: "retired" });
    const out = await tools.app_list({ venture: "civic-intelligence-engine", stage: ["active", "paused"] });
    expect(out.map((a) => a.slug).sort()).toEqual(["active-app", "paused-app"]);
  });

  test("list filters by kind array", async () => {
    await tools.app_create({ ...input, slug: "static-app", kind: "static" });
    await tools.app_create({ ...input, slug: "web-app", kind: "web" });
    await tools.app_create({ ...input, slug: "api-app", kind: "api" });
    const out = await tools.app_list({ venture: "civic-intelligence-engine", kind: ["static", "web"] });
    expect(out.map((a) => a.slug).sort()).toEqual(["static-app", "web-app"]);
  });

  test("update merges a patch", async () => {
    await tools.app_create(input);
    const out = await tools.app_update({ venture: "civic-intelligence-engine", slug: "listening", patch: { run: "npm run dev" } });
    expect(out.run).toBe("npm run dev");
  });

  test("close sets stage and appends notes", async () => {
    await tools.app_create(input);
    const out = await tools.app_close({ venture: "civic-intelligence-engine", slug: "listening", stage: "retired", retro_md: "Pilot cancelled." });
    expect(out.stage).toBe("retired");
    expect(out.notes).toBe("Pilot cancelled.");
  });

  test("get returns null when missing", async () => {
    expect(await tools.app_get({ venture: "civic-intelligence-engine", slug: "nope" })).toBeNull();
  });
});
