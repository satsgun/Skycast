/**
 * The browser's EventSource API only issues GET requests, but /query
 * requires a POST body (the QueryRequest). This client uses fetch()
 * with a streaming body reader (response.body.getReader()) and parses
 * the SSE wire format by hand, rather than a POST-capable SSE library
 * -- the wire format this backend actually emits is deliberately
 * minimal (a single unnamed `data: {json}` line per event, no
 * `event:`/`id:`/`retry:` fields, no multi-line data -- see
 * docs/sse-contract.md), which makes hand-parsing tractable without
 * adding a dependency.
 */
import { API_BASE_URL } from "../config/env";
import type {
  AnswerPayload,
  ClarifyPayload,
  ErrorPayload,
  QueryRequest,
  SSEEvent,
  StepPayload,
} from "../contract";

export interface RunQueryHandlers {
  onStep: (payload: StepPayload) => void;
  onClarify: (payload: ClarifyPayload) => void;
  onAnswer: (payload: AnswerPayload) => void;
  onError: (payload: ErrorPayload) => void;
}

export async function runQuery(
  request: QueryRequest,
  handlers: RunQueryHandlers,
  signal?: AbortSignal,
): Promise<void> {
  try {
    const response = await fetch(`${API_BASE_URL}/query`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify(request),
      signal,
    });

    if (!response.ok) {
      handlers.onError(
        internalError(`server responded with status ${response.status}`),
      );
      return;
    }
    if (response.body === null) {
      handlers.onError(internalError("response had no body"));
      return;
    }

    await readEvents(response.body, handlers);
  } catch (err) {
    if (isAbortError(err)) {
      return;
    }
    handlers.onError(
      providerUnreachableError(
        `could not reach the server: ${errorMessage(err)}`,
      ),
    );
  }
}

async function readEvents(
  body: ReadableStream<Uint8Array>,
  handlers: RunQueryHandlers,
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });

    let separatorIndex = buffer.indexOf("\n\n");
    while (separatorIndex !== -1) {
      const record = buffer.slice(0, separatorIndex);
      buffer = buffer.slice(separatorIndex + 2);

      if (dispatchRecord(record, handlers) === "stop") {
        return;
      }
      separatorIndex = buffer.indexOf("\n\n");
    }
  }

  handlers.onError(
    internalError("stream closed before a terminal event was received"),
  );
}

function dispatchRecord(
  record: string,
  handlers: RunQueryHandlers,
): "continue" | "stop" {
  const trimmed = record.trim();
  if (trimmed === "") {
    return "continue";
  }

  const jsonText = trimmed.startsWith("data:")
    ? trimmed.slice(5).trim()
    : trimmed;

  let event: SSEEvent;
  try {
    event = JSON.parse(jsonText) as SSEEvent;
  } catch {
    handlers.onError(
      internalError(`received malformed event data: ${jsonText}`),
    );
    return "stop";
  }

  switch (event.type) {
    case "step":
      handlers.onStep(event.data);
      return "continue";
    case "clarify":
      handlers.onClarify(event.data);
      return "stop";
    case "answer":
      handlers.onAnswer(event.data);
      return "stop";
    case "error":
      handlers.onError(event.data);
      return "stop";
    default:
      handlers.onError(
        internalError("received an event with an unrecognized type"),
      );
      return "stop";
  }
}

function internalError(message: string): ErrorPayload {
  return { kind: "internal", message };
}

function providerUnreachableError(message: string): ErrorPayload {
  return { kind: "provider_unreachable", message };
}

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

function isAbortError(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}
