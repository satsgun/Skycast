import type { UnitsSettings } from "../state/settingsStore";

export function celsiusToFahrenheit(celsius: number): number {
  return (celsius * 9) / 5 + 32;
}

export function formatTemperature(
  celsius: number,
  unit: UnitsSettings["temperature"],
): string {
  const value = unit === "F" ? celsiusToFahrenheit(celsius) : celsius;
  return `${Math.round(value)}°${unit}`;
}
