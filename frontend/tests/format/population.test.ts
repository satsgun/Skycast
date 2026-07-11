import { describe, expect, it } from "vitest";

import { formatPopulation } from "../../src/format/population";

describe("formatPopulation", () => {
  it("formats thousands with a lowercase k", () => {
    expect(formatPopulation(114_000)).toBe("114k");
    expect(formatPopulation(169_000)).toBe("169k");
    expect(formatPopulation(155_000)).toBe("155k");
  });

  it("formats raw numbers below 1,000 as-is", () => {
    expect(formatPopulation(842)).toBe("842");
  });

  it("formats millions with a lowercase-free M suffix", () => {
    expect(formatPopulation(8_000_000)).toBe("8M");
    expect(formatPopulation(1_200_000)).toBe("1.2M");
  });
});
