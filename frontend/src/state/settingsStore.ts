import { useState } from "react";

import type { Location } from "../contract";
import { readPersisted, writePersisted } from "./persistence";

export interface UnitsSettings {
  temperature: "C" | "F";
  windSpeed: "kmh" | "mph" | "ms";
  timeFormat: "12h" | "24h";
}

export interface SettingsState {
  units: UnitsSettings;
  defaultLocation: Location | null;
}

export interface UseSettingsStoreResult {
  settings: SettingsState;
  setUnits: (units: Partial<UnitsSettings>) => void;
  setDefaultLocation: (location: Location | null) => void;
  toQueryRequestFields: () => { default_location?: Location; units?: string };
}

const STORAGE_KEY = "skycast:settings";

const DEFAULT_UNITS: UnitsSettings = {
  temperature: "C",
  windSpeed: "kmh",
  timeFormat: "24h",
};

function defaultSettings(): SettingsState {
  return { units: DEFAULT_UNITS, defaultLocation: null };
}

const TEMPERATURE_HINT: Record<UnitsSettings["temperature"], string> = {
  C: "celsius",
  F: "fahrenheit",
};

export function useSettingsStore(): UseSettingsStoreResult {
  const [settings, setSettings] = useState<SettingsState>(() =>
    readPersisted(STORAGE_KEY, defaultSettings()),
  );

  function setUnits(units: Partial<UnitsSettings>): void {
    setSettings((previous) => {
      const next: SettingsState = {
        ...previous,
        units: { ...previous.units, ...units },
      };
      writePersisted(STORAGE_KEY, next);
      return next;
    });
  }

  function setDefaultLocation(location: Location | null): void {
    setSettings((previous) => {
      const next: SettingsState = { ...previous, defaultLocation: location };
      writePersisted(STORAGE_KEY, next);
      return next;
    });
  }

  function toQueryRequestFields(): {
    default_location?: Location;
    units?: string;
  } {
    const fields: { default_location?: Location; units?: string } = {
      units: TEMPERATURE_HINT[settings.units.temperature],
    };
    if (settings.defaultLocation !== null) {
      fields.default_location = settings.defaultLocation;
    }
    return fields;
  }

  return { settings, setUnits, setDefaultLocation, toQueryRequestFields };
}
