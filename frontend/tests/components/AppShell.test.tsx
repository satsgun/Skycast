import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "../../src/components/AppShell";
import type { MachineState } from "../../src/state/machine";
import type { UseQueryResult } from "../../src/state/useQuery";
import type { UseSettingsStoreResult } from "../../src/state/settingsStore";

function makeQuery(main: MachineState["main"], isSettingsOpen = false) {
  const state: MachineState = { main, isSettingsOpen };
  const query: UseQueryResult = {
    state,
    dispatch: vi.fn(),
    submitQuery: vi.fn(),
    selectCandidate: vi.fn(),
  };
  return query;
}

const SETTINGS: UseSettingsStoreResult = {
  settings: {
    units: { temperature: "C", windSpeed: "kmh", timeFormat: "24h" },
    defaultLocation: null,
  },
  setUnits: vi.fn(),
  setDefaultLocation: vi.fn(),
  toQueryRequestFields: vi.fn(() => ({})),
};

describe("AppShell", () => {
  afterEach(() => {
    cleanup();
  });

  it("always renders the header, scroll area, and input bar", () => {
    const query = makeQuery({ type: "empty" });
    render(<AppShell query={query} settings={SETTINGS} />);

    expect(screen.getByText("Skycast")).toBeTruthy();
    expect(screen.getByRole("textbox")).toBeTruthy();
  });

  it("does not render the settings overlay when closed", () => {
    const query = makeQuery({ type: "empty" }, false);
    render(<AppShell query={query} settings={SETTINGS} />);

    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("renders the settings overlay when open", () => {
    const query = makeQuery({ type: "empty" }, true);
    render(<AppShell query={query} settings={SETTINGS} />);

    expect(screen.getByRole("dialog")).toBeTruthy();
  });

  it("dispatches OPEN_SETTINGS when the header settings button is clicked", () => {
    const query = makeQuery({ type: "empty" });
    render(<AppShell query={query} settings={SETTINGS} />);

    fireEvent.click(screen.getByRole("button", { name: /settings/i }));

    expect(query.dispatch).toHaveBeenCalledWith({ type: "OPEN_SETTINGS" });
  });

  it("dispatches CLOSE_SETTINGS when the overlay close button is clicked", () => {
    const query = makeQuery({ type: "empty" }, true);
    render(<AppShell query={query} settings={SETTINGS} />);

    fireEvent.click(screen.getByRole("button", { name: /close/i }));

    expect(query.dispatch).toHaveBeenCalledWith({ type: "CLOSE_SETTINGS" });
  });

  const MINIMAL_FORECAST = {
    location: {
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
    },
    units: {
      temperature: "celsius",
      wind_speed: "kmh",
      precip_amount: "mm",
      precip_probability: "percent",
    },
    current: null,
    hourly: null,
    daily: null,
  };

  const MINIMAL_CANDIDATES = [
    {
      id: "1",
      name: "Springfield",
      latitude: 39.8,
      longitude: -89.6,
      country: "USA",
      country_code: "US",
      admin1: "Illinois",
      admin2: null,
      population: 114_000,
      timezone: "America/Chicago",
    },
    {
      id: "2",
      name: "Springfield",
      latitude: 37.2,
      longitude: -93.3,
      country: "USA",
      country_code: "US",
      admin1: "Missouri",
      admin2: null,
      population: 169_000,
      timezone: "America/Chicago",
    },
  ];

  it.each([
    { type: "thinking", query: "will it rain", steps: [] },
    {
      type: "answer",
      query: "will it rain",
      answer: {
        text: "yes",
        card: { forecasts: [MINIMAL_FORECAST], highlight: null },
      },
      isStale: false,
      followUpChips: [],
    },
    { type: "clarify", query: "will it rain", candidates: MINIMAL_CANDIDATES },
    {
      type: "error",
      query: "will it rain",
      error: { kind: "internal", message: "boom" },
      actions: [],
    },
  ] as MachineState["main"][])(
    "renders the query text for main state %o without throwing",
    (main) => {
      const query = makeQuery(main);
      render(<AppShell query={query} settings={SETTINGS} />);

      expect(screen.getByText(/will it rain/)).toBeTruthy();
    },
  );

  it("renders the empty-state heading and starter chips", () => {
    const query = makeQuery({ type: "empty" });
    render(<AppShell query={query} settings={SETTINGS} />);

    expect(screen.getByText("What would you like to know?")).toBeTruthy();
    expect(
      screen.getByText("Do I need an umbrella this evening?"),
    ).toBeTruthy();
  });

  it("renders thinking steps through the full tree", () => {
    const query = makeQuery({
      type: "thinking",
      query: "will it rain",
      steps: [{ label: "Understood request", stage: "decompose" }],
    });
    render(<AppShell query={query} settings={SETTINGS} />);

    expect(screen.getByText("Understood request")).toBeTruthy();
  });

  it("renders an answer through the full tree", () => {
    const query = makeQuery({
      type: "answer",
      query: "will it rain",
      answer: {
        text: "Saturday stays dry and sunny.",
        card: { forecasts: [MINIMAL_FORECAST], highlight: null },
      },
      isStale: false,
      followUpChips: ["What about tomorrow?"],
    });
    render(<AppShell query={query} settings={SETTINGS} />);

    expect(screen.getByText("Saturday stays dry and sunny.")).toBeTruthy();
    expect(screen.getByText("Hyderabad")).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "What about tomorrow?" }),
    ).toBeTruthy();
  });

  it("renders clarify candidates through the full tree and selects one on tap", () => {
    const query = makeQuery({
      type: "clarify",
      query: "will it rain",
      candidates: MINIMAL_CANDIDATES,
    });
    render(<AppShell query={query} settings={SETTINGS} />);

    expect(screen.getByText(/Springfields/)).toBeTruthy();
    const buttons = screen.getAllByRole("button", { name: /Springfield/ });
    fireEvent.click(buttons[1]);

    expect(query.selectCandidate).toHaveBeenCalledWith(MINIMAL_CANDIDATES[1]);
  });
});
