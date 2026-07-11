import type { DailyReading } from "../contract";

/**
 * True if `timestamp` falls within any daily entry's [sunrise, sunset)
 * window (absolute-instant comparison, timezone-agnostic). Defaults to
 * true (daytime) when there's no usable sunrise/sunset data to check
 * against at all -- matching getConditionIcon's own isDaytime=true
 * default -- but returns false when real data confirms the timestamp
 * falls outside every known daylight window (a confident "it's night"
 * answer, not an absence of data).
 */
export function isDaytimeAt(
  timestamp: string,
  daily: DailyReading[] | null,
): boolean {
  if (daily === null) return true;

  const t = new Date(timestamp).getTime();
  let hasUsableWindow = false;

  for (const day of daily) {
    if (day.sunrise === null || day.sunset === null) continue;
    hasUsableWindow = true;

    const sunrise = new Date(day.sunrise).getTime();
    const sunset = new Date(day.sunset).getTime();
    if (t >= sunrise && t < sunset) return true;
  }

  return !hasUsableWindow;
}
