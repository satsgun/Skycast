/**
 * Contract drift detection (Task F1.6) -- the safeguard that replaces
 * codegen for the hand-written types in src/contract/. Reaches across
 * this monorepo's other directories on purpose: this is a test, run in
 * CI/dev where the full checkout is present, not shipped code (unlike
 * F1.3's vendored conditionCodes.ts, which must be self-contained
 * inside the browser bundle).
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  CONDITION_CODES,
  type ConditionCode,
} from "../../src/contract/conditionCodes";
import { getConditionIcon } from "../../src/icons/conditionIcons";

const SSE_CONTRACT_DOC_PATH = join(__dirname, "../../../docs/sse-contract.md");
const BACKEND_CONDITIONS_JSON_PATH = join(
  __dirname,
  "../../../backend/src/skycast/domain/conditions.json",
);

const PIPELINE_STAGES = [
  "decompose",
  "plan",
  "execute_geocode",
  "execute_forecast",
  "synthesize",
];
const ERROR_KINDS = [
  "not_found",
  "provider_unreachable",
  "bad_input",
  "internal",
];
const FORECAST_BLOCKS = ["current", "hourly", "daily"];

function isString(value: unknown): value is string {
  return typeof value === "string";
}

function isNumber(value: unknown): value is number {
  return typeof value === "number";
}

function isStringOrNull(value: unknown): value is string | null {
  return value === null || isString(value);
}

function isNumberOrNull(value: unknown): value is number | null {
  return value === null || isNumber(value);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function assertValidLocation(value: unknown, path: string): void {
  if (!isRecord(value)) {
    throw new Error(
      `${path}: expected an object, got ${JSON.stringify(value)}`,
    );
  }
  const fields: [string, (v: unknown) => boolean][] = [
    ["id", isString],
    ["name", isString],
    ["latitude", isNumber],
    ["longitude", isNumber],
    ["country", isStringOrNull],
    ["country_code", isStringOrNull],
    ["admin1", isStringOrNull],
    ["admin2", isStringOrNull],
    ["population", isNumberOrNull],
    ["timezone", isStringOrNull],
  ];
  for (const [field, check] of fields) {
    if (!check(value[field])) {
      throw new Error(
        `${path}.${field}: unexpected value ${JSON.stringify(value[field])}`,
      );
    }
  }
}

function assertValidConditionCode(value: unknown, path: string): void {
  if (
    !isString(value) ||
    !(CONDITION_CODES as readonly string[]).includes(value)
  ) {
    throw new Error(
      `${path}: ${JSON.stringify(value)} is not a vendored ConditionCode`,
    );
  }
}

function assertValidReading(
  value: unknown,
  path: string,
  isDaily: boolean,
): void {
  if (!isRecord(value)) {
    throw new Error(
      `${path}: expected an object, got ${JSON.stringify(value)}`,
    );
  }
  const commonFields: [string, (v: unknown) => boolean][] = [
    ["precip_probability", isNumberOrNull],
    ["precip_amount", isNumberOrNull],
  ];
  for (const [field, check] of commonFields) {
    if (!check(value[field])) {
      throw new Error(
        `${path}.${field}: unexpected value ${JSON.stringify(value[field])}`,
      );
    }
  }
  assertValidConditionCode(value.condition_code, `${path}.condition_code`);

  if (isDaily) {
    if (!isString(value.date))
      throw new Error(`${path}.date: expected a string`);
    if (!isNumber(value.temp_min))
      throw new Error(`${path}.temp_min: expected a number`);
    if (!isNumber(value.temp_max))
      throw new Error(`${path}.temp_max: expected a number`);
    if (!isNumberOrNull(value.wind_speed_max)) {
      throw new Error(`${path}.wind_speed_max: unexpected value`);
    }
    if (!isStringOrNull(value.sunrise))
      throw new Error(`${path}.sunrise: unexpected value`);
    if (!isStringOrNull(value.sunset))
      throw new Error(`${path}.sunset: unexpected value`);
  } else {
    if (!isString(value.timestamp))
      throw new Error(`${path}.timestamp: expected a string`);
    if (!isNumber(value.temperature))
      throw new Error(`${path}.temperature: expected a number`);
    if (!isNumberOrNull(value.feels_like))
      throw new Error(`${path}.feels_like: unexpected value`);
    if (!isNumberOrNull(value.wind_speed))
      throw new Error(`${path}.wind_speed: unexpected value`);
  }
}

function assertValidForecast(value: unknown, path: string): void {
  if (!isRecord(value)) {
    throw new Error(
      `${path}: expected an object, got ${JSON.stringify(value)}`,
    );
  }
  assertValidLocation(value.location, `${path}.location`);

  const units = value.units;
  if (!isRecord(units)) {
    throw new Error(`${path}.units: expected an object`);
  }
  for (const field of [
    "temperature",
    "wind_speed",
    "precip_amount",
    "precip_probability",
  ]) {
    if (!isString(units[field])) {
      throw new Error(`${path}.units.${field}: expected a string`);
    }
  }

  if (value.current !== null) {
    assertValidReading(value.current, `${path}.current`, false);
  }
  if (value.hourly !== null) {
    if (!Array.isArray(value.hourly))
      throw new Error(`${path}.hourly: expected an array or null`);
    value.hourly.forEach((r, i) =>
      assertValidReading(r, `${path}.hourly[${i}]`, false),
    );
  }
  if (value.daily !== null) {
    if (!Array.isArray(value.daily))
      throw new Error(`${path}.daily: expected an array or null`);
    value.daily.forEach((r, i) =>
      assertValidReading(r, `${path}.daily[${i}]`, true),
    );
  }
}

function assertValidHighlight(value: unknown, path: string): void {
  if (value === null) return;
  if (!isRecord(value)) {
    throw new Error(
      `${path}: expected an object or null, got ${JSON.stringify(value)}`,
    );
  }
  if (!isNumber(value.forecast_index)) {
    throw new Error(`${path}.forecast_index: expected a number`);
  }
  const locator = value.locator;
  if (
    !isRecord(locator) ||
    !FORECAST_BLOCKS.includes(locator.block as string)
  ) {
    throw new Error(`${path}.locator.block: unexpected value`);
  }
  if (!isNumberOrNull(locator.index)) {
    throw new Error(`${path}.locator.index: unexpected value`);
  }
}

function assertValidSSEEvent(value: unknown, rawLine: string): void {
  if (!isRecord(value)) {
    throw new Error(`invalid event (not an object): ${rawLine}`);
  }
  const { type, data } = value;

  switch (type) {
    case "step": {
      if (!isRecord(data) || !isString(data.label)) {
        throw new Error(`step.data.label: expected a string in: ${rawLine}`);
      }
      if (!PIPELINE_STAGES.includes(data.stage as string)) {
        throw new Error(`step.data.stage: unexpected value in: ${rawLine}`);
      }
      return;
    }
    case "clarify": {
      if (
        !isRecord(data) ||
        !Array.isArray(data.candidates) ||
        data.candidates.length === 0
      ) {
        throw new Error(
          `clarify.data.candidates: expected a non-empty array in: ${rawLine}`,
        );
      }
      data.candidates.forEach((c, i) =>
        assertValidLocation(c, `clarify.data.candidates[${i}]`),
      );
      if (!isString(data.for_location_name)) {
        throw new Error(
          `clarify.data.for_location_name: expected a string in: ${rawLine}`,
        );
      }
      if (!isRecord(data.resolved)) {
        throw new Error(
          `clarify.data.resolved: expected an object in: ${rawLine}`,
        );
      }
      for (const [name, loc] of Object.entries(data.resolved)) {
        assertValidLocation(loc, `clarify.data.resolved[${name}]`);
      }
      return;
    }
    case "answer": {
      if (!isRecord(data) || !isString(data.text)) {
        throw new Error(`answer.data.text: expected a string in: ${rawLine}`);
      }
      const card = data.card;
      if (!isRecord(card) || !Array.isArray(card.forecasts)) {
        throw new Error(
          `answer.data.card.forecasts: expected an array in: ${rawLine}`,
        );
      }
      card.forecasts.forEach((f, i) =>
        assertValidForecast(f, `answer.data.card.forecasts[${i}]`),
      );
      assertValidHighlight(card.highlight, "answer.data.card.highlight");
      return;
    }
    case "error": {
      if (!isRecord(data) || !ERROR_KINDS.includes(data.kind as string)) {
        throw new Error(`error.data.kind: unexpected value in: ${rawLine}`);
      }
      if (!isString(data.message)) {
        throw new Error(`error.data.message: expected a string in: ${rawLine}`);
      }
      return;
    }
    default:
      throw new Error(
        `unknown event type ${JSON.stringify(type)} in: ${rawLine}`,
      );
  }
}

function extractSSEDataLines(doc: string): string[] {
  return doc
    .split("\n")
    .filter((line) => line.startsWith("data: "))
    .map((line) => line.slice("data: ".length));
}

describe("SSE example-stream drift detection", () => {
  const doc = readFileSync(SSE_CONTRACT_DOC_PATH, "utf-8");
  const dataLines = extractSSEDataLines(doc);

  it("finds at least one example event in the generated doc", () => {
    expect(dataLines.length).toBeGreaterThan(0);
  });

  it("parses every example event cleanly into the F1.2 contract shapes", () => {
    for (const line of dataLines) {
      const parsed: unknown = JSON.parse(line);
      assertValidSSEEvent(parsed, line);
    }
  });
});

describe("ConditionCode/icon-map drift detection", () => {
  const backendCodes: string[] = JSON.parse(
    readFileSync(BACKEND_CONDITIONS_JSON_PATH, "utf-8"),
  );

  it("vendored CONDITION_CODES has exactly the backend's members", () => {
    expect(new Set(CONDITION_CODES)).toEqual(new Set(backendCodes));
  });

  it("the icon map covers every condition code the backend actually defines", () => {
    for (const code of backendCodes) {
      expect(typeof getConditionIcon(code as ConditionCode)).toBe("string");
    }
  });
});
