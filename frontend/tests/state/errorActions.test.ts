import { describe, expect, it } from "vitest";

import type { AnswerPayload, ErrorKind } from "../../src/contract";
import { actionsFor } from "../../src/state/errorActions";
import type { CachedAnswer } from "../../src/state/offlineCache";

const ANSWER: AnswerPayload = {
  text: "It's sunny.",
  card: { forecasts: [], highlight: null },
};

const CACHED_ANSWER: CachedAnswer = {
  answer: ANSWER,
  cachedAt: "2026-07-11T10:00:00Z",
};

describe("actionsFor", () => {
  const kinds: ErrorKind[] = [
    "not_found",
    "provider_unreachable",
    "bad_input",
    "internal",
  ];

  for (const kind of kinds) {
    it(`yields at least one action for kind=${kind}`, () => {
      expect(actionsFor(kind, null).length).toBeGreaterThanOrEqual(1);
    });
  }

  it("not_found yields free-text retry only", () => {
    expect(actionsFor("not_found", null)).toEqual([
      { type: "retry_free_text" },
    ]);
  });

  it("bad_input yields open_settings and free-text retry", () => {
    expect(actionsFor("bad_input", null)).toEqual([
      { type: "open_settings" },
      { type: "retry_free_text" },
    ]);
  });

  it("internal yields retry only", () => {
    expect(actionsFor("internal", null)).toEqual([{ type: "retry" }]);
  });

  it("provider_unreachable yields retry only when there is no cached answer", () => {
    expect(actionsFor("provider_unreachable", null)).toEqual([
      { type: "retry" },
    ]);
  });

  it("provider_unreachable yields retry + show_cached with the freshness timestamp when cached", () => {
    expect(actionsFor("provider_unreachable", CACHED_ANSWER)).toEqual([
      { type: "retry" },
      { type: "show_cached", cachedAt: CACHED_ANSWER.cachedAt },
    ]);
  });

  const nonCacheAwareKinds: ErrorKind[] = [
    "not_found",
    "bad_input",
    "internal",
  ];
  for (const kind of nonCacheAwareKinds) {
    it(`a cached answer has no effect on kind=${kind}`, () => {
      expect(actionsFor(kind, CACHED_ANSWER)).toEqual(actionsFor(kind, null));
    });
  }
});
