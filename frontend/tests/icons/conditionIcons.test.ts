import { describe, expect, it } from "vitest";

import { CONDITION_CODES } from "../../src/contract/conditionCodes";
import { getConditionIcon } from "../../src/icons/conditionIcons";

const DAY_NIGHT_VARIANT_CODES = new Set(["CLEAR", "MAINLY_CLEAR"]);

describe("getConditionIcon", () => {
  it("returns an icon for every vendored condition code", () => {
    for (const code of CONDITION_CODES) {
      expect(typeof getConditionIcon(code)).toBe("string");
    }
  });

  it("returns different icons for CLEAR by day vs night", () => {
    expect(getConditionIcon("CLEAR", true)).not.toBe(
      getConditionIcon("CLEAR", false),
    );
  });

  it("returns different icons for MAINLY_CLEAR by day vs night", () => {
    expect(getConditionIcon("MAINLY_CLEAR", true)).not.toBe(
      getConditionIcon("MAINLY_CLEAR", false),
    );
  });

  it("is day/night-invariant for every other condition code", () => {
    for (const code of CONDITION_CODES) {
      if (DAY_NIGHT_VARIANT_CODES.has(code)) {
        continue;
      }
      expect(getConditionIcon(code, true)).toBe(getConditionIcon(code, false));
    }
  });

  it("defaults isDaytime to true", () => {
    expect(getConditionIcon("CLEAR")).toBe(getConditionIcon("CLEAR", true));
  });
});
