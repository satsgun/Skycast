import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SettingsPanel } from "../../src/components/SettingsPanel";
import type { SettingsState } from "../../src/state/settingsStore";

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

function settingsWith(overrides: Partial<SettingsState>): SettingsState {
  return {
    units: { temperature: "C", windSpeed: "kmh", timeFormat: "24h" },
    defaultLocation: null,
    ...overrides,
  };
}

describe("SettingsPanel", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows the current default location name and a Clear button when set", () => {
    render(
      <SettingsPanel
        settings={settingsWith({ defaultLocation: LOCATION })}
        onSetUnits={vi.fn()}
        onSetDefaultLocation={vi.fn()}
      />,
    );

    expect(screen.getByText("Hyderabad")).toBeTruthy();
    expect(screen.getByRole("button", { name: /clear/i })).toBeTruthy();
  });

  it('shows "Not set" and no Clear button when no default is set', () => {
    render(
      <SettingsPanel
        settings={settingsWith({})}
        onSetUnits={vi.fn()}
        onSetDefaultLocation={vi.fn()}
      />,
    );

    expect(screen.getByText("Not set")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /clear/i })).toBeNull();
  });

  it("calls onSetDefaultLocation(null) when Clear is tapped", () => {
    const onSetDefaultLocation = vi.fn();
    render(
      <SettingsPanel
        settings={settingsWith({ defaultLocation: LOCATION })}
        onSetUnits={vi.fn()}
        onSetDefaultLocation={onSetDefaultLocation}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /clear/i }));

    expect(onSetDefaultLocation).toHaveBeenCalledWith(null);
  });

  it("wires the temperature control to onSetUnits with a single-field partial", () => {
    const onSetUnits = vi.fn();
    render(
      <SettingsPanel
        settings={settingsWith({})}
        onSetUnits={onSetUnits}
        onSetDefaultLocation={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "°F" }));

    expect(onSetUnits).toHaveBeenCalledWith({ temperature: "F" });
  });

  it("wires the wind speed control to onSetUnits with a single-field partial", () => {
    const onSetUnits = vi.fn();
    render(
      <SettingsPanel
        settings={settingsWith({})}
        onSetUnits={onSetUnits}
        onSetDefaultLocation={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "mph" }));

    expect(onSetUnits).toHaveBeenCalledWith({ windSpeed: "mph" });
  });

  it("wires the time format control to onSetUnits with a single-field partial", () => {
    const onSetUnits = vi.fn();
    render(
      <SettingsPanel
        settings={settingsWith({})}
        onSetUnits={onSetUnits}
        onSetDefaultLocation={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "12h" }));

    expect(onSetUnits).toHaveBeenCalledWith({ timeFormat: "12h" });
  });

  it("does not render a current-location toggle or Save/Cancel buttons", () => {
    render(
      <SettingsPanel
        settings={settingsWith({})}
        onSetUnits={vi.fn()}
        onSetDefaultLocation={vi.fn()}
      />,
    );

    expect(screen.queryByText(/current location/i)).toBeNull();
    expect(screen.queryByRole("button", { name: /save/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /cancel/i })).toBeNull();
  });
});
