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
    const query = makeQuery({ type: "empty", currentConditionsGlance: null });
    render(<AppShell query={query} settings={SETTINGS} />);

    expect(screen.getByText("Skycast")).toBeTruthy();
    expect(screen.getByRole("textbox")).toBeTruthy();
  });

  it("does not render the settings overlay when closed", () => {
    const query = makeQuery(
      { type: "empty", currentConditionsGlance: null },
      false,
    );
    render(<AppShell query={query} settings={SETTINGS} />);

    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("renders the settings overlay when open", () => {
    const query = makeQuery(
      { type: "empty", currentConditionsGlance: null },
      true,
    );
    render(<AppShell query={query} settings={SETTINGS} />);

    expect(screen.getByRole("dialog")).toBeTruthy();
  });

  it("dispatches OPEN_SETTINGS when the header settings button is clicked", () => {
    const query = makeQuery({ type: "empty", currentConditionsGlance: null });
    render(<AppShell query={query} settings={SETTINGS} />);

    fireEvent.click(screen.getByRole("button", { name: /settings/i }));

    expect(query.dispatch).toHaveBeenCalledWith({ type: "OPEN_SETTINGS" });
  });

  it("dispatches CLOSE_SETTINGS when the overlay close button is clicked", () => {
    const query = makeQuery(
      { type: "empty", currentConditionsGlance: null },
      true,
    );
    render(<AppShell query={query} settings={SETTINGS} />);

    fireEvent.click(screen.getByRole("button", { name: /close/i }));

    expect(query.dispatch).toHaveBeenCalledWith({ type: "CLOSE_SETTINGS" });
  });

  it.each([
    { type: "thinking", query: "will it rain", steps: [] },
    {
      type: "answer",
      query: "will it rain",
      answer: { text: "yes", card: { forecasts: [], highlight: null } },
      isStale: false,
      followUpChips: [],
    },
    { type: "clarify", query: "will it rain", candidates: [] },
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

  it("renders a static prompt for the empty state", () => {
    const query = makeQuery({ type: "empty", currentConditionsGlance: null });
    render(<AppShell query={query} settings={SETTINGS} />);

    expect(screen.getByTestId("conversation-empty")).toBeTruthy();
  });
});
