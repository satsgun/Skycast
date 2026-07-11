import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  AnswerPayload,
  DailyReading,
  Forecast,
  HourlyReading,
  Location,
  QueryRequest,
} from "../../src/contract";
import { useOfflineCache } from "../../src/state/offlineCache";
import { useSessionStore } from "../../src/state/sessionStore";
import { useQuery } from "../../src/state/useQuery";

const NOW = new Date("2026-07-10T12:00:00Z");

const LOCATION: Location = {
  id: "1",
  name: "Austin",
  latitude: 30.27,
  longitude: -97.74,
  country: null,
  country_code: "US",
  admin1: null,
  admin2: null,
  population: null,
  timezone: null,
};

const OTHER_LOCATION: Location = {
  id: "2",
  name: "Dallas",
  latitude: 32.78,
  longitude: -96.8,
  country: null,
  country_code: "US",
  admin1: null,
  admin2: null,
  population: null,
  timezone: null,
};

interface StreamOptions {
  keepOpen?: boolean;
}

function sseStream(
  records: string[],
  signal: AbortSignal | undefined,
  options?: StreamOptions,
): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const record of records) {
        controller.enqueue(encoder.encode(`data: ${record}\n\n`));
      }
      if (options?.keepOpen) {
        signal?.addEventListener("abort", () => {
          controller.error(
            new DOMException("The operation was aborted.", "AbortError"),
          );
        });
      } else {
        controller.close();
      }
    },
  });
}

interface FetchCall {
  request: QueryRequest;
  signal: AbortSignal;
}

function stubFetchQueue(
  streamBuilders: Array<
    (signal: AbortSignal | undefined) => ReadableStream<Uint8Array>
  >,
): FetchCall[] {
  const calls: FetchCall[] = [];
  let index = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_url: string | URL, init?: RequestInit) => {
      const signal = init?.signal ?? undefined;
      const request = JSON.parse(init?.body as string) as QueryRequest;
      calls.push({ request, signal: signal as AbortSignal });
      const builder =
        streamBuilders[Math.min(index, streamBuilders.length - 1)];
      index += 1;
      return new Response(builder(signal), { status: 200 });
    }),
  );
  return calls;
}

function hourlyReading(timestamp: string, temperature: number): HourlyReading {
  return {
    timestamp,
    temperature,
    feels_like: null,
    precip_probability: null,
    precip_amount: null,
    wind_speed: null,
    condition_code: "CLEAR",
  };
}

function dailyReading(
  date: string,
  tempMin: number,
  tempMax: number,
): DailyReading {
  return {
    date,
    temp_min: tempMin,
    temp_max: tempMax,
    precip_probability: null,
    precip_amount: null,
    wind_speed_max: null,
    condition_code: "CLEAR",
    sunrise: null,
    sunset: null,
  };
}

interface ForecastOverrides {
  location?: Location;
  current?: HourlyReading | null;
  hourly?: HourlyReading[] | null;
  daily?: DailyReading[] | null;
}

function forecastWith(overrides: ForecastOverrides): Forecast {
  return {
    location: overrides.location ?? LOCATION,
    units: {
      temperature: "celsius",
      wind_speed: "kmh",
      precip_amount: "mm",
      precip_probability: "percent",
    },
    current:
      "current" in overrides
        ? (overrides.current ?? null)
        : hourlyReading(NOW.toISOString(), 25),
    hourly: overrides.hourly ?? null,
    daily: overrides.daily ?? null,
  };
}

