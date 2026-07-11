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
import { useSettingsStore } from "./settingsStore";

export interface UseQueryResult {
  state: MachineState;
  dispatch: Dispatch<MachineEvent>;
  submitQuery: (
    text: string,
    options?: { resolvedLocation?: Location },
  ) => void;
}

export function useQuery(): UseQueryResult {
  const [state, dispatch] = useMachine();
  const settingsStore = useSettingsStore();
  const sessionStore = useSessionStore();
  const offlineCache = useOfflineCache();
  // NOTE(F2.6): SESSION_EXPIRED must also abort abortControllerRef.current,
  // or a late terminal event will throw inside this hook's un-awaited
  // runQuery promise (machineReducer rejects any event once main is no
  // longer "thinking").
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  function submitQuery(
    text: string,
    options?: { resolvedLocation?: Location },
  ): void {
    abortControllerRef.current?.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;

    dispatch({ type: "SUBMIT", query: text });

    const request: QueryRequest = {
      query: text,
      now: new Date().toISOString(),
      ...settingsStore.toQueryRequestFields(),
    };
    if (options?.resolvedLocation !== undefined) {
      request.resolved_location = options.resolvedLocation;
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
          dispatch({ type: "ERROR", payload });
          sessionStore.recordActivity({ query: text });
        },
      },
      controller.signal,
    );
  }

  return { state, dispatch, submitQuery };
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
