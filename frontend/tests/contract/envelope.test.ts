import { describe, expect, it } from "vitest";

import type { SSEEvent } from "../../src/contract";

function describeEvent(event: SSEEvent): string {
  switch (event.type) {
    case "step":
      return `step: ${event.data.label} (${event.data.stage})`;
    case "clarify":
      return `clarify: ${event.data.candidates.length} candidates`;
    case "answer":
      return `answer: ${event.data.text}`;
    case "error":
      return `error: ${event.data.kind} - ${event.data.message}`;
  }
}

describe("SSEEvent discriminated union", () => {
  it("narrows to StepPayload for a step event", () => {
    const event: SSEEvent = {
      type: "step",
      data: { label: "Understanding your question...", stage: "decompose" },
    };

    expect(describeEvent(event)).toBe(
      "step: Understanding your question... (decompose)",
    );
  });

  it("narrows to ClarifyPayload for a clarify event", () => {
    const event: SSEEvent = {
      type: "clarify",
      data: {
        candidates: [
          {
            id: "1",
            name: "Springfield",
            latitude: 39.7817,
            longitude: -89.6501,
            country: null,
            country_code: "US",
            admin1: "Illinois",
            admin2: null,
            population: null,
            timezone: null,
          },
        ],
        for_location_name: "Springfield",
        resolved: {},
      },
    };

    expect(describeEvent(event)).toBe("clarify: 1 candidates");
  });

  it("narrows to AnswerPayload for an answer event", () => {
    const event: SSEEvent = {
      type: "answer",
      data: {
        text: "Yes, bring an umbrella this evening -- rain is likely around 6pm.",
        card: {
          forecasts: [
            {
              location: {
                id: "1",
                name: "Hyderabad",
                latitude: 17.385,
                longitude: 78.4867,
                country: null,
                country_code: "IN",
                admin1: null,
                admin2: null,
                population: null,
                timezone: "Asia/Kolkata",
              },
              units: {
                temperature: "celsius",
                wind_speed: "kmh",
                precip_amount: "mm",
                precip_probability: "percent",
              },
              current: {
                timestamp: "2024-06-01T18:00:00Z",
                temperature: 27.0,
                feels_like: null,
                precip_probability: 80.0,
                precip_amount: null,
                wind_speed: null,
                condition_code: "RAIN",
              },
              hourly: null,
              daily: null,
            },
          ],
          highlight: {
            forecast_index: 0,
            locator: { block: "current", index: null },
          },
        },
      },
    };

    expect(describeEvent(event)).toBe(
      "answer: Yes, bring an umbrella this evening -- rain is likely around 6pm.",
    );
  });

  it("narrows to ErrorPayload for an error event", () => {
    const event: SSEEvent = {
      type: "error",
      data: { kind: "internal", message: "boom" },
    };

    expect(describeEvent(event)).toBe("error: internal - boom");
  });
});