function answerPayload(overrides: Partial<AnswerPayload> = {}): AnswerPayload {
  return {
    text: "It's sunny in Austin.",
    card: { forecasts: [forecastWith({})], highlight: null },
    ...overrides,
  };
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(NOW);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("submitQuery request building", () => {
  it("builds query/now/units/default_location from the settings store", async () => {
    localStorage.setItem(
      "skycast:settings",
      JSON.stringify({
        units: { temperature: "F", windSpeed: "mph", timeFormat: "12h" },
        defaultLocation: LOCATION,
      }),
    );
    const calls = stubFetchQueue([
      (signal) => sseStream([], signal, { keepOpen: true }),
    ]);
    const { result } = renderHook(() => useQuery());

    act(() => {
      result.current.submitQuery("what's the weather?");
    });

    expect(calls).toHaveLength(1);
    expect(calls[0].request).toEqual({
      query: "what's the weather?",
      now: NOW.toISOString(),
      units: "fahrenheit",
      default_location: LOCATION,
    });
  });

  it("includes resolved_location when passed", async () => {
    const calls = stubFetchQueue([
      (signal) => sseStream([], signal, { keepOpen: true }),
    ]);
    const { result } = renderHook(() => useQuery());

    act(() => {
      result.current.submitQuery("Springfield weather?", {
        resolvedLocation: LOCATION,
      });
    });

    expect(calls[0].request.resolved_location).toEqual(LOCATION);
  });

  it("omits resolved_location when not passed", async () => {
    const calls = stubFetchQueue([
      (signal) => sseStream([], signal, { keepOpen: true }),
    ]);
    const { result } = renderHook(() => useQuery());

    act(() => {
      result.current.submitQuery("what's the weather?");
    });

    expect(calls[0].request.resolved_location).toBeUndefined();
  });
});

describe("machine wiring", () => {
  it("appends a step with no terminal event", async () => {
    stubFetchQueue([
      (signal) =>
        sseStream(
          [
            JSON.stringify({
              type: "step",
              data: { label: "Understanding...", stage: "decompose" },
            }),
          ],
          signal,
          { keepOpen: true },
        ),
    ]);
    const { result } = renderHook(() => useQuery());

    act(() => {
      result.current.submitQuery("what's the weather?");
    });

    await waitFor(() =>
      expect(result.current.state.main).toEqual({
        type: "thinking",
        query: "what's the weather?",
        steps: [{ label: "Understanding...", stage: "decompose" }],
      }),
    );
  });

  it("settles on answer after steps", async () => {
    const answer = answerPayload();
    stubFetchQueue([
      (signal) =>
        sseStream(
          [
            JSON.stringify({
              type: "step",
              data: { label: "Understanding...", stage: "decompose" },
            }),
            JSON.stringify({ type: "answer", data: answer }),
          ],
          signal,
        ),
    ]);
    const { result } = renderHook(() => useQuery());

    act(() => {
      result.current.submitQuery("what's the weather?");
    });

    await waitFor(() => expect(result.current.state.main.type).toBe("answer"));
    expect(
      (result.current.state.main as { answer: AnswerPayload }).answer,
    ).toEqual(answer);
  });

  it("settles on clarify", async () => {
    stubFetchQueue([
      (signal) =>
        sseStream(
          [
            JSON.stringify({
              type: "clarify",
              data: { candidates: [LOCATION, OTHER_LOCATION] },
            }),
          ],
          signal,
        ),
    ]);
    const { result } = renderHook(() => useQuery());

    act(() => {
      result.current.submitQuery("Springfield weather?");
    });

    await waitFor(() => expect(result.current.state.main.type).toBe("clarify"));
    expect(
      (result.current.state.main as { candidates: Location[] }).candidates,
    ).toEqual([LOCATION, OTHER_LOCATION]);
  });

  it("settles on error", async () => {
    stubFetchQueue([
      (signal) =>
        sseStream(
          [
            JSON.stringify({
              type: "error",
              data: { kind: "internal", message: "boom" },
            }),
          ],
          signal,
        ),
    ]);
    const { result } = renderHook(() => useQuery());

    act(() => {
      result.current.submitQuery("what's the weather?");
    });

    await waitFor(() => expect(result.current.state.main.type).toBe("error"));
  });
});

describe("cancellation", () => {
  it("aborts the in-flight stream when a new query is submitted", async () => {
    const calls = stubFetchQueue([
      (signal) => sseStream([], signal, { keepOpen: true }),
      (signal) => sseStream([], signal, { keepOpen: true }),
    ]);
    const { result } = renderHook(() => useQuery());

    act(() => {
      result.current.submitQuery("first query");
    });
    act(() => {
      result.current.submitQuery("second query");
    });

    expect(calls[0].signal.aborted).toBe(true);
    expect(calls[1].signal.aborted).toBe(false);
    await waitFor(() =>
      expect((result.current.state.main as { query: string }).query).toBe(
        "second query",
      ),
    );
  });

  it("aborts the in-flight stream on unmount", async () => {
    const calls = stubFetchQueue([
      (signal) => sseStream([], signal, { keepOpen: true }),
    ]);
    const { result, unmount } = renderHook(() => useQuery());

    act(() => {
      result.current.submitQuery("what's the weather?");
    });
    unmount();

    expect(calls[0].signal.aborted).toBe(true);
  });
});

describe("offline cache", () => {
  it("caches the answer payload with a timestamp", async () => {
    const answer = answerPayload();
    stubFetchQueue([
      (signal) =>
        sseStream([JSON.stringify({ type: "answer", data: answer })], signal),
    ]);
    const { result } = renderHook(() => useQuery());

    act(() => {
      result.current.submitQuery("what's the weather?");
    });
    await waitFor(() => expect(result.current.state.main.type).toBe("answer"));

    const cache = renderHook(() => useOfflineCache());
    expect(cache.result.current.cached).toEqual({
      answer,
      cachedAt: NOW.toISOString(),
    });
  });
});

describe("session carry-over", () => {
  it("derives location and time window from hourly readings", async () => {
    const forecast = forecastWith({
      hourly: [
        hourlyReading("2026-07-10T13:00:00Z", 26),
        hourlyReading("2026-07-10T18:00:00Z", 24),
      ],
      current: null,
    });
    const answer = answerPayload({
      card: { forecasts: [forecast], highlight: null },
    });
    stubFetchQueue([
      (signal) =>
        sseStream([JSON.stringify({ type: "answer", data: answer })], signal),
    ]);
    const { result } = renderHook(() => useQuery());

    act(() => {
      result.current.submitQuery("what's the weather this evening?");
    });
    await waitFor(() => expect(result.current.state.main.type).toBe("answer"));

    const session = renderHook(() => useSessionStore());
    expect(session.result.current.session.lastLocation).toEqual(LOCATION);
    expect(session.result.current.session.lastTimeWindow).toEqual({
      start: "2026-07-10T13:00:00Z",
      end: "2026-07-10T18:00:00Z",
    });
  });

  it("derives location and time window from daily readings when hourly is absent", async () => {
    const forecast = forecastWith({
      daily: [
        dailyReading("2026-07-10", 20, 30),
        dailyReading("2026-07-11", 19, 28),
      ],
      current: null,
    });
    const answer = answerPayload({
      card: { forecasts: [forecast], highlight: null },
    });
    stubFetchQueue([
      (signal) =>
        sseStream([JSON.stringify({ type: "answer", data: answer })], signal),
    ]);
    const { result } = renderHook(() => useQuery());

    act(() => {
      result.current.submitQuery("what's the weather this week?");
    });
    await waitFor(() => expect(result.current.state.main.type).toBe("answer"));

    const session = renderHook(() => useSessionStore());
    expect(session.result.current.session.lastTimeWindow).toEqual({
      start: "2026-07-10",
      end: "2026-07-11",
    });
  });

  it("sets location but preserves the prior time window when only current is populated", async () => {
    const answer = answerPayload();
    stubFetchQueue([
      (signal) =>
        sseStream([JSON.stringify({ type: "answer", data: answer })], signal),
    ]);
    const { result } = renderHook(() => useQuery());

    act(() => {
      result.current.submitQuery("what's the weather right now?");
    });
    await waitFor(() => expect(result.current.state.main.type).toBe("answer"));

    const session = renderHook(() => useSessionStore());
    expect(session.result.current.session.lastLocation).toEqual(LOCATION);
    expect(session.result.current.session.lastTimeWindow).toBeNull();
  });

  it("carries context from the highlighted forecast, not always the first", async () => {
    const answer = answerPayload({
      card: {
        forecasts: [
          forecastWith({ location: LOCATION }),
          forecastWith({ location: OTHER_LOCATION }),
        ],
        highlight: {
          forecast_index: 1,
          locator: { block: "current", index: null },
        },
      },
    });
    stubFetchQueue([
      (signal) =>
        sseStream([JSON.stringify({ type: "answer", data: answer })], signal),
    ]);
    const { result } = renderHook(() => useQuery());

    act(() => {
      result.current.submitQuery("compare Austin and Dallas");
    });
    await waitFor(() => expect(result.current.state.main.type).toBe("answer"));

    const session = renderHook(() => useSessionStore());
    expect(session.result.current.session.lastLocation).toEqual(OTHER_LOCATION);
  });

  it("falls back to the first forecast when there is no highlight", async () => {
    const answer = answerPayload({
      card: {
        forecasts: [
          forecastWith({ location: LOCATION }),
          forecastWith({ location: OTHER_LOCATION }),
        ],
        highlight: null,
      },
    });
    stubFetchQueue([
      (signal) =>
        sseStream([JSON.stringify({ type: "answer", data: answer })], signal),
    ]);
    const { result } = renderHook(() => useQuery());

    act(() => {
      result.current.submitQuery("compare Austin and Dallas");
    });
    await waitFor(() => expect(result.current.state.main.type).toBe("answer"));

    const session = renderHook(() => useSessionStore());
    expect(session.result.current.session.lastLocation).toEqual(LOCATION);
  });

  it("records only the query when there are no forecasts to carry", async () => {
    const answer = answerPayload({ card: { forecasts: [], highlight: null } });
    stubFetchQueue([
      (signal) =>
        sseStream([JSON.stringify({ type: "answer", data: answer })], signal),
    ]);
    const { result } = renderHook(() => useQuery());

    act(() => {
      result.current.submitQuery("what's the weather?");
    });
    await waitFor(() => expect(result.current.state.main.type).toBe("answer"));

    const session = renderHook(() => useSessionStore());
    expect(session.result.current.session.queryHistory).toEqual([
      "what's the weather?",
    ]);
    expect(session.result.current.session.lastLocation).toBeNull();
  });

  it("refreshes session activity on clarify without fabricating location/time window", async () => {
    stubFetchQueue([
      (signal) =>
        sseStream(
          [
            JSON.stringify({
              type: "clarify",
              data: { candidates: [LOCATION] },
            }),
          ],
          signal,
        ),
    ]);
    const { result } = renderHook(() => useQuery());

    act(() => {
      result.current.submitQuery("Springfield weather?");
    });
    await waitFor(() => expect(result.current.state.main.type).toBe("clarify"));

    const session = renderHook(() => useSessionStore());
    expect(session.result.current.session.queryHistory).toEqual([
      "Springfield weather?",
    ]);
    expect(session.result.current.session.lastLocation).toBeNull();
    expect(session.result.current.session.lastTimeWindow).toBeNull();
  });

  it("refreshes session activity on error without fabricating location/time window", async () => {
    stubFetchQueue([
      (signal) =>
        sseStream(
          [
            JSON.stringify({
              type: "error",
              data: { kind: "internal", message: "boom" },
            }),
          ],
          signal,
        ),
    ]);
    const { result } = renderHook(() => useQuery());

    act(() => {
      result.current.submitQuery("what's the weather?");
    });
    await waitFor(() => expect(result.current.state.main.type).toBe("error"));

    const session = renderHook(() => useSessionStore());
    expect(session.result.current.session.queryHistory).toEqual([
      "what's the weather?",
    ]);
    expect(session.result.current.session.lastLocation).toBeNull();
    expect(session.result.current.session.lastTimeWindow).toBeNull();
  });
});
