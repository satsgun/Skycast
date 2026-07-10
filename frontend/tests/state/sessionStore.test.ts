import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Location } from "../../src/contract";
import { useSessionStore } from "../../src/state/sessionStore";

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

const NOW = new Date("2026-07-10T12:00:00Z");

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(NOW);
});

afterEach(() => {
  vi.useRealTimers();
  localStorage.clear();
});

describe("useSessionStore", () => {
  it("recordActivity updates location, time window, and query history", () => {
    const { result } = renderHook(() => useSessionStore());

    act(() => {
      result.current.recordActivity({
        query: "what's the weather in Austin?",
        location: LOCATION,
        timeWindow: {
          start: "2026-07-10T12:00:00Z",
          end: "2026-07-10T18:00:00Z",
        },
      });
    });

    expect(result.current.session.lastLocation).toEqual(LOCATION);
    expect(result.current.session.lastTimeWindow).toEqual({
      start: "2026-07-10T12:00:00Z",
      end: "2026-07-10T18:00:00Z",
    });
    expect(result.current.session.queryHistory).toEqual([
      "what's the weather in Austin?",
    ]);
  });

  it("carries context across a simulated reload within the window", () => {
    const first = renderHook(() => useSessionStore());
    act(() => {
      first.result.current.recordActivity({
        query: "what's the weather?",
        location: LOCATION,
      });
    });
    first.unmount();

    vi.setSystemTime(new Date(NOW.getTime() + 10 * 60 * 1000)); // 10 min later

    const second = renderHook(() => useSessionStore());

    expect(second.result.current.session.lastLocation).toEqual(LOCATION);
    expect(second.result.current.session.queryHistory).toEqual([
      "what's the weather?",
    ]);
  });

  it("resets to empty state after the 30-minute window expires", () => {
    const first = renderHook(() => useSessionStore());
    act(() => {
      first.result.current.recordActivity({
        query: "what's the weather?",
        location: LOCATION,
      });
    });
    first.unmount();

    vi.setSystemTime(new Date(NOW.getTime() + 31 * 60 * 1000)); // 31 min later

    const second = renderHook(() => useSessionStore());

    expect(second.result.current.session.lastLocation).toBeNull();
    expect(second.result.current.session.queryHistory).toEqual([]);
  });

  it("caps queryHistory at the last 10 entries", () => {
    const { result } = renderHook(() => useSessionStore());

    act(() => {
      for (let i = 0; i < 12; i++) {
        result.current.recordActivity({ query: `query ${i}` });
      }
    });

    expect(result.current.session.queryHistory).toHaveLength(10);
    expect(result.current.session.queryHistory[0]).toBe("query 2");
    expect(result.current.session.queryHistory[9]).toBe("query 11");
  });

  it("clearSession resets to the empty state and persists it", () => {
    const { result } = renderHook(() => useSessionStore());
    act(() => {
      result.current.recordActivity({
        query: "what's the weather?",
        location: LOCATION,
      });
    });

    act(() => {
      result.current.clearSession();
    });

    expect(result.current.session.lastLocation).toBeNull();
    expect(result.current.session.queryHistory).toEqual([]);

    const reloaded = renderHook(() => useSessionStore());
    expect(reloaded.result.current.session.lastLocation).toBeNull();
  });
});
