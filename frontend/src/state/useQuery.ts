import { useEffect, useRef } from "react";
import type { Dispatch } from "react";

import type {
  AnswerPayload,
  Forecast,
  Location,
  QueryRequest,
} from "../contract";
import { runQuery } from "../transport/sseClient";
import type { MachineEvent, MachineState } from "./machine";
import { useMachine } from "./machine";
import { useOfflineCache } from "./offlineCache";
import type { TimeWindow } from "./sessionStore";
import { useSessionStore } from "./sessionStore";
import type { UseSettingsStoreResult } from "./settingsStore";

export interface UseQueryResult {
  state: MachineState;
  dispatch: Dispatch<MachineEvent>;
  submitQuery: (
    text: string,
    options?: { resolvedLocations?: Record<string, Location> },
  ) => void;
  selectCandidate: (candidate: Location) => void;
  showCached: () => void;
}

export function useQuery(
  settingsStore: UseSettingsStoreResult,
): UseQueryResult {
  const [state, dispatch] = useMachine();
  const sessionStore = useSessionStore();
  const offlineCache = useOfflineCache();
  // Any dispatcher of SESSION_EXPIRED must abort abortControllerRef.current
  // first, or a late terminal event from the still-in-flight stream will
  // throw inside this hook's un-awaited runQuery promise (machineReducer
  // rejects any event once main is no longer "thinking"). submitQuery below
  // gets this for free -- its own abort() call always precedes its
  // SESSION_EXPIRED dispatch -- but a future independent dispatcher (an
  // idle timer, a sign-out action) would need the same guarantee.
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  function submitQuery(
    text: string,
    options?: { resolvedLocations?: Record<string, Location> },
  ): void {
    abortControllerRef.current?.abort();

    if (sessionStore.isExpired()) {
      dispatch({ type: "SESSION_EXPIRED" });
      sessionStore.clearSession();
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;

    dispatch({ type: "SUBMIT", query: text });

    const request: QueryRequest = {
      query: text,
      now: new Date().toISOString(),
      ...settingsStore.toQueryRequestFields(),
    };
    if (options?.resolvedLocations !== undefined) {
      request.resolved_locations = options.resolvedLocations;
    }

    void runQuery(
      request,
      {
        onStep: (payload) => dispatch({ type: "STEP", payload }),
        onClarify: (payload) => {
          dispatch({ type: "CLARIFY", payload });
          sessionStore.recordActivity({ query: text });
        },
        onAnswer: (payload) => {
          dispatch({ type: "ANSWER", payload });
          offlineCache.cacheAnswer(payload);
          sessionStore.recordActivity({
            query: text,
            ...deriveCarriedContext(payload),
          });
        },
        onError: (payload) => {
          dispatch({
            type: "ERROR",
            payload,
            cachedAnswer: offlineCache.cached,
          });
          sessionStore.recordActivity({ query: text });
        },
      },
      controller.signal,
    );
  }

  function selectCandidate(candidate: Location): void {
    if (state.main.type !== "clarify") {
      throw new Error(
        "selectCandidate called while the machine is not in clarify state",
      );
    }
    const originalQuery = state.main.query;
    sessionStore.recordActivity({ query: originalQuery, location: candidate });
    submitQuery(originalQuery, {
      resolvedLocations: {
        ...state.main.resolvedSoFar,
        [state.main.forLocationName]: candidate,
      },
    });
  }

  function showCached(): void {
    if (offlineCache.cached === null) return;
    dispatch({ type: "SHOW_CACHED", payload: offlineCache.cached.answer });
  }

  return { state, dispatch, submitQuery, selectCandidate, showCached };
}

function deriveCarriedContext(answer: AnswerPayload): {
  location?: Location;
  timeWindow?: TimeWindow;
} {
  const index = answer.card.highlight?.forecast_index ?? 0;
  const forecast = answer.card.forecasts[index];
  if (forecast === undefined) return {};
  return {
    location: forecast.location,
    timeWindow: deriveTimeWindow(forecast),
  };
}

function deriveTimeWindow(forecast: Forecast): TimeWindow | undefined {
  if (forecast.hourly !== null && forecast.hourly.length > 0) {
    const h = forecast.hourly;
    return { start: h[0].timestamp, end: h[h.length - 1].timestamp };
  }
  if (forecast.daily !== null && forecast.daily.length > 0) {
    const d = forecast.daily;
    return { start: d[0].date, end: d[d.length - 1].date };
  }
  return undefined;
}
