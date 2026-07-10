import { describe, expect, it } from "vitest";

import {
  celsiusToFahrenheit,
  formatTemperature,
} from "../../src/format/temperature";

describe("celsiusToFahrenheit", () => {
  it("converts freezing point", () => {
    expect(celsiusToFahrenheit(0)).toBe(32);
  });

  it("converts boiling point", () => {
    expect(celsiusToFahrenheit(100)).toBe(212);
  });
});

describe("formatTemperature", () => {
  it("passes Celsius through unconverted", () => {
    expect(formatTemperature(20, "C")).toBe("20°C");
  });

  it("converts and rounds to Fahrenheit", () => {
    // 21°C -> 69.8°F, rounds up to 70
    expect(formatTemperature(21, "F")).toBe("70°F");
  });

  it("handles negative values", () => {
    // -10°C -> 14°F exactly
    expect(formatTemperature(-10, "F")).toBe("14°F");
  });
});
