import type { ErrorKind } from "../contract";
import type { CachedAnswer } from "./offlineCache";

export type ErrorAction =
  | { type: "retry" }
  | { type: "retry_free_text" }
  | { type: "show_cached"; cachedAt: string }
  | { type: "open_settings" };

export function actionsFor(
  kind: ErrorKind,
  cachedAnswer: CachedAnswer | null,
): ErrorAction[] {
  switch (kind) {
    case "not_found":
      // Fuzzy-alternative suggestion chips would need candidate data
      // ErrorPayload doesn't carry (see docs/sse-contract.md) -- not
      // derivable on the frontend alone, so v1 offers free-text retry.
      return [{ type: "retry_free_text" }];
    case "provider_unreachable":
      return cachedAnswer === null
        ? [{ type: "retry" }]
        : [
            { type: "retry" },
            { type: "show_cached", cachedAt: cachedAnswer.cachedAt },
          ];
    case "bad_input":
      return [{ type: "open_settings" }, { type: "retry_free_text" }];
    case "internal":
      return [{ type: "retry" }];
  }
}
