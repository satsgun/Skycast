import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const TOKENS_CSS = readFileSync(
  join(__dirname, "../../src/styles/tokens.css"),
  "utf-8",
);

describe("tokens.css", () => {
  it.each([
    ["--skycast-color-bg", "#F1EFE8"],
    ["--skycast-color-accent", "#185FA5"],
    ["--skycast-font-family", "-apple-system"],
    ["--skycast-radius-md", "12px"],
    ["--skycast-space-4", "16px"],
    ["--skycast-border-width", "1px"],
  ])("defines %s with the documented value", (name, value) => {
    const declaration = new RegExp(
      `${name}:\\s*[^;]*${value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`,
      "i",
    );

    expect(TOKENS_CSS).toMatch(declaration);
  });

  it("defines a prefers-reduced-motion override", () => {
    expect(TOKENS_CSS).toMatch(/@media\s*\(prefers-reduced-motion:\s*reduce\)/);
  });
});
