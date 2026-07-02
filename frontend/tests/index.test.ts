import { describe, expect, it } from "vitest";

import { greet } from "../src/index";

describe("greet", () => {
  it("returns a welcome message", () => {
    expect(greet("Alice")).toBe("Hello, Alice! Welcome to SkyCast.");
  });
});
