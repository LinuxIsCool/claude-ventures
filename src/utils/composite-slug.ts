/**
 * Composite slug utilities for the fractal V/P/M hierarchy.
 * Format: "bcrg" (venture), "bcrg.tbff" (project), "bcrg.tbff.m1-spec" (milestone).
 */

export type CompositeSlugLevel = "venture" | "project" | "milestone";

export interface ParsedCompositeSlug {
  level: CompositeSlugLevel;
  venture: string;
  project?: string;
  milestone?: string;
}

export interface BuildCompositeSlugInput {
  venture: string;
  project?: string;
  milestone?: string;
}

const SLUG_SEGMENT_RE = /^[a-z0-9][a-z0-9-]*$/;

export function isValidSlugSegment(s: string): boolean {
  return SLUG_SEGMENT_RE.test(s);
}

export function parseCompositeSlug(slug: string): ParsedCompositeSlug {
  if (!slug) throw new Error("empty composite slug");
  const parts = slug.split(".");
  if (parts.length > 3) throw new Error(`too many segments in "${slug}" (max 3)`);
  for (const seg of parts) {
    if (!isValidSlugSegment(seg)) {
      throw new Error(`invalid slug segment "${seg}" in "${slug}"`);
    }
  }
  const level: CompositeSlugLevel =
    parts.length === 1 ? "venture" : parts.length === 2 ? "project" : "milestone";
  return {
    level,
    venture: parts[0],
    project: parts[1],
    milestone: parts[2],
  };
}

export function buildCompositeSlug(input: BuildCompositeSlugInput): string {
  if (input.project && !input.venture) {
    throw new Error("venture required when project specified");
  }
  if (input.milestone && !input.project) {
    throw new Error("project required when milestone specified");
  }
  const parts = [input.venture];
  if (input.project) parts.push(input.project);
  if (input.milestone) parts.push(input.milestone);
  return parts.join(".");
}

export function slugLevel(slug: string): CompositeSlugLevel {
  return parseCompositeSlug(slug).level;
}
