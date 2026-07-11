import { describe, expect, it } from "vitest";

import { formatDayLabel, formatTime } from "../../src/format/time";

describe("formatTime", () => {
  it("formats in 24h", () => {
    expect(formatTime("2026-07-10T15:45:00Z", "24h", "UTC")).toBe("15:45");
  });

  it("formats in 12h with AM/PM", () => {
    expect(formatTime("2026-07-10T15:45:00Z", "12h", "UTC")).toBe("3:45 PM");
  });

  it("formats midnight as 12 AM", () => {
    expect(formatTime("2026-07-10T00:15:00Z", "12h", "UTC")).toBe("12:15 AM");
  });

  it("formats noon as 12 PM", () => {
    expect(formatTime("2026-07-10T12:00:00Z", "12h", "UTC")).toBe("12:00 PM");
  });

  it("converts to the reading's own location timezone, not the caller's", () => {
    expect(formatTime("2026-07-10T15:45:00Z", "12h", "Asia/Tokyo")).toBe(
      "12:45 AM",
    );
  });

  it("falls back gracefully when the timezone is null", () => {
    const result = formatTime("2026-07-10T15:45:00Z", "12h", null);
    expect(result).toMatch(/^\d{1,2}:\d{2}/);
  });

  it("falls back gracefully when the timezone is omitted", () => {
    const result = formatTime("2026-07-10T15:45:00Z", "24h");
    expect(result).toMatch(/^\d{1,2}:\d{2}/);
  });
});

describe("formatDayLabel", () => {
  it("formats a date as a short weekday", () => {
    expect(formatDayLabel("2026-07-10")).toBe("Fri");
  });

  it("reads the weekday from the date string itself, not a local timezone", () => {
    expect(formatDayLabel("2026-07-12")).toBe("Sun");
  });
});
