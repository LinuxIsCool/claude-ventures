/**
 * Priority scoring for Projects and Milestones (deadline-driven work items).
 *
 * Mirrors the external-deadline cliff curve from ../priority/calculator.ts
 * (venture-level formula) but drops the venture-only components — strategic
 * alignment and financial signal don't apply to a single project/milestone.
 *
 * Weights:
 *   Deadline urgency: 60%
 *   Manual priority tag: 40%
 *
 * Projects/milestones only have one deadline field (no external/internal
 * distinction like ventures do), so they always use the steeper "external"
 * cliff curve — a project deadline is treated as effectively immovable.
 */

import type { PriorityLevelValue } from "../types";

export const ITEM_PRIORITY_WEIGHTS = {
  deadline_urgency: 0.6,
  manual_priority: 0.4,
} as const;

const MANUAL_PRIORITY_SCORES: Record<PriorityLevelValue, number> = {
  critical: 100,
  high: 75,
  medium: 50,
  low: 25,
  none: 0,
};

function daysBetween(from: Date, to: Date): number {
  const msPerDay = 24 * 60 * 60 * 1000;
  return (to.getTime() - from.getTime()) / msPerDay;
}

/**
 * Deadline urgency cliff curve — same shape as the venture calculator's
 * external-deadline curve (overdue = 100 flat, ramps hard in the final
 * 14 days, long tail beyond 90 days).
 */
export function calculateItemDeadlineUrgency(
  deadline: string | undefined,
  now: Date = new Date()
): number {
  if (!deadline) return 0;

  const deadlineDate = new Date(deadline);
  if (Number.isNaN(deadlineDate.getTime())) return 0;
  deadlineDate.setHours(23, 59, 59, 999);

  const daysUntil = daysBetween(now, deadlineDate);

  if (daysUntil < 0) return 100; // Overdue
  if (daysUntil < 1) return 98; // Due today
  if (daysUntil < 3) return 95 - daysUntil * 1.67;
  if (daysUntil < 7) return 90 - (daysUntil - 3) * 2.5;
  if (daysUntil < 14) return 80 - (daysUntil - 7) * 2.86;
  if (daysUntil < 30) return 60 - (daysUntil - 14) * 1.25;
  if (daysUntil < 60) return 40 - (daysUntil - 30) * 0.67;
  if (daysUntil < 90) return 20 - (daysUntil - 60) * 0.33;
  return Math.max(5, 10 - (daysUntil - 90) * 0.05);
}

export function calculateManualPriorityScore(priority: PriorityLevelValue): number {
  return MANUAL_PRIORITY_SCORES[priority] ?? 0;
}

/**
 * Weighted priority score (0-100, higher = more urgent) for a project or
 * milestone. Same field name/shape as venture.calculated_priority so
 * downstream consumers (min_priority filters, etc.) stay compatible.
 */
export function calculateItemPriority(
  priority: PriorityLevelValue,
  deadline: string | undefined,
  now: Date = new Date()
): number {
  const deadlineUrgency = calculateItemDeadlineUrgency(deadline, now);
  const manualPriority = calculateManualPriorityScore(priority);

  const total =
    deadlineUrgency * ITEM_PRIORITY_WEIGHTS.deadline_urgency +
    manualPriority * ITEM_PRIORITY_WEIGHTS.manual_priority;

  return Math.round(Math.min(100, Math.max(0, total)));
}
