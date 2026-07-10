import { afterEach, describe, expect, it, vi } from "vitest";

import {
  clearPersisted,
  readPersisted,
  writePersisted,
} from "../../src/state/persistence";

const KEY = "skycast-test-key";

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("persistence", () => {
  it("round-trips a value through writePersisted/readPersisted", () => {
    writePersisted(KEY, { a: 1, b: "two" });

    expect(readPersisted(KEY, null)).toEqual({ a: 1, b: "two" });
  });

  it("returns the fallback when nothing is stored", () => {
    expect(readPersisted(KEY, { default: true })).toEqual({ default: true });
  });

  it("clearPersisted removes the stored value", () => {
    writePersisted(KEY, "value");
    clearPersisted(KEY);

    expect(readPersisted(KEY, "fallback")).toBe("fallback");
  });

  it("returns the fallback (does not throw) if localStorage.getItem throws", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("storage disabled");
    });

    expect(readPersisted(KEY, "fallback")).toBe("fallback");
  });

  it("does not throw if localStorage.setItem throws", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("quota exceeded");
    });

    expect(() => writePersisted(KEY, "value")).not.toThrow();
  });

  it("returns the fallback when the stored value is not valid JSON", () => {
    localStorage.setItem(KEY, "{not valid json");

    expect(readPersisted(KEY, "fallback")).toBe("fallback");
  });
});
