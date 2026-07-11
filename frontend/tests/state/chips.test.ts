import { describe, expect, it } from "vitest";

import type {
  AnswerPayload,
  DailyReading,
  ForecastBlock,
  HourlyReading,
  Location,
} from "../../src/contract";
import { generateFollowUpChips, STARTER_CHIPS } from "../../src/state/chips";

const LOCATION: Location = {
  id: "1",
  name: "Austin",
  latitude: 30.27,
  longitude: -97.74,
  country: null,
  country_code: "US",
  admin1: null,
  admin2: null,
  population: null,
  timezone: null,
};

const UNITS = {
  temperature: "celsius",
  wind_speed: "kmh",
  precip_amount: "mm",
  precip_probability: "percent",
};

function hourlyReading(overrides: Partial<HourlyReading> = {}): HourlyReading {
  return {
    timestamp: "2026-07-11T18:00:00Z",
    temperature: 22,
    feels_like: 22,
    precip_probability: 10,
    precip_amount: 0,
    wind_speed: 5,
    condition_code: "CLEAR",
    ...overrides,
  };
}

function dailyReading(overrides: Partial<DailyReading> = {}): DailyReading {
  return {
    date: "2026-07-11",
    temp_min: 15,
    temp_max: 25,
    precip_probability: 10,
    precip_amount: 0,
    wind_speed_max: 10,
    condition_code: "CLEAR",
    sunrise: null,
    sunset: null,
    ...overrides,
  };
}

function answerWith(
  granularity: ForecastBlock | null,
  options: { comparison?: boolean; text?: string } = {},
): AnswerPayload {
  const forecast = {
    location: LOCATION,
    units: UNITS,
    current: granularity === "current" ? hourlyReading() : null,
    hourly: granularity === "hourly" ? [hourlyReading()] : null,
    daily: granularity === "daily" ? [dailyReading()] : null,
  };
  const forecasts = options.comparison
    ? [
        forecast,
        { ...forecast, location: { ...LOCATION, id: "2", name: "Dallas" } },
      ]
    : [forecast];

  return {
    text: options.text ?? "Here's the forecast.",
    card: {
      forecasts,
      highlight:
        granularity === null
          ? null
          : { forecast_index: 0, locator: { block: granularity, index: null } },
    },
  };
}

describe("generateFollowUpChips", () => {
  const granularities: ForecastBlock[] = ["current", "hourly", "daily"];

  for (const granularity of granularities) {
    for (const comparison of [false, true]) {
      it(`returns exactly 2 non-empty, distinct chips for granularity=${granularity} comparison=${comparison}`, () => {
        const chips = generateFollowUpChips(
          "what's the weather?",
          answerWith(granularity, { comparison }),
        );

        expect(chips).toHaveLength(2);
        for (const chip of chips) {
          expect(chip.length).toBeGreaterThan(0);
        }
        expect(chips[0]).not.toBe(chips[1]);
      });
    }
  }

  it("varies chip content across granularities for the same (non-comparison) shape", () => {
    const current = generateFollowUpChips(
      "what's the weather?",
      answerWith("current"),
    );
    const hourly = generateFollowUpChips(
      "what's the weather?",
      answerWith("hourly"),
    );
    const daily = generateFollowUpChips(
      "what's the weather?",
      answerWith("daily"),
    );

    expect(current).not.toEqual(hourly);
    expect(hourly).not.toEqual(daily);
    expect(current).not.toEqual(daily);
  });

  it("varies chip wording between comparison and single-location answers at the same granularity", () => {
    const single = generateFollowUpChips(
      "what's the weather?",
      answerWith("hourly"),
    );
    const comparison = generateFollowUpChips(
      "what's the weather?",
      answerWith("hourly", { comparison: true }),
    );

    expect(single).not.toEqual(comparison);
  });

  it("swaps out the decision chip when the query already mentions a decision keyword", () => {
    const chips = generateFollowUpChips(
      "do I need an umbrella today",
      answerWith("hourly"),
    );

    expect(chips).not.toContain("Do I need an umbrella?");
    expect(chips).not.toContain("Which one needs an umbrella?");
  });

  it("swaps out the decision chip when only the answer text mentions a decision keyword", () => {
    const chips = generateFollowUpChips(
      "what's the weather?",
      answerWith("hourly", { text: "Yes, bring an umbrella." }),
    );

    expect(chips).not.toContain("Do I need an umbrella?");
    expect(chips).not.toContain("Which one needs an umbrella?");
  });

  it("includes a decision chip when neither query nor answer text mentions one", () => {
    const chips = generateFollowUpChips(
      "what's the weather?",
      answerWith("hourly", { text: "It's sunny." }),
    );

    expect(chips).toContain("Do I need an umbrella?");
  });

  it("handles the machine.test.ts ANSWER fixture shape (empty forecasts, null highlight) without crashing", () => {
    const answer: AnswerPayload = {
      text: "Yes, bring an umbrella.",
      card: { forecasts: [], highlight: null },
    };

    const chips = generateFollowUpChips("what's the weather?", answer);

    expect(chips).toHaveLength(2);
  });
});

describe("STARTER_CHIPS", () => {
  it("has at least 3 entries, all non-empty strings", () => {
    expect(STARTER_CHIPS.length).toBeGreaterThanOrEqual(3);
    for (const chip of STARTER_CHIPS) {
      expect(typeof chip).toBe("string");
      expect(chip.length).toBeGreaterThan(0);
    }
  });

  it("includes an agentic capability-teaching prompt about what to wear", () => {
    expect(STARTER_CHIPS.some((chip) => /wear/i.test(chip))).toBe(true);
  });
});
