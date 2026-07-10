import type { UnitsSettings } from "../state/settingsStore";

// Some Node/ICU versions separate the hour from AM/PM with a narrow
// no-break space (U+202F) instead of a plain space for this locale --
// normalized away so callers get one exact string regardless of which
// ICU snapshot the runtime bundles.
const NARROW_NO_BREAK_SPACE = " ";

export function formatTime(
  isoTimestamp: string,
  format: UnitsSettings["timeFormat"],
  timezone?: string | null,
): string {
  const formatter = new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
    hour12: format === "12h",
    timeZone: timezone ?? undefined,
  });
  return formatter
    .format(new Date(isoTimestamp))
    .replaceAll(NARROW_NO_BREAK_SPACE, " ");
}
