/**
 * Claude Ventures - Configuration
 *
 * Paths anchored to ~/.claude/local/ventures/ for the venture index (layer 2).
 * Heavy data lives on the data drive (layer 3), configured via data_drive_path.
 */

import { join } from "path";
import { homedir } from "os";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "fs";
import { parse as parseYaml, stringify as stringifyYaml } from "yaml";
import type { VenturesConfig, PriorityWeights, VentureStageValue } from "./types";
import { DEFAULT_PRIORITY_WEIGHTS, DEFAULT_CONFIG } from "./types";

// =============================================================================
// Path Configuration
// =============================================================================

function getVenturesBasePath(): string {
  return join(homedir(), ".claude", "local", "ventures");
}

function getStagePath(stage: string): string {
  return join(getVenturesBasePath(), stage);
}

function getConfigPath(): string {
  return join(getVenturesBasePath(), "config.yml");
}

export function getVentureDirectory(stage: VentureStageValue): string {
  return getStagePath(stage);
}

/**
 * Per-venture tree root: ~/.claude/local/ventures/{venture-slug}/
 * Used by Project + Milestone storage per fractal Phase 0 spec.
 */
export function getVentureTreeRoot(ventureSlug: string): string {
  return join(paths.base, ventureSlug);
}

/**
 * Project directory: ~/.claude/local/ventures/{venture}/projects/{project}/
 */
export function getProjectDirectory(ventureSlug: string, projectSlug: string): string {
  return join(getVentureTreeRoot(ventureSlug), "projects", projectSlug);
}

/**
 * Project file: ~/.claude/local/ventures/{venture}/projects/{project}/project.md
 */
export function getProjectFilePath(ventureSlug: string, projectSlug: string): string {
  return join(getProjectDirectory(ventureSlug, projectSlug), "project.md");
}

/**
 * Milestone docs directory: ~/.claude/local/ventures/{venture}/projects/{project}/milestones/{milestone}/
 * Sibling to the milestone .md file.
 */
export function getMilestoneDirectory(
  ventureSlug: string,
  projectSlug: string,
  milestoneSlug: string
): string {
  return join(
    getProjectDirectory(ventureSlug, projectSlug),
    "milestones",
    milestoneSlug
  );
}

/**
 * Milestone file: ~/.claude/local/ventures/{venture}/projects/{project}/milestones/{milestone}.md
 */
export function getMilestoneFilePath(
  ventureSlug: string,
  projectSlug: string,
  milestoneSlug: string
): string {
  return join(
    getProjectDirectory(ventureSlug, projectSlug),
    "milestones",
    `${milestoneSlug}.md`
  );
}

export const paths = {
  get base() {
    return getVenturesBasePath();
  },
  get active() {
    return getStagePath("active");
  },
  get exploring() {
    return getStagePath("exploring");
  },
  get seed() {
    return getStagePath("seed");
  },
  get sustaining() {
    return getStagePath("sustaining");
  },
  get dormant() {
    return getStagePath("dormant");
  },
  get harvesting() {
    return getStagePath("harvesting");
  },
  get config() {
    return getConfigPath();
  },
};

// =============================================================================
// Directory Initialization
// =============================================================================

export function ensureDirectories(): void {
  const dirs = [
    getVenturesBasePath(),
    getStagePath("seed"),
    getStagePath("exploring"),
    getStagePath("active"),
    getStagePath("sustaining"),
    getStagePath("dormant"),
    getStagePath("harvesting"),
  ];

  for (const dir of dirs) {
    if (!existsSync(dir)) {
      mkdirSync(dir, { recursive: true });
    }
  }
}

export function isInitialized(): boolean {
  return existsSync(getVenturesBasePath()) && existsSync(getStagePath("active"));
}

// =============================================================================
// Configuration Management
// =============================================================================

export const defaultConfig: VenturesConfig = { ...DEFAULT_CONFIG };

export function loadConfig(): VenturesConfig {
  const configPath = getConfigPath();

  if (!existsSync(configPath)) {
    return { ...defaultConfig };
  }

  try {
    const content = readFileSync(configPath, "utf-8");
    const parsed = parseYaml(content) as Partial<VenturesConfig>;

    return {
      ...defaultConfig,
      ...parsed,
      priority_weights: {
        ...defaultConfig.priority_weights,
        ...(parsed.priority_weights || {}),
      },
    };
  } catch {
    console.error("Failed to load ventures config, using defaults");
    return { ...defaultConfig };
  }
}

export function saveConfig(config: VenturesConfig): void {
  ensureDirectories();
  const configPath = getConfigPath();
  const content = stringifyYaml(config);
  writeFileSync(configPath, content, "utf-8");
}

export function updatePriorityWeights(weights: Partial<PriorityWeights>): void {
  const config = loadConfig();
  config.priority_weights = {
    ...config.priority_weights,
    ...weights,
  };
  saveConfig(config);
}
