/**
 * Priority Calculator
 *
 * Venture-adapted priority ranking with these weights:
 *   External deadline urgency:  45%
 *   Manual priority:            30%
 *   Strategic alignment:        15%
 *   Financial signal:            5%
 *   Stage modifier:              5%
 *
 * Key differences from upstream projects plugin:
 * - No recency decay — dormant ventures keep their manual priority indefinitely
 * - External deadlines use cliff curve (spike as date approaches)
 * - Deadlines typed as external (immovable) vs internal (flexible)
 * - Strategic alignment boosts ventures connected to other active ventures
 */

import type {
  Venture,
  Deadline,
  PriorityContext,
  PriorityScore,
  PriorityBreakdown,
  PriorityWeights,
  VentureStageValue,
  PriorityLevelValue,
} from "../types";
import { DEFAULT_PRIORITY_WEIGHTS } from "../types";

// =============================================================================
// Date Utilities
// =============================================================================

function daysBetween(from: Date, to: Date): number {
  const msPerDay = 24 * 60 * 60 * 1000;
  return (to.getTime() - from.getTime()) / msPerDay;
}

function parseDeadline(deadline: Deadline): Date {
  const date = new Date(deadline.date);
  if (deadline.time) {
    const [hours, minutes] = deadline.time.split(":").map(Number);
    date.setHours(hours, minutes, 0, 0);
  } else {
    date.setHours(23, 59, 59, 999);
  }
  return date;
}

// =============================================================================
// Component Calculators
// =============================================================================

function findNearestDeadline(venture: Venture): Deadline | null {
  const deadlines: Deadline[] = [...venture.deadlines];

  for (const milestone of venture.milestones) {
    if (!milestone.completed && milestone.deadline) {
      deadlines.push(milestone.deadline);
    }
    for (const deliverable of milestone.deliverables) {
      if (!deliverable.completed && deliverable.deadline) {
        deadlines.push(deliverable.deadline);
      }
    }
  }

  if (deadlines.length === 0) return null;

  deadlines.sort(
    (a, b) => parseDeadline(a).getTime() - parseDeadline(b).getTime()
  );
  return deadlines[0];
}

/**
 * Deadline urgency with cliff curve for external deadlines.
 * External deadlines spike harder as they approach (immovable).
 * Internal deadlines use a gentler curve (flexible).
 */
function calculateDeadlineUrgency(venture: Venture, now: Date): number {
  const nearest = findNearestDeadline(venture);
  if (!nearest) return 0;

  const deadlineDate = parseDeadline(nearest);
  const daysUntil = daysBetween(now, deadlineDate);
  const isExternal = nearest.type === "external";

  if (daysUntil < 0) return 100; // Overdue
  if (daysUntil < 1) return isExternal ? 98 : 90; // Due today

  if (isExternal) {
    // Cliff curve for external deadlines — steep ramp in final 14 days
    if (daysUntil < 3) return 95 - daysUntil * 1.67;
    if (daysUntil < 7) return 90 - (daysUntil - 3) * 2.5;
    if (daysUntil < 14) return 80 - (daysUntil - 7) * 2.86;
    if (daysUntil < 30) return 60 - (daysUntil - 14) * 1.25;
    if (daysUntil < 60) return 40 - (daysUntil - 30) * 0.67;
    if (daysUntil < 90) return 20 - (daysUntil - 60) * 0.33;
    return Math.max(5, 10 - (daysUntil - 90) * 0.05);
  } else {
    // Gentler curve for internal deadlines
    if (daysUntil < 3) return 85 - daysUntil * 3.33;
    if (daysUntil < 7) return 75 - (daysUntil - 3) * 3.75;
    if (daysUntil < 14) return 60 - (daysUntil - 7) * 2.86;
    if (daysUntil < 30) return 40 - (daysUntil - 14) * 1.25;
    if (daysUntil < 90) return 20 - (daysUntil - 30) * 0.17;
    return Math.max(3, 10 - (daysUntil - 90) * 0.05);
  }
}

function calculateManualPriority(priority: PriorityLevelValue): number {
  const scores: Record<PriorityLevelValue, number> = {
    critical: 100,
    high: 75,
    medium: 50,
    low: 25,
    none: 0,
  };
  return scores[priority] ?? 0;
}

/**
 * Strategic alignment: boost ventures connected to other active ventures.
 * Each active related venture adds a connection bonus.
 */
