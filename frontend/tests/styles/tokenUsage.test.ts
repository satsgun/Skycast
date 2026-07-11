import { readFileSync, readdirSync, statSync } from "node:fs";
import { extname, join, relative } from "node:path";

import { describe, expect, it } from "vitest";

const SRC_DIR = join(__dirname, "../../src");
const HEX_COLOR = /#[0-9a-fA-F]{3,8}\b/;

function collectSourceFiles(dir: string): string[] {
  const files: string[] = [];

  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);

    if (statSync(path).isDirectory()) {
      files.push(...collectSourceFiles(path));
      continue;
    }

    if (extname(path) === ".ts" || extname(path) === ".tsx") {
      files.push(path);
    }
  }

  return files;
}

describe("token usage", () => {
  it("has no raw hex-color literals outside tokens.css", () => {
    // Scoped to hex colors only, not px -- px has too many legitimate
    // non-themed uses (hairline border widths, resets). See
    // design-tokens.md for the full rationale.
    const offenders: string[] = [];

    for (const file of collectSourceFiles(SRC_DIR)) {
      const contents = readFileSync(file, "utf-8");

      if (HEX_COLOR.test(contents)) {
        offenders.push(relative(SRC_DIR, file));
      }
    }

    expect(offenders).toEqual([]);
  });
});
