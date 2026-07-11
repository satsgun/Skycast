import { describe, expect, it } from "vitest";

import type { ErrorKind } from "../../src/contract";
import { errorKindLabel, isSystemError } from "../../src/format/errorKind";

const KINDS: ErrorKind[] = [
  "not_found",
  "provider_unreachable",
  "bad_input",
  "internal",
];

describe("errorKindLabel", () => {
  it("returns a non-empty label for every error kind", () => {
    for (const kind of KINDS) {
      expect(typeof errorKindLabel(kind)).toBe("string");
      expect(errorKindLabel(kind).length).toBeGreaterThan(0);
    }
  });

  it("returns the expected label for each kind", () => {
    expect(errorKindLabel("not_found")).toBe("Location not found");
    expect(errorKindLabel("provider_unreachable")).toBe("Service offline");
  });
});

describe("isSystemError", () => {
  it("classifies provider_unreachable and internal as system errors", () => {
    expect(isSystemError("provider_unreachable")).toBe(true);
    expect(isSystemError("internal")).toBe(true);
  });

  it("classifies not_found and bad_input as user-correctable", () => {
    expect(isSystemError("not_found")).toBe(false);
    expect(isSystemError("bad_input")).toBe(false);
  });
});
