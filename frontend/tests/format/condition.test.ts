import { describe, expect, it } from "vitest";

import { CONDITION_CODES } from "../../src/contract/conditionCodes";
import { conditionLabel } from "../../src/format/condition";

describe("conditionLabel", () => {
  it("returns a non-empty label for every vendored condition code", () => {
    for (const code of CONDITION_CODES) {
      expect(typeof conditionLabel(code)).toBe("string");
      expect(conditionLabel(code).length).toBeGreaterThan(0);
    }
  });

  it("returns the expected label for a couple of representative codes", () => {
    expect(conditionLabel("CLEAR")).toBe("Sunny");
    expect(conditionLabel("THUNDERSTORM")).toBe("Thunderstorms");
    expect(conditionLabel("UNKNOWN")).toBe("Unknown");
  });
});