function calculateStrategicAlignment(
  venture: Venture,
  allVentures?: Venture[]
): number {
  if (!allVentures || venture.related_ventures.length === 0) return 0;

  const activeRelated = venture.related_ventures.filter((relId) => {
    const related = allVentures.find((v) => v.id === relId);
    return related && (related.stage === "active" || related.stage === "exploring");
  });

  // Each active connection contributes up to 25 points, max 100
  return Math.min(100, activeRelated.length * 25);
}

function calculateFinancialSignal(venture: Venture): number {
  if (!venture.financial) return 0;

  const { outstanding, status, opportunities } = venture.financial;

  // Outstanding payments get highest signal
  if (outstanding && outstanding.amount > 0) {
    const logValue = Math.log10(Math.max(outstanding.amount, 1));
    return Math.min(100, (logValue / 6) * 100);
  }

  // Funding status signal
  if (status === "seeking") return 40;
  if (status === "partial") return 30;
  if (status === "funded") return 20;

  // Opportunities with deadlines
  if (opportunities && opportunities.length > 0) {
    return 15;
  }

  return 0;
}

/**
 * Stage modifier — non-linear, ventures can be in any stage.
 * Dormant ventures keep their manual priority (no decay).
 */
function calculateStageModifier(stage: VentureStageValue): number {
  const modifiers: Record<VentureStageValue, number> = {
    active: 1.0,
    exploring: 0.8,
    sustaining: 0.7,
    seed: 0.5,
    harvesting: 0.4,
    dormant: 0.3,
  };
  return modifiers[stage] ?? 0.5;
}

// =============================================================================
// Main Calculator
// =============================================================================

export function createDefaultContext(
  weights?: Partial<PriorityWeights>
): PriorityContext {
  return {
    now: new Date(),
    weights: { ...DEFAULT_PRIORITY_WEIGHTS, ...weights },
  };
}

export function calculatePriority(
  venture: Venture,
  context: PriorityContext = createDefaultContext()
): PriorityScore {
  const { now, weights, all_ventures } = context;

  const deadlineUrgency = calculateDeadlineUrgency(venture, now);
  const manualPriority = calculateManualPriority(venture.priority);
  const strategicAlignment = calculateStrategicAlignment(venture, all_ventures);
  const financialSignal = calculateFinancialSignal(venture);
  const stageModifier = calculateStageModifier(venture.stage);

  // Weighted sum
  const totalRaw =
    deadlineUrgency * weights.deadline_urgency +
    manualPriority * weights.manual_priority +
    strategicAlignment * weights.strategic_alignment +
    financialSignal * weights.financial_signal +
    stageModifier * 100 * weights.stage_modifier;

  const breakdown: PriorityBreakdown = {
    deadline_urgency: Math.round(deadlineUrgency * weights.deadline_urgency),
    manual_priority: Math.round(manualPriority * weights.manual_priority),
    strategic_alignment: Math.round(strategicAlignment * weights.strategic_alignment),
    financial_signal: Math.round(financialSignal * weights.financial_signal),
    stage_modifier: Math.round(stageModifier * 100 * weights.stage_modifier),
    total_raw: Math.round(totalRaw),
  };

  const nearestDeadline = findNearestDeadline(venture);
  const daysUntilDeadline = nearestDeadline
    ? daysBetween(now, parseDeadline(nearestDeadline))
    : undefined;

  return {
    total: Math.min(100, Math.max(0, Math.round(totalRaw))),
    breakdown,
    nearest_deadline: nearestDeadline?.date,
    days_until_deadline:
      daysUntilDeadline !== undefined ? Math.round(daysUntilDeadline) : undefined,
  };
}

export function sortByPriority(
  ventures: Venture[],
  context?: PriorityContext
): Venture[] {
  const ctx = context || createDefaultContext();
  // Provide all ventures for strategic alignment calculation
  const ctxWithAll = { ...ctx, all_ventures: ventures };

  return [...ventures]
    .map((venture) => ({
      venture,
      score: calculatePriority(venture, ctxWithAll),
    }))
    .sort((a, b) => b.score.total - a.score.total)
    .map(({ venture, score }) => ({
      ...venture,
      calculated_priority: score.total,
    }));
}

export function getUrgentVentures(
  ventures: Venture[],
  daysThreshold = 14
): Venture[] {
  const now = new Date();

  return ventures.filter((venture) => {
    if (venture.stage === "dormant" || venture.stage === "harvesting") return false;

    const nearest = findNearestDeadline(venture);
    if (!nearest) return false;

    const daysUntil = daysBetween(now, parseDeadline(nearest));
    return daysUntil <= daysThreshold;
  });
}
