import type { UnitsSettings } from "../state/settingsStore";

export function kmhToMph(kmh: number): number {
  return kmh * 0.621371;
}

export function kmhToMs(kmh: number): number {
  return kmh / 3.6;
}

export function formatWindSpeed(
  kmh: number,
  unit: UnitsSettings["windSpeed"],
): string {
  switch (unit) {
    case "kmh":
      return `${Math.round(kmh)} km/h`;
    case "mph":
      return `${Math.round(kmhToMph(kmh))} mph`;
    case "ms":
      return `${kmhToMs(kmh).toFixed(1)} m/s`;
  }
}
