import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AnswerPayload } from "../../src/contract";
import { useOfflineCache } from "../../src/state/offlineCache";

const ANSWER: AnswerPayload = {
  text: "It's sunny and 28C in Austin right now.",
  card: { forecasts: [], highlight: null },
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

describe("useOfflineCache", () => {
  it("has no cached answer and null freshness initially", () => {
    const { result } = renderHook(() => useOfflineCache());

    expect(result.current.cached).toBeNull();
    expect(result.current.minutesSinceCached()).toBeNull();
  });

  it("cacheAnswer stores the answer with a timestamp", () => {
    const { result } = renderHook(() => useOfflineCache());

    act(() => {
      result.current.cacheAnswer(ANSWER);
    });

    expect(result.current.cached).toEqual({
      answer: ANSWER,
      cachedAt: NOW.toISOString(),
    });
  });

  it("persists the cached answer across a simulated reload", () => {
    const first = renderHook(() => useOfflineCache());
    act(() => {
      first.result.current.cacheAnswer(ANSWER);
    });
    first.unmount();

    const second = renderHook(() => useOfflineCache());

    expect(second.result.current.cached?.answer).toEqual(ANSWER);
  });

  it("computes minutesSinceCached correctly as time passes", () => {
    const { result } = renderHook(() => useOfflineCache());
    act(() => {
      result.current.cacheAnswer(ANSWER);
    });

    vi.setSystemTime(new Date(NOW.getTime() + 5 * 60 * 1000));

    expect(result.current.minutesSinceCached()).toBe(5);
  });

  it("clearCache removes the cached answer", () => {
    const { result } = renderHook(() => useOfflineCache());
    act(() => {
      result.current.cacheAnswer(ANSWER);
    });

    act(() => {
      result.current.clearCache();
    });

    expect(result.current.cached).toBeNull();
    expect(result.current.minutesSinceCached()).toBeNull();
  });
});
