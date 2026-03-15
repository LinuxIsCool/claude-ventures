/**
 * Date utilities for claude-ventures
 *
 * Uses local timezone — not UTC — so dates match the user's wall clock.
 */

/** Format a Date as "YYYY-MM-DD" in local timezone */
export function formatDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** Return today as "YYYY-MM-DD" in local timezone */
export function localDateStr(d: Date = new Date()): string {
  return formatDate(d);
}
