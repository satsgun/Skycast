import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { Location } from "../../src/contract";
import { useSettingsStore } from "../../src/state/settingsStore";

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

afterEach(() => {
  localStorage.clear();
});

describe("useSettingsStore", () => {
  it("defaults to celsius/kmh/24h and no default location", () => {
    const { result } = renderHook(() => useSettingsStore());

    expect(result.current.settings.units).toEqual({
      temperature: "C",
      windSpeed: "kmh",
      timeFormat: "24h",
    });
    expect(result.current.settings.defaultLocation).toBeNull();
  });

  it("setUnits merges rather than clobbering other unit fields", () => {
    const { result } = renderHook(() => useSettingsStore());

    act(() => {
      result.current.setUnits({ temperature: "F" });
    });

    expect(result.current.settings.units).toEqual({
      temperature: "F",
      windSpeed: "kmh",
      timeFormat: "24h",
    });
  });

  it("persists settings across a simulated reload", () => {
    const first = renderHook(() => useSettingsStore());
    act(() => {
      first.result.current.setUnits({ temperature: "F" });
      first.result.current.setDefaultLocation(LOCATION);
    });
    first.unmount();

    const second = renderHook(() => useSettingsStore());

    expect(second.result.current.settings.units.temperature).toBe("F");
    expect(second.result.current.settings.defaultLocation).toEqual(LOCATION);
  });

  it("toQueryRequestFields maps C to celsius and includes the default location", () => {
    const { result } = renderHook(() => useSettingsStore());
    act(() => {
      result.current.setDefaultLocation(LOCATION);
    });

    expect(result.current.toQueryRequestFields()).toEqual({
      units: "celsius",
      default_location: LOCATION,
    });
  });

  it("toQueryRequestFields maps F to fahrenheit and omits an unset default location", () => {
    const { result } = renderHook(() => useSettingsStore());
    act(() => {
      result.current.setUnits({ temperature: "F" });
    });

    expect(result.current.toQueryRequestFields()).toEqual({
      units: "fahrenheit",
    });
  });
});
