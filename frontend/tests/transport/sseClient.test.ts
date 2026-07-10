import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  AnswerPayload,
  ClarifyPayload,
  ErrorPayload,
  StepPayload,
} from "../../src/contract";
import { runQuery } from "../../src/transport/sseClient";

const REQUEST = { query: "what's the weather", now: "2026-07-10T12:00:00Z" };

function sseStream(
  records: string[],
  signal?: AbortSignal,
): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const record of records) {
        controller.enqueue(encoder.encode(`data: ${record}\n\n`));
      }
      if (signal) {
        signal.addEventListener("abort", () => {
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

function stubFetch(response: Response): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => response),
  );
}

function stubFetchRejecting(error: unknown): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => {
      throw error;
    }),
  );
}

function makeHandlers() {
  return {
    onStep: vi.fn<(payload: StepPayload) => void>(),
    onClarify: vi.fn<(payload: ClarifyPayload) => void>(),
    onAnswer: vi.fn<(payload: AnswerPayload) => void>(),
    onError: vi.fn<(payload: ErrorPayload) => void>(),
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("runQuery", () => {
  it("invokes onStep in order then onAnswer, and resolves", async () => {
    const stream = sseStream([
      JSON.stringify({
        type: "step",
        data: { label: "Understanding...", stage: "decompose" },
      }),
      JSON.stringify({
        type: "step",
        data: { label: "Planning...", stage: "plan" },
      }),
      JSON.stringify({
        type: "answer",
        data: {
          text: "Yes, bring an umbrella.",
          card: { forecasts: [], highlight: null },
        },
      }),
    ]);
    stubFetch(new Response(stream, { status: 200 }));
    const handlers = makeHandlers();

    await runQuery(REQUEST, handlers);

    expect(handlers.onStep).toHaveBeenNthCalledWith(1, {
      label: "Understanding...",
      stage: "decompose",
    });
    expect(handlers.onStep).toHaveBeenNthCalledWith(2, {
      label: "Planning...",
      stage: "plan",
    });
    expect(handlers.onAnswer).toHaveBeenCalledWith({
      text: "Yes, bring an umbrella.",
      card: { forecasts: [], highlight: null },
    });
    expect(handlers.onError).not.toHaveBeenCalled();
  });

  it("resolves with onClarify given steps then a clarify terminal event", async () => {
    const candidates = [
      {
        id: "1",
        name: "Springfield",
        latitude: 39.78,
        longitude: -89.65,
        country: null,
        country_code: "US",
        admin1: "Illinois",
        admin2: null,
        population: null,
        timezone: null,
      },
    ];
    const stream = sseStream([
      JSON.stringify({
        type: "step",
        data: { label: "Looking up...", stage: "execute_geocode" },
      }),
      JSON.stringify({ type: "clarify", data: { candidates } }),
    ]);
    stubFetch(new Response(stream, { status: 200 }));
    const handlers = makeHandlers();

    await runQuery(REQUEST, handlers);

    expect(handlers.onClarify).toHaveBeenCalledWith({ candidates });
    expect(handlers.onAnswer).not.toHaveBeenCalled();
    expect(handlers.onError).not.toHaveBeenCalled();
  });

  it("synthesizes an internal error when the stream closes with no terminal event", async () => {
    const stream = sseStream([
      JSON.stringify({
        type: "step",
        data: { label: "Understanding...", stage: "decompose" },
      }),
    ]);
    stubFetch(new Response(stream, { status: 200 }));
    const handlers = makeHandlers();

    await runQuery(REQUEST, handlers);

    expect(handlers.onError).toHaveBeenCalledTimes(1);
    expect(handlers.onError.mock.calls[0][0].kind).toBe("internal");
  });

  it("synthesizes an internal error on malformed JSON, without throwing", async () => {
    const stream = sseStream(["{not valid json"]);
    stubFetch(new Response(stream, { status: 200 }));
    const handlers = makeHandlers();

    await expect(runQuery(REQUEST, handlers)).resolves.toBeUndefined();

    expect(handlers.onError).toHaveBeenCalledTimes(1);
    expect(handlers.onError.mock.calls[0][0].kind).toBe("internal");
  });

  it("synthesizes an internal error on a non-2xx response", async () => {
    stubFetch(new Response(null, { status: 500 }));
    const handlers = makeHandlers();

    await runQuery(REQUEST, handlers);

    expect(handlers.onError).toHaveBeenCalledTimes(1);
    expect(handlers.onError.mock.calls[0][0].kind).toBe("internal");
  });

  it("synthesizes a provider_unreachable error when fetch itself rejects", async () => {
    stubFetchRejecting(new TypeError("Failed to fetch"));
    const handlers = makeHandlers();

    await runQuery(REQUEST, handlers);

    expect(handlers.onError).toHaveBeenCalledTimes(1);
    expect(handlers.onError.mock.calls[0][0].kind).toBe("provider_unreachable");
  });

  it("accepts a record with no data: prefix", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(
          encoder.encode(
            `${JSON.stringify({
              type: "answer",
              data: { text: "ok", card: { forecasts: [], highlight: null } },
            })}\n\n`,
          ),
        );
        controller.close();
      },
    });
    stubFetch(new Response(stream, { status: 200 }));
    const handlers = makeHandlers();

    await runQuery(REQUEST, handlers);

    expect(handlers.onAnswer).toHaveBeenCalledWith({
      text: "ok",
      card: { forecasts: [], highlight: null },
    });
  });

  it("stringifies a non-Error value thrown by fetch", async () => {
    stubFetchRejecting("network down");
    const handlers = makeHandlers();

    await runQuery(REQUEST, handlers);

    expect(handlers.onError).toHaveBeenCalledTimes(1);
    expect(handlers.onError.mock.calls[0][0].message).toContain("network down");
  });

  it("synthesizes an internal error when a 2xx response has no body", async () => {
    stubFetch(new Response(null, { status: 200 }));
    const handlers = makeHandlers();

    await runQuery(REQUEST, handlers);

    expect(handlers.onError).toHaveBeenCalledTimes(1);
    expect(handlers.onError.mock.calls[0][0].kind).toBe("internal");
  });

  it("passes through a genuine backend error event unchanged", async () => {
    const stream = sseStream([
      JSON.stringify({
        type: "error",
        data: { kind: "not_found", message: "no such place" },
      }),
    ]);
    stubFetch(new Response(stream, { status: 200 }));
    const handlers = makeHandlers();

    await runQuery(REQUEST, handlers);

    expect(handlers.onError).toHaveBeenCalledWith({
      kind: "not_found",
      message: "no such place",
    });
  });

  it("skips blank records between events", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode("\n\n"));
        controller.enqueue(
          encoder.encode(
            `data: ${JSON.stringify({
              type: "answer",
              data: { text: "ok", card: { forecasts: [], highlight: null } },
            })}\n\n`,
          ),
        );
        controller.close();
      },
    });
    stubFetch(new Response(stream, { status: 200 }));
    const handlers = makeHandlers();

    await runQuery(REQUEST, handlers);

    expect(handlers.onAnswer).toHaveBeenCalledWith({
      text: "ok",
      card: { forecasts: [], highlight: null },
    });
    expect(handlers.onError).not.toHaveBeenCalled();
  });

  it("synthesizes an internal error for an event with an unrecognized type", async () => {
    const stream = sseStream([
      JSON.stringify({ type: "unknown_event", data: {} }),
    ]);
    stubFetch(new Response(stream, { status: 200 }));
    const handlers = makeHandlers();

    await runQuery(REQUEST, handlers);

    expect(handlers.onError).toHaveBeenCalledTimes(1);
    expect(handlers.onError.mock.calls[0][0].kind).toBe("internal");
  });

  it("cancels cleanly on abort mid-stream, without calling onError", async () => {
    const controller = new AbortController();
    const handlers = makeHandlers();
    handlers.onStep.mockImplementation(() => {
      controller.abort();
    });
    const stream = sseStream(
      [
        JSON.stringify({
          type: "step",
          data: { label: "Understanding...", stage: "decompose" },
        }),
      ],
      controller.signal,
    );
    stubFetch(new Response(stream, { status: 200 }));

    await expect(
      runQuery(REQUEST, handlers, controller.signal),
    ).resolves.toBeUndefined();

    expect(handlers.onStep).toHaveBeenCalledTimes(1);
    expect(handlers.onError).not.toHaveBeenCalled();
  });
});
