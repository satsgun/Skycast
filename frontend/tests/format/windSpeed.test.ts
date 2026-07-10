import { describe, expect, it } from "vitest";

import { formatWindSpeed, kmhToMph, kmhToMs } from "../../src/format/windSpeed";

describe("kmhToMph", () => {
  it("converts km/h to mph", () => {
    expect(kmhToMph(10)).toBeCloseTo(6.21371, 5);
  });
});

describe("kmhToMs", () => {
  it("converts km/h to m/s", () => {
    expect(kmhToMs(10)).toBeCloseTo(2.77778, 5);
  });
});

describe("formatWindSpeed", () => {
  it("passes km/h through unconverted, rounded", () => {
    expect(formatWindSpeed(10, "kmh")).toBe("10 km/h");
  });

  it("converts and rounds to mph", () => {
    expect(formatWindSpeed(10, "mph")).toBe("6 mph");
  });

  it("converts to m/s with one decimal place", () => {
    expect(formatWindSpeed(10, "ms")).toBe("2.8 m/s");
  });
});
