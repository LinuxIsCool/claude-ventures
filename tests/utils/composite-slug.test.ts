import { describe, expect, test } from "bun:test";
import {
  parseCompositeSlug,
  buildCompositeSlug,
  slugLevel,
  isValidSlugSegment,
  type CompositeSlugLevel,
} from "../../src/utils/composite-slug";

describe("parseCompositeSlug", () => {
  test("parses venture-level slug", () => {
    expect(parseCompositeSlug("bcrg")).toEqual({
      level: "venture",
      venture: "bcrg",
      project: undefined,
      milestone: undefined,
    });
  });

  test("parses project-level slug", () => {
    expect(parseCompositeSlug("bcrg.tbff")).toEqual({
      level: "project",
      venture: "bcrg",
      project: "tbff",
      milestone: undefined,
    });
  });

  test("parses milestone-level slug", () => {
    expect(parseCompositeSlug("bcrg.tbff.m1-spec")).toEqual({
      level: "milestone",
      venture: "bcrg",
      project: "tbff",
      milestone: "m1-spec",
    });
  });

  test("throws on empty", () => {
    expect(() => parseCompositeSlug("")).toThrow("empty composite slug");
  });

  test("throws on >3 segments", () => {
    expect(() => parseCompositeSlug("a.b.c.d")).toThrow("too many segments");
  });

  test("throws on invalid segment characters", () => {
    expect(() => parseCompositeSlug("bcrg.t bff")).toThrow("invalid slug segment");
  });
});

describe("buildCompositeSlug", () => {
  test("builds venture-level", () => {
    expect(buildCompositeSlug({ venture: "bcrg" })).toBe("bcrg");
  });

  test("builds project-level", () => {
    expect(buildCompositeSlug({ venture: "bcrg", project: "tbff" })).toBe("bcrg.tbff");
  });

  test("builds milestone-level", () => {
    expect(
      buildCompositeSlug({ venture: "bcrg", project: "tbff", milestone: "m1-spec" })
    ).toBe("bcrg.tbff.m1-spec");
  });

  test("throws if project given but venture missing", () => {
    expect(() => buildCompositeSlug({ project: "tbff" } as any)).toThrow(
      "venture required when project specified"
    );
  });

  test("throws if milestone given but project missing", () => {
    expect(() => buildCompositeSlug({ venture: "bcrg", milestone: "m1" } as any)).toThrow(
      "project required when milestone specified"
    );
  });
});

describe("slugLevel", () => {
  test("identifies venture", () => expect(slugLevel("bcrg")).toBe("venture"));
  test("identifies project", () => expect(slugLevel("bcrg.tbff")).toBe("project"));
  test("identifies milestone", () => expect(slugLevel("bcrg.tbff.m1-spec")).toBe("milestone"));
});

describe("isValidSlugSegment", () => {
  test("accepts lowercase + digits + dash", () => {
    expect(isValidSlugSegment("bcrg-2")).toBe(true);
  });
  test("rejects uppercase", () => expect(isValidSlugSegment("BCRG")).toBe(false));
  test("rejects spaces", () => expect(isValidSlugSegment("b crg")).toBe(false));
  test("rejects empty", () => expect(isValidSlugSegment("")).toBe(false));
  test("rejects dots", () => expect(isValidSlugSegment("b.c")).toBe(false));
});
