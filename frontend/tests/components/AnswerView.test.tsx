import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AnswerView } from "../../src/components/AnswerView";
import type { AnswerPayload } from "../../src/contract";
import type { UnitsSettings } from "../../src/state/settingsStore";

const LOCATION = {
  id: "1",
  name: "Hyderabad",
  latitude: 17.4,
  longitude: 78.5,
  country: "India",
  country_code: "IN",
  admin1: null,
  admin2: null,
  population: 1_000_000,
  timezone: "UTC",
};

const UNITS: UnitsSettings = {
  temperature: "C",
  windSpeed: "kmh",
  timeFormat: "24h",
};

function answer(overrides: Partial<AnswerPayload>): AnswerPayload {
  return {
    text: "Saturday stays dry and sunny.",
    card: {
      forecasts: [
        {
          location: LOCATION,
          units: {
            temperature: "celsius",
            wind_speed: "kmh",
            precip_amount: "mm",
            precip_probability: "percent",
          },
          current: null,
          hourly: null,
          daily: null,
        },
      ],
      highlight: null,
    },
    ...overrides,
  };
}

describe("AnswerView", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders the conclusion above the forecast card", () => {
    const { container } = render(
      <AnswerView
        answer={answer({})}
        isStale={false}
        followUpChips={[]}
        units={UNITS}
        onSubmit={vi.fn()}
      />,
    );

    const text = container.textContent ?? "";
    const conclusionIndex = text.indexOf("Saturday stays dry and sunny.");
    const locationIndex = text.indexOf("Hyderabad");
    expect(conclusionIndex).toBeGreaterThanOrEqual(0);
    expect(locationIndex).toBeGreaterThan(conclusionIndex);
  });

  it("does not show a stale note for a fresh answer", () => {
    render(
      <AnswerView
        answer={answer({})}
        isStale={false}
        followUpChips={[]}
        units={UNITS}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.queryByText(/cached/i)).toBeNull();
  });

  it("shows a stale note for a cached answer", () => {
    render(
      <AnswerView
        answer={answer({})}
        isStale={true}
        followUpChips={[]}
        units={UNITS}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByText(/cached/i)).toBeTruthy();
  });

  it("renders every follow-up chip and submits its exact text on tap", () => {
    const onSubmit = vi.fn();
    render(
      <AnswerView
        answer={answer({})}
        isStale={false}
        followUpChips={["What about tomorrow?", "What about next week?"]}
        units={UNITS}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.click(
      screen.getByRole("button", { name: "What about tomorrow?" }),
    );

    expect(onSubmit).toHaveBeenCalledWith("What about tomorrow?");
    expect(
      screen.getByRole("button", { name: "What about next week?" }),
    ).toBeTruthy();
  });

  it("renders cleanly when card.highlight is null", () => {
    render(
      <AnswerView
        answer={answer({
          card: { forecasts: answer({}).card.forecasts, highlight: null },
        })}
        isStale={false}
        followUpChips={[]}
        units={UNITS}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByText("Hyderabad")).toBeTruthy();
  });

  it("passes the highlight locator through to the forecast card when forecast_index matches", () => {
    const CURRENT = {
      timestamp: "2026-07-10T12:00:00Z",
      temperature: 31,
      feels_like: 34,
      precip_probability: 10,
      precip_amount: 0,
      wind_speed: 12,
      condition_code: "CLEAR" as const,
    };
    render(
      <AnswerView
        answer={answer({
          card: {
            forecasts: [{ ...answer({}).card.forecasts[0], current: CURRENT }],
            highlight: {
              forecast_index: 0,
              locator: { block: "current", index: null },
            },
          },
        })}
        isStale={false}
        followUpChips={[]}
        units={UNITS}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByTestId("forecast-current").className).toContain(
      "active",
    );
  });

  it("emphasizes nothing when the highlight points at a different forecast", () => {
    const CURRENT = {
      timestamp: "2026-07-10T12:00:00Z",
      temperature: 31,
      feels_like: 34,
      precip_probability: 10,
      precip_amount: 0,
      wind_speed: 12,
      condition_code: "CLEAR" as const,
    };
    render(
      <AnswerView
        answer={answer({
          card: {
            forecasts: [{ ...answer({}).card.forecasts[0], current: CURRENT }],
            highlight: {
              forecast_index: 1,
              locator: { block: "current", index: null },
            },
          },
        })}
        isStale={false}
        followUpChips={[]}
        units={UNITS}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByTestId("forecast-current").className).not.toContain(
      "active",
    );
  });
});
