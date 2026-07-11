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

const LOCATION_2 = {
  id: "2",
  name: "Bangalore",
  latitude: 12.97,
  longitude: 77.59,
  country: "India",
  country_code: "IN",
  admin1: null,
  admin2: null,
  population: 8_000_000,
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
        defaultLocation={null}
        onSetDefaultLocation={vi.fn()}
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
        defaultLocation={null}
        onSetDefaultLocation={vi.fn()}
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
        defaultLocation={null}
        onSetDefaultLocation={vi.fn()}
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
        defaultLocation={null}
        onSetDefaultLocation={vi.fn()}
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
        defaultLocation={null}
        onSetDefaultLocation={vi.fn()}
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
        defaultLocation={null}
        onSetDefaultLocation={vi.fn()}
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
        defaultLocation={null}
        onSetDefaultLocation={vi.fn()}
      />,
    );

    expect(screen.getByTestId("forecast-current").className).not.toContain(
      "active",
    );
  });

  it("renders both forecasts side by side when there is more than one", () => {
    const forecast1 = answer({}).card.forecasts[0];
    const forecast2 = { ...forecast1, location: LOCATION_2 };
    render(
      <AnswerView
        answer={answer({
          card: { forecasts: [forecast1, forecast2], highlight: null },
        })}
        isStale={false}
        followUpChips={[]}
        units={UNITS}
        onSubmit={vi.fn()}
        defaultLocation={null}
        onSetDefaultLocation={vi.fn()}
      />,
    );

    expect(screen.getByText("Hyderabad")).toBeTruthy();
    expect(screen.getByText("Bangalore")).toBeTruthy();
  });

  it("highlight.forecast_index selects the correct side in a comparison", () => {
    const CURRENT = {
      timestamp: "2026-07-10T12:00:00Z",
      temperature: 31,
      feels_like: 34,
      precip_probability: 10,
      precip_amount: 0,
      wind_speed: 12,
      condition_code: "CLEAR" as const,
    };
    const forecast1 = { ...answer({}).card.forecasts[0], current: CURRENT };
    const forecast2 = { ...forecast1, location: LOCATION_2 };
    render(
      <AnswerView
        answer={answer({
          card: {
            forecasts: [forecast1, forecast2],
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
        defaultLocation={null}
        onSetDefaultLocation={vi.fn()}
      />,
    );

    const cards = screen.getAllByTestId("forecast-current");
    expect(cards).toHaveLength(2);
    expect(cards[0].className).not.toContain("active");
    expect(cards[1].className).toContain("active");
  });

  it("renders the conclusion once, above both forecast cards", () => {
    const forecast1 = answer({}).card.forecasts[0];
    const forecast2 = { ...forecast1, location: LOCATION_2 };
    const { container } = render(
      <AnswerView
        answer={answer({
          card: { forecasts: [forecast1, forecast2], highlight: null },
        })}
        isStale={false}
        followUpChips={[]}
        units={UNITS}
        onSubmit={vi.fn()}
        defaultLocation={null}
        onSetDefaultLocation={vi.fn()}
      />,
    );

    expect(screen.getAllByText("Saturday stays dry and sunny.")).toHaveLength(
      1,
    );
    const text = container.textContent ?? "";
    const conclusionIndex = text.indexOf("Saturday stays dry and sunny.");
    const bangaloreIndex = text.indexOf("Bangalore");
    expect(bangaloreIndex).toBeGreaterThan(conclusionIndex);
  });

  it("marks only the forecast matching defaultLocation as the default", () => {
    const forecast1 = answer({}).card.forecasts[0];
    const forecast2 = { ...forecast1, location: LOCATION_2 };
    render(
      <AnswerView
        answer={answer({
          card: { forecasts: [forecast1, forecast2], highlight: null },
        })}
        isStale={false}
        followUpChips={[]}
        units={UNITS}
        onSubmit={vi.fn()}
        defaultLocation={LOCATION_2}
        onSetDefaultLocation={vi.fn()}
      />,
    );

    expect(screen.getByText("Set as default")).toBeTruthy();
    expect(screen.getByText("Default location")).toBeTruthy();
  });

  it("calls onSetDefaultLocation with that forecast's own location when tapped", () => {
    const onSetDefaultLocation = vi.fn();
    const forecast1 = answer({}).card.forecasts[0];
    const forecast2 = { ...forecast1, location: LOCATION_2 };
    render(
      <AnswerView
        answer={answer({
          card: { forecasts: [forecast1, forecast2], highlight: null },
        })}
        isStale={false}
        followUpChips={[]}
        units={UNITS}
        onSubmit={vi.fn()}
        defaultLocation={null}
        onSetDefaultLocation={onSetDefaultLocation}
      />,
    );

    fireEvent.click(screen.getAllByText("Set as default")[1]);

    expect(onSetDefaultLocation).toHaveBeenCalledWith(LOCATION_2);
  });

  it("renders an Open-Meteo attribution link", () => {
    render(
      <AnswerView
        answer={answer({})}
        isStale={false}
        followUpChips={[]}
        units={UNITS}
        onSubmit={vi.fn()}
        defaultLocation={null}
        onSetDefaultLocation={vi.fn()}
      />,
    );

    const link = screen.getByRole("link", { name: "Open-Meteo.com" });
    expect(link.getAttribute("href")).toBe("https://open-meteo.com");
  });

  it("opens the attribution link in a new tab safely", () => {
    render(
      <AnswerView
        answer={answer({})}
        isStale={false}
        followUpChips={[]}
        units={UNITS}
        onSubmit={vi.fn()}
        defaultLocation={null}
        onSetDefaultLocation={vi.fn()}
      />,
    );

    const link = screen.getByRole("link", { name: "Open-Meteo.com" });
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")).toBe("noopener noreferrer");
  });
});
