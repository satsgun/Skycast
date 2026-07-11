import { describe, expect, it } from "vitest";

import type { DailyReading } from "../../src/contract";
import { isDaytimeAt } from "../../src/format/daylight";

function daily(overrides: Partial<DailyReading>): DailyReading {
  return {
    date: "2026-07-10",
    temp_min: 20,
    temp_max: 30,
    precip_probability: null,
    precip_amount: null,
    wind_speed_max: null,
    condition_code: "CLEAR",
    sunrise: "2026-07-10T06:00:00Z",
    sunset: "2026-07-10T18:00:00Z",
    ...overrides,
  };
}

describe("isDaytimeAt", () => {
  it("is true for a timestamp inside the daily window", () => {
    expect(isDaytimeAt("2026-07-10T12:00:00Z", [daily({})])).toBe(true);
  });

  it("is false for a timestamp outside every daily window", () => {
    expect(isDaytimeAt("2026-07-10T22:00:00Z", [daily({})])).toBe(false);
  });

  it("is true (default) when daily is null", () => {
    expect(isDaytimeAt("2026-07-10T22:00:00Z", null)).toBe(true);
  });

  it("matches the correct entry among multiple daily readings", () => {
    const days = [
      daily({
        date: "2026-07-10",
        sunrise: "2026-07-10T06:00:00Z",
        sunset: "2026-07-10T18:00:00Z",
      }),
      daily({
        date: "2026-07-11",
        sunrise: "2026-07-11T06:05:00Z",
        sunset: "2026-07-11T18:05:00Z",
      }),
    ];

    expect(isDaytimeAt("2026-07-11T12:00:00Z", days)).toBe(true);
    expect(isDaytimeAt("2026-07-11T23:00:00Z", days)).toBe(false);
  });

  it("defaults to true when a daily entry has no sunrise/sunset", () => {
    expect(
      isDaytimeAt("2026-07-10T22:00:00Z", [
        daily({ sunrise: null, sunset: null }),
      ]),
    ).toBe(true);
  });
});
